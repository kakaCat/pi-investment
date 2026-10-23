"""
信号类定时任务

包含：signal_generate, signal_execution_daily, fund_flow_update
"""
import logging
from typing import Any, Dict

from qs_ops.application.jobs.job_protocol import Job, JobResult

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
            from qs_sourcing.adapters.outbound.repositories.signal_repository import SignalORMRepository
            from adapters.outbound.repositories.strategy_repository import StrategyORMRepository
            from qs_sourcing.application.services.pool_signal_scanner import PoolSignalScanner
            from datetime import date as date_type

            strategy_ids = params.get("strategy_ids") or [179, 178, 163, 193]
            signal_date = params.get("date", date_type.today().isoformat())
            lookback_days = params.get("lookback_days", 60)

            repo = HeatmapRepository()
            universe = repo.get_pool_members_now() | repo.get_current_holding_symbols()

            # 2026-10-20：扫描宇宙并入独立量化闭环账户（rotation_main）的持仓——
            # 原宇宙只含池成员 ∪ 实盘组合持仓，rotation_main 买入的标的永远扫不出
            # SELL 信号，持仓只能靠止损线退出（退出路径盲区）
            try:
                from adapters.outbound.repositories import SimulationORMRepository
                sim_repo = SimulationORMRepository()
                universe |= {
                    p.symbol for p in sim_repo.get_all_positions('rotation_main')
                    if (p.shares_total or 0) > 0
                }
            except Exception as e:
                logger.warning(f"signal_generate: 并入 rotation_main 持仓失败: {e}")

            symbols = sorted({s.split('.')[0] for s in universe})

            if not symbols:
                return JobResult.ok(
                    self.name,
                    message="宇宙为空（无非空池成员且无持仓）",
                    details={
                        "universe_size": 0, "signals_found": 0,
                        "signals_saved": 0, "duplicates": 0,
                        "sell_filtered_unheld": 0, "strategy_errors": [],
                    }
                )

            names = {s: m['name'] for s, m in repo.get_stocks_meta(symbols).items()}
            scanner = PoolSignalScanner(KlineORMRepository(), StrategyORMRepository())
            sig_repo = SignalORMRepository()

            # 2026-10-20 信号降噪：SELL 信号只对有持仓的标的落库。
            # 实测 2026-10-19：60 条信号里 48 条 SELL 因「无持仓」被风控拒
            # （池子里不持有的票也出卖出信号），纯噪声且淹没执行日志。
            # 持仓口径 = 实盘组合 ∪ 全部 active 模拟账户。
            held_symbols = set(repo.get_current_holding_symbols())
            _holdings_query_ok = True
            try:
                from adapters.outbound.repositories import SimulationORMRepository
                _sim = SimulationORMRepository()
                for acct in _sim.list_accounts(status='active'):
                    for p in _sim.get_all_positions(acct.account_name):
                        if (p.shares_total or 0) > 0:
                            held_symbols.add(p.symbol)
            except Exception as e:
                logger.warning(f"signal_generate: 汇总模拟持仓失败（SELL 不降噪）: {e}")
                _holdings_query_ok = False  # 查询失败时不降噪，保持原行为
            held_symbols = {s.split('.')[0] for s in held_symbols}

            found = saved = duplicates = sell_filtered = 0
            strategy_errors = []
            for sid in strategy_ids:
                try:
                    result = scanner.scan_pool_signals(
                        symbols=symbols, strategy_id=sid, lookback_days=lookback_days)
                    for sig in result.get('buy_signals', []) + result.get('sell_signals', []):
                        found += 1
                        # SELL 降噪：无任何账户持有 → 不落库
                        # （注意与"查询失败"区分：真的零持仓时应滤掉全部 SELL）
                        if (sig['signal'].upper() == 'SELL' and _holdings_query_ok
                                and sig['symbol'].split('.')[0] not in held_symbols):
                            sell_filtered += 1
                            continue
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

            details = {
                "universe_size": len(symbols),
                "signals_found": found,
                "signals_saved": saved,
                "duplicates": duplicates,
                "sell_filtered_unheld": sell_filtered,
                "strategy_errors": strategy_errors,
            }
            # 假成功防护（2026-10-23 从被委托的 SchedulerService 实现迁回）：
            # 宇宙非空但**所有策略都失败且零落库**时必须显式 failed，否则漏报
            if strategy_errors and len(strategy_errors) == len(strategy_ids) and saved == 0:
                return JobResult(
                    success=False,
                    action=self.name,
                    message=f"信号生成失败: 全部 {len(strategy_ids)} 个策略报错且零落库",
                    details={"details": details},
                    error='; '.join(strategy_errors),
                )
            return JobResult.ok(
                self.name,
                message=f"信号生成完成: {saved} saved, {duplicates} duplicates, {sell_filtered} unheld-sell filtered",
                details=details,
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
            # 242 修复（2026-09-02）：rebind 到 handle_signal_execution_daily。
            # 2026-10-20 重绑（用户裁定：量化虚拟交易独立于 Agent 主链路）：
            # 该 handler 现执行真实闭环——收集当日 pending 信号 → 风控 →
            # PaperTradingEngine(rotation_main) 成交 → 状态回写。
            from qs_ops.application.services.scheduler_tasks_signals import handle_signal_execution_daily
            result = handle_signal_execution_daily(params)
            return JobResult.ok(
                self.name,
                message="信号执行（独立量化闭环）完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


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


class SignalPerfBackfillJob(Job):
    """信号胜率回填每日任务（M3-3，ADR-002 Phase 1 补齐）

    背景：原由 Agent OS 的 signal-perf-backfill-daily 任务经
    signal-perf-backfill.sh 脚本 curl 直连后端（A-2 临时办法），
    该任务在 DSH 原生调度迁移中被禁用，回填职责悬空。归位 v2。
    """

    @property
    def name(self) -> str:
        return "signal_perf_backfill_daily"

    @property
    def description(self) -> str:
        return "回填信号 5/10/20 日表现（signal_track update，盘后 15:45）"

    @property
    def timeout_seconds(self) -> int:
        return 1800

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        import asyncio

        def _run() -> Dict[str, Any]:
            from qs_sourcing.application.services.signal_tracking_service import SignalTrackingService
            # 不传连接：SignalTrackingRepository 内部自建 psycopg2 裸连接
            svc = SignalTrackingService()
            return svc.update_performance(lookback_days=params.get('lookback_days', 30))

        try:
            result = await asyncio.to_thread(_run)
            updated = result.get('updated', 0)
            return JobResult.ok(self.name, message=f"信号回填完成：更新 {updated} 条", details=result)
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有信号类任务
SIGNAL_JOBS = [
    SignalGenerateJob(),
    SignalExecutionDailyJob(),
    FundFlowUpdateJob(),
    SignalPerfBackfillJob(),
]
