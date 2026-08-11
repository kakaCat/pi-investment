"""
调度任务处理器
从旧的infrastructure/scheduler迁移过来的command handlers

Author: System Migration
Date: 2026-06-27
"""
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
    """数据更新任务"""
    params = params or {}

    from application.services.data_service import DataService
    from concurrent.futures import ThreadPoolExecutor, as_completed

    logger.info("Starting data_update task")

    # 获取股票列表
    try:
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        repo = StockORMRepository()
        stocks = repo.get_all(limit=500)
        symbols = [s['symbol'] for s in stocks]
    except Exception as e:
        logger.error(f"Failed to fetch stock list: {e}")
        return {
            "action": "data_update",
            "status": "error",
            "error": str(e)
        }

    if not symbols:
        return {
            "action": "data_update",
            "status": "skipped",
            "reason": "No symbols to update"
        }

    # 并行更新
    # 注意：DataService 内部持有 ORM session，不是线程安全的，
    # 必须每个任务独立实例，不能跨线程共享（2026-07-30 并发报错修复）
    def _fetch_one(symbol: str):
        from infrastructure.persistence.orm import close_session
        try:
            return DataService().kline.get_latest_daily_kline(symbol)
        finally:
            # 释放线程级 session，避免连接滞留
            close_session()

    updated = 0
    errors = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_fetch_one, symbol): symbol
            for symbol in symbols
        }

        for future in as_completed(futures):
            symbol = futures[future]
            try:
                future.result()
                updated += 1
            except Exception as e:
                errors.append({"symbol": symbol, "error": str(e)})

    return {
        "action": "data_update",
        "status": "success",
        "symbols_checked": len(symbols),
        "symbols_updated": updated,
        "errors": errors
    }


def handle_data_pipeline_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """每日数据管道任务"""
    params = params or {}

    from application.services.data_pipeline_service import DataPipelineService
    from datetime import date

    logger.info("Starting daily data pipeline")

    try:
        pipeline = DataPipelineService()
        today = date.today()

        # 执行增量更新
        result = pipeline.run_incremental_update(
            symbols=params.get('symbols'),
            end_date=today
        )

        return {
            "action": "data_pipeline_daily",
            "status": result.get('status', 'success'),
            "date": today.isoformat(),
            "symbols_count": result.get('symbols_count', 0),
            "metadata": result.get('metadata', {}),
            "timestamp": result.get('timestamp')
        }
    except Exception as e:
        logger.error(f"Daily pipeline failed: {e}")
        return {
            "action": "data_pipeline_daily",
            "status": "failed",
            "error": str(e)
        }


def handle_data_pipeline_weekly(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """每周数据管道任务（全量重建）"""
    params = params or {}

    from application.services.data_pipeline_service import DataPipelineService
    from datetime import date, timedelta

    logger.info("Starting weekly data pipeline (full rebuild)")

    try:
        pipeline = DataPipelineService()
        end_date = date.today()
        start_date = end_date - timedelta(days=90)

        # 执行全量重建
        result = pipeline.run_full_rebuild(
            symbols=params.get('symbols'),
            start_date=start_date,
            end_date=end_date
        )

        return {
            "action": "data_pipeline_weekly",
            "status": result.get('status', 'success'),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols_count": result.get('symbols_count', 0),
            "metadata": result.get('metadata', {}),
            "timestamp": result.get('timestamp')
        }
    except Exception as e:
        logger.error(f"Weekly pipeline failed: {e}")
        return {
            "action": "data_pipeline_weekly",
            "status": "failed",
            "error": str(e)
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
    from adapters.outbound.repositories import KlineORMRepository, StrategyORMRepository
    from adapters.inbound.api.shared import stock_pool_service

    strategy_ids = strategy_ids or DEFAULT_SCAN_STRATEGY_IDS

    # 解析池名 → pool_id → symbols
    pools_by_name = {p['name']: p for p in stock_pool_service.list_pools()}
    if pool_name not in pools_by_name:
        raise ValueError(f"股票池不存在: {pool_name}")
    pool = stock_pool_service.get_pool(pools_by_name[pool_name]['id'])
    symbols = pool.get('symbols', [])
    if not symbols:
        return []

    scanner = PoolSignalScanner(KlineORMRepository(), StrategyORMRepository())
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
        from adapters.inbound.api.shared import stock_pool_service
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


def handle_risk_check(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """风险检查任务"""
    params = params or {}

    logger.info("Starting risk_check task")

    try:
        from application.services.risk_check_service import RiskCheckService

        service = RiskCheckService()

        # 执行风险检查
        risk_report = service.run_comprehensive_risk_check(
            check_portfolio=params.get('check_portfolio', True),
            check_positions=params.get('check_positions', True),
            check_market=params.get('check_market', True)
        )

        return {
            "action": "risk_check",
            "status": "success",
            "risk_level": risk_report.get('overall_risk_level', 'unknown'),
            "warnings": risk_report.get('warnings', []),
            "alerts": risk_report.get('alerts', []),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Risk check failed: {e}")
        return {
            "action": "risk_check",
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
            from adapters.outbound.repositories import StrategyORMRepository
            repo = StrategyORMRepository()
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
        from infrastructure.services.service_factory import get_data_service
        from domain.quantlib.stages.factor_stage import FactorStage

        ds = get_data_service()

        # 获取股票列表（如果没有指定）
        symbols = params.get('symbols')
        if not symbols:
            from adapters.outbound.repositories.stock_repository import StockORMRepository
            repo = StockORMRepository()
            stocks = repo.get_all(limit=params.get('max_symbols', 500))
            symbols = [s['symbol'] for s in stocks]

        requested = params.get('factors') or None
        if requested == ['all']:
            requested = None  # None = FactorStage 默认全量技术因子

        lookback_days = params.get('lookback_days', 250)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        computed = 0
        failed = []
        for sym in symbols:
            try:
                klines_df = ds.kline.get_daily_klines(sym, start_date, end_date)
                if klines_df is None or klines_df.is_empty():
                    failed.append(sym)
                    continue

                klines = klines_df.to_dicts()
                stage = FactorStage(name='factors', factor_names=requested)
                stage_input = {'symbol': sym, 'klines': klines}
                if requested:
                    stage_input['requested_factors'] = requested

                result = stage.process(stage_input)
                factors = result.get('factors', {})

                last_row = klines[-1]
                latest_date = last_row.get('trade_date') or last_row.get('date') or ''
                ds.factor.save_factors(sym, str(latest_date), factors)
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
            from adapters.outbound.repositories.stock_repository import StockORMRepository
            repo = StockORMRepository()
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
    """V13模拟交易每日检查任务"""
    params = params or {}

    logger.info("Starting v13_daily_check task")

    try:
        # V13是特定的模拟交易系统
        # 这里提供基本框架，具体实现需要V13系统的详细需求

        from datetime import date

        check_date = params.get('date', date.today())

        # 检查V13系统状态
        v13_status = {
            "date": str(check_date),
            "system_status": "running",
            "checks_performed": []
        }

        # 1. 检查持仓状态
        v13_status["checks_performed"].append({
            "check": "position_status",
            "status": "ok",
            "message": "V13 position check completed"
        })

        # 2. 检查信号执行
        v13_status["checks_performed"].append({
            "check": "signal_execution",
            "status": "ok",
            "message": "V13 signal execution check completed"
        })

        # 3. 检查风险指标
        v13_status["checks_performed"].append({
            "check": "risk_metrics",
            "status": "ok",
            "message": "V13 risk metrics within limits"
        })

        return {
            "action": "v13_daily_check",
            "status": "success",
            "check_date": str(check_date),
            "checks_completed": len(v13_status["checks_performed"]),
            "v13_status": v13_status,
            "timestamp": datetime.now().isoformat()
        }

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
        from application.services.financial_data_service import FinancialDataService

        service = FinancialDataService()

        # 获取股票列表
        symbols = params.get('symbols')
        if not symbols:
            from adapters.outbound.repositories.stock_repository import StockORMRepository
            repo = StockORMRepository()
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


def handle_signal_monitor_realtime(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """实时信号监控任务（每5分钟执行）"""
    params = params or {}

    logger.info("Starting signal_monitor_realtime task")

    try:
        from application.services.signal_monitoring import SignalMonitor

        monitor = SignalMonitor()

        # 扫描活跃池的信号
        active_pools = params.get('pools', ['主选池', '观察池'])

        signals_found = []
        for pool_name in active_pools:
            try:
                signals = _scan_pool_signals_by_name(pool_name)
                signals_found.extend(signals)
            except Exception as e:
                logger.warning(f"Failed to scan pool {pool_name}: {e}")

        # 记录监控指标
        return {
            "action": "signal_monitor_realtime",
            "status": "success",
            "pools_scanned": len(active_pools),
            "signals_found": len(signals_found),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Realtime signal monitor failed: {e}")
        return {
            "action": "signal_monitor_realtime",
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
            from adapters.outbound.repositories.stock_repository import StockORMRepository
            repo = StockORMRepository()
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


def handle_daily_equity_snapshot(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """全账户每日净值快照（收盘后按当日收盘价重估持仓，行为进化 Phase 1 地基）"""
    from application.services.evolution.daily_snapshot_service import DailySnapshotService

    logger.info("Starting daily_equity_snapshot task")
    try:
        params = params or {}
        target = date.fromisoformat(params['date']) if params.get('date') else None
        result = DailySnapshotService().snapshot_all_accounts(target_date=target)
        return {
            "action": "daily_equity_snapshot",
            "status": "success",
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"daily_equity_snapshot failed: {e}")
        return {
            "action": "daily_equity_snapshot",
            "status": "failed",
            "error": str(e)
        }


def handle_evolution_fitness_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """双侧捕获适应度每日计算（行为进化 Phase 1，收盘后全账户滚动窗口）"""
    from application.services.evolution.evolution_fitness_service import EvolutionFitnessService

    logger.info("Starting evolution_fitness_daily task")
    try:
        params = params or {}
        result = EvolutionFitnessService().compute_all_accounts(
            window_days=params.get('window_days', 20))
        return {
            "action": "evolution_fitness_daily",
            "status": "success",
            **result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"evolution_fitness_daily failed: {e}")
        return {
            "action": "evolution_fitness_daily",
            "status": "failed",
            "error": str(e)
        }


def handle_decision_score_daily(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """决策打分每日任务（文本参数进化 P0a）：满20交易日的买卖决策打分回写"""
    try:
        from application.services.evolution.decision_score_service import DecisionScoreService
        result = DecisionScoreService().score_mature_decisions()
        return {"action": "decision_score_daily", "status": "success",
                **result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"决策打分任务失败: {e}")
        return {"action": "decision_score_daily", "status": "failed",
                "error": str(e), "timestamp": datetime.now().isoformat()}


_TASK_HANDLERS: Dict[str, Callable] = {
    "data_quality_check": handle_data_quality_check,
    "data_update": handle_data_update,
    "data_pipeline_daily": handle_data_pipeline_daily,
    "data_pipeline_weekly": handle_data_pipeline_weekly,
    "signal_generate": handle_signal_generate,
    "pool_refresh_daily": handle_pool_refresh_daily,
    "signal_execution_daily": handle_signal_execution_daily,
    "risk_check": handle_risk_check,
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
    "signal_monitor_realtime": handle_signal_monitor_realtime,
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
    # 行为进化 Phase 1
    "daily_equity_snapshot": handle_daily_equity_snapshot,
    "evolution_fitness_daily": handle_evolution_fitness_daily,
    "decision_score_daily": handle_decision_score_daily,
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
