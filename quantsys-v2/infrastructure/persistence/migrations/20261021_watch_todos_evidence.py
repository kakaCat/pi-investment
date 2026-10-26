#!/usr/bin/env python
"""quant.watch_todos 增列 evidence + 未收敛去重索引（2026-10-21 · REQ-261021194640-69b8）

## 做什么

消息命中转为 P1 待办后，需要回答「因为哪条消息建的单」。在本迁移之前
`quant.watch_todos` 没有任何载荷列，消息待办无法追溯来源；本迁移只做两件事：

1. `evidence jsonb NULL` —— 待办的**只读证据**（来源 / 标题 / 命中词 / 告警 id）。
   可空：历史待办与价格触发待办没有消息证据，强制非空会阻断建单。
2. `idx_watch_todos_open_symbol_action` —— 部分索引
   `(symbol, action_kind) WHERE terminal IS NULL`，服务「同标的未收敛消息待办」去重查询。
   只覆盖未收敛行，收敛后的历史行不进索引。

## 幂等

- DDL 一律 `ADD COLUMN IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`；
  执行前再用 information_schema / pg_indexes 预检，dry-run 能报「将执行 / 已存在」；
- 第二次 `--apply` 命中零变更（输出 changed=0），不会重复建列/建索引。

## 回滚

- 列保留无害：旧代码不读写 `evidence`；缺列库上**写路径**降级（忽略证据 + 告警），
  读路径要求迁移先行（未迁移会响亮报未定义列，不静默把「有证据」伪装成「无证据」）。
- 需要彻底回滚时执行脚本末尾注释里的两条语句（DROP INDEX / DROP COLUMN）；
  删列会丢证据，但不影响待办状态机与交易数据。

用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261021_watch_todos_evidence.py            # dry-run
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261021_watch_todos_evidence.py --apply
    # 生产库与 *_test 库各执行一次（--dsn 可显式指定）
"""
from __future__ import annotations

import argparse
import os
from typing import List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

DEFAULT_SCHEMA = 'quant'
TODO_TABLE = 'watch_todos'
EVIDENCE_COLUMN = 'evidence'
EVIDENCE_DDL = 'jsonb'
INDEX_NAME = 'idx_watch_todos_open_symbol_action'

COLUMN_COMMENT = (
    '待办证据（消息来源/标题/命中词/告警 id，JSON）：'
    '回答「为什么建这条待办」；只读附注，不参与状态机'
)

#: (kind, 描述, 预检 SQL, 执行 SQL)
#: 预检 SQL 返回 1 = 已存在（跳过）；返回 0/空 = 需要执行。
_STEPS: Tuple[Tuple[str, str, str, str], ...] = (
    (
        'column',
        '%s.%s.%s (%s)' % (DEFAULT_SCHEMA, TODO_TABLE, EVIDENCE_COLUMN, EVIDENCE_DDL),
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = :schema AND table_name = :table AND column_name = :column",
        "ALTER TABLE {schema}.{table} ADD COLUMN IF NOT EXISTS {column} {ddl}",
    ),
    (
        'index',
        '%s (部分索引: 未收敛 symbol+action_kind)' % INDEX_NAME,
        "SELECT 1 FROM pg_indexes WHERE schemaname = :schema AND indexname = :index",
        "CREATE INDEX IF NOT EXISTS {index} ON {schema}.{table} (symbol, action_kind) "
        "WHERE terminal IS NULL",
    ),
)

_BACKFILL_NOTE = '无需回填：历史待办的 evidence 保持 NULL（读侧按「无证据」展示）'


def _engine(dsn: Optional[str] = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


def _exists(conn: Connection, kind: str, schema: str) -> bool:
    if kind == 'column':
        row = conn.execute(
            text(_STEPS[0][2]),
            {'schema': schema, 'table': TODO_TABLE, 'column': EVIDENCE_COLUMN},
        ).first()
    else:
        row = conn.execute(
            text(_STEPS[1][2]),
            {'schema': schema, 'index': INDEX_NAME},
        ).first()
    return row is not None


def _sql(kind: str, schema: str) -> str:
    template = _STEPS[0][3] if kind == 'column' else _STEPS[1][3]
    return template.format(
        schema=schema, table=TODO_TABLE, column=EVIDENCE_COLUMN,
        ddl=EVIDENCE_DDL, index=INDEX_NAME,
    )


def plan(conn: Connection, schema: str = DEFAULT_SCHEMA) -> List[dict]:
    """返回每步的计划（exists / sql / label），不写库。"""
    out = []
    for kind, label, _precheck, _ddl in _STEPS:
        out.append({
            'kind': kind,
            'label': label,
            'sql': _sql(kind, schema),
            'exists': _exists(conn, kind, schema),
        })
    return out


def apply(conn: Connection, schema: str = DEFAULT_SCHEMA) -> dict:
    """执行缺失的步骤；返回 {changed, skipped, executed}。"""
    changed = 0
    skipped = 0
    executed: List[str] = []
    for kind, label, _precheck, _ddl in _STEPS:
        if _exists(conn, kind, schema):
            skipped += 1
            continue
        conn.execute(text(_sql(kind, schema)))
        changed += 1
        executed.append(label)
    return {'changed': changed, 'skipped': skipped, 'executed': executed}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='watch_todos.evidence 迁移')
    parser.add_argument('--apply', action='store_true', help='真正写库（缺省 dry-run）')
    parser.add_argument('--dsn', default=None, help='覆盖数据库连接串')
    parser.add_argument('--schema', default=DEFAULT_SCHEMA, help='目标 schema（缺省 quant）')
    args = parser.parse_args(argv)

    try:
        engine = _engine(args.dsn)
    except Exception as e:  # noqa: BLE001
        print('[migrate] 连接失败：%s' % e)
        return 2

    try:
        with engine.connect() as conn:
            steps = plan(conn, args.schema)
            print('[migrate] schema=%s table=%s（%s）'
                  % (args.schema, TODO_TABLE, 'apply' if args.apply else 'dry-run'))
            for step in steps:
                state = '已存在（跳过）' if step['exists'] else '将执行'
                print('  - %-10s %-8s %s' % (step['kind'], state, step['sql']))
            print('  - %s' % _BACKFILL_NOTE)

            if not args.apply:
                pending = sum(1 for s in steps if not s['exists'])
                print('[migrate] dry-run 完成：待执行 %d 步（未写库）' % pending)
                return 0

            if conn.in_transaction():
                conn.commit()
            with conn.begin():
                result = apply(conn, args.schema)
            print('[migrate] apply 完成：changed=%d skipped=%d'
                  % (result['changed'], result['skipped']))
            for label in result['executed']:
                print('  + %s' % label)
            return 0
    except Exception as e:  # noqa: BLE001 - 失败要响亮：退出码 2 + 原文
        print('[migrate] 执行失败：%s' % e)
        return 2
    finally:
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())

# 回滚（按需手工执行）：
#   DROP INDEX IF EXISTS quant.idx_watch_todos_open_symbol_action;
#   ALTER TABLE quant.watch_todos DROP COLUMN IF EXISTS evidence;
