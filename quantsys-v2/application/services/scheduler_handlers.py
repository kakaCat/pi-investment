"""Job handlers for Agent OS Scheduler webhooks.

This module contains all job handler functions that are called when
Agent OS Scheduler triggers scheduled tasks. Each handler is registered
via the @register_job_handler decorator and receives metadata from the
webhook payload.

Handlers delegate to existing service methods to maintain business logic
in the appropriate layers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from api.internal.scheduler_webhook import register_job_handler, JOB_HANDLERS

logger = logging.getLogger(__name__)


# ==================== Data Update Jobs ====================


@register_job_handler("kline_update")
async def handle_kline_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Update daily K-line data for all stocks.

    Original: SchedulerService._handle_kline_update
    Schedule: 工作日 17:40
    """
    logger.info("Starting kline_update job")
    from infrastructure.jobs.kline_update_job import execute

    result = execute(**(metadata or {}))
    return result


@register_job_handler("index_constituents_update")
async def handle_index_constituents_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Update index constituents (HS300/STAR50/ChiNext) into quant.index_constituents.

    Original: infrastructure/jobs/index_constituents_update_job.py
    Schedule: 工作日 15:40（原 scheduler_task_configs 迁移遗失，2026-08-19 重建）
    背景：该表是 stock_pool_service.get_hot_stocks 的数据源，失注册会导致
    机会雷达扫描池静默过期。
    """
    logger.info("Starting index_constituents_update job")
    from infrastructure.jobs.index_constituents_update_job import execute

    result = execute(**(metadata or {}))
    return result


@register_job_handler("chip_distribution_update")
async def handle_chip_distribution_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate chip distribution for all stocks.

    Original: SchedulerService._handle_chip_distribution_update
    Schedule: 工作日 18:00
    """
    logger.info("Starting chip_distribution_update job")
    from infrastructure.jobs.chip_distribution_update_job import execute

    result = execute(**(metadata or {}))
    return result


@register_job_handler("data_update")
async def handle_data_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Update market data (K-line fetching).

    Original: SchedulerService._handle_data_update
    Schedule: 工作日 07:30
    """
    logger.info("Starting data_update job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_data_update(metadata)
    return result


@register_job_handler("data_quality_check")
async def handle_data_quality_check(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute data quality check and auto-backfill.

    Original: SchedulerService._handle_data_quality_check
    Schedule: 每日 16:00
    """
    logger.info("Starting data_quality_check job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_data_quality_check(metadata)
    return result


# ==================== Pool Management Jobs ====================


@register_job_handler("pool_refresh")
async def handle_pool_refresh(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Refresh dynamic stock pools.

    Original: Implemented in application/services/scheduler_tasks.py
    Schedule: 每日 02:00
    """
    logger.info("Starting pool_refresh job")
    from application.services.scheduler_tasks import _TASK_HANDLERS

    handler = _TASK_HANDLERS.get("pool_refresh_daily")
    if handler:
        result = handler(metadata)
        return result
    else:
        raise ValueError("pool_refresh_daily handler not found")


# ==================== Signal Jobs ====================



@register_job_handler("market_perception_daily")
async def handle_market_perception_daily(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    M1 Market Perception daily snapshot (RFC 007)
    
    Executes:
    1. regime_daily - market regime classification
    2. sentiment snapshot - market sentiment indicators
    3. theme detection - hot themes and catalysts
    """
    logger.info("Starting market_perception_daily job")
    
    from application.services.market_perception_service import MarketPerceptionService
    
    try:
        service = MarketPerceptionService()
        
        # Execute regime daily snapshot
        regime_result = await service.regime_daily()
        logger.info(f"Regime snapshot completed: {regime_result.get('regime')}")
        
        # Note: sentiment and theme updates are triggered by regime_daily internally
        # or via separate API calls if needed
        
        return {
            "success": True,
            "regime": regime_result.get("regime"),
            "date": regime_result.get("date"),
            "message": "M1 market perception daily snapshot completed"
        }
    except Exception as e:
        logger.error(f"market_perception_daily failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

@register_job_handler("signal_generate")
async def handle_signal_generate(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """扫描 agent 宇宙（非空池成员 ∪ 当前持仓）× 活跃策略，买卖信号落库.

    Original: SchedulerService._handle_signal_generate
    Schedule: 工作日 09:00 (买入), 15:30 (卖出)
    """
    logger.info("Starting signal_generate job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_signal_generate(metadata)
    return result


@register_job_handler("signal_execution_daily")
async def handle_signal_execution_daily(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute daily signal execution task.

    Original: SchedulerService._handle_signal_execution_daily
    Schedule: 工作日 15:30
    """
    logger.info("Starting signal_execution_daily job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_signal_execution_daily(metadata)
    return result


@register_job_handler("signal_monitor_realtime")
async def handle_signal_monitor_realtime(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute realtime signal monitoring task.

    Original: SchedulerService._handle_signal_monitor_realtime
    Schedule: 盘中实时
    """
    logger.info("Starting signal_monitor_realtime job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_signal_monitor_realtime(metadata)
    return result


# ==================== Strategy Jobs ====================


@register_job_handler("strategy_validate_daily")
async def handle_strategy_validate_daily(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute daily strategy validation task.

    Original: SchedulerService._handle_strategy_validate_daily
    Schedule: 工作日 13:00
    """
    logger.info("Starting strategy_validate_daily job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_strategy_validate_daily(metadata)
    return result


@register_job_handler("strategy_discover_weekly")
async def handle_strategy_discover_weekly(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute weekly strategy discovery task.

    Original: SchedulerService._handle_strategy_discover_weekly
    Schedule: 每周日
    """
    logger.info("Starting strategy_discover_weekly job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_strategy_discover_weekly(metadata)
    return result


# ==================== V13/V14 Trading Jobs ====================


@register_job_handler("v13_daily_check")
async def handle_v13_daily_check(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute V13 simulation trading daily check.

    Original: SchedulerService._handle_v13_daily_check
    Schedule: 工作日 14:30
    """
    logger.info("Starting v13_daily_check job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_v13_daily_check(metadata)
    return result


@register_job_handler("v13_risk_check")
async def handle_v13_risk_check(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """v13 盘后风险检查.

    Original: SchedulerService._handle_v13_risk_check
    Schedule: 工作日 16:00
    """
    logger.info("Starting v13_risk_check job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_v13_risk_check(metadata)
    return result


@register_job_handler("v13_verification")
async def handle_v13_verification(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """v13 交易验证.

    Original: SchedulerService._handle_v13_verification
    Schedule: 工作日 16:30
    """
    logger.info("Starting v13_verification job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_v13_verification(metadata)
    return result


@register_job_handler("v13_weekly_report")
async def handle_v13_weekly_report(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """v13 周报.

    Original: SchedulerService._handle_v13_weekly_report
    Schedule: 每周六
    """
    logger.info("Starting v13_weekly_report job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_v13_weekly_report(metadata)
    return result


@register_job_handler("v14_daily_check")
async def handle_v14_daily_check(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """v14 模拟交易每日检查.

    Original: SchedulerService._handle_v14_daily_check
    Schedule: 工作日 14:30
    """
    logger.info("Starting v14_daily_check job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_v14_daily_check(metadata)
    return result


# ==================== Financial Data Jobs ====================


@register_job_handler("financial_statement_update")
async def handle_financial_statement_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """季度财报三大报表落库.

    Original: SchedulerService._handle_financial_statement_update
    Schedule: 每周六 20:00
    """
    logger.info("Starting financial_statement_update job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_financial_statement_update(metadata)
    return result


@register_job_handler("financial_data_update")
async def handle_financial_data_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute financial data update task.

    Original: SchedulerService._handle_financial_data_update
    Schedule: 每周六 18:30
    """
    logger.info("Starting financial_data_update job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_financial_data_update(metadata)
    return result


# ==================== Analysis Jobs ====================


@register_job_handler("factor_compute")
async def handle_factor_compute(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Compute factors for stocks.

    Original: SchedulerService._handle_factor_compute
    Schedule: 工作日 08:00
    """
    logger.info("Starting factor_compute job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_factor_compute(metadata)
    return result


@register_job_handler("chan_scan")
async def handle_chan_scan(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Chan theory analysis scan.

    Schedule: 工作日 10:10
    """
    logger.info("Starting chan_scan job")
    from application.services.scheduler_tasks import _TASK_HANDLERS

    handler = _TASK_HANDLERS.get("chan_scan")
    if handler:
        result = handler(metadata)
        return result
    else:
        raise ValueError("chan_scan handler not found")


@register_job_handler("chan_knowledge_distill")
async def handle_chan_knowledge_distill(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Chan knowledge distillation.

    Schedule: 每周日 12:00
    """
    logger.info("Starting chan_knowledge_distill job")
    from application.services.scheduler_tasks import _TASK_HANDLERS

    handler = _TASK_HANDLERS.get("chan_knowledge_distill_weekly")
    if handler:
        result = handler(metadata)
        return result
    else:
        raise ValueError("chan_knowledge_distill_weekly handler not found")


# ==================== Pipeline Jobs ====================


@register_job_handler("data_pipeline_daily")
async def handle_data_pipeline_daily(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute daily data pipeline task.

    Original: SchedulerService._handle_data_pipeline_daily
    Schedule: 工作日 16:30
    """
    logger.info("Starting data_pipeline_daily job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_data_pipeline_daily(metadata)
    return result


@register_job_handler("data_pipeline_weekly")
async def handle_data_pipeline_weekly(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute weekly data pipeline rebuild task.

    Original: SchedulerService._handle_data_pipeline_weekly
    Schedule: 每周六 18:00
    """
    logger.info("Starting data_pipeline_weekly job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_data_pipeline_weekly(metadata)
    return result


# ==================== Market Jobs ====================


@register_job_handler("market_style_update")
async def handle_market_style_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute daily market style update task.

    Original: SchedulerService._handle_market_style_update
    Schedule: 工作日 15:30
    """
    logger.info("Starting market_style_update job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_market_style_update(metadata)
    return result


@register_job_handler("market_scan_preopen")
async def handle_market_scan_preopen(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Execute pre-market scan task.

    Original: SchedulerService._handle_market_scan_preopen
    Schedule: 工作日 09:00
    """
    logger.info("Starting market_scan_preopen job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_market_scan_preopen(metadata)
    return result


# ==================== Risk Jobs ====================


@register_job_handler("risk_check")
async def handle_risk_check(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Run a risk assessment across the portfolio.

    Original: SchedulerService._handle_risk_check
    Schedule: 每周一 01:00
    """
    logger.info("Starting risk_check job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_risk_check(metadata)
    return result


# ==================== Report Jobs ====================


@register_job_handler("report_daily")
async def handle_report_daily(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a daily summary report.

    Original: SchedulerService._handle_report_daily
    Schedule: 每周五 10:00
    """
    logger.info("Starting report_daily job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_report_daily(metadata)
    return result


@register_job_handler("daily_equity_snapshot")
async def handle_daily_equity_snapshot(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Take daily equity snapshot for all accounts.

    Schedule: 工作日 18:00
    """
    logger.info("Starting daily_equity_snapshot job")
    from application.services.scheduler_tasks import _TASK_HANDLERS

    handler = _TASK_HANDLERS.get("daily_equity_snapshot")
    if handler:
        result = handler(metadata)
        return result
    else:
        raise ValueError("daily_equity_snapshot handler not found")


# ==================== Backtest Jobs ====================


@register_job_handler("backtest_run")
async def handle_backtest_run(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger a backtest pipeline run.

    Original: SchedulerService._handle_backtest_run
    """
    logger.info("Starting backtest_run job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_backtest_run(metadata)
    return result


@register_job_handler("benchmark_run")
async def handle_benchmark_run(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Run one or more performance benchmarks.

    Original: SchedulerService._handle_benchmark_run
    """
    logger.info("Starting benchmark_run job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_benchmark_run(metadata)
    return result


# ==================== ML Jobs ====================


@register_job_handler("model_train")
async def handle_model_train(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger ML model training.

    Original: SchedulerService._handle_model_train
    """
    logger.info("Starting model_train job")
    from infrastructure.scheduler.scheduler import SchedulerService

    scheduler = SchedulerService()
    result = scheduler._handle_model_train(metadata)
    return result


# ==================== Trading Verification ====================


@register_job_handler("trade_verify_daily")
async def handle_trade_verify_daily(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """每日交易对账（M5-2，RFC 005）
    
    Schedule: 工作日 15:35（盘后）
    
    对账逻辑：
        复用 agent-dh trading 插件的 localTradeVerify 检查项：
        1. 重复成交检测（同标的+方向+价+量+分钟）
        2. 关键字段完整性（symbol/action/price/quantity 非空且合法）
        3. 持仓勾稽（Σ买入 - Σ卖出 = 当前持仓，逐标的）
    
    Architecture:
        后端实现简化版对账（不依赖 DSH API），检查成交记录的自洽性。
        注意：不检查"订单-成交"匹配，因为 simulation_order 表无 get 方法。
    
    Background:
        2026-08-28: 初始实现，基于 SimulationRepository 的 get_trades_by_account
        和 get_all_positions 方法。
    """
    logger.info("Starting trade_verify_daily job")
    
    from datetime import date, datetime
    from collections import Counter
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    
    account_name = metadata.get("account_name", "agent_virtual")
    date_str = metadata.get("date")  # None = 当日
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    
    repo = SimulationORMRepository()
    anomalies = []
    
    try:
        # 1. 拉取成交记录（全量，用于持仓勾稽）
        all_trades = repo.get_trades_by_account(account_name)
        day_trades = [t for t in all_trades if t.trade_date == target_date]
        
        logger.info(f"Trade verification for {account_name} on {target_date}: {len(day_trades)} trades")
        
        # 2. 重复成交检测（同标的+方向+价+量+分钟）
        seen = {}
        for trade in day_trades:
            # 生成唯一键：symbol + action + price + shares + trade_time (精确到分钟)
            trade_time_str = trade.trade_time.strftime('%Y-%m-%d %H:%M') if trade.trade_time else ''
            key = f"{trade.symbol}|{trade.action}|{trade.price}|{trade.shares}|{trade_time_str}"
            
            if key in seen:
                seen[key] += 1
                anomalies.append({
                    "type": "duplicate_trade",
                    "detail": f"疑似重复成交: {trade.symbol} {trade.action} {trade.shares}股@{trade.price}（第{seen[key]}次）",
                    "trade_id": trade.id,
                    "symbol": trade.symbol
                })
            else:
                seen[key] = 1
        
        # 3. 关键字段完整性检测
        for trade in day_trades:
            missing = []
            if not trade.symbol:
                missing.append('symbol')
            if not trade.action:
                missing.append('action')
            if not trade.price or float(trade.price) <= 0:
                missing.append('price')
            if not trade.shares or trade.shares <= 0:
                missing.append('shares')
            
            if missing:
                anomalies.append({
                    "type": "missing_fields",
                    "detail": f"成交记录缺字段或非法值 {'/'.join(missing)}: trade_id={trade.id}",
                    "trade_id": trade.id,
                    "symbol": trade.symbol or 'unknown'
                })
        
        # 4. 持仓勾稽（Σ买入 - Σ卖出 = 当前持仓，逐标的）
        positions = repo.get_all_positions(account_name)
        pos_map = {p.symbol: p.shares_total for p in positions}
        
        # 计算成交净额（买入为正，卖出为负）
        net_map = {}
        has_buy = set()  # 记录有买入记录的标的
        
        for trade in all_trades:
            symbol = trade.symbol
            shares = trade.shares
            
            if trade.action.upper() == 'BUY':
                net_map[symbol] = net_map.get(symbol, 0) + shares
                has_buy.add(symbol)
            elif trade.action.upper() == 'SELL':
                net_map[symbol] = net_map.get(symbol, 0) - shares
        
        # 持仓勾稽检查
        for symbol, net_shares in net_map.items():
            held = pos_map.get(symbol, 0)
            
            # 只有当前有持仓且与成交净额不符，且差异 >= 100 股时才算异常
            if held > 0 and held != net_shares and abs(held - net_shares) >= 100:
                # 如果该标的没有买入记录，说明是迁移持仓（历史数据缺失），不算异常
                if symbol not in has_buy:
                    logger.info(f"Skipping position mismatch for {symbol}: migration position (no buy history)")
                else:
                    anomalies.append({
                        "type": "position_mismatch",
                        "detail": f"持仓勾稽不符 {symbol}: 账面 {held} vs 成交净额 {net_shares}",
                        "symbol": symbol,
                        "held": held,
                        "net_trades": net_shares
                    })
        
        # 生成结果
        matched = len(day_trades) - len([a for a in anomalies if a.get("trade_id") in [t.id for t in day_trades]])
        
        result = {
            "success": True,
            "date": target_date.isoformat(),
            "total_orders": len(day_trades),
            "matched": matched,
            "mismatched": len(anomalies),
            "anomalies": anomalies
        }
        
        # 记录结果
        if anomalies:
            logger.warning(
                f"Trade verification found {len(anomalies)} anomalies",
                extra={
                    "date": target_date.isoformat(),
                    "anomalies": anomalies[:5]  # 只记录前5个
                }
            )
        else:
            logger.info(f"Trade verification passed: {len(day_trades)} trades clean")
        
        return result
        
    except Exception as e:
        logger.error(f"Trade verification failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "date": target_date.isoformat(),
            "total_orders": 0,
            "matched": 0,
            "mismatched": 0,
            "anomalies": []
        }


# ==================== Fund Flow Jobs ====================


@register_job_handler("fund_flow_update")
async def handle_fund_flow_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """全市场资金流向每日采集（东财clist，落库stock_fund_flow）。

    Original: infrastructure/jobs/fund_flow_update_job.py
    Schedule: 工作日 15:30
    """
    logger.info("Starting fund_flow_update job")
    from infrastructure.jobs.fund_flow_update_job import execute

    result = execute(**(metadata or {}))
    return result


# ==================== Summary ====================

logger.info(f"Registered {len(JOB_HANDLERS)} job handlers")
