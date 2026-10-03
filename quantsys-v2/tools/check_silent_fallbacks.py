#!/usr/bin/env python3
"""扫「静默兜底」—— 失败与"空数据/成功"不可区分的路径（2026-10-02 · REQ-261001145152-3982）。

## 为什么需要

本仓出过两起**同类**事故，都是"**外观正常、内里已死**"：

1. `WatchTriggerRepository.get_rule_trigger_stats()`：无主触发（`rule_id` 为 NULL，
   外键 `ON DELETE SET NULL` 造成）排在分组第一行 → `int(None)` 抛错 → 被 except 吞掉 →
   **统计在生产恒返回空字典**（盯盘每条规则的今日触发数一直是空的）。
   而日志里只留下 122 条 warning，很容易被当成"噪音"。
2. `SchedulerRepository.count_tasks()`：读失败静默返回 `0` → 调用方（`apscheduler_service`）
   会把它当成"**没有任何任务要调度**"；`get_task_by_name()` 静默返回 `None` →
   调用方会当成"任务不存在"而**重复创建**。

⇒ 判据：**当一个读/写的失败，与"空结果 / 成功"在返回值上无法区分，且不留 error 级痕迹时，
它就是隐患** —— 因为调用方会照常往下走。

## 判据（本工具实现的）

- **读路径**：`try` 体里做 DB 操作；handler **不回滚异常**（无 raise）、
  返回空值（`{}` / `[]` / `None` / `0` / `False` / `''`），且**没有 error 级日志**。
- **写路径**：`try` 体里含 `commit()` / `add()` / `insert()` / `update()` / `delete()` / `flush()`；
  handler 吞掉（无 raise）、**不记 error**，却返回成功值或静默通过。

**日志检测认三种写法**（早期版本漏掉第三种，导致误报）：
`logger.error(` / `logging.error(` / `structlog…get_logger(…).error(`，
亦覆盖 `level='error'` 这类结构化写法。

## 用法

    python tools/check_silent_fallbacks.py            # 列表报告
    python tools/check_silent_fallbacks.py --strict   # 有命中即退出码 2

退出码：0 = 无命中（或未加 --strict）；2 = 有命中且加了 --strict；3 = 工具自身出错。

## 读结果的态度

**命中 ≠ 一定是 bug**：要逐个判断"这个失败与空数据是否真的不可区分"。
本仓有**合法的静默返回**（例如"账户不存在 → None"与"算不出来 → None"在调用方语义相同）。
工具的用途是**把候选缩到可手查的范围**，不是自动定罪。
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import sys

ROOTS = (
    'adapters/outbound/repositories',
    'application/services',
    'infrastructure/jobs',
    'domain',
)
WRITE_MARKS = ('commit()', '.add(', 'insert(', 'update(', 'delete(', 'flush()', 'merge(', 'upsert')
EMPTY_VALUES = ('{}', '[]', 'None', '0', '0.0', 'False', "''", '""', 'set()')
ERROR_LOG_FORMS = ('logger.error', 'logging.error', 'level="error"', "level='error'",
                   'log.error', 'structlog')


def _has_error_log(src: str) -> bool:
    low = src.lower()
    if any(f in src for f in ('logger.error', 'logging.error', 'log.error')):
        return True
    if "level='error'" in low or 'level="error"' in low:
        return True
    # structlog 的单行写法：structlog.get_logger(__name__).error("...", ...)
    return 'structlog' in src and '.error(' in src


def scan() -> list[tuple[str, str, int, str]]:
    hits: list[tuple[str, str, int, str]] = []
    for root in ROOTS:
        base = pathlib.Path(root)
        if not base.exists():
            continue
        for f in base.rglob('*.py'):
            if '__pycache__' in str(f):
                continue
            try:
                tree = ast.parse(f.read_text(encoding='utf-8', errors='ignore'))
            except SyntaxError:
                continue
            for fn in [n for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for tn in [n for n in ast.walk(fn) if isinstance(n, ast.Try)]:
                    try_src = ast.unparse(tn)
                    is_db = any(k in try_src for k in ('session', 'query(', 'execute('))
                    is_write = any(m in try_src for m in WRITE_MARKS)
                    if not (is_db or is_write):
                        continue
                    for h in tn.handlers:
                        hsrc = ast.unparse(h)
                        if any(isinstance(n, ast.Raise) for n in ast.walk(h)):
                            continue
                        if _has_error_log(hsrc):
                            continue
                        rets = [n for n in ast.walk(h) if isinstance(n, ast.Return)]
                        val = ast.unparse(rets[-1].value) if rets and rets[-1].value else ''
                        rolled = 'rollback' in hsrc
                        if is_write and is_db:
                            if val in ('True', '1') or (not val and not rolled) or val in EMPTY_VALUES:
                                hits.append((str(f), fn.name, h.lineno, f'写路径→{val or "静默通过"}'))
                        elif is_db and val in EMPTY_VALUES:
                            hits.append((str(f), fn.name, h.lineno, f'读路径→{val}'))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()

    try:
        hits = scan()
    except Exception as e:  # noqa: BLE001
        print(f'❌ 扫描失败: {e}', file=sys.stderr)
        return 3

    print('  按「失败与空数据/成功不可区分、且无 error 级日志」扫描：')
    if not hits:
        print('    ✅ 无命中')
    by_file: dict[str, list[str]] = {}
    for path, fn, ln, why in hits:
        by_file.setdefault(path, []).append(f'{fn}:{ln} {why}')
    for path, items in sorted(by_file.items(), key=lambda x: -len(x[1])):
        print(f'    {path:<58} {len(items)} 处')
        for it in items[:4]:
            print(f'        {it}')
    print(f'\n  合计 {len(hits)} 处候选 —— **命中不等于 bug**，'
          f'需逐个判断"该失败与空数据是否真的不可区分"。')
    return 2 if (hits and args.strict) else 0


if __name__ == '__main__':
    raise SystemExit(main())
