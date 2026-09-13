#!/usr/bin/env python3
"""非 ORM 数据访问扫描器（REQ-24e15d 的基线与验收工具）。

用法：
  1) 作为「quantsys-v2 裸 SQL 全量迁 ORM」的**可复跑基线**——每批改完重跑，看计数下降；
  2) 作为**验收闸门**：`--gate` 模式下 P0 非 0 即退出码 1（可直接接进发版体检）。

指标口径（**粗指标与风险指标分开**，避免把"改得多"当"改得好"）：

  P0 fstring_value_interp ：SQL 行里出现**引号内插值**（值位置注入签名），如
                            f"... WHERE symbol IN ('{symbol_list}')" / f"... = '{x}'"
                            —— 这一类是真正必须修的：取值必须走绑定参数。
  P0 raw_connect          ：psycopg2/sqlite3 直接 connect（绕过 session 管理与 session_guard）。
  P1 cursor_execute       ：cursor.execute(...) 原生 SQL（含仓储内；目标逐层清零）。
  P1 core_text_sql        ：session.execute(text(...)) —— SQLAlchemy Core，属"半 ORM"，逐处评估。
  P2 fstring_sql          ：**粗指标**，任何 f-string 里的 SQL。其中「标识符插值」（列名/表名，
                            如 f"SELECT {column} FROM ..."）无法用绑定参数、只能白名单校验，
                            属正当写法 —— 因此该指标**不应作为 t1 的验收值**（不会也不需要归零）。
  P2 read_sql             ：pandas.read_sql（绕过仓储契约）。
  P2 psql_subprocess      ：subprocess 调 psql。

配套纪律（2026-09-13 实证）：**标识符进 SQL 前必须过白名单**，取值一律绑定参数。
  反例：f"SELECT {factor_name} ... WHERE symbol IN ('{symbol_list}')"（列名 + 取值双重注入）；
  正例：f"SELECT {column} FROM ... WHERE symbol = ANY(%s)"（column 过白名单，取值走参数）。

排除：venv/、tests/、infrastructure/persistence/migrations/（DDL 与数据迁移本就该用原生 SQL）、
      tools/oneoff/（一次性运维脚本，单独评估）。
      scripts/ 与 tools/ 下的诊断脚本**计入统计但不属本轮范围**（单列在报告末尾）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Dict, List

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDE_DIR_PARTS = {
    "venv", ".venv", "tests", "node_modules", "__pycache__", ".git",
    "migrations",  # DDL/数据迁移：原生 SQL 是正当用法
    "oneoff",      # 一次性运维脚本：单独评估
}
OUT_OF_SCOPE_TOP = ("scripts/", "tools/", "live_trading/")  # 记账但本轮不改
# 测试基础设施与根级临时校验脚本：不是生产数据访问，单独排除
EXCLUDE_FILES = {"conftest.py", "simple_verify.py"}

PATTERNS = {
    "fstring_sql": re.compile(r"""(?:f|F)["'][^"']*\b(?:SELECT|INSERT|UPDATE|DELETE)\b"""),
    "raw_connect": re.compile(r"\b(?:psycopg2|sqlite3)\.connect\("),
    "cursor_execute": re.compile(r"\bcursor\.execute\("),
    "core_text_sql": re.compile(r"session\.execute\(\s*text\("),
    "read_sql": re.compile(r"\bread_sql(?:_query)?\("),
    "psql_subprocess": re.compile(r"subprocess\.[A-Za-z_]+\("),  # 与下一行联合判定
}
PSQL_SUBPROCESS_RX = re.compile(r"""subprocess\.[A-Za-z_]+\(\s*\[?\s*["']psql""")
SQL_LINE_RX = re.compile(r"""(?:f|F)["'][^"']*\b(?:SELECT|INSERT|UPDATE|DELETE)\b""")
QUOTED_INTERP_RX = re.compile(r"""(?:'\{[^{}]*\}'|"\{[^{}]*\}")""")  # '{x}' / "{x}"

P0 = ("fstring_value_interp", "raw_connect")
METRIC_ORDER = ("fstring_value_interp", "raw_connect", "cursor_execute", "core_text_sql",
                "fstring_sql", "read_sql", "psql_subprocess")


def iter_py_files() -> List[pathlib.Path]:
    out = []
    for p in ROOT.rglob("*.py"):
        if any(part in EXCLUDE_DIR_PARTS for part in p.parts):
            continue
        if p.name in EXCLUDE_FILES:
            continue
        out.append(p)
    return sorted(out)


def docstring_lines(source: str) -> set:
    """返回 docstring 覆盖的行号集合（1-based）。

    只认「模块/类/函数体的第一个语句且是字符串常量」—— 这是 Python 对 docstring 的定义；
    其余字符串字面量（含多行 SQL）**照常计入**，避免漏计真实 SQL。
    """
    import ast

    try:
        import warnings

        with warnings.catch_warnings():
            # 本仓有些文件含非法转义序列的正则字符串（如 '\\s'），解析时会打 SyntaxWarning：
            # 与本次扫描无关，静音以免污染报告。
            warnings.simplefilter("ignore")
            tree = ast.parse(source)
    except SyntaxError:
        return set()
    skip = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None) or []
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            start = getattr(first.value, "lineno", 1)
            end = getattr(first.value, "end_lineno", start) or start
            skip.update(range(start, end + 1))
    return skip


def scan() -> Dict[str, Dict[str, int]]:
    result: Dict[str, Dict[str, int]] = {}
    for path in iter_py_files():
        rel = str(path.relative_to(ROOT))
        source = path.read_text(encoding="utf-8", errors="replace")
        raw_lines = source.splitlines()
        # 只扫**代码行**：整行注释与 **docstring** 都不计 —— 否则"在注释/文档里引用反例写法"
        # 会被算成命中（2026-09-13 实测两次踩到）。
        # 关键：用 AST 精确识别 docstring，**不能**按三引号粗暴跳过 ——
        # 本仓大量 SQL 写在 `cursor.execute("""...""")` 的多行字面量里，那样会漏计真实 SQL。
        skip = docstring_lines(source)
        code_lines = [
            ln for i, ln in enumerate(raw_lines, 1)
            if i not in skip and not ln.lstrip().startswith("#")
        ]
        text = "\n".join(code_lines)
        counts: Dict[str, int] = {}
        for name in ("fstring_sql", "raw_connect", "cursor_execute", "core_text_sql", "read_sql"):
            n = len(PATTERNS[name].findall(text))
            if n:
                counts[name] = n
        # 派生：P0 细指标 —— 只在"SQL 行"里数引号内插值（值位置注入签名）
        vi = sum(len(QUOTED_INTERP_RX.findall(ln)) for ln in code_lines if SQL_LINE_RX.search(ln))
        if vi:
            counts["fstring_value_interp"] = vi
        n = len(PSQL_SUBPROCESS_RX.findall(text))
        if n:
            counts["psql_subprocess"] = n
        if counts:
            result[rel] = counts
    return result


def in_scope(rel: str) -> bool:
    return not rel.startswith(OUT_OF_SCOPE_TOP)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--gate", action="store_true", help="P0 非 0 时退出码 1")
    args = ap.parse_args()

    data = scan()
    totals: Dict[str, int] = {k: 0 for k in METRIC_ORDER}
    scoped: Dict[str, int] = {k: 0 for k in METRIC_ORDER}
    oos_totals: Dict[str, int] = {k: 0 for k in METRIC_ORDER}
    for rel, counts in data.items():
        for k, v in counts.items():
            totals[k] += v
            (scoped if in_scope(rel) else oos_totals)[k] += v

    if args.json:
        print(json.dumps({"files": data, "totals": totals, "in_scope": scoped,
                          "out_of_scope": oos_totals, "scope_prefixes": list(OUT_OF_SCOPE_TOP)},
                         ensure_ascii=False, indent=2))
    else:
        print(f"扫描根：{ROOT}")
        print(f"扫描文件：{len(iter_py_files())} 个（已排除 venv/tests/migrations/oneoff）")
        print("")
        print("指标（本轮范围 = 非 scripts|tools|live_trading）:")
        for name in METRIC_ORDER:
            tag = "P0" if name in P0 else "P1" if name in ("cursor_execute", "core_text_sql") else "P2"
            print(f"  [{tag}] {name:22s} 合计 {totals[name]:5d}   本轮范围 {scoped[name]:5d}")
        print("")
        print("本轮范围内按文件：")
        for rel, counts in sorted(((r, c) for r, c in data.items() if in_scope(r)),
                                  key=lambda kv: -sum(kv[1].values())):
            detail = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            print(f"  {sum(counts.values()):4d}  {rel}  ({detail})")
        print("")
        print(f"范围外（{", ".join(OUT_OF_SCOPE_TOP)}）合计：{sum(oos_totals.values())}（本轮不改，另议）")

    if args.gate:
        bad = {k: scoped[k] for k in P0 if scoped[k]}
        if bad:
            print(f"\n❌ P0 未清零（本轮范围）：{bad}", file=sys.stderr)
            return 1
        print("\n✅ P0 已清零（值位置注入 / 裸连接）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
