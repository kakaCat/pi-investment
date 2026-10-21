#!/usr/bin/env python
"""quant.watch_pool_bindings 建表（2026-10-20 · 选池↔盯盘接线）

池级盯盘绑定：把一个 stock_pools 池的成员批量映射为盯盘规则（成员自带
buy_point/sell_point + 池级条件模板），池变更（增删成员/调点位）经 reconcile
自动增删改规则。

ORM：infrastructure/persistence/orm/models/watch_pool_binding.py WatchPoolBinding；
服务：qs_watch...watch_engine/pool_watch_service.py。
"""
import argparse
import os

from sqlalchemy import create_engine, text

DDL = """
CREATE TABLE IF NOT EXISTS quant.watch_pool_bindings (
    id SERIAL PRIMARY KEY,
    pool_id INTEGER NOT NULL,
    pool_name VARCHAR(128) NOT NULL DEFAULT '',
    conditions_template JSONB,
    use_member_points BOOLEAN NOT NULL DEFAULT TRUE,
    member_points_mode VARCHAR(16) NOT NULL DEFAULT 'breakout',
    intent VARCHAR(30) NOT NULL DEFAULT 'trend_observe',
    account VARCHAR(60),
    cooldown_sec INTEGER,
    max_members INTEGER NOT NULL DEFAULT 100,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync_summary JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

COMMENT = ("COMMENT ON TABLE quant.watch_pool_bindings IS "
           "'池级盯盘绑定（2026-10-20）：stock_pools 成员 ↔ watch_rules 的接线配置'")


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    eng = _engine()
    with eng.begin() as conn:
        if args.apply:
            conn.execute(text(DDL))
            conn.execute(text(COMMENT))
        print(('APPLY ' if args.apply else 'DRY   ') + 'CREATE TABLE quant.watch_pool_bindings')
    if args.apply:
        with eng.connect() as conn:
            conn.execute(text('SELECT id FROM quant.watch_pool_bindings LIMIT 1')).fetchone()
        print('VERIFY OK')
    else:
        print('DRY-RUN done（--apply 生效；请对生产库与 *_test 库各执行一次）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
