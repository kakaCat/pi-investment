"""
任务健康监控

监控任务执行状态，检测：
1. 任务是否超过预期时间未执行
2. 任务是否卡住（running 超时）
3. 任务是否反复失败
"""
import json
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

    # 六域打标覆盖（2026-09-13, REQ-c970e5 / w-a1402b8c）
    #
    # 为什么放进健康检查：`domain` 是创建路径长期没有接的字段（端口/域服务/仓储/路由四处
    # 签名都没有它）→ 每个新建任务静默 born-NULL。历史：2026-09-02 加列当天回填 30 个
    # （0 NULL）→ 09-12 又修 12 条 → 09-13 新建 6 条再 NULL。每次都靠人肉读看板才发现。
    # 这里把它变成**每日自曝**信号，源头修复见 add_task/update_task 的 domain 参数。
    #
    # 口径与看板一致：只对 **enabled** 任务计缺口 —— 未启用/已软删的任务不参与打标对账
    # （session-probe 即"disabled + 全仓无实现 + 溯源不明"的有意留空，不该天天刷告警）。
    untagged_domain: list = []
    try:
        for t in repo.list_tasks(enabled_only=True):
            params = t.get("params")
            if isinstance(params, str):
                try:
                    params = json.loads(params or "{}")
                except (TypeError, ValueError):
                    params = {}
            if isinstance(params, dict) and params.get("_deleted_at"):
                continue
            if not str(t.get("domain") or "").strip():
                untagged_domain.append(str(t.get("name") or ""))
        if untagged_domain:
            head = ", ".join(untagged_domain[:5])
            issues.append({
                "type": "domain_missing",
                "severity": "medium",
                "job": head,
                "message": (
                    f"{len(untagged_domain)} 个启用任务未打六域标（domain=NULL）：{head}"
                    + (" 等" if len(untagged_domain) > 5 else "")
                ),
                "count": len(untagged_domain),
                "tasks": untagged_domain,
            })
    except Exception as e:  # 健康检查本身不得因为新指标而整体失败
        logger.warning(f"domain 覆盖检查失败（不影响其它检查）: {e}")

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
            "domain_missing": len(untagged_domain),
            "domain_missing_tasks": untagged_domain,
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
