#!/usr/bin/env python
"""把盯盘 V2 的 10/30 分钟档调度限制在连续竞价时段（2026-10-26）。

10 分钟档：09:30-11:20、13:00-14:50，每 10 分钟。
30 分钟档：09:30、10:00、10:30、11:00、13:00、13:30、14:00、14:30。
跨小时的非整段分钟区间拆成多条调度，仍调用原来的两个 Job。

幂等：重复执行只更新调度定义，不重复插行，也不改变已有任务的启用状态。
默认 dry-run，--apply 写库；执行后调用 POST /api/scheduler/reload 或重启 5001。
"""
import argparse
import os

from sqlalchemy import create_engine, text

TASKS = [
    ('watch_scan_10m', '0 30-59/10 9 * * 1-5', 'watch_scan_10m',
     '盯盘V2：10分钟档（09:30-09:50）'),
    ('watch_scan_10m_mid', '0 */10 10,13-14 * * 1-5', 'watch_scan_10m',
     '盯盘V2：10分钟档（10点及下午整段）'),
    ('watch_scan_10m_11', '0 0-29/10 11 * * 1-5', 'watch_scan_10m',
     '盯盘V2：10分钟档（11:00-11:20）'),
    ('watch_scan_30m', '0 30 9 * * 1-5', 'watch_scan_30m',
     '盯盘V2：30分钟档（09:30）'),
    ('watch_scan_30m_mid', '0 0,30 10,13-14 * * 1-5', 'watch_scan_30m',
     '盯盘V2：30分钟档（10点及下午整段）'),
    ('watch_scan_30m_11', '0 0 11 * * 1-5', 'watch_scan_30m',
     '盯盘V2：30分钟档（11:00）'),
]

UPSERT = """
INSERT INTO quant.scheduler_tasks
    (name, description, cron_expression, command, params, is_enabled,
     task_type, executor_type, misfire_grace_time_seconds)
VALUES
    (:name, :description, :cron_expression, :command, '{}'::jsonb,
     true, 'cron', 'system', :misfire_grace_time_seconds)
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
WHERE name = ANY(:names)
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
        for name, cron_expression, command, description in TASKS:
            params = {
                'name': name,
                'cron_expression': cron_expression,
                'command': command,
                'description': description,
                'misfire_grace_time_seconds': 60 if command == 'watch_scan_10m' else 120,
            }
            if args.apply:
                conn.execute(text(UPSERT), params)
            print(f"{'APPLY' if args.apply else 'DRY '} {name}: {cron_expression}")
    if args.apply:
        with eng.connect() as conn:
            rows = conn.execute(text(VERIFY), {'names': [t[0] for t in TASKS]}).fetchall()
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
