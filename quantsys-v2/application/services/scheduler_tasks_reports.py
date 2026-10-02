"""报告与回测类任务处理器

2026-10-01（REQ-261001145152-3982 t-686185）：由 scheduler_tasks.py（原 1607 行）
机械拆分而来；函数体与签名**逐字未改**，原模块保留为转发壳，既有导入路径不受影响。
"""
from domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta
import json
from application.services.scheduler_tasks_common import logger  # noqa: F401

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
        # 2026-09-05 修复：get_market_summary() 方法不存在（MarketDataService 从未实现，
        # AttributeError 被下方 except 吞掉 → "市场概况"节自始永远缺失），改走真实存在的
        # MarketDataService.get_market_overview()（全市场涨跌家数统计）。
        try:
            from application.services.market_data_service import MarketDataService
            market_service = MarketDataService()
            market_summary = market_service.get_market_overview()
            if market_summary.get("success") and market_summary.get("data"):
                report_content["sections"].append({
                    "title": "市场概况",
                    "data": market_summary["data"]
                })
            else:
                logger.warning(f"Failed to get market summary: {market_summary.get('error')}")
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
            from infrastructure.services.service_factory import ServiceFactory
            from domain.ports import IStrategyRepository
            repo = ServiceFactory.resolve(IStrategyRepository)
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


