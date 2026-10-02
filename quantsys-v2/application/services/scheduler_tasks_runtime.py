"""运行时杂项任务处理器（orchestrator/盘中监控/挂单撮合）

2026-10-01（REQ-261001145152-3982 t-686185）：由 scheduler_tasks.py（原 1607 行）
机械拆分而来；函数体与签名**逐字未改**，原模块保留为转发壳，既有导入路径不受影响。
"""
from domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta
import json
from application.services.scheduler_tasks_common import logger  # noqa: F401

def handle_orchestrator_tick(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """日常编排器 tick 任务处理器"""
    try:
        from application.services.daily_orchestrator import get_daily_orchestrator
        orchestrator = get_daily_orchestrator()
        orchestrator.tick()
        return {"action": "orchestrator_tick", "status": "success"}
    except Exception as e:
        logger.error(f"Orchestrator tick failed: {e}")
        return {"action": "orchestrator_tick", "status": "failed", "error": str(e)}


def handle_intraday_monitor(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """盘中监控任务处理器"""
    try:
        from application.services.intraday_monitor import get_intraday_monitor
        monitor = get_intraday_monitor()
        result = monitor.check()
        return {"action": "intraday_monitor", "status": "success", "result": result}
    except Exception as e:
        logger.error(f"Intraday monitor failed: {e}")
        return {"action": "intraday_monitor", "status": "failed", "error": str(e)}


def handle_pending_orders_match(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """挂单撮合任务 - 开盘后执行所有 pending 挂单

    调度时机: 每个交易日 9:31 (开盘后1分钟)

    功能:
    1. 获取所有 pending 状态的挂单
    2. 逐个执行完整交易护栏校验
    3. 成交成功 -> status='executed'
    4. 护栏拒绝 -> status='failed' + fail_reason

    Args:
        params: 可选参数
            - account_name: 仅撮合指定账户（可选）

    Returns:
        执行结果统计
    """
    params = params or {}
    logger.info("开始挂单撮合任务", params=params)

    try:
        from application.services.account_trading_service import AccountTradingService
        from infrastructure.services.service_factory import ServiceFactory
        from domain.ports import ISimulationRepository

        # 获取服务
        repo = ServiceFactory.resolve(ISimulationRepository)
        trading_service = AccountTradingService(repo=repo)

        # 执行撮合
        result = trading_service.execute_pending_orders()

        logger.info(
            "挂单撮合完成",
            executed=result['executed'],
            failed=result['failed'],
        )

        return {
            "action": "pending_orders_match",
            "status": "success",
            "executed": result['executed'],
            "failed": result['failed'],
            "details": result.get('details', []),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"挂单撮合失败: {e}", exc_info=True)
        return {
            "action": "pending_orders_match",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


