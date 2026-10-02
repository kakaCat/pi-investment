"""策略类任务处理器（验证/发现/轮动/V13/盘前扫描）

2026-10-01（REQ-261001145152-3982 t-686185）：由 scheduler_tasks.py（原 1607 行）
机械拆分而来；函数体与签名**逐字未改**，原模块保留为转发壳，既有导入路径不受影响。
"""
from domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta
import json
from application.services.scheduler_tasks_common import logger  # noqa: F401
from application.services.scheduler_tasks_signals import _scan_pool_signals_by_name  # noqa: F401

def handle_strategy_validate_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """每日策略验证任务"""
    params = params or {}

    # Fix④: 原实现调用 validate_all_strategies(force_refresh=...) —— 该方法签名无 force_refresh，
    # 且依赖已删除的 /api/backtest/batch 路由必然失败；mark_strategy_invalid 亦不存在。
    # 对齐为与 Job / scheduler._handle_strategy_validate_daily 相同的真实委托：
    # 基于最近落库回测证据的报告性验证（无证据显式跳过，不自动停用）。
    logger.info("Starting strategy_validate_daily task")

    try:
        from application.services.strategy_validation_service import StrategyValidationService
        from adapters.outbound.repositories.strategy_repository import StrategyORMRepository
        from adapters.outbound.repositories.stock_repository import StockORMRepository

        service = StrategyValidationService(
            strategy_repo=StrategyORMRepository(),
            stock_repo=StockORMRepository(),
        )
        result = service.validate_from_recent_backtests(
            lookback_days=int(params.get('lookback_days', 30)),
            threshold=float(params.get('threshold', 60.0)),
            dry_run=bool(params.get('dry_run', False)),
        )

        return {
            "action": "strategy_validate_daily",
            "status": "success",
            "total_strategies": result['total'],
            "valid_count": result['passed'],
            "invalid_count": result['failed'],
            "with_evidence": result['with_evidence'],
            "no_evidence_skipped": result['no_evidence'],
            "reports_written": result['reports_written'],
            "dry_run": result['dry_run'],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Strategy validation failed: {e}")
        return {
            "action": "strategy_validate_daily",
            "status": "failed",
            "error": str(e)
        }


def handle_strategy_discover_weekly(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """每周策略发现任务"""
    params = params or {}

    logger.info("Starting strategy_discover_weekly task")

    try:
        from application.services.strategy_discovery_service import StrategyDiscoveryService

        service = StrategyDiscoveryService()

        # 获取股票池
        symbols = params.get('symbols')
        if not symbols:
            from infrastructure.services.service_factory import ServiceFactory
            from domain.ports import IStockRepository
            repo = ServiceFactory.resolve(IStockRepository)
            stocks = repo.get_all(limit=50)  # 限制数量避免太慢
            symbols = [s['symbol'] for s in stocks]

        # 运行策略发现
        discovery_report = service.run(
            symbols=symbols,
            max_strategies_per_archetype=params.get('max_strategies', 5),
            lookback_days=params.get('lookback_days', 365)
        )

        return {
            "action": "strategy_discover_weekly",
            "status": "success",
            "symbols_scanned": len(symbols),
            "strategies_discovered": discovery_report.get('total_discovered', 0),
            "top_strategies": discovery_report.get('top_strategies', [])[:5],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Strategy discovery failed: {e}")
        return {
            "action": "strategy_discover_weekly",
            "status": "failed",
            "error": str(e)
        }


def handle_strategy_rotation(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """策略轮动评估任务处理器"""
    try:
        from application.services.strategy_rotation_engine import get_rotation_engine
        engine = get_rotation_engine()
        result = engine.evaluate()
        return {"action": "strategy_rotation", "status": "success", "result": result}
    except Exception as e:
        logger.error(f"Strategy rotation failed: {e}")
        return {"action": "strategy_rotation", "status": "failed", "error": str(e)}


def handle_v13_daily_check(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """V13模拟交易每日检查任务

    2026-08-13 修桩：原实现是返回编造 checks_performed 的假桩，
    替换为委托真 job（infrastructure.jobs.strategy_trading_job.v13_daily_check）。
    本函数是 _TASK_HANDLERS 回落路径，假桩会在 handlers 解析顺序变化时静默跑假任务。
    """
    logger.info("Starting v13_daily_check task")
    try:
        from infrastructure.jobs.strategy_trading_job import v13_daily_check
        return v13_daily_check(**(params or {}))
    except Exception as e:
        logger.error(f"V13 daily check failed: {e}")
        return {
            "action": "v13_daily_check",
            "status": "failed",
            "error": str(e)
        }


def handle_market_scan_preopen(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """开盘前市场扫描任务（09:25执行）"""
    params = params or {}

    logger.info("Starting market_scan_preopen task")

    try:
        from application.services.market_monitor_scheduler import MarketMonitorScheduler

        # 扫描主要池子的开盘信号
        pools_to_scan = params.get('pools', ['主选池', '备选池'])

        scan_results = []
        for pool_name in pools_to_scan:
            try:
                signals = _scan_pool_signals_by_name(pool_name)
                scan_results.append({
                    'pool': pool_name,
                    'signals_count': len(signals),
                    'signals': signals[:10]  # 只保留前10个
                })
            except Exception as e:
                logger.warning(f"Failed to scan pool {pool_name}: {e}")

        total_signals = sum(r['signals_count'] for r in scan_results)

        return {
            "action": "market_scan_preopen",
            "status": "success",
            "pools_scanned": len(pools_to_scan),
            "total_signals": total_signals,
            "results": scan_results,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Pre-market scan failed: {e}")
        return {
            "action": "market_scan_preopen",
            "status": "failed",
            "error": str(e)
        }


def handle_agent_reminder(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Agent提醒任务处理器

    Agent可以创建提醒任务，在指定时间提醒自己

    Args:
        params: 任务参数，包含:
            - agent_id: Agent ID
            - message: 提醒消息
            - remind_at: 提醒时间

    Returns:
        执行结果
    """
    params = params or {}

    agent_id = params.get("agent_id", "default_agent")
    message = params.get("message", "这是一个提醒")
    remind_at = params.get("remind_at")

    logger.info(f"🔔 Agent Reminder for {agent_id}: {message}")

    try:
        # 尝试使用通知服务
        try:
            from application.services.agent_notification_service import AgentNotificationService

            notification_service = AgentNotificationService()
            notification_service.send_reminder(
                agent_id=agent_id,
                message=message,
                remind_at=remind_at
            )
        except Exception as notify_error:
            logger.warning(f"Notification service not available: {notify_error}")

        # 记录到日志（作为备份）
        logger.info(f"📌 Agent {agent_id} reminder: {message} (scheduled for {remind_at})")

        return {
            "action": "agent_reminder",
            "status": "success",
            "agent_id": agent_id,
            "message": message,
            "remind_at": remind_at,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Agent reminder failed: {e}")
        return {
            "action": "agent_reminder",
            "status": "failed",
            "error": str(e)
        }


