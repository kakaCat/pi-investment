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
  P1 core_text_sql        ：<任意接收者>.execute(text(...)) —— SQLAlchemy Core，属"半 ORM"，逐处评估。
                            （2026-09-14 修正口径，见下方 PATTERNS 处的说明：原正则写死 session.
                              实测系统性漏计 conn.execute(text(...)) / c.execute(text(...))。）
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

**「未迁移」与「按设计即 SQL」必须分开**（2026-09-15，chore/v2-orm-residual）：

  报告里的「本轮范围」是**总量**，其中一部分**无法也不应**改成 ORM —— 通用执行器原语、
  连通性探针（SELECT 1）、PG 专有构造、以及"改回 ORM 反而会引入连接泄漏"的历史修复点。
  把它们和真债堆在同一个数字里，结果是：数字永远归不了零，每个新人都要把这十处重查一遍。

  故引入 EXEMPTIONS（显式基线）：登记为豁免的处数从「未迁移」里扣除，并**逐条打印理由**。
  基线自身受三条硬校验（空理由 / 数量多于登记 / 数量少于登记 → --gate 一律失败），
  见 exemption_problems()。这样「未迁移 = 0」才是可证伪的陈述，而不是靠人记性好。

  ⚠️ 审计桶 session_execute_var **不计入「未迁移」**：正则无法判定 session.execute(<标识符>)
     装的是 select() 还是裸 text()，单列供人工复核（本仓实测 63 处，绝大多数是 stmt=select(...)）。
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
    "cursor_execute": re.compile(r"\bcursor\.execute\("),  # 兼容保留；实际口径见 ANY_EXECUTE_RX
    # 2026-09-14（w-32314d00，B4-c4 前置）：原口径 session\.execute\(\s*text\( ——
    # **只认接收者恰好叫 session** 的调用，实测系统性漏计 conn.execute(text(...)) /
    # cur.execute(text(...))（daily_jobs_bootstrap 一个文件就漏计 11 处真实 SQL）。
    # 漏计方向最危险：这些点改完指标**纹丝不动**，等于"改了也不记功"；
    # 而漏计同时意味着验收看着绿、实际没改完（与 B1 修正 cursor_execute 同因同果）。
    # 现改为任意接收者；与 classify_execute_calls 里"execute(text(...)) 不算 cursor_execute"
    # 的分工不变 —— 同一个调用只会计入 core_text_sql 一次，不会重复计数。
    "core_text_sql": re.compile(r"\.execute\(\s*text\("),
    "read_sql": re.compile(r"\bread_sql(?:_query)?\("),
    "psql_subprocess": re.compile(r"subprocess\.[A-Za-z_]+\("),  # 与下一行联合判定
}
PSQL_SUBPROCESS_RX = re.compile(r"""subprocess\.[A-Za-z_]+\(\s*\[?\s*["']psql""")
SQL_LINE_RX = re.compile(r"""(?:f|F)["'][^"']*\b(?:SELECT|INSERT|UPDATE|DELETE)\b""")
QUOTED_INTERP_RX = re.compile(r"""(?:'\{[^{}]*\}'|"\{[^{}]*\}")""")  # '{x}' / "{x}"

# 2026-09-13（w-32314d00，B1 前置）：`cursor_execute` 原口径是 \bcursor\.execute\( ——
# **只认变量名恰好叫 cursor** 的调用，实测系统性漏计两类真实裸 SQL：
#   ① `cur.execute(...)`（kline_update_job 的 3 个完整性自检查询本就是裸 SQL，此前完全没被数到）
#   ② `conn.execute(...)` / `c.execute(...)` 等同义写法
# 指标偏低 = 验收看着绿、实际没改完（正是本文档开头警告的"把改得多当改得好"的反面）。
# 现改为「任意 .execute/.executemany 接收者」，再剔除 SQLAlchemy 构造器入参
# （execute(select()/text()/insert()/update()/delete()) 是 ORM/Core 的正常写法）。
# 注意：`session.execute("SELECT ...")` 传裸字符串**仍计入本指标** —— 它确实是裸 SQL。
EXECUTE_CALL_RX = re.compile(
    r"(?P<recv>(?:[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)*[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*\.\s*(?:execute|executemany)\(")
# DB-API 游标/连接系的接收者名（含 self._cursor / self._conn 这类）
DBAPI_RECEIVER_TAILS = {"cursor", "cur", "c", "conn", "connection", "db", "cx", "database"}
# SQLAlchemy 的 Session / Engine
ORM_RECEIVER_TAILS = {"session", "engine"}
# execute(...) 的首参若是这些构造器 → 是 ORM/Core 正常写法，不算裸 SQL
ORM_CONSTRUCT_ARG_RX = re.compile(r"\s*(?:text|select|insert|update|delete)\s*\(")
IDENT_ARG_RX = re.compile(r"\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)")


def classify_execute_calls(text: str):
    """按「接收者 + 首参形态」判定每个 .execute/.executemany 调用。

    2026-09-13（w-32314d00）：第一版宽化（任意接收者）会**误数非 DB 对象**——
    实测 `self.indicator_executor.execute(...)` / `self.script_executor.execute(...)`
    （策略执行器，与数据库无关）被算成裸 SQL。故加接收者白名单：
      · cursor/cur/c/conn/connection/db/cx  → DB-API，算裸 SQL；
      · session/engine                       → 看首参：构造器(select/text/…)不算；
                                                标识符且名字带 sql/query 的算（如 _d_grade_sql）；
                                                其余标识符（如 stmt）单列 session_execute_var 供人工复核；
                                                字符串/f-string 字面量算。
    返回值 (cursor_execute, session_execute_var)。
    """
    n_cursor = n_var = 0
    for m in EXECUTE_CALL_RX.finditer(text):
        recv = m.group("recv").split(".")[-1].strip().strip("_").lower()
        after = m.end()
        if ORM_CONSTRUCT_ARG_RX.match(text, after):
            continue                      # execute(select()/text()/…) → ORM/Core，不计
        if recv in DBAPI_RECEIVER_TAILS:
            n_cursor += 1
            continue
        if recv in ORM_RECEIVER_TAILS:
            im = IDENT_ARG_RX.match(text, after)
            if im:
                name = im.group("name").lower()
                # 标识符后紧跟引号 → 其实是 f"..." 这类字面量，按裸 SQL 计
                tail = text[im.end():im.end() + 1]
                if tail in ("'", '"'):
                    n_cursor += 1
                elif "sql" in name or "query" in name:
                    n_cursor += 1
                else:
                    n_var += 1
            else:
                n_cursor += 1             # 字符串字面量首参 → 裸 SQL
    return n_cursor, n_var

P0 = ("fstring_value_interp", "raw_connect")
METRIC_ORDER = ("fstring_value_interp", "raw_connect", "cursor_execute", "core_text_sql",
                "session_execute_var", "fstring_sql", "read_sql", "psql_subprocess")
# 仅作人工复核的中间桶：session.execute(<标识符>) 无法用正则判定它装的是 SQL 还是 ORM 构造
# （本仓 orm/async_base.py 与 *_async_repository.py 都传 stmt=select(...)，属正常写法）。
AUDIT_ONLY = ("session_execute_var",)


def iter_py_files() -> List[pathlib.Path]:
    out = []
    for p in ROOT.rglob("*.py"):
        if any(part in EXCLUDE_DIR_PARTS for part in p.parts):
            continue
        if p.name in EXCLUDE_FILES:
            continue
        out.append(p)
    return sorted(out)


def docstring_lines(source: str):
    """返回 (docstring 行号集合, 是否解析成功)。

    只认「模块/类/函数体的第一个语句且是字符串常量」—— 这是 Python 对 docstring 的定义；
    其余字符串字面量（含多行 SQL）**照常计入**，避免漏计真实 SQL。

    2026-09-14（w-32314d00，B4-c4 复核）：原实现在 SyntaxError 时 `return set()` ——
    **返回空集等于断言"这个文件没有 docstring"**，于是文件里所有 docstring 都会被当成代码行扫，
    指标**向上虚高**（旧实现下一个语法坏掉的文件会被报出更多"裸 SQL"）。
    这正是最难查的方向：你恰好在排查一个坏文件时，尺子自己先撒谎了。
    实测场景：并发窗口把 backtest_repository.py 的 docstring 写坏时，该文件的命中会假性增加。
    现改为显式返回解析失败标志，由 scan() 跳过该文件并单列报告 —— 宁可说"这个文件没量到"，
    也不要给一个看起来有数、实际是错的数。
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
        return set(), False
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
    return skip, True


def scan():
    """返回 (per-file counts, 无法解析的文件列表)。

    无法解析的文件**不产出任何计数**（而不是产出虚高的计数）—— 见 docstring_lines 的说明。
    """
    result: Dict[str, Dict[str, int]] = {}
    unparseable: List[str] = []
    for path in iter_py_files():
        rel = str(path.relative_to(ROOT))
        source = path.read_text(encoding="utf-8", errors="replace")
        raw_lines = source.splitlines()
        # 只扫**代码行**：整行注释与 **docstring** 都不计 —— 否则"在注释/文档里引用反例写法"
        # 会被算成命中（2026-09-13 实测两次踩到）。
        # 关键：用 AST 精确识别 docstring，**不能**按三引号粗暴跳过 ——
        # 本仓大量 SQL 写在 `cursor.execute("""...""")` 的多行字面量里，那样会漏计真实 SQL。
        skip, parse_ok = docstring_lines(source)
        if not parse_ok:
            # 语法坏掉的文件量不准：docstring 边界无从判定，任何计数都是猜的。
            unparseable.append(rel)
            continue
        code_lines = [
            ln for i, ln in enumerate(raw_lines, 1)
            if i not in skip and not ln.lstrip().startswith("#")
        ]
        text = "\n".join(code_lines)
        counts: Dict[str, int] = {}
        for name in ("fstring_sql", "raw_connect", "core_text_sql", "read_sql"):
            n = len(PATTERNS[name].findall(text))
            if n:
                counts[name] = n
        # cursor_execute：DB-API 接收者 + session/engine 传裸 SQL（见 classify_execute_calls）
        n, n_var = classify_execute_calls(text)
        if n:
            counts["cursor_execute"] = n
        if n_var:
            counts["session_execute_var"] = n_var
        # 派生：P0 细指标 —— 只在"SQL 行"里数引号内插值（值位置注入签名）
        vi = sum(len(QUOTED_INTERP_RX.findall(ln)) for ln in code_lines if SQL_LINE_RX.search(ln))
        if vi:
            counts["fstring_value_interp"] = vi
        n = len(PSQL_SUBPROCESS_RX.findall(text))
        if n:
            counts["psql_subprocess"] = n
        if counts:
            result[rel] = counts
    return result, unparseable


# ── 按设计即 SQL 的豁免登记（2026-09-15，w-2129d492，chore/v2-orm-residual）──────────
#
# 判定标准（三条全满足才可登记）：该处的裸 SQL
#   ① 无法或不应改成 ORM/Core（改了要么更差、要么把 ORM 写进调用点）；
#   ② 不构成本需求要消灭的**风险**：裸连接长期持有 / idle-in-transaction / 值位置注入；
#   ③ 连接由框架管理（Session / AsyncConnection / 池化游标），执行完即归还。
#
# EXEMPTIONS 是**显式基线**，不是静默忽略 —— 三条自维护纪律：
#   · 必须写理由：理由为空 → --gate 失败（空理由=不想解释，那就别豁免）；
#   · 数量必须**精确匹配**：实际 > 登记 → 豁免文件里混进了新的未迁移 SQL，失败；
#     实际 < 登记 → 登记过期（多半已迁移完），同样失败，提醒删掉这一条。
#   · 全部逐条打印在报告里 —— 豁免表本身就是被审阅的对象，不藏在代码里。
# 约定与 tests/test_orm_db_drift.py 的 _KNOWN_DANGLING_TABLES / _EXTEND_EXISTING_BASELINE
# 一致：宁可让基线显式、可审计，也不让它变成一个没人敢碰的常驻计数。
EXEMPTIONS = {
    ('infrastructure/persistence/database/async_base_repository.py', 'core_text_sql'): (
        5,
        '通用异步执行器原语：fetchall/fetchrow/fetchval/execute/executemany 的方法签名就是'
        '「执行调用方传进来的 SQL」—— 用 ORM 表达等于把 ORM 塞进每个调用点。全部经 '
        '_connection_context()/AsyncConnection 执行，连接由 SQLAlchemy 管理、执行完即归还，'
        '不存在裸连接长期持有或 idle-in-transaction。',
    ),
    ('infrastructure/diagnostics/dependency_check.py', 'core_text_sql'): (
        1,
        '依赖自检的连通性探针（SELECT 1）。探针要回答的正是「能不能连上并执行一条语句」，'
        '用 ORM 表达不增加任何信息量。',
    ),
    ('infrastructure/diagnostics/dependency_check.py', 'fstring_sql'): (
        1,
        '同上探针的 f-string 形态。本指标是**粗指标**，不区分标识符插值与取值插值 —— '
        '该处不含引号内取值插值（P0 fstring_value_interp 本轮范围=0 即为证），故不是注入面。',
    ),
    ('adapters/outbound/repositories/ml_model_repository.py', 'cursor_execute'): (
        1,
        '会话健康探针 self.session.execute(sql_text(SELECT 1))。经 SQLAlchemy Session 执行'
        '（不是裸游标）、连接受框架管理；且探针语义无法用 ORM 表达。',
    ),
    ('adapters/outbound/repositories/portfolio_repository.py', 'core_text_sql'): (
        1,
        '该文件内已写明此处「无法用 ORM 表达」（PG 专有构造），故按仓储契约（SQL 只允许出现在'
        '仓储层）用 session.execute(text(...)) 实现。经 Session 执行，无裸连接。',
    ),
    ('utils/symbol_classifier.py', 'cursor_execute'): (
        1,
        '代码注释已写明**故意**不用 ORM：走 ORM 会在 ThreadPoolExecutor 线程上开 thread-local '
        'session 且不关闭，实测造成 session_leak_detected 与 idle in transaction ~337s 被 DB 强杀'
        '（REQ-24e15d t2 改用池化游标修复）。把它改回 ORM 是**回退**那次修复。',
    ),
}


def exempted_by_metric() -> Dict[str, int]:
    """按豁免登记汇总「本轮范围内每个指标被豁免掉多少处」。"""
    out: Dict[str, int] = {k: 0 for k in METRIC_ORDER}
    for (_rel, metric), (n, _reason) in EXEMPTIONS.items():
        out[metric] += n
    return out


def exemption_problems(data: Dict[str, Dict[str, int]]) -> List[str]:
    """校验豁免表自身：空理由 / 登记过期 / 豁免文件混入新债 —— 三者任一即失败。"""
    problems: List[str] = []
    for (rel, metric), (expected, reason) in sorted(EXEMPTIONS.items()):
        if not (reason or '').strip():
            problems.append('%s 的 %s：豁免理由为空（空理由不得豁免）' % (rel, metric))
        actual = data.get(rel, {}).get(metric, 0)
        if actual > expected:
            problems.append(
                '%s 的 %s：实际 %d > 登记 %d —— 同文件同指标混入了**新的**未迁移 SQL；'
                '请迁移它，或确认同属「按设计即 SQL」后上调登记并写明理由'
                % (rel, metric, actual, expected))
        elif actual < expected:
            problems.append(
                '%s 的 %s：实际 %d < 登记 %d —— **登记过期**（多半已迁移完），请删除该条豁免'
                % (rel, metric, actual, expected))
    return problems


def in_scope(rel: str) -> bool:
    return not rel.startswith(OUT_OF_SCOPE_TOP)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--gate", action="store_true",
                    help="P0（扣除豁免后）非 0，或豁免表自身不合法时退出码 1")
    args = ap.parse_args()

    data, unparseable = scan()
    totals: Dict[str, int] = {k: 0 for k in METRIC_ORDER}
    scoped: Dict[str, int] = {k: 0 for k in METRIC_ORDER}
    oos_totals: Dict[str, int] = {k: 0 for k in METRIC_ORDER}
    for rel, counts in data.items():
        for k, v in counts.items():
            totals[k] += v
            (scoped if in_scope(rel) else oos_totals)[k] += v

    exempted = exempted_by_metric()
    # 「未迁移」= 本轮范围 − 已登记为「按设计即 SQL」的豁免。这才是剩余工作量。
    unmigrated = {k: scoped[k] - exempted[k] for k in METRIC_ORDER}
    problems = exemption_problems(data)

    if args.json:
        print(json.dumps({
            "files": data, "totals": totals, "in_scope": scoped,
            "exempted": exempted, "unmigrated": unmigrated,
            "exemptions": [
                {"file": rel, "metric": metric, "count": n, "reason": reason}
                for (rel, metric), (n, reason) in sorted(EXEMPTIONS.items())
            ],
            "exemption_problems": problems,
            "out_of_scope": oos_totals, "scope_prefixes": list(OUT_OF_SCOPE_TOP),
            "unparseable": unparseable, "scanned_files": len(iter_py_files()),
        }, ensure_ascii=False, indent=2))
    else:
        print("扫描根：" + str(ROOT))
        print("扫描文件：%d 个（已排除 venv/tests/migrations/oneoff）" % len(iter_py_files()))
        if unparseable:
            # 不静默：这些文件量不到，谁都不该把它们当成 0 命中。
            print("⚠️ 无法解析（语法错误）%d 个，本次**未计入任何指标**：" % len(unparseable))
            for rel in unparseable:
                print("     " + rel)
        print("")
        print("指标（本轮范围 = 非 scripts|tools|live_trading）:")
        for name in METRIC_ORDER:
            tag = "P0" if name in P0 else "P1" if name in ("cursor_execute", "core_text_sql") else "P2"
            if name in AUDIT_ONLY:
                # 审计桶：正则无法判定 session.execute(<标识符>) 装的是 select() 还是裸 SQL，
                # 故**不算入未迁移**，只作人工复核入口（与旧口径一致，避免虚增剩余量）。
                print("  [%s] %-22s 合计 %5d   本轮范围 %5d   已豁免 %3d   (审计桶，未判定)"
                      % (tag, name, totals[name], scoped[name], exempted[name]))
            else:
                print("  [%s] %-22s 合计 %5d   本轮范围 %5d   已豁免 %3d   **未迁移 %5d**"
                      % (tag, name, totals[name], scoped[name], exempted[name], unmigrated[name]))
        print("")
        print("按设计即 SQL 的豁免（显式基线，逐条可审）:")
        if not EXEMPTIONS:
            print("  (无)")
        for (rel, metric), (n, reason) in sorted(EXEMPTIONS.items()):
            print("  %s  [%s x%d]" % (rel, metric, n))
            print("      理由：%s" % reason)
        if problems:
            print("")
            print("⚠️ 豁免表自身有问题 %d 条：" % len(problems))
            for p in problems:
                print("     - " + p)
        print("")
        print("**未迁移**（本轮范围 − 豁免）按文件 —— 这才是剩余工作量:")
        rows = []
        for rel, counts in data.items():
            if not in_scope(rel):
                continue
            leftover = {}
            for k, v in counts.items():
                if k in AUDIT_ONLY:
                    continue          # 审计桶单列在表尾，不混进"剩余工作量"
                ex = sum(n for (r2, m2), (n, _r) in EXEMPTIONS.items() if r2 == rel and m2 == k)
                if v - ex > 0:
                    leftover[k] = v - ex
            if leftover:
                rows.append((rel, leftover))
        for rel, leftover in sorted(rows, key=lambda kv: -sum(kv[1].values())):
            detail = ", ".join("%s=%d" % (k, v) for k, v in sorted(leftover.items()))
            print("  %4d  %s  (%s)" % (sum(leftover.values()), rel, detail))
        if not rows:
            print("  (无：本轮范围内已无未迁移的裸 SQL)")
        pending = sum(v for r, c in data.items() if in_scope(r)
                      for k, v in c.items() if k not in AUDIT_ONLY)
        pending -= sum(n for (_r, m), (n, _x) in EXEMPTIONS.items() if m not in AUDIT_ONLY)
        print("  " + "-" * 66)
        print("  未迁移合计 %d 处（不含审计桶）；审计桶 session_execute_var %d 处需人工复核"
              % (pending, scoped.get("session_execute_var", 0)))
        print("")
        joined = ", ".join(OUT_OF_SCOPE_TOP)
        print("范围外（%s）合计：%d（本轮不改，另议）" % (joined, sum(oos_totals.values())))

    if args.gate:
        bad = {k: unmigrated[k] for k in P0 if unmigrated[k]}
        if bad:
            print("\n❌ P0 未清零（本轮范围，已扣除豁免）：%s" % bad, file=sys.stderr)
            return 1
        if problems:
            print("\n❌ 豁免表自身不合法（%d 条，见上）" % len(problems), file=sys.stderr)
            return 1
        print("\n✅ P0 已清零（值位置注入 / 裸连接）；豁免 %d 条均带理由且数量精确匹配"
              % len(EXEMPTIONS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
