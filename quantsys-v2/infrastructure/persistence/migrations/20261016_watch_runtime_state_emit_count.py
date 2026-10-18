#!/usr/bin/env python
"""quant.watch_runtime_state 加每日通知计数列（2026-10-16 · REQ-261016155500-4f2a wt:engine:1）

支撑「每规则每条件每交易日 ≤ DEFAULT_DAILY_EMIT_CAP(2) 次通知」的跨重启持久化：
emit_count_date（计数所属交易日，非今天则作废）+ emit_count（当日已通知次数）。
不加这两列时引擎照常运行（计数纯内存，重启归零）——上限在重启后短暂失效。

幂等：ADD COLUMN IF NOT EXISTS。默认 dry-run，`--apply` 写库。

用法：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261016_watch_runtime_state_emit_count.py
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261016_watch_runtime_state_emit_count.py --apply
"""
import argparse
import os

from sqlalchemy import create_engine, text


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


DDL = [
    "ALTER TABLE quant.watch_runtime_state ADD COLUMN IF NOT EXISTS emit_count_date date",
    "ALTER TABLE quant.watch_runtime_state ADD COLUMN IF NOT EXISTS emit_count integer",
    "COMMENT ON COLUMN quant.watch_runtime_state.emit_count_date IS "
    "'通知计数所属交易日（REQ-261016155500-4f2a，非今天则计数作废）'",
    "COMMENT ON COLUMN quant.watch_runtime_state.emit_count IS "
    "'当日已通知次数（每规则每条件每日上限）'",
]

VERIFY = ("select emit_count_date, emit_count from quant.watch_runtime_state limit 1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    eng = _engine()
    with eng.begin() as conn:
        for ddl in DDL:
            if args.apply:
                conn.execute(text(ddl))
            print(('APPLY ' if args.apply else 'DRY   ') + ddl[:90])
    if args.apply:
        with eng.connect() as conn:
            conn.execute(text(VERIFY)).fetchone()
        print('VERIFY OK')
    else:
        print('DRY-RUN done（--apply 生效；生产与测试库本次已同步执行）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
