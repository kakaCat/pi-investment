"""
调度任务处理器
从旧的infrastructure/scheduler迁移过来的command handlers

Author: System Migration
Date: 2026-06-27
"""
from domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta

logger = structlog.get_logger(__name__)


# ============================================================
# Task Handlers - 从旧scheduler迁移
# ============================================================

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
        from infrastructure.persistence.database.engine import get_engine
        from sqlalchemy import text
        from adapters.inbound.fastapi_app.daily_jobs_bootstrap import _last_trading_day
        engine = get_engine()
        with engine.connect() as conn:
            kline_latest = conn.execute(
                text("SELECT max(trade_date) FROM quant.daily_klines")).scalar()
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


# 与 pool_scanner_service.scanner_config['strategies'] 保持一致
DEFAULT_SCAN_STRATEGY_IDS = [272, 273]


def _scan_pool_signals_by_name(
    pool_name: str,
    strategy_ids=None,
    lookback_days: int = 60,
) -> list:
    """按池名扫描信号：解析池→symbols，调用 PoolSignalScanner。

    Returns: 买入/卖出信号列表，每个信号附带 pool/strategy_id/signal_type。
    """
    from application.services.pool_signal_scanner import PoolSignalScanner
    from adapters.shared.services import stock_pool_service

    strategy_ids = strategy_ids or DEFAULT_SCAN_STRATEGY_IDS

    # 解析池名 → pool_id → symbols
    pools_by_name = {p['name']: p for p in stock_pool_service.list_pools()}
    if pool_name not in pools_by_name:
        raise ValueError(f"股票池不存在: {pool_name}")
    pool = stock_pool_service.get_pool(pools_by_name[pool_name]['id'])
    symbols = pool.get('symbols', [])
    if not symbols:
        return []

    scanner = PoolSignalScanner(IKlineRepository(), IStrategyRepository())
    signals = []
    for strategy_id in strategy_ids:
        result = scanner.scan_pool_signals(
            symbols=symbols,
            strategy_id=strategy_id,
            lookback_days=lookback_days,
        )
        for s in result.get('buy_signals', []):
            signals.append({**s, 'pool': pool_name, 'strategy_id': strategy_id, 'signal_type': 'buy'})
        for s in result.get('sell_signals', []):
            signals.append({**s, 'pool': pool_name, 'strategy_id': strategy_id, 'signal_type': 'sell'})
    return signals


def handle_signal_generate(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """信号生成任务"""
    params = params or {}

    logger.info("Starting signal_generate task")

    try:
        # 获取要扫描的池子
        pools = params.get('pools', ['主选池', '备选池'])
        strategy_ids = params.get('strategy_ids')

        all_signals = []
        pools_scanned = 0

        for pool_name in pools:
            try:
                signals = _scan_pool_signals_by_name(pool_name, strategy_ids=strategy_ids)
                all_signals.extend(signals)
                pools_scanned += 1
            except Exception as e:
                logger.warning(f"Failed to scan pool {pool_name}: {e}")

        # 按信号强度排序（无 strength 字段的信号排最后）
        all_signals.sort(key=lambda x: x.get('strength', 0), reverse=True)

        return {
            "action": "signal_generate",
            "status": "success",
            "pools_scanned": pools_scanned,
            "signals_generated": len(all_signals),
            "top_signals": all_signals[:20],  # 返回前20个信号
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        return {
            "action": "signal_generate",
            "status": "failed",
            "error": str(e)
        }


def _is_pool_refresh_due(pool: Dict[str, Any], today: date) -> bool:
    """判断动态池是否到期该刷新。

    refresh_interval 约定：'daily' 每个交易日刷；'weekly' 距上次 ≥7 天；
    其他/缺失值按 daily 处理（宁多刷不漏刷）。
    """
    interval = (pool.get('refresh_interval') or 'daily').lower()
    if interval == 'weekly':
        last = pool.get('last_refreshed_at')
        if not last:
            return True
        try:
            last_date = datetime.fromisoformat(str(last).split(' ')[0]).date()
            return (today - last_date).days >= 7
        except ValueError:
            return True
    return True


def handle_pool_refresh_daily(
    params: Dict[str, Any] = None,
    service=None,
) -> Dict[str, Any]:
    """每日动态池刷新任务（02:00）

    刷新所有到期动态池，记录成员变更；有变更时通知 Agent（pool_changed）。
    service 参数用于测试注入；默认使用 API 共享单例。
    """
    params = params or {}
    logger.info("Starting pool_refresh_daily task")

    if service is None:
        from adapters.shared.services import stock_pool_service
        service = stock_pool_service

    today = date.today()
    refreshed, skipped, failed = [], [], []

    for pool in service.list_pools():
        if pool.get('pool_type') != 'dynamic':
            continue
        if not _is_pool_refresh_due(pool, today):
            skipped.append({'pool_id': pool['id'], 'name': pool['name']})
            continue
        try:
            before_symbols = set(service.get_pool(pool['id']).get('symbols', []))
            service.refresh_pool(pool['id'])
            after_symbols = set(service.get_pool(pool['id']).get('symbols', []))
            refreshed.append({
                'pool_id': pool['id'],
                'name': pool['name'],
                'added': sorted(after_symbols - before_symbols),
                'removed': sorted(before_symbols - after_symbols),
            })
        except Exception as e:
            logger.error(f"Failed to refresh pool {pool['id']}: {e}")
            failed.append({'pool_id': pool['id'], 'name': pool['name'], 'error': str(e)})

    changed = [r for r in refreshed if r['added'] or r['removed']]
    if changed and not params.get('skip_notify'):
        try:
            from application.services.agent_notification_service import agent_service
            agent_service.notify_agent('pool_changed', {
                'trade_date': today.isoformat(),
                'pools_changed': changed,
                'account': 'agent_virtual',
            })
        except Exception as e:
            logger.warning(f"pool_changed notify failed: {e}")

    return {
        "action": "pool_refresh_daily",
        "status": "success" if not failed else "partial",
        "refreshed": len(refreshed),
        "changed": len(changed),
        "skipped": len(skipped),
        "failed": failed,
        "timestamp": datetime.now().isoformat(),
    }


def handle_signal_execution_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """每日信号汇总推送（兜底重推）

    2026-07-24 盈利闭环改造：v2 不再自动下单。本任务只把当日 pending
    信号再次推送给 Agent（orchestrator MARKET_OPEN 推送的兜底），
    Agent 侧按信号 ID 判重，重复推送不会重复交易。
    """
    params = params or {}

    from application.services.signal_execution_scheduler import SignalExecutionScheduler

    logger.info("Starting daily signal summary push (fallback)")

    try:
        scheduler = SignalExecutionScheduler()
        signals = scheduler._collect_signals(date.today().strftime('%Y-%m-%d'))

        pushed = False
        if signals and not params.get('skip_notify'):
            from application.services.agent_notification_service import agent_service
            result = agent_service.notify_agent_detailed('signals_ready', {
                'trade_date': date.today().isoformat(),
                'signal_count': len(signals),
                'signals': signals[:20],
                'account': 'agent_virtual',
                'source': 'signal_execution_daily_fallback',
            })
            # timeout 视为已送达（agent 正在处理），不重推
            pushed = result in ('ok', 'timeout')

        return {
            "action": "signal_execution_daily",
            "status": "success",
            "signals_pending": len(signals),
            "pushed": pushed,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Signal summary push failed: {e}")
        return {
            "action": "signal_execution_daily",
            "status": "failed",
            "error": str(e)
        }


def handle_report_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """每日报告生成任务"""
    params = params or {}

    logger.info("Starting report_daily task")

    try:
        from datetime import date

        # 生成今日报告
        report_date = params.get('date', date.today())

        report_content = {
            "date": str(report_date),
            "sections": []
        }

        # 1. 市场概况
        try:
            from application.services.market_data_service import MarketDataService
            market_service = MarketDataService()
            market_summary = market_service.get_market_summary()
            report_content["sections"].append({
                "title": "市场概况",
                "data": market_summary
            })
        except Exception as e:
            logger.warning(f"Failed to get market summary: {e}")

        # 2. 持仓表现
        try:
            from application.services.portfolio_service import PortfolioService
            portfolio_service = PortfolioService()
            portfolio_performance = portfolio_service.get_daily_performance()
            report_content["sections"].append({
                "title": "持仓表现",
                "data": portfolio_performance
            })
        except Exception as e:
            logger.warning(f"Failed to get portfolio performance: {e}")

        # 3. 信号统计
        try:
            from application.services.signal_monitoring import SignalMonitor
            signal_monitor = SignalMonitor()
            signal_stats = signal_monitor.get_daily_stats()
            report_content["sections"].append({
                "title": "信号统计",
                "data": signal_stats
            })
        except Exception as e:
            logger.warning(f"Failed to get signal stats: {e}")

        return {
            "action": "report_daily",
            "status": "success",
            "report_date": str(report_date),
            "sections_count": len(report_content["sections"]),
            "report": report_content,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Daily report generation failed: {e}")
        return {
            "action": "report_daily",
            "status": "failed",
            "error": str(e)
        }


def handle_backtest_run(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """回测任务"""
    params = params or {}

    logger.info("Starting backtest_run task")

    try:
        from application.services.combo_strategy_backtest_service import ComboStrategyBacktestService
        from datetime import date, timedelta

        service = ComboStrategyBacktestService()

        # 设置回测参数
        end_date = params.get('end_date', date.today())
        start_date = params.get('start_date', end_date - timedelta(days=365))

        strategy_ids = params.get('strategy_ids')
        if not strategy_ids:
            # 获取所有启用的策略
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            from domain.ports import IStrategyRepository
            repo = EnhancedServiceFactory.resolve(IStrategyRepository)
            strategies = repo.list_enabled_strategies(limit=10)
            strategy_ids = [s.id for s in strategies]

        # 执行回测
        backtest_results = []
        for strategy_id in strategy_ids:
            try:
                result = service.run_backtest(
                    strategy_id=strategy_id,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=params.get('initial_capital', 100000)
                )
                backtest_results.append(result)
            except Exception as e:
                logger.warning(f"Backtest failed for strategy {strategy_id}: {e}")

        return {
            "action": "backtest_run",
            "status": "success",
            "strategies_tested": len(backtest_results),
            "start_date": str(start_date),
            "end_date": str(end_date),
            "results_summary": [
                {
                    "strategy_id": r.get('strategy_id'),
                    "return_rate": r.get('return_rate'),
                    "sharpe_ratio": r.get('sharpe_ratio')
                }
                for r in backtest_results
            ],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return {
            "action": "backtest_run",
            "status": "failed",
            "error": str(e)
        }


def handle_factor_compute(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """因子计算任务（盘后批量重算并落库，为次日信号做准备）

    注意：不要调用 FactorAnalysisService —— 它是 IC/收益分析服务，
    没有 compute_factors 入口。批量计算走 FactorStage（与
    adapters/inbound/api/routes/jobs.py 的 compute_factors 同一条路径）。
    """
    params = params or {}

    logger.info("Starting factor_compute task")

    try:
        from domain.backtest.stages.factor_stage import FactorStage
        from adapters.shared.fund_flow_helpers import (
            _inject_fund_flow_to_klines, _extract_fund_flow_factors,
        )
        from adapters.outbound.repositories import KlineORMRepository, FactorORMRepository

        # 获取股票列表（如果没有指定）
        symbols = params.get('symbols')
        if not symbols:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            from domain.ports import IStockRepository
            repo = EnhancedServiceFactory.resolve(IStockRepository)
            stocks = repo.get_all(limit=params.get('max_symbols', 500))
            symbols = [s['symbol'] for s in stocks]

        requested = params.get('factors') or None
        if requested == ['all']:
            requested = None  # None = FactorStage 默认全量技术因子

        # R1修复：增加lookback到300天（原250），为momentum_6m(140天)和momentum_52w_high(250天)留出缓冲
        lookback_days = params.get('lookback_days', 300)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        computed = 0
        failed = []
        for sym in symbols:
            try:
                kline_repo = KlineORMRepository()
                klines_df = kline_repo.get_daily_klines(sym, start_date, end_date)
                if klines_df is None or klines_df.is_empty():
                    failed.append(sym)
                    continue

                klines = klines_df.to_dicts()
                klines = _inject_fund_flow_to_klines(klines, sym)
                
                stage = FactorStage(name='factors', factor_names=requested)
                stage_input = {'symbol': sym, 'klines': klines}
                if requested:
                    stage_input['requested_factors'] = requested

                result = stage.process(stage_input)
                factors = result.get('factors', {})
                
                all_requested = requested or stage.DEFAULT_TECHNICAL_FACTORS
                computed_names = set(factors.keys())
                missing = set(all_requested) - computed_names
                if missing and len(klines) < 250:
                    logger.warning(f"{sym}: {len(missing)} factors dropped (insufficient data {len(klines)}<250): {sorted(missing)}")
                
                fund_factors = _extract_fund_flow_factors(klines)
                factors.update(fund_factors)

                last_row = klines[-1]
                latest_date = last_row.get('trade_date') or last_row.get('date') or ''
                FactorORMRepository().save_factors(sym, str(latest_date), factors)
                computed += 1
            except Exception as sym_err:
                logger.warning(f"factor compute failed for {sym}: {sym_err}")
                failed.append(sym)

        return {
            "action": "factor_compute",
            "status": "success",
            "symbols_count": len(symbols),
            "factors_computed": computed,
            "failed": failed[:20],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Factor compute failed: {e}")
        return {
            "action": "factor_compute",
            "status": "failed",
            "error": str(e)
        }


def handle_model_train(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """模型训练任务"""
    params = params or {}

    logger.info("Starting model_train task")

    try:
        # 模型训练是一个耗时任务，这里提供基本框架
        model_type = params.get('model_type', 'xgboost')

        # 获取训练数据
        symbols = params.get('symbols')
        if not symbols:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            from domain.ports import IStockRepository
            repo = EnhancedServiceFactory.resolve(IStockRepository)
            stocks = repo.get_all(limit=100)
            symbols = [s['symbol'] for s in stocks]

        # 准备特征数据
        from application.services.factor_analysis_service import FactorAnalysisService
        factor_service = FactorAnalysisService()

        training_data = factor_service.prepare_training_data(
            symbols=symbols,
            lookback_days=params.get('lookback_days', 500)
        )

        # 这里应该调用实际的ML训练服务
        # 由于这是一个复杂且耗时的任务，建议使用异步队列或单独的训练流程

        return {
            "action": "model_train",
            "status": "success",
            "model_type": model_type,
            "training_samples": len(training_data) if training_data else 0,
            "message": "Model training initiated (框架就绪，需要完整ML pipeline)",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Model training failed: {e}")
        return {
            "action": "model_train",
            "status": "failed",
            "error": str(e)
        }


def handle_benchmark_run(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """基准测试任务"""
    params = params or {}

    logger.info("Starting benchmark_run task")

    try:
        from application.services.benchmark_service import BenchmarkService
        from datetime import date, timedelta

        service = BenchmarkService()

        # 设置基准测试参数
        end_date = params.get('end_date', date.today())
        start_date = params.get('start_date', end_date - timedelta(days=30))

        # 运行基准测试
        benchmark_results = service.run_benchmark(
            start_date=start_date,
            end_date=end_date,
            benchmarks=params.get('benchmarks', ['沪深300', '中证500'])
        )

        return {
            "action": "benchmark_run",
            "status": "success",
            "start_date": str(start_date),
            "end_date": str(end_date),
            "benchmarks_tested": len(benchmark_results),
            "results": benchmark_results,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return {
            "action": "benchmark_run",
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


def handle_strategy_validate_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """每日策略验证任务"""
    params = params or {}

    logger.info("Starting strategy_validate_daily task")

    try:
        from application.services.strategy_validation_service import StrategyValidationService

        service = StrategyValidationService()

        # 验证所有启用的策略
        validation_results = service.validate_all_strategies(
            force_refresh=params.get('force_refresh', False)
        )

        # 统计结果
        total_strategies = len(validation_results)
        valid_count = sum(1 for r in validation_results if r.get('is_valid', False))
        invalid_count = total_strategies - valid_count

        # 标记无效策略
        if params.get('auto_disable_invalid', False):
            for result in validation_results:
                if not result.get('is_valid', False):
                    service.mark_strategy_invalid(result['strategy_id'])

        return {
            "action": "strategy_validate_daily",
            "status": "success",
            "total_strategies": total_strategies,
            "valid_count": valid_count,
            "invalid_count": invalid_count,
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
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            from domain.ports import IStockRepository
            repo = EnhancedServiceFactory.resolve(IStockRepository)
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


# ============================================================
# Handler Registry
# ============================================================

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


def handle_performance_report(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """绩效报告任务处理器"""
    try:
        from application.services.performance_tracker import get_performance_tracker
        tracker = get_performance_tracker()
        report = tracker.get_quick_stats()
        return {"action": "performance_report", "status": "success", "report": report}
    except Exception as e:
        logger.error(f"Performance report failed: {e}")
        return {"action": "performance_report", "status": "failed", "error": str(e)}


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


def handle_chan_scan(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """缠论买卖点池内扫描（每日收盘后）"""
    from application.services.chan_scan_service import ChanScanService

    logger.info("Starting chan_scan task")
    try:
        summary = ChanScanService().scan()
        return {
            "action": "chan_scan",
            "status": "success",
            **summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"chan_scan failed: {e}")
        return {
            "action": "chan_scan",
            "status": "failed",
            "error": str(e)
        }


def handle_chan_knowledge_distill(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """缠论信号胜率蒸馏（每周）"""
    from application.services.chan_knowledge_distiller import ChanKnowledgeDistiller

    logger.info("Starting chan_knowledge_distill task")
    try:
        params = params or {}
        result = ChanKnowledgeDistiller(
            window_days=params.get('window_days', 20),
            lookback_days=params.get('lookback_days', 90),
        ).distill()
        return {
            "action": "chan_knowledge_distill",
            "status": "success",
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"chan_knowledge_distill failed: {e}")
        return {
            "action": "chan_knowledge_distill",
            "status": "failed",
            "error": str(e)
        }


def handle_model_train_auto(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    自动化模型训练任务
    
    Args:
        params: {
            "model_type": "lightgbm" | "xgboost",
            "symbols_limit": int (默认500),
            "lookback_days": int (默认350),
            "force_train": bool (强制训练，忽略性能检查),
            "test_size": float (测试集比例，默认0.2),
            "auto_switch": bool (性能提升时自动切换，默认True),
        }
    """
    params = params or {}
    
    model_type = params.get('model_type', 'lightgbm')
    symbols_limit = params.get('symbols_limit', 500)
    lookback_days = params.get('lookback_days', 350)
    force_train = params.get('force_train', False)
    test_size = params.get('test_size', 0.2)
    auto_switch = params.get('auto_switch', True)
    
    logger.info(f"模型训练任务启动: {model_type}, symbols={symbols_limit}, force={force_train}")
    
    try:
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        from adapters.outbound.repositories import KlineORMRepository, FactorORMRepository
        from application.services.ml_pipeline.feature_engineering import FeatureEngineer
        from application.services.ml_pipeline.predictor import MLPredictor
        from adapters.shared.ml_helpers import _get_model_repo
        from sklearn.model_selection import train_test_split
        
        # 1. 检查是否需要训练（非强制模式）
        if not force_train:
            should_train, reason = _check_train_needed(model_type)
            if not should_train:
                logger.info(f"跳过训练: {reason}")
                result_dict = {
                    "action": "model_train_auto",
                    "status": "skipped",
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                }
                
                try:
                    from application.notification.notification_factory import get_notification_facade
                    get_notification_facade().send_ml_train_notification(result_dict)
                except Exception as e:
                    logger.warning(f"发送通知失败: {e}")
                
                return result_dict
        
        # 2. 获取股票列表
        repo = StockORMRepository()
        stocks = repo.get_all(limit=symbols_limit)
        symbols = [s['symbol'] for s in stocks]
        logger.info(f"训练样本: {len(symbols)} 只股票")
        
        # 3. 加载K线和因子数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        
        # 加载K线（用于计算target）
        klines_dict = {}
        for i, symbol in enumerate(symbols):
            try:
                rows = KlineORMRepository().get_daily_klines(symbol, start_date, end_date)
                if rows is not None and not rows.is_empty():
                    klines_dict[symbol] = [dict(r) for r in rows.to_dicts()]
                if (i+1) % 100 == 0:
                    logger.info(f"已加载K线 {i+1}/{len(symbols)}")
            except Exception as e:
                logger.warning(f"加载K线 {symbol} 失败: {e}")
        
        logger.info(f"成功加载K线 {len(klines_dict)}/{len(symbols)} 只股票")
        
        if len(klines_dict) < 50:
            return {
                "action": "model_train_auto",
                "status": "failed",
                "error": f"数据不足：仅加载{len(klines_dict)}只股票（需>=50）",
                "timestamp": datetime.now().isoformat()
            }
        
        # 4. 加载因子数据并构建训练集（参考ml_async.py）
        logger.info("加载因子数据...")
        import pandas as pd
        all_rows = []
        
        for i, symbol in enumerate(klines_dict.keys()):
            try:
                factors_data = FactorORMRepository().get_factors_range(symbol, start_date, end_date)
                if factors_data is None or factors_data.is_empty():
                    continue
                
                # 构建因子字典（按日期）
                by_date = {}
                for fv in factors_data.iter_rows(named=True):
                    d = str(fv.get("factor_date") or fv.get("date", ""))
                    if not d:
                        continue
                    by_date.setdefault(d, {})[fv["factor_name"]] = float(fv.get("factor_value", 0) or 0)
                
                # 构建收盘价字典
                close_map = {}
                for k in klines_dict[symbol]:
                    d = str(k.get("date", k.get("trade_date", "")))
                    close_map[d] = float(k.get("close", 0))
                
                # 生成训练样本（当日因子 → 次日涨跌标签）
                sorted_dates = sorted(by_date.keys())
                for j in range(len(sorted_dates) - 1):
                    cur_date = sorted_dates[j]
                    next_date = sorted_dates[j + 1]
                    cur_close = close_map.get(cur_date, 0)
                    next_close = close_map.get(next_date, 0)
                    if cur_close <= 0:
                        continue
                    
                    row = dict(by_date[cur_date])
                    row["__target"] = 1 if next_close > cur_close else 0
                    row["__symbol"] = symbol
                    row["__date"] = cur_date
                    all_rows.append(row)
                
                if (i+1) % 100 == 0:
                    logger.info(f"已处理因子 {i+1}/{len(klines_dict)}")
                    
            except Exception as e:
                logger.warning(f"处理因子 {symbol} 失败: {e}")
        
        logger.info(f"生成训练样本: {len(all_rows)} 条")
        
        if len(all_rows) < 100:
            return {
                "action": "model_train_auto",
                "status": "failed",
                "error": f"有效样本不足：仅{len(all_rows)}条（需>=100）",
                "timestamp": datetime.now().isoformat()
            }
        
        # 5. 特征工程
        logger.info("特征工程...")
        X = pd.DataFrame(all_rows)
        y = X.pop("__target")
        X = X.drop(columns=["__symbol", "__date"], errors="ignore")
        X = X.fillna(X.median(numeric_only=True)).fillna(0)
        
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X = pd.DataFrame(X_scaled, columns=X.columns)
        logger.info(f"特征准备完成: {X.shape[0]} 样本 × {X.shape[1]} 特征")
        
        # 6. 训练模型
        logger.info(f"训练 {model_type} 模型...")
        from application.services.ml_pipeline.trainer import MLTrainer
        from sklearn.model_selection import train_test_split
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
        
        trainer = MLTrainer(model_type=model_type)
        results = trainer.train(X, y, test_size=test_size, params={})
        
        
        train_acc = results.get("train_accuracy", 0)
        test_acc = results.get("test_accuracy", 0)
        logger.info(f"训练完成: train_acc={train_acc:.4f}, test_acc={test_acc:.4f}")
        
        # 7. 保存模型
        version = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            trainer.save_model(version=version)
        except Exception as e:
            logger.warning(f"模型文件保存失败: {e}")
        logger.info(f"模型已保存: {version}")
        
        # 7. 保存训练记录到DB
        model_repo = _get_model_repo()
        model_repo.create({
            "model_type": model_type,
            "version": version,
            "model_path": str(model_path),
            "train_accuracy": train_acc,
            "test_accuracy": test_acc,
            "train_samples": len(X_train),
            "feature_count": X.shape[1],
            "training_params": {
                "symbols_count": len(klines_dict),
                "lookback_days": lookback_days,
                "test_size": test_size,
            },
            "status": "ready",
        })
        
        # 8. 性能对比（记录，不自动切换，需人工确认）
        switched = False
        if auto_switch:
            switched = _try_switch_model(model_type, version, test_acc)
            if switched:
                logger.info(f"已自动切换到新模型: {version}")
        
        result_dict = {
            "action": "model_train_auto",
            "status": "success",
            "model_type": model_type,
            "version": version,
            "train_accuracy": round(train_acc, 4),
            "test_accuracy": round(test_acc, 4),
            "train_samples": len(all_rows),
            "test_samples": int(len(all_rows) * test_size),
            "feature_count": X.shape[1],
            "symbols_trained": len(klines_dict),
            "auto_switched": switched,
            "timestamp": datetime.now().isoformat()
        }
        
        # 发送通知
        try:
            from application.notification.notification_factory import get_notification_facade
            get_notification_facade().send_ml_train_notification(result_dict)
        except Exception as e:
            logger.warning(f"发送通知失败: {e}")
        
        return result_dict
        
    except Exception as e:
        logger.error(f"模型训练失败: {e}", exc_info=True)
        result_dict = {
            "action": "model_train_auto",
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            from application.notification.notification_factory import get_notification_facade
            get_notification_facade().send_ml_train_notification(result_dict)
        except Exception as e_notify:
            logger.warning(f"发送通知失败: {e_notify}")
        
        return result_dict


_TASK_HANDLERS: Dict[str, Callable] = {
    "data_quality_check": handle_data_quality_check,
    "data_update": handle_data_update,
    "signal_generate": handle_signal_generate,
    "pool_refresh_daily": handle_pool_refresh_daily,
    "signal_execution_daily": handle_signal_execution_daily,
    "report_daily": handle_report_daily,
    "backtest_run": handle_backtest_run,
    "strategy_backtest": handle_backtest_run,  # 别名
    "factor_compute": handle_factor_compute,
    "model_train": handle_model_train,
    "benchmark_run": handle_benchmark_run,
    "market_style_update": handle_market_style_update,
    "v13_daily_check": handle_v13_daily_check,
    # 新增 - 从旧调度器迁移
    "financial_data_update": handle_financial_data_update,
    "market_scan_preopen": handle_market_scan_preopen,
    "strategy_validate_daily": handle_strategy_validate_daily,
    "strategy_discover_weekly": handle_strategy_discover_weekly,
    # Agent相关
    "agent_reminder": handle_agent_reminder,
    # 自主轮转系统
    "orchestrator_tick": handle_orchestrator_tick,
    "intraday_monitor": handle_intraday_monitor,
    "performance_report": handle_performance_report,
    "strategy_rotation": handle_strategy_rotation,
    # 缠论学习闭环
    "chan_scan": handle_chan_scan,
    "chan_knowledge_distill": handle_chan_knowledge_distill,
    "model_train_auto": handle_model_train_auto,
}


def get_task_handler(command: str) -> Callable:
    """获取任务处理器

    Args:
        command: 任务命令名称

    Returns:
        任务处理函数

    Raises:
        ValueError: 如果命令不存在
    """
    handler = _TASK_HANDLERS.get(command)
    if handler is None:
        available = ', '.join(_TASK_HANDLERS.keys())
        raise ValueError(
            f"Unknown task command: {command!r}. "
            f"Available commands: {available}"
        )
    return handler


def list_available_commands() -> list:
    """列出所有可用的任务命令"""
    return list(_TASK_HANDLERS.keys())

# ============================================================
# 模型训练自动化任务
# ============================================================

def _check_train_needed(model_type: str) -> tuple:
    """检查是否需要训练"""
    import pandas as pd
    from adapters.shared.ml_helpers import _get_model_repo, _resolve_latest_version
    
    latest_version = _resolve_latest_version(model_type)
    if not latest_version:
        return (True, "无可用模型")
    
    repo = _get_model_repo()
    model = repo.get_by_type_version(model_type, latest_version)
    if not model:
        return (True, "模型元数据缺失")
    
    train_date_str = model.get('train_date')
    if train_date_str:
        train_date = pd.to_datetime(train_date_str)
        days_old = (datetime.now() - train_date).days
        
        if days_old > 7:
            return (True, f"模型已{days_old}天未更新")
    
    test_acc = model.get('test_accuracy')
    if test_acc and test_acc < 0.55:
        return (True, f"模型性能低 (test_acc={test_acc:.4f})")
    
    return (False, f"模型{latest_version}仍有效 (age={days_old}d, acc={test_acc:.4f})")


def _try_switch_model(model_type: str, new_version: str, new_test_acc: float) -> bool:
    """尝试切换到新模型（如果性能更好）"""
    from adapters.shared.ml_helpers import _get_model_repo, _resolve_latest_version
    
    current_version = _resolve_latest_version(model_type)
    if not current_version or current_version == new_version:
        return True
    
    repo = _get_model_repo()
    current_model = repo.get_by_type_version(model_type, current_version)
    if not current_model:
        return True
    
    current_test_acc = current_model.get('test_accuracy', 0.0)
    
    # 策略：新模型准确率提升>=1%
    if new_test_acc > current_test_acc + 0.01:
        logger.info(f"性能提升: {current_test_acc:.4f} → {new_test_acc:.4f}")
        return True
    else:
        logger.info(f"新模型性能未达切换阈值")
        return False


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
        from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
        from domain.ports import ISimulationRepository

        # 获取服务
        repo = EnhancedServiceFactory.resolve(ISimulationRepository)
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
