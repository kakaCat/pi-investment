#!/usr/bin/env python3
"""scheduler_daemon 退役任务迁移（2026-08-13）—— 幂等

背景：daemon 读的 quant.scheduler_task_configs 表 08-05 后无宿主执行（9 个
启用任务失传）；FastAPI lifespan 的 SchedulerService 读 quant.scheduler_tasks。
本脚本把失传任务在 scheduler_tasks 重建，并给交易类任务配置 misfire 宽限
（对齐原 daemon/APScheduler 的 per-task misfire_grace_time 语义）。

时区注意：scheduler_task_configs 的 cron 是 Asia/Shanghai（daemon APScheduler），
scheduler_tasks 的 cron 是 UTC（SchedulerService.next_run_time 逐分钟扫描 UTC）。
下方 cron 已换算（CST-8h），且 DOW 从 0-4 修正为 1-5（原配置周日空跑/周五漏跑）。

步骤：
1. scheduler_tasks 加列 misfire_grace_time_seconds（NULL=无限宽限=现语义）
2. INSERT 5 个失传任务（按 name 探测跳过）
3. UPDATE v13-simulation-trading 宽限 300s
4. scheduler_task_configs 全部 is_enabled=false（表保留不删，回滚可 flip）

生产与测试库各跑一次：
    python scripts/migrate_20260813_scheduler_tasks.py
    PGDATABASE=quant_test python scripts/migrate_20260813_scheduler_tasks.py
"""
import json

import structlog
from sqlalchemy import text

from infrastructure.persistence.database.engine import get_engine
from infrastructure.scheduler.scheduler import next_run_time

logger = structlog.get_logger(__name__)

# (name, description, cron(UTC), command, misfire_grace_time_seconds)
_MIGRATED_TASKS = [
    ('v13-risk-check', 'v13 盘后风险检查（自 scheduler_daemon 迁入）',
     '0 8 * * 1-5', 'v13_risk_check', 300),
    ('v13-verification', 'v13 交易验证（自 scheduler_daemon 迁入）',
     '30 7 * * 1-5', 'v13_verification', 43200),
    ('v14-daily-trading', 'v14 模拟交易每日检查（自 scheduler_daemon 迁入）',
     '30 7 * * 1-5', 'v14_daily_check', 300),
    ('v13-weekly-report', 'v13 周报（自 scheduler_daemon 迁入）',
     '0 1 * * 0', 'v13_weekly_report', 43200),
    ('financial-statement-update', '季度财报三大报表落库（自 scheduler_daemon 迁入；≠financial_data_update 指标）',
     '0 12 * * 6', 'financial_statement_update', 43200),
]

# 已存在但需补 misfire 宽限的存量任务
_GRACE_UPDATES = {
    'v13-simulation-trading': 300,
}


def run_migration():
    engine = get_engine()
    with engine.begin() as conn:
        # 1) 加列（幂等）
        conn.execute(text(
            "ALTER TABLE quant.scheduler_tasks "
            "ADD COLUMN IF NOT EXISTS misfire_grace_time_seconds INTEGER"
        ))

        # 2) 插入失传任务（按 name 幂等）
        for name, desc, cron, command, grace in _MIGRATED_TASKS:
            exists = conn.execute(text(
                "SELECT 1 FROM quant.scheduler_tasks WHERE name = :n"
            ), {'n': name}).fetchone()
            if exists:
                logger.info("task_exists_skip", name=name)
                continue
            conn.execute(text(
                "INSERT INTO quant.scheduler_tasks "
                "(name, description, cron_expression, command, params, "
                " is_enabled, next_run_at, misfire_grace_time_seconds) "
                "VALUES (:n, :d, :c, :cmd, :p, true, :nr, :g)"
            ), {
                'n': name, 'd': desc, 'c': cron, 'cmd': command,
                'p': json.dumps({}), 'nr': next_run_time(cron), 'g': grace,
            })
            logger.info("task_migrated", name=name, cron=cron, command=command)

        # 3) 存量任务补宽限
        for name, grace in _GRACE_UPDATES.items():
            result = conn.execute(text(
                "UPDATE quant.scheduler_tasks SET misfire_grace_time_seconds = :g "
                "WHERE name = :n AND misfire_grace_time_seconds IS NULL"
            ), {'g': grace, 'n': name})
            logger.info("grace_updated", name=name, rows=result.rowcount)

        # 4) 关停旧表（表保留不删，回滚 flip 即可）
        result = conn.execute(text(
            "UPDATE quant.scheduler_task_configs SET is_enabled = false "
            "WHERE is_enabled = true"
        ))
        logger.info("legacy_configs_disabled", rows=result.rowcount)

    logger.info("scheduler_tasks_migration_done")


if __name__ == '__main__':
    run_migration()
