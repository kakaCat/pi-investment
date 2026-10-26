"""V2 每日循环重置任务（REQ-261022235419-2299 / t9）

D-18 用户裁定：10 次循环是**当天运行方式**，每日定时任务是**另一个运行方式** ——
收盘后把**活跃规则**的循环计数与 agent 处理状态清零，次日从循环首发（agent 先处理）
重新开始。2026-10-23 用户裁定：只重置活跃规则（引擎判定集合），非活跃规则
（invalid/archived/停用/过期）不参与判定，不需要重置。

与 V1 的 watch_rule_health（16:30）分开：本任务只管计数/状态重置，
不做健康判定、不标 invalid。
"""
from typing import Any, Dict

import structlog

logger = structlog.get_logger(__name__)


def _job_v2_daily_cycle_reset() -> Dict[str, Any]:
    """V2 每日循环重置：**仅活跃规则** cycle_count=0、process_state='pending'。

    活跃 = 引擎判定集合（rule_state='active' 且启用且未过期，与 list_by_state
    同一口径）；非活跃规则不进判定，不需要重置（2026-10-23 用户裁定）。

    返回：{reset_count, scope, status}；仓储缺列/异常时 reset_count=0 且
    status=degraded（不抛异常，避免打断当天其余任务）。
    """
    from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository

    repo = WatchRuleRepository()
    try:
        reset_count = repo.reset_active_cycles()
    except Exception as exc:  # noqa: BLE001 - 重置失败不打断当日其他任务
        logger.error('V2 每日循环重置失败', error=str(exc))
        return {'reset_count': 0, 'scope': 'active', 'status': 'degraded',
                'error': str(exc)}

    logger.info('V2 每日循环重置完成（仅活跃规则；次日从循环首发 agent 重新开始）',
                reset_count=reset_count, scope='active')
    return {'reset_count': reset_count, 'scope': 'active', 'status': 'ok'}
