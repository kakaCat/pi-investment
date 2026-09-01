"""
信号类定时任务

包含：signal_generate, signal_execution_daily, signal_monitor_realtime,
      fund_flow_update
"""
import logging
from typing import Any, Dict

from application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


class SignalGenerateJob(Job):
    """信号生成任务"""

    @property
    def name(self) -> str:
        return "signal_generate"

    @property
    def description(self) -> str:
        return "扫描宇宙（非空池成员 ∪ 当前持仓）× 活跃策略，生成买卖信号"

    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from adapters.outbound.repositories.heatmap_repository import HeatmapRepository
            from adapters.outbound.repositories.kline_repository import KlineORMRepository
            from adapters.outbound.repositories.signal_repository import SignalORMRepository
            from adapters.outbound.repositories.strategy_repository import StrategyORMRepository
            from application.services.pool_signal_scanner import PoolSignalScanner
            from datetime import date as date_type

            strategy_ids = params.get("strategy_ids") or [179, 178, 163, 193]
            signal_date = params.get("date", date_type.today().isoformat())
            lookback_days = params.get("lookback_days", 60)

            repo = HeatmapRepository()
            universe = repo.get_pool_members_now() | repo.get_current_holding_symbols()
            symbols = sorted({s.split('.')[0] for s in universe})

            if not symbols:
                return JobResult.ok(
                    self.name,
                    message="宇宙为空（无非空池成员且无持仓）",
                    details={"universe_size": 0, "signals_found": 0}
                )

            names = {s: m['name'] for s, m in repo.get_stocks_meta(symbols).items()}
            scanner = PoolSignalScanner(KlineORMRepository(), StrategyORMRepository())
            sig_repo = SignalORMRepository()

            found = saved = duplicates = 0
            strategy_errors = []
            for sid in strategy_ids:
                try:
                    result = scanner.scan_pool_signals(
                        symbols=symbols, strategy_id=sid, lookback_days=lookback_days)
                    for sig in result.get('buy_signals', []) + result.get('sell_signals', []):
                        found += 1
                        signal_id = sig_repo.create_signal({
                            'signal_date': signal_date,
                            'symbol': sig['symbol'],
                            'name': names.get(sig['symbol'], ''),
                            'action': sig['signal'].upper(),
                            'strategy_id': str(sid),
                            'price': sig.get('current_price'),
                            'reason': '; '.join(sig.get('reasons', [])),
                            'indicators': sig.get('indicators'),
                            'status': 'pending',
                        })
                        if signal_id > 0:
                            saved += 1
                        else:
                            duplicates += 1
                except Exception as e:
                    logger.warning(f"signal_generate: strategy {sid} failed: {e}")
                    strategy_errors.append(f"{sid}: {e}")

            return JobResult.ok(
                self.name,
                message=f"信号生成完成: {saved} saved, {duplicates} duplicates",
                details={
                    "universe_size": len(symbols),
                    "signals_found": found,
                    "signals_saved": saved,
                    "duplicates": duplicates,
                    "strategy_errors": strategy_errors,
                }
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class SignalExecutionDailyJob(Job):
    """每日信号执行任务"""

    @property
    def name(self) -> str:
        return "signal_execution_daily"

    @property
    def description(self) -> str:
        return "执行信号交易（策略运行 → 信号收集 → 风险检查 → 下单）"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 1小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.scheduler.signal_execution_job import execute_daily_signals_job
            result = execute_daily_signals_job()
            return JobResult.ok(
                self.name,
                message="信号执行完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class SignalMonitorRealtimeJob(Job):
    """实时信号监控任务"""

    @property
    def name(self) -> str:
        return "signal_monitor_realtime"

    @property
    def description(self) -> str:
        return "盘中实时监控信号"

    @property
    def timeout_seconds(self) -> int:
        return 300  # 5分钟

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        # TODO: 实现实时监控逻辑
        return JobResult.ok(
            self.name,
            message="实时监控完成（待实现）",
            details={"signals_checked": 0, "active_signals": 0}
        )


class FundFlowUpdateJob(Job):
    """全市场资金流向每日采集"""

    @property
    def name(self) -> str:
        return "fund_flow_update"

    @property
    def description(self) -> str:
        return "采集全市场资金流向数据"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 1小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.fund_flow_update_job import execute
            result = execute(**params)
            return JobResult.ok(
                self.name,
                message="资金流向更新完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有信号类任务
SIGNAL_JOBS = [
    SignalGenerateJob(),
    SignalExecutionDailyJob(),
    SignalMonitorRealtimeJob(),
    FundFlowUpdateJob(),
]
