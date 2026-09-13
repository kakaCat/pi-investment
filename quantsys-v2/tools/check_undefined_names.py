"""未定义名检查器（tools/check_undefined_names.py，2026-09-14 w-c8cae280）

为什么需要它（根因）：仓里没有 ruff/pyflakes/flake8，于是 "用了但没定义" 的名字无人拦截。
实证（2026-09-13）：adapters/outbound/datasources/providers/quantlib/akshare_adapter.py
用 logger 26 次，却只在某个方法内局部定义过一次 → 模块级/其它方法里的 logger 是未定义名 →
NameError；**而且它崩在 except 块内，把真实异常掩盖成 "name 'logger' is not defined"**，
排障时永远看不到真正的失败原因。

本检查器只做**保守**判定，宁漏不误报：
  - 只看函数/方法体内的 Name 读取；
  - 排除 builtins；
  - 排除模块级已绑定的名字（import/赋值/def/class/for/with/except/walrus/global）；
  - 排除在**同一函数内**任何位置被绑定的名字（含参数、赋值、for/with/except/comprehension/import）；
  - 含 "from x import *" 的文件整体跳过（名字来源不可静态判定）。

退出码 0=干净 / 1=存在疑似未定义名。
"""
from __future__ import annotations

import argparse
import ast
import builtins
import sys
from pathlib import Path
from typing import Iterator, Set

SKIP_DIRS = {"venv", ".venv", "__pycache__", ".git", "node_modules", "build", "dist"}
BUILTINS = set(dir(builtins))


def _iter_py(root: Path) -> Iterator[Path]:
    for p in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def _bound_names(node: ast.AST) -> Set[str]:
    """收集一个节点内**直接**绑定的名字（不递归进嵌套函数体，由调用方处理）。"""
    out: Set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, ast.alias):
            out.add((n.asname or n.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.Global) or isinstance(n, ast.Nonlocal):
            out.update(n.names)
        elif isinstance(n, ast.NamedExpr):
            if isinstance(n.target, ast.Name):
                out.add(n.target.id)
    return out


def _star_import(tree: ast.AST) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names):
            return True
    return False


NOQA = "noqa: undefined-name"


def scan_file(path: Path) -> list:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    src_lines = src.split(chr(10))

    def _exempt(lineno: int) -> bool:
        # 行内豁免：该行标注 # noqa: undefined-name 即跳过（用于**有据可查**的技术债，
        # 例如为 parity 原样保留的 Flask 时代 latent bug —— 文件头已注明的那种）。
        if 1 <= lineno <= len(src_lines) and NOQA in src_lines[lineno - 1]:
            return True
        return False
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    if _star_import(tree):
        return []
    module_bound = _bound_names(tree)
    findings = []

    def walk_scope(fn: ast.AST):
        local = _bound_names(fn)
        for sub in ast.walk(fn):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and sub is not fn:
                continue  # 嵌套定义由其自身作用域处理（保守：跳过）
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                nm = sub.id
                if nm in BUILTINS or nm in local or nm in module_bound:
                    continue
                if nm.startswith("__"):
                    continue
                findings.append((sub.lineno, nm))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            walk_scope(node)
    # 去重（同一行同名只报一次）
    seen, uniq = set(), []
    for ln, nm in sorted(findings):
        if (ln, nm) in seen or _exempt(ln):
            continue
        seen.add((ln, nm))
        uniq.append((ln, nm))
    return uniq


def scan(root: Path) -> list:
    out = []
    for f in _iter_py(root):
        for ln, nm in scan_file(f):
            out.append({"file": str(f.relative_to(root)), "line": ln, "name": nm})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    fs = scan(root)
    if not fs:
        if not a.quiet:
            print("✅ 未发现疑似未定义名")
        return 0
    print("❌ 发现 %d 处**疑似未定义名**（用了但本作用域与模块级都没绑定）：" % len(fs))
    for x in fs[:80]:
        print("   %s:%d  %s" % (x["file"], x["line"], x["name"]))
    if len(fs) > 80:
        print("   ... 另有 %d 处" % (len(fs) - 80))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
