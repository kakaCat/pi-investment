#!/usr/bin/env python
"""quant.watch_rules 加 V2 触发路由三列 + engine 标记（2026-10-23 · REQ-261022235419-2299 t1）

字段（REQ-261022235419-2299 / D-14~D-19）：
  trigger_channel   'agent'(默认) | 'direct' —— 是否触发 agent（D-15 用户裁定字段）
  process_state     'pending'(默认) | 'processed' —— agent 处理状态（D-14：处理=改状态）
  cycle_count       0..9 —— 10 次循环计数（D-16/19：每规则独立，第 10 次归零）
  engine            'v1'(默认) | 'v2' —— 触发落库来源标记（backend.md：影子期双写对账）

幂等：ADD COLUMN IF NOT EXISTS + CHECK（DO 块包名查重）+ 注释 + 存量回填默认值。
VERIFY 输出含首行默认值，便于人眼对账（agent/pending/0/v1）。
默认 dry-run，--apply 写库；请对生产库与 *_test 库各执行一次。
回滚 = DROP COLUMN 四列（同名 CHECK 约束随列自动删除）。

用法：
    python infrastructure/persistence/migrations/20261023_watch_rules_v2_routing.py
    python infrastructure/persistence/migrations/20261023_watch_rules_v2_routing.py --apply
"""
import argparse
import os

from sqlalchemy import create_engine, text

COLUMNS = [
    ('watch_rules', 'trigger_channel', 'VARCHAR(16)'),
    ('watch_rules', 'process_state', 'VARCHAR(16)'),
    ('watch_rules', 'cycle_count', 'INTEGER'),
    ('watch_rules', 'engine', 'VARCHAR(8)'),
]

DDL = [
    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS trigger_channel VARCHAR(16) NOT NULL DEFAULT 'agent'",

    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS process_state VARCHAR(16) NOT NULL DEFAULT 'pending'",

    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS cycle_count INTEGER NOT NULL DEFAULT 0",

    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS engine VARCHAR(8) NOT NULL DEFAULT 'v1'",

    # 触发落库来源标记（backend.md：影子期 V1/V2 同写 watch_triggers，按 engine 对账）
    "ALTER TABLE quant.watch_triggers "
    "ADD COLUMN IF NOT EXISTS engine VARCHAR(8) NOT NULL DEFAULT 'v1'",

    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'watch_rules_trigger_channel_chk'
        ) THEN
            ALTER TABLE quant.watch_rules
            ADD CONSTRAINT watch_rules_trigger_channel_chk
            CHECK (trigger_channel IN ('agent', 'direct'));
        END IF;
    END $$;
    """,

    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'watch_rules_process_state_chk'
        ) THEN
            ALTER TABLE quant.watch_rules
            ADD CONSTRAINT watch_rules_process_state_chk
            CHECK (process_state IN ('pending', 'processed'));
        END IF;
    END $$;
    """,

    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'watch_rules_cycle_count_chk'
        ) THEN
            ALTER TABLE quant.watch_rules
            ADD CONSTRAINT watch_rules_cycle_count_chk
            CHECK (cycle_count >= 0 AND cycle_count <= 9);
        END IF;
    END $$;
    """,

    "COMMENT ON COLUMN quant.watch_rules.trigger_channel IS "
    "'是否触发 agent（D-15）：agent=默认发 agent 判断 / direct=直发。每日收盘重置任务不清此字段'",

    "COMMENT ON COLUMN quant.watch_rules.process_state IS "
    "'agent 处理状态（D-14）：pending=待处理 / processed=已处理；每日收盘重置回 pending'",

    "COMMENT ON COLUMN quant.watch_rules.cycle_count IS "
    "'10 次循环计数 0..9（D-16/19）：每规则独立；循环第 1 次发 agent、第 10 次直通群并归零'",

    "COMMENT ON COLUMN quant.watch_rules.engine IS "
    "'触发落库来源标记（backend.md）：v1/v2——影子期双写对账按此区分'",

    "COMMENT ON COLUMN quant.watch_triggers.engine IS "
    "'触发来源标记（backend.md）：v1/v2——影子期双写对账按此区分'",
]

BACKFILL = [
    # 存量回填默认值（新列已有 DEFAULT，此处兜底历史异常 NULL——NOT NULL 下理论上无 NULL，幂等保险）
    "UPDATE quant.watch_rules SET trigger_channel = 'agent' WHERE trigger_channel IS NULL",
    "UPDATE quant.watch_rules SET process_state = 'pending' WHERE process_state IS NULL",
    "UPDATE quant.watch_rules SET cycle_count = 0 WHERE cycle_count IS NULL",
    "UPDATE quant.watch_rules SET engine = 'v1' WHERE engine IS NULL",
    "UPDATE quant.watch_triggers SET engine = 'v1' WHERE engine IS NULL",
]

VERIFY = ("SELECT trigger_channel, process_state, cycle_count, engine "
          "FROM quant.watch_rules LIMIT 1")


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
        for ddl in DDL:
            if args.apply:
                conn.execute(text(ddl))
            print(('APPLY ' if args.apply else 'DRY   ') + ddl[:100].replace('\n', ' '))
        for stmt in BACKFILL:
            if args.apply:
                result = conn.execute(text(stmt))
                print(f'  backfill rows: {result.rowcount}')
            print(('APPLY ' if args.apply else 'DRY   ') + stmt[:100])
    if args.apply:
        with eng.connect() as conn:
            row = conn.execute(text(VERIFY)).fetchone()
        vals = '/'.join(str(v) for v in row) if row else '(no rows)'
        print(f'VERIFY OK — 首行默认值: {vals}')
    else:
        print('DRY-RUN done（--apply 生效；请对生产库与 *_test 库各执行一次）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
