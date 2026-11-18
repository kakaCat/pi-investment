#!/usr/bin/env python
"""注册每交易日 09:10 的股票机会扫描任务（2026-10-26）。

任务 command=opportunity_scan_daily，对应 JobRegistry 中的 OpportunityScanDailyJob。
幂等：重复执行更新调度定义，不重复插行，也不改变已有任务的启用状态和参数。
默认 dry-run，--apply 写库；执行后调用 POST /api/scheduler/reload 或重启服务。
"""
import argparse
import os

from sqlalchemy import create_engine, text

TASK = {
    "name": "opportunity_scan_daily",
    "description": "每交易日扫描股票机会，高分买入机会生成 V2 盯盘规则",
    "cron_expression": "10 9 * * 1-5",
}

UPSERT = """
INSERT INTO quant.scheduler_tasks
    (name, description, cron_expression, command, params, is_enabled,
     task_type, executor_type, misfire_grace_time_seconds)
VALUES
    (:name, :description, :cron_expression, 'opportunity_scan_daily', '{}'::jsonb,
     true, 'cron', 'system', 3600)
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
SELECT name, cron_expression, command, is_enabled, misfire_grace_time_seconds
FROM quant.scheduler_tasks
WHERE name = 'opportunity_scan_daily'
"""


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get("QUANT_DATABASE_URL") or "postgresql+psycopg2:///quant_investment"
    return create_engine(url)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dsn")
    args = parser.parse_args()

    eng = _engine(args.dsn)
    with eng.begin() as conn:
        if args.apply:
            conn.execute(text(UPSERT), TASK)
        print(
            f"{'APPLY' if args.apply else 'DRY '} {TASK['name']}: "
            f"{TASK['cron_expression']}"
        )
    if args.apply:
        with eng.connect() as conn:
            row = conn.execute(text(VERIFY)).fetchone()
        if row is None:
            raise RuntimeError("调度核验失败：opportunity_scan_daily 未写入")
        print("VERIFY OK:", tuple(row))
    else:
        print("DRY-RUN done（--apply 生效）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
