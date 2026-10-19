#!/usr/bin/env python
"""quant.watch_runtime_meta 加 staged_break_states 列（2026-10-19 · 两段式伏击 P1）

支撑 staged_break「触及→观察→确认」状态机的跨重启持久化：JSONB 存
{'<rule_id>:<cond_idx>': {touch_at, deadline, touch_price}}。
ORM（infrastructure/persistence/orm/models/watch_todo.py WatchRuntimeMeta）与
WatchRuntimeStateRepository.load/save_staged_states 都指认本迁移。
列缺失时调用方（StagedBreakManager）响亮降级为纯内存，不阻塞引擎启动。

幂等：ADD COLUMN IF NOT EXISTS。默认 dry-run，`--apply` 写库。

用法：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261019_watch_runtime_meta_staged_states.py
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261019_watch_runtime_meta_staged_states.py --apply
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
    "ALTER TABLE quant.watch_runtime_meta ADD COLUMN IF NOT EXISTS staged_break_states jsonb",
    "COMMENT ON COLUMN quant.watch_runtime_meta.staged_break_states IS "
    "'staged_break 两段式观察态快照 {rule:cond: {touch_at,deadline,touch_price}}（2026-10-19 P1）'",
]

VERIFY = "select staged_break_states from quant.watch_runtime_meta limit 1"


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
        print('DRY-RUN done（--apply 生效；请对生产库与 *_test 库各执行一次）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
