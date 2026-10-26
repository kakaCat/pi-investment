#!/usr/bin/env python
"""把盯盘 V2 的 30 秒档调度限制在连续竞价时段（2026-10-26）。

单条 cron 无法表达跨小时但排除首尾部分分钟的区间，因此拆成四条调度，
都调用同一个 watch_scan_30s Job：
    09:30:00-09:59:30 / 10:00:00-10:59:30
    11:00:00-11:29:30 / 13:00:00-14:59:30

幂等：重复执行只更新调度定义，不重复插行，也不改变已有任务的启用状态。
默认 dry-run，--apply 写库；执行后调用 POST /api/scheduler/reload 或重启 5001。
"""
import argparse
import os

from sqlalchemy import create_engine, text

TASKS = [
    ('watch_scan_30s', '*/30 30-59 9 * * 1-5', '盯盘V2：30秒档（09:30-09:59）'),
    ('watch_scan_30s_10', '*/30 * 10 * * 1-5', '盯盘V2：30秒档（10:00-10:59）'),
    ('watch_scan_30s_11', '*/30 0-29 11 * * 1-5', '盯盘V2：30秒档（11:00-11:29）'),
    ('watch_scan_30s_pm', '*/30 * 13-14 * * 1-5', '盯盘V2：30秒档（13:00-14:59）'),
]

UPSERT = """
INSERT INTO quant.scheduler_tasks
    (name, description, cron_expression, command, params, is_enabled,
     task_type, executor_type, misfire_grace_time_seconds)
VALUES
    (:name, :description, :cron_expression, 'watch_scan_30s', '{}'::jsonb,
     true, 'cron', 'system', 5)
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    cron_expression = EXCLUDED.cron_expression,
    command = EXCLUDED.command,
    task_type = EXCLUDED.task_type,
    executor_type = EXCLUDED.executor_type,
    misfire_grace_time_seconds = EXCLUDED.misfire_grace_time_seconds,
    updated_at = CURRENT_TIMESTAMP
"""

VERIFY = """
SELECT name, cron_expression, command, is_enabled
FROM quant.scheduler_tasks
WHERE name IN ('watch_scan_30s', 'watch_scan_30s_10',
               'watch_scan_30s_11', 'watch_scan_30s_pm')
ORDER BY name
"""


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
        for name, cron_expression, description in TASKS:
            params = {'name': name, 'cron_expression': cron_expression,
                      'description': description}
            if args.apply:
                conn.execute(text(UPSERT), params)
            print(f"{'APPLY' if args.apply else 'DRY '} {name}: {cron_expression}")
    if args.apply:
        with eng.connect() as conn:
            rows = conn.execute(text(VERIFY)).fetchall()
        if len(rows) != len(TASKS):
            raise RuntimeError(f'调度核验失败：期望 {len(TASKS)} 行，实际 {len(rows)} 行')
        print('VERIFY OK')
        for row in rows:
            print(' ', tuple(row))
    else:
        print('DRY-RUN done（--apply 生效）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
