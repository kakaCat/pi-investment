"""字符串模块路径检查器（tools/check_module_paths.py，2026-09-14 w-c8cae280）

为什么需要它（根因，不是症状）：
  mock.patch('quantlib.finrl.finrl_agent.PPO')、importlib.import_module('X')、
  register_adapter("mock_test", "quantlib.adapters.base_adapter.BaseMarketAdapter") 这类调用
  把**模块路径写成字符串字面量** —— 没有任何编辑器/类型系统/导入检查会发现它失效。
  于是当包搬家（quantlib → domain.quantlib；adapters → adapters.outbound.datasources.providers.quantlib）
  这些字符串原地不动，直到运行时才炸出 "ModuleNotFoundError: No module named 'quantlib'"，
  而报错栈全是 <frozen importlib._bootstrap>，看不到一行仓内代码 —— 极易被误判为"环境/包冲突"。
  实证：2026-09-13 全量测试里这一个根因占了约 53 项红账（35 errors + 18 failed）。

本检查器做什么：把这类字符串**当导入来验证**，不支持则报告 file:line。
退出码：0=全部可解析；1=存在悬空字符串路径。

用法：venv/bin/python tools/check_module_paths.py [--root .] [--quiet]
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import sys
from pathlib import Path
from typing import Iterator, List, Tuple

# 形如 X.Y.Z 的模块路径（至少两段，首段为标识符）
CALL_SHAPES = {
    # func_name: 第几个位置参数是模块路径
    "patch": 0,               # mock.patch('pkg.mod.attr')
    "import_module": 0,       # importlib.import_module('pkg.mod')
    "__import__": 0,          # __import__('pkg.mod')
    "setattr": 0,             # monkeypatch.setattr('pkg.mod.attr', ...)
    "register_adapter": 1,    # 自定义注册表（本仓 adapters 工厂）
    "get_adapter_class": 0,
    "load_class": 0,
    "resolve": 0,
}
SKIP_DIRS = {"venv", ".venv", "__pycache__", ".git", "node_modules", ".mypy_cache", "build", "dist"}


def _iter_py(root: Path) -> Iterator[Path]:
    for p in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def _str_arg(call: ast.Call, idx: int):
    """取第 idx 个位置参数（或同名关键字）的字符串常量值。"""
    args = list(call.args)
    if len(args) > idx:
        a = args[idx]
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            return a.value
    for kw in call.keywords:
        if kw.arg is None and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _looks_like_module_path(s: str) -> bool:
    if not s or " " in s or "/" in s or s.startswith("."):
        return False
    parts = s.split(".")
    if len(parts) < 2:
        return False
    return all(p.isidentifier() for p in parts)


def _resolve_module_chain(path: str) -> Tuple[bool, str]:
    """把 pkg.mod.attr 逐段缩短，找到第一个**能导入的模块前缀**。

    返回 (ok, detail)：
      - 若最长可导入前缀 == 整串        → ok（可能本身就是模块，或全部是属性）
      - 若最长可导入前缀 < 目标前缀      → 报告不可解析的部分
    """
    parts = path.split(".")
    for cut in range(len(parts), 0, -1):
        cand = ".".join(parts[:cut])
        try:
            if importlib.util.find_spec(cand) is not None:
                return True, cand
        except (ImportError, ValueError, ModuleNotFoundError):
            continue
    return False, ""


def scan(root: Path) -> List[dict]:
    findings: List[dict] = []
    for f in _iter_py(root):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = None
            if isinstance(fn, ast.Attribute):
                name = fn.attr
            elif isinstance(fn, ast.Name):
                name = fn.id
            if name not in CALL_SHAPES:
                continue
            s = _str_arg(node, CALL_SHAPES[name])
            if not s or not _looks_like_module_path(s):
                continue
            ok, resolved = _resolve_module_chain(s)
            if not ok:
                findings.append({
                    "file": str(f.relative_to(root)), "line": node.lineno,
                    "call": name, "path": s,
                })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    findings = scan(root)
    if not findings:
        if not a.quiet:
            print("✅ 未发现悬空的字符串模块路径")
        return 0
    print("❌ 发现 %d 处**无法解析的字符串模块路径**（包搬家后字符串不会跟着动，只会在运行时炸）：" % len(findings))
    for x in findings:
        print("   %s:%d  %s('%s')" % (x["file"], x["line"], x["call"], x["path"]))
    print("\n修法：① 改字符串到当前路径；② 更好的做法是不写字符串 —— "
          "import 模块后用 patch.object(module, 'attr')（搬家时在 import 处**立刻**报错，且 IDE/类型检查能解析）。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
