#!/usr/bin/env python3
"""把生产库的**列默认值**对齐到测试库（仅测试库）。

## 为什么需要（2026-10-02 · REQ-261001145152-3982 审查）

测试库并非生产库的镜像，两库在列默认值上已有 **59 处**不一致。后果不是"少个默认值"
这么轻，而是**同一段代码在库里表现不同**：

    实测：quant.simulation_trades.commission
      生产库 → NOT NULL DEFAULT 0    → 不传该列也能插入 ✅
      测试库 → NOT NULL 且无默认值    → 插入报 NotNullViolation ❌
    → tests/live_trading/test_trade_action_case.py 3 条失败，
      而报错指向的是"代码没传 commission"，**指向了错误的方向**。

## 口径（与本次审查一致）

- **以生产库为准**（它是线上真实结构）；
- **只改测试库**；脚本拒绝在库名不以 `_test` 结尾的库上执行；
- **只对齐"测试库已存在该列"的默认值**：测试库独有的列（如 `create_all` 造出的表）
  一概不动；
- 幂等：默认值相同则跳过；可反复运行。

## 用法

    python tools/align_test_db_defaults.py            # 预演（只报告差异）
    python tools/align_test_db_defaults.py --apply    # 实际执行
    python tools/align_test_db_defaults.py --apply --prod-dsn ... --test-dsn ...
"""
from __future__ import annotations

import argparse
import subprocess
import sys

PROD_DB = 'quant_investment'
TEST_DB = 'quant_test'
SCHEMA = 'quant'


def _psql(db: str, sql: str) -> list[str]:
    r = subprocess.run(['psql', '-d', db, '-tAc', sql], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'psql({db}) 失败: {r.stderr.strip()[:200]}')
    return [x for x in r.stdout.strip().split('\n') if x]


def _defaults(db: str) -> dict[tuple[str, str], str]:
    rows = _psql(db, f"""
        select table_name||'|'||column_name||'|'||coalesce(column_default, '')
        from information_schema.columns
        where table_schema='{SCHEMA}'
    """)
    out: dict[tuple[str, str], str] = {}
    for row in rows:
        parts = row.split('|', 2)
        if len(parts) == 3:
            out[(parts[0], parts[1])] = parts[2]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正执行（默认只预演）')
    ap.add_argument('--prod-db', default=PROD_DB)
    ap.add_argument('--test-db', default=TEST_DB)
    args = ap.parse_args()

    if not args.test_db.endswith('_test'):
        print(f'❌ 拒绝执行：目标库 {args.test_db!r} 不以 _test 结尾', file=sys.stderr)
        return 2

    prod = _defaults(args.prod_db)
    test = _defaults(args.test_db)

    todo = []
    for (table, col), pdef in sorted(prod.items()):
        if not pdef:                       # 生产无默认值 → 不涉及
            continue
        tdef = test.get((table, col))
        if tdef is None:                   # 测试库没这列 → 不动（两库结构本就不同）
            continue
        if tdef != pdef:
            todo.append((table, col, pdef, tdef))

    print(f'  生产库有默认值的列: {len(prod)}｜两库都有但值不同: {len(todo)}')
    for table, col, pdef, tdef in todo[:10]:
        print(f'    {table}.{col}: 测试库={tdef or "(无)"} → {pdef}')
    if len(todo) > 10:
        print(f'    …另外 {len(todo) - 10} 处')

    if not args.apply:
        print('\n  （预演模式，未改动；加 --apply 执行）')
        return 0

    ok = err = 0
    for table, col, pdef, _ in todo:
        sql = f'alter table {SCHEMA}."{table}" alter column "{col}" set default {pdef}'
        r = subprocess.run(['psql', '-d', args.test_db, '-c', sql],
                           capture_output=True, text=True)
        if r.returncode == 0:
            ok += 1
        else:
            err += 1
            print(f'    ⚠️ {table}.{col}: {r.stderr.strip()[:120]}')
    print(f'  ✅ 已对齐 {ok} 列｜失败 {err} 列')
    return 0 if err == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
