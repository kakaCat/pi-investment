#!/usr/bin/env python
"""trading_plan_rules 加 batch 列（REQ-261021222905-6dff t6，2026-10-22）

背景：同一标的的减仓计划是**多批**的（+8% 卖 1/3、+15% 卖完），
原 PK (plan_id, role, symbol) 装不下「一个标的、一个 role、多个批次」——
第二个批次会与第一个冲突。本迁移：
  1. 加列 batch integer NOT NULL DEFAULT 0（entry/stop_loss 等非批次角色恒 0）；
  2. PK 改为 (plan_id, role, symbol, batch)。

幂等：ADD COLUMN IF NOT EXISTS + 先查 pg_constraint 再换 PK。
dry-run 默认；--apply 写库。
"""
import argparse
import sys

from sqlalchemy import text

from qs_kernel.infrastructure.persistence.database.engine import get_engine

SCHEMA = 'quant'
TABLE = 'trading_plan_rules'
PK_NAME = 'trading_plan_rules_pkey'
NEW_PK = 'PRIMARY KEY (plan_id, role, symbol, batch)'


def _column_exists(conn) -> bool:
    return bool(conn.execute(text(
        "SELECT 1 FROM information_schema.columns WHERE table_schema=:s "
        "AND table_name=:t AND column_name='batch'"), {'s': SCHEMA, 't': TABLE}).scalar())


def _pk_def(conn):
    return conn.execute(text(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
        "JOIN pg_class t ON t.oid = c.conrelid "
        "JOIN pg_namespace n ON n.oid = t.relnamespace "
        "WHERE n.nspname=:s AND t.relname=:t AND c.contype='p'"),
        {'s': SCHEMA, 't': TABLE}).scalar()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dsn', default=None)
    args = ap.parse_args()
    eng = get_engine()
    if args.dsn:
        from sqlalchemy import create_engine
        eng = create_engine(args.dsn)
    with eng.begin() as conn:
        has_col = _column_exists(conn)
        pk = _pk_def(conn) or ''
        pk_ok = 'batch' in pk
        print(('DRY   ' if not args.apply else 'APPLY ') +
              'column batch: %s · pk: %s' % ('exists' if has_col else 'would-add', pk))
        if args.apply:
            if not has_col:
                conn.execute(text(
                    "ALTER TABLE %s.%s ADD COLUMN IF NOT EXISTS batch integer NOT NULL DEFAULT 0"
                    % (SCHEMA, TABLE)))
            if not pk_ok:
                conn.execute(text('ALTER TABLE %s.%s DROP CONSTRAINT %s'
                                  % (SCHEMA, TABLE, PK_NAME)))
                conn.execute(text('ALTER TABLE %s.%s ADD CONSTRAINT %s %s'
                                  % (SCHEMA, TABLE, PK_NAME, NEW_PK)))
        if args.apply:
            has_col2 = _column_exists(conn)
            pk2 = _pk_def(conn) or ''
            ok = has_col2 and 'batch' in pk2
            print('VERIFY %s: column=%s pk=%s' % ('OK' if ok else 'FAILED', has_col2, pk2))
            return 0 if ok else 2
    print('DRY-RUN done（--apply 才写库）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
