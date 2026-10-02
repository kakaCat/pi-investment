"""数据类任务处理器（质量检查/数据更新/财务/市场风格）

2026-10-01（REQ-261001145152-3982 t-686185）：由 scheduler_tasks.py（原 1607 行）
机械拆分而来；函数体与签名**逐字未改**，原模块保留为转发壳，既有导入路径不受影响。
"""
from domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta
import json
from application.services.scheduler_tasks_common import logger  # noqa: F401

def handle_data_quality_check(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """数据质量检查任务"""
    params = params or {}

    from infrastructure.jobs.data_quality_check_job import DataQualityCheckJob

    job = DataQualityCheckJob()
    result = job.run(params)

    if result['success']:
        check_summary = result.get('check_summary', {})
        return {
            "action": "data_quality_check",
            "status": "success",
            "checked_symbols": check_summary.get('total_symbols', 0),
            "passed": check_summary.get('passed', 0),
            "failed": check_summary.get('failed', 0),
            "quality_score": check_summary.get('quality_score', 0),
            "timestamp": result.get('timestamp')
        }
    else:
        return {
            "action": "data_quality_check",
            "status": "failed",
            "error": result.get('error')
        }


def handle_data_update(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """数据更新任务（盘前新鲜度检查）

    2026-09-02 两连修：
    1) 原实现只读 get_latest_daily_kline 做"存在性检查"就把只读查询计数为
       symbols_updated——假干活，从不真正同步（9-01 数据因此整体缺失）。
    2) 第一次修复把真同步放这里，但本函数会被 orchestrator
       resume_from_breakpoint 在 FastAPI 主线程同步执行，全市场同步
       （50 分钟级）把启动卡死（10:45 启动挂起事故）。
    最终形态：只做新鲜度检查（快、无网络）；真同步由进程内 daily_jobs 宿主的
    morning_topup（08:35）/ evening_pipeline（15:40）任务线程承担。
    """
    params = params or {}

    logger.info("Starting data_update task")

    kline_latest = None
    expected = None
    # 新鲜度检查：已新鲜则跳过（幂等，不重复拉全市场）
    try:
        # 2026-09-14（REQ-24e15d B4-c5）：原为裸 SQL
        #     SELECT max(trade_date) FROM quant.daily_klines
        # 收进 KlineORMRepository.get_latest_trade_date_strict()。用 strict 变体（读失败回滚并
        # 上抛，走下面 except → status=error），而不是会吞异常的 get_latest_trade_date
        # （那会把"读失败"静默降级成"数据滞后" = stale）。
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        from adapters.inbound.fastapi_app.daily_jobs_bootstrap import _last_trading_day
        kline_latest = KlineORMRepository().get_latest_trade_date_strict()
        expected = _last_trading_day(datetime.now())
        if kline_latest and str(kline_latest) >= expected:
            return {
                "action": "data_update",
                "status": "skipped",
                "reason": f"K线已新鲜（最新 {kline_latest} ≥ {expected}），晚间 pipeline 已覆盖",
            }
        logger.warning(f"K线滞后（最新 {kline_latest} < {expected}），待 morning_topup/evening_pipeline 补同步")
    except Exception as e:
        logger.error(f"新鲜度检查失败: {e}")
        return {
            "action": "data_update",
            "status": "error",
            "error": str(e),
        }

    # 滞后只报告不真同步（重活必须在任务线程，不能在 orchestrator 阶段/主线程）
    return {
        "action": "data_update",
        "status": "stale",
        "reason": f"K线滞后（最新 {kline_latest} < {expected}），由 morning_topup/evening_pipeline 任务线程补同步",
        "kline_latest": str(kline_latest) if kline_latest else None,
        "expected": expected,
    }


def handle_financial_data_update(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """财务数据更新任务

    默认更新最近5年（20个季度）的财务数据
    可通过params['periods']自定义期数
    """
    params = params or {}

    logger.info("Starting financial_data_update task")

    try:
        from application.services.financial_data_service_adapter import FinancialDataServiceAdapter as FinancialDataService

        service = FinancialDataService()

        # 获取股票列表
        symbols = params.get('symbols')
        if not symbols:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            from domain.ports import IStockRepository
            repo = EnhancedServiceFactory.resolve(IStockRepository)
            stocks = repo.list_by_market(market='A', limit=500)
            symbols = [s.symbol for s in stocks]

        updated_count = 0
        errors = []

        # 批量更新财务数据
        for symbol in symbols:
            try:
                financial_data = service.get_financial_indicators(symbol)
                if financial_data:
                    updated_count += 1
            except Exception as e:
                errors.append({"symbol": symbol, "error": str(e)})

        return {
            "action": "financial_data_update",
            "status": "success",
            "symbols_checked": len(symbols),
            "symbols_updated": updated_count,
            "errors_count": len(errors),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Financial data update failed: {e}")
        return {
            "action": "financial_data_update",
            "status": "failed",
            "error": str(e)
        }


def handle_market_style_update(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """市场风格更新任务"""
    params = params or {}

    logger.info("Starting market_style_update task")

    try:
        from application.services.market_style_detector import MarketStyleDetector

        detector = MarketStyleDetector()

        # 检测当前市场风格
        current_style = detector.detect_market_style(
            lookback_days=params.get('lookback_days', 20)
        )

        # 风格历史由 strategy_rotation_engine 自行维护，
        # 原 detector.update_style_history 已不存在（2026-07-23 修复）
        style_update = {'changes': []}

        return {
            "action": "market_style_update",
            "status": "success",
            "current_style": current_style.get('style', 'unknown'),
            "confidence": current_style.get('confidence', 0),
            "style_changes": style_update.get('changes', []),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Market style update failed: {e}")
        return {
            "action": "market_style_update",
            "status": "failed",
            "error": str(e)
        }


