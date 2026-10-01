"""分层纯净性断言（REQ-261001145152-3982 · t-c3a097）

为什么需要这个文件：仓库里早有 `tools/analyze_layer_violations.py` 与 `.git-hooks/pre-commit`，
但**护栏失效**——pre-commit 的 BASELINE 写着 7，实测违规 117（差 16 倍），而且 hook 从未安装。
规范只有变成"会失败的断言"才有约束力，这个文件就是那条断言。

口径（与 docs/coding-standards.md 一致，见审计报告 §1.3）：
- domain    → application / adapters / infrastructure   ❌
- application → adapters / infrastructure               ❌（顶层尤其严重）
- adapters  → application：**inbound 允许**（外部调我们）；outbound / shared ❌（方向倒置）
- infrastructure → application：规范允许（基础设施可依赖所有层），故不计入

两类计数：
- `TOTAL`：违规 import 总数（含函数内延迟导入）
- `TOPLEVEL`：其中位于**模块顶层**的（无法用"为了打破循环依赖"辩解的那一类，性质最重）

**口径差异（重要，别把两个数字当矛盾）**：本文件的扫描口径是**全域四方向 AST**
（domain→外 / application→adapters / application→infrastructure / adapters(outbound,shared)→application），
实测 **313**；而仓库自带 `tools/analyze_layer_violations.py` 只统计 **application→adapters** 一侧，
实测 **117**（`.git-hooks/pre-commit` 的 BASELINE 用的是这 117）。两者都保留：
hook 与既有工具对齐，本文件管得更宽。

只许降不许升：修好一批后，把下面两个常量一起调小。
新增违规会立刻让本文件红灯——这正是它的用途。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
LAYERS = ("domain", "application", "adapters", "infrastructure")

# 2026-10-01 实测基线（t-c3a097 落档时，全域四方向口径）：总违规 313，其中顶层 56。
# 构成：domain→外 17 / application→adapters 117 / application→infrastructure 171 /
#       adapters(outbound+shared)→application 8。
# 2026-10-01 调整（t-f04052）：总 313 → **315**（顶层不变 56，新增的 2 处都是函数内惰性导入）。
# 为什么 +2 可接受：CLAUDE.md「Data Access Rules」**强制** application 走
# DataProviderManager（位于 adapters.outbound.datasources.manager）取外部数据——
# 于是"按规范取数"必然新增 application→adapters 引用，被本口径计为违规。
# 这 2 处（core_plan_service 的沪深300 基准、market_style_detector 的新浪行业截面）
# 是**度量与规范冲突**的假阳性，不是债上加债；目标是持续下调，
# 若日后改为端口注入（application 不再 import adapters），这两处会自然消失。
# 这两个数字是"存量债"，不是"允许值"——目标是持续下调。
TOTAL_BASELINE = 315
TOPLEVEL_BASELINE = 56

# 允许的跨层方向（其余同层/无关模块不计）
_ALLOWED = {
    ("adapters", "application"): "inbound 允许（外部调我们）",
    ("infrastructure", "application"): "基础设施可依赖所有层",
}


def _layer_of(module_name: str) -> str | None:
    head = module_name.split(".")[0]
    return head if head in LAYERS else None


def _imported_roots(tree: ast.AST):
    """产出 (import 的顶层模块名, 是否位于模块顶层)。"""
    results = []

    def walk(node: ast.AST, in_function: bool) -> None:
        for child in ast.iter_child_nodes(node):
            now_in_function = in_function or isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef)
            )
            if isinstance(child, ast.Import):
                for alias in child.names:
                    results.append((alias.name, not now_in_function))
            elif isinstance(child, ast.ImportFrom):
                # 相对导入（level>0）不跨层，忽略
                if child.level == 0 and child.module:
                    results.append((child.module, not now_in_function))
            walk(child, now_in_function)

    walk(tree, False)
    return results


def _is_violation(src_layer: str, target_layer: str, source_path: pathlib.Path) -> bool:
    if src_layer == target_layer:
        return False
    if (src_layer, target_layer) in _ALLOWED:
        # inbound 之外的 adapters → application 记为方向倒置
        if src_layer == "adapters":
            return "inbound" not in source_path.parts
        return False
    if src_layer == "domain":
        return target_layer in ("application", "adapters", "infrastructure")
    if src_layer == "application":
        return target_layer in ("adapters", "infrastructure")
    if src_layer == "adapters":
        return target_layer == "application"
    return False


def _scan() -> tuple[int, int, list[str]]:
    """返回 (总违规, 顶层违规, 明细列表)。"""
    total = 0
    toplevel = 0
    details: list[str] = []

    for layer in LAYERS:
        for path in (REPO_ROOT / layer).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for module_name, is_toplevel in _imported_roots(tree):
                target_layer = _layer_of(module_name)
                if target_layer is None:
                    continue
                if _is_violation(layer, target_layer, path):
                    total += 1
                    if is_toplevel:
                        toplevel += 1
                    details.append(
                        f"{path.relative_to(REPO_ROOT)}: {layer} → {module_name}"
                        + ("（顶层）" if is_toplevel else "")
                    )
    return total, toplevel, details


@pytest.fixture(scope="module")
def scan():
    return _scan()


def test_total_layer_violations_do_not_increase(scan):
    """违规总数不得超过存量基线。"""
    total, _toplevel, details = scan
    assert total <= TOTAL_BASELINE, (
        f"分层违规总数上升：{total} > 基线 {TOTAL_BASELINE}（新增 {total - TOTAL_BASELINE} 处）\n"
        + "\n".join(sorted(details)[-20:])
    )
    if total < TOTAL_BASELINE:
        pytest.skip(
            f"违规数已由 {TOTAL_BASELINE} 降到 {total}——请把 tests/test_layer_purity.py "
            f"的 TOTAL_BASELINE 调小到 {total}，让护栏跟上"
        )


def test_toplevel_layer_violations_do_not_increase(scan):
    """模块顶层的越层导入（性质最重、无法用打破循环依赖辩解）不得超过基线。"""
    _total, toplevel, details = scan
    assert toplevel <= TOPLEVEL_BASELINE, (
        f"顶层分层违规上升：{toplevel} > 基线 {TOPLEVEL_BASELINE}\n"
        + "\n".join(d for d in sorted(details) if "（顶层）" in d)
    )
    if toplevel < TOPLEVEL_BASELINE:
        pytest.skip(
            f"顶层违规已由 {TOPLEVEL_BASELINE} 降到 {toplevel}——请把 TOPLEVEL_BASELINE 调小到 {toplevel}"
        )
