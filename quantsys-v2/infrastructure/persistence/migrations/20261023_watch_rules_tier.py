#!/usr/bin/env python
"""watch_rules 加档位字段 + 5 条盯盘 V2 定时任务（2026-10-23）

背景：盯盘 V2 从"常驻循环"改为"定时任务"驱动（用户裁定）。每条规则带一个档位，
决定它多久被查一次：

    watch_tier = 30    → 30 秒（贴近触发线）
    watch_tier = 600   → 10 分钟
    watch_tier = 1800  → 30 分钟（远离触发线）

档位由开盘任务（全量）与各档位任务（本档）按距离重算并回写。

定时任务（5 条，全部 cron；30 秒档用 6 段表达式，首位是秒）：
    watch_open_am   25 9 * * 1-5                 上午开盘：全部规则算档位
    watch_open_pm   0 13 * * 1-5                 下午开盘：全部规则算档位
    watch_scan_30s  */30 * 9-11,13-14 * * 1-5    本档 30s 规则
    watch_scan_10m  0 */10 9-11,13-14 * * 1-5    本档 600s 规则
    watch_scan_30m  0 0,30 9-11,13-14 * * 1-5    本档 1800s 规则

幂等：ADD COLUMN IF NOT EXISTS + DO 块加约束 + INSERT ... ON CONFLICT (name) DO NOTHING。
默认 dry-run，`--apply` 写库；请对生产库与 `*_test` 库各执行一次。

用法：
    PYTHONPATH=. python infrastructure/persistence/migrations/20261023_watch_rules_tier.py
    PYTHONPATH=. python infrastructure/persistence/migrations/20261023_watch_rules_tier.py --apply
"""
import argparse
import os

from sqlalchemy import create_engine, text

DDL = [
    "ALTER TABLE quant.watch_rules "
    "ADD COLUMN IF NOT EXISTS watch_tier SMALLINT NOT NULL DEFAULT 30",

    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'watch_rules_watch_tier_chk'
        ) THEN
            ALTER TABLE quant.watch_rules
            ADD CONSTRAINT watch_rules_watch_tier_chk
            CHECK (watch_tier IN (30, 600, 1800));
        END IF;
    END $$;
    """,

    "CREATE INDEX IF NOT EXISTS idx_watch_rules_state_tier "
    "ON quant.watch_rules (rule_state, watch_tier)",

    "COMMENT ON COLUMN quant.watch_rules.watch_tier IS "
    "'盯盘档位（秒）：30=30秒 / 600=10分钟 / 1800=30分钟；由开盘任务与档位任务按距离重算'",
]

#: 5 条定时任务（name 唯一，重复执行幂等）
SEED = [
    """
    INSERT INTO quant.scheduler_tasks
        (name, description, cron_expression, command, params, is_enabled,
         task_type, executor_type, misfire_grace_time_seconds)
    VALUES
        ('watch_open_am', '盯盘V2：上午开盘，全部规则重算档位',
         '25 9 * * 1-5', 'watch_open_am', '{}'::jsonb, true, 'cron', 'system', NULL),
        ('watch_open_pm', '盯盘V2：下午开盘，全部规则重算档位',
         '0 13 * * 1-5', 'watch_open_pm', '{}'::jsonb, true, 'cron', 'system', NULL),
        ('watch_scan_30s', '盯盘V2：30秒档规则判定（6段cron，首位秒）',
         '*/30 * 9-11,13-14 * * 1-5', 'watch_scan_30s', '{}'::jsonb, true, 'cron', 'system', 5),
        ('watch_scan_10m', '盯盘V2：10分钟档规则判定',
         '0 */10 9-11,13-14 * * 1-5', 'watch_scan_10m', '{}'::jsonb, true, 'cron', 'system', 60),
        ('watch_scan_30m', '盯盘V2：30分钟档规则判定',
         '0 0,30 9-11,13-14 * * 1-5', 'watch_scan_30m', '{}'::jsonb, true, 'cron', 'system', 120)
    ON CONFLICT (name) DO NOTHING
    """,
]

VERIFY_WATCH_RULES = "SELECT watch_tier FROM quant.watch_rules LIMIT 1"
VERIFY_TASKS = ("SELECT name, cron_expression FROM quant.scheduler_tasks "
                "WHERE name LIKE 'watch_%' ORDER BY name")


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
        for stmt in SEED:
            if args.apply:
                result = conn.execute(text(stmt))
                print(f'  seeded rows: {result.rowcount}')
            print(('APPLY ' if args.apply else 'DRY   ') + stmt[:100].replace('\n', ' '))
    if args.apply:
        with eng.connect() as conn:
            conn.execute(text(VERIFY_WATCH_RULES)).fetchone()
            rows = conn.execute(text(VERIFY_TASKS)).fetchall()
        print('VERIFY OK; watch tasks:', [r[0] for r in rows])
    else:
        print('DRY-RUN done（--apply 生效；请对生产库与 *_test 库各执行一次）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
