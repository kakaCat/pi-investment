"""
任务健康监控

监控任务执行状态，检测：
1. 任务是否超过预期时间未执行
2. 任务是否卡住（running 超时）
3. 任务是否反复失败
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from domain.ports import ISchedulerRepository

logger = logging.getLogger(__name__)


def check_job_health(repo: ISchedulerRepository) -> Dict[str, Any]:
    issues: list = []

    for row in repo.find_zombie_runs(threshold_hours=1):
        issues.append({
            "type": "zombie_running",
            "severity": "high",
            "job": row["name"],
            "message": f"任务卡死 {row['hours_running']:.1f} 小时",
            "run_id": row["run_id"],
        })

    for row in repo.find_missed_tasks(threshold_hours=24):
        issues.append({
            "type": "missed_execution",
            "severity": "medium",
            "job": row["name"],
            "message": "超过 24 小时未执行",
            "last_run": row["last_run_at"],
        })

    for row in repo.find_high_failure_tasks(days=7, min_runs=3, fail_rate_threshold=0.5):
        issues.append({
            "type": "high_failure_rate",
            "severity": "high",
            "job": row["name"],
            "message": f"失败率 {row['fail_rate']:.0%} ({row['failed']}/{row['total']})",
            "total": row["total"],
            "failed": row["failed"],
        })

    total_enabled = repo.count_enabled_tasks()
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
