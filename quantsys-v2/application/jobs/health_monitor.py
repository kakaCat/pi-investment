"""
任务健康监控

监控任务执行状态，检测：
1. 任务是否超过预期时间未执行
2. 任务是否卡住（running 超时）
3. 任务是否反复失败
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

DB_DSN = "postgresql://mac@127.0.0.1:5432/quant_investment"


def check_job_health() -> Dict[str, Any]:
    """检查所有任务的健康状态。

    Returns:
        {
            "healthy": bool,
            "issues": [...],
            "summary": {"total_enabled": N, "zombie": N, "missed": N, "high_failure": N},
            "checked_at": "ISO timestamp"
        }
    """
    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    issues: List[Dict[str, Any]] = []

    # 1. 僵尸 running 任务（running 超过 1 小时）
    cursor.execute(
        """
        SELECT t.name, r.id as run_id, r.started_at,
               EXTRACT(EPOCH FROM (now() - r.started_at)) / 3600 as hours_running
        FROM quant.scheduler_runs r
        JOIN quant.scheduler_tasks t ON r.task_id = t.id
        WHERE r.status = 'running'
        AND r.started_at < now() - interval '1 hour'
        """
    )
    for row in cursor.fetchall():
        issues.append({
            "type": "zombie_running",
            "severity": "high",
            "job": row["name"],
            "message": f"任务卡死 {row['hours_running']:.1f} 小时",
            "run_id": row["run_id"],
        })

    # 2. 超过 24 小时未执行的启用任务（仅检查有 cron 的工作日任务）
    cursor.execute(
        """
        SELECT name, cron_expression, last_run_at
        FROM quant.scheduler_tasks
        WHERE is_enabled = true
        AND cron_expression NOT LIKE 'managed_by_agent_%'
        AND (last_run_at IS NULL OR last_run_at < now() - interval '24 hours')
        """
    )
    for row in cursor.fetchall():
        issues.append({
            "type": "missed_execution",
            "severity": "medium",
            "job": row["name"],
            "message": "超过 24 小时未执行",
            "last_run": str(row["last_run_at"] or "NEVER"),
        })

    # 3. 最近 7 天失败率高的任务
    cursor.execute(
        """
        SELECT t.name,
               COUNT(*) as total,
               SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM quant.scheduler_runs r
        JOIN quant.scheduler_tasks t ON r.task_id = t.id
        WHERE r.started_at > now() - interval '7 days'
        GROUP BY t.name
        HAVING COUNT(*) >= 3
        """
    )
    for row in cursor.fetchall():
        total = row["total"]
        failed = row["failed"] or 0
        fail_rate = failed / total if total > 0 else 0
        if fail_rate > 0.5:
            issues.append({
                "type": "high_failure_rate",
                "severity": "high",
                "job": row["name"],
                "message": f"失败率 {fail_rate:.0%} ({failed}/{total})",
                "total": total,
                "failed": failed,
            })

    # Summary
    cursor.execute(
        "SELECT count(*) as cnt FROM quant.scheduler_tasks WHERE is_enabled = true"
    )
    total_enabled = cursor.fetchone()["cnt"]

    conn.close()

    zombie_count = sum(1 for i in issues if i["type"] == "zombie_running")
    missed_count = sum(1 for i in issues if i["type"] == "missed_execution")
    high_fail_count = sum(1 for i in issues if i["type"] == "high_failure_rate")

    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "summary": {
            "total_enabled": total_enabled,
            "zombie": zombie_count,
            "missed": missed_count,
            "high_failure": high_fail_count,
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
