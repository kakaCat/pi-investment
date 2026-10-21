#!/usr/bin/env python
"""quant.watch_runtime_meta 加 overlap_reported 列（2026-10-16 · REQ-261016155500-4f2a wt:engine:3）

支撑「跨规则重叠已上报规则对」的跨重启持久化：JSONB 存 [[a, b], ...]。
ORM（infrastructure/persistence/orm/models/watch_todo.py WatchRuntimeMeta）与
WatchRuntimeStateRepository.load/save_overlap_reported 都指认本迁移。

⚠️ 本迁移是**补录**：该列此前在生产/测试库已手工加过（列缺失时 state_manager 每次读写
都抛错降级——「重启后同一对重叠会再落一条治理项」），但一直没有迁移文件，重建库拿不到。
幂等：ADD COLUMN IF NOT EXISTS。默认 dry-run，`--apply` 写库。

用法：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261016_watch_runtime_meta_overlap_reported.py
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261016_watch_runtime_meta_overlap_reported.py --apply
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
    "ALTER TABLE quant.watch_runtime_meta ADD COLUMN IF NOT EXISTS overlap_reported jsonb",
    "COMMENT ON COLUMN quant.watch_runtime_meta.overlap_reported IS "
    "'跨规则重叠已上报规则对 [[a,b],...]（重启不重复落治理项，REQ-261016155500-4f2a wt:engine:3）'",
]

VERIFY = "select overlap_reported from quant.watch_runtime_meta limit 1"


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
