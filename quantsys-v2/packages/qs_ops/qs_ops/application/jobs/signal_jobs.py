"""
信号类定时任务

包含：signal_generate, signal_execution_daily, opportunity_scan_daily, fund_flow_update
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


class OpportunityScanDailyJob(Job):
    """每日综合评分机会扫描，并把高分买入机会转成盯盘规则。"""

    def __init__(self, scoring_service=None, stock_pool_service=None,
                 watchlist_reader=None, rule_service=None, trading_day_guard=None,
                 notification_sender=None):
        self._scoring_service = scoring_service
        self._stock_pool_service = stock_pool_service
        self._watchlist_reader = watchlist_reader
        self._rule_service = rule_service
        self._trading_day_guard = trading_day_guard
        self._notification_sender = notification_sender

    @property
    def name(self) -> str:
        return "opportunity_scan_daily"

    @property
    def description(self) -> str:
        return "每交易日扫描自选股与热门池，高分买入机会生成 V2 盯盘规则"

    @property
    def timeout_seconds(self) -> int:
        return 1800

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        import asyncio

        try:
            return await asyncio.to_thread(self._run, params or {})
        except Exception as e:
            logger.exception("opportunity_scan_daily failed", error=str(e))
            return JobResult.fail(self.name, str(e))

    def _run(self, params: Dict[str, Any]) -> JobResult:
        guard = self._trading_day_guard
        if guard is None:
            from qs_ops.application.services.trading_day_guard import TradingDayGuard
            guard = TradingDayGuard
        if not guard.is_trading_day():
            return JobResult.ok(
                self.name, message="非交易日，跳过机会扫描",
                skipped="non_trading_day", scanned=0, candidates=0,
            )

        scoring_service = self._scoring_service
        stock_pool_service = self._stock_pool_service
        if scoring_service is None or stock_pool_service is None:
            from infrastructure.services.service_factory import ServiceFactory
            scoring_service = scoring_service or ServiceFactory.get_scoring_service()
            stock_pool_service = stock_pool_service or ServiceFactory.get_stock_pool_service()

        symbols_param = params.get("symbols") or []
        if symbols_param:
            symbols = (list(symbols_param) if isinstance(symbols_param, list)
                       else [symbols_param])
        else:
            reader = self._watchlist_reader
            if reader is None:
                from adapters.shared import _read_watchlist
                reader = _read_watchlist
            try:
                watchlist = reader() or {}
                watchlist_symbols = [item["symbol"] for item in watchlist.get("items", [])
                                     if item.get("symbol")]
            except Exception as e:
                logger.warning("opportunity_scan_daily: 自选股读取失败，仅扫描热门池", error=str(e))
                watchlist_symbols = []
            symbols = stock_pool_service.get_scan_universe(watchlist_symbols)
        symbols = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        if not symbols:
            return JobResult.fail(self.name, "机会扫描宇宙为空，请检查股票池数据源")

        no_cache = bool(params.get("no_cache", False))
        opportunities = scoring_service.score_stocks(
            symbols=symbols,
            filters={"technical": [], "fundamental": []},
            weights=None,
            no_cache=no_cache,
        ) or []
        diagnostics = dict(getattr(scoring_service, "last_diagnostics", None) or {})
        scored = int(diagnostics.get("scored", len(opportunities)))
        if scored == 0:
            return JobResult(
                success=False,
                action=self.name,
                message="股票池非空但没有股票评分成功",
                details={"scanned": len(symbols), "scored": 0,
                         "diagnostics": diagnostics},
                error="all_scoring_failed",
            )

        min_score = float(params.get("min_score", 80))
        max_risk_level = str(params.get("max_risk_level", "high"))
        top_n = max(1, min(int(params.get("top_n", 10)), 100))
        risk_levels = {"low": 1, "medium": 2, "high": 3}
        max_risk = risk_levels.get(max_risk_level, 3)
        candidates = [
            opp for opp in opportunities
            if risk_levels.get(opp.get("risk_level"), 3) <= max_risk
            and float(opp.get("score", 0)) >= min_score
        ]
        candidates.sort(key=lambda opp: float(opp.get("score", 0)), reverse=True)
        candidates = candidates[:top_n]
        for opp in candidates:
            opp["scoring_method"] = "ddd_industry_neutral_smooth"

        auto_create = bool(params.get("auto_create_rules", True))
        rule_results = []
        if auto_create and candidates:
            rule_service = self._rule_service
            if rule_service is None:
                from qs_watch.application.services.opportunity_to_watch_rule_service import (
                    OpportunityToWatchRuleService,
                )
                rule_service = OpportunityToWatchRuleService()
            watch_account = str(params.get('account_name') or params.get('watch_account') or '').strip() or None
            rule_results = rule_service.auto_create_rules(candidates, account=watch_account)

        created = sum(result.get("action") == "created" for result in rule_results)
        skipped = sum(result.get("action") == "skipped" for result in rule_results)
        failed = sum(result.get("action") == "failed" for result in rule_results)
        high_score_candidates = [
            opp for opp in candidates if float(opp.get("score", 0)) >= 80
        ]
        notify = bool(params.get("notify", True))
        notified = False
        notification_error = None
        if notify and high_score_candidates:
            from qs_notification.infrastructure.formatters.opportunity_scan_formatter import (
                render_opportunity_scan_summary,
            )
            title, body = render_opportunity_scan_summary(
                high_score_candidates,
                rule_results,
                scanned=len(symbols),
                scored=scored,
                trade_date=params.get("trade_date"),
                auto_create_rules=auto_create,
            )
            sender = self._notification_sender
            if sender is None:
                from qs_notification.application import get_notification_facade
                facade = get_notification_facade()

                def sender(title, body):
                    return facade.send_watch_receipt(
                        title, body, os_channel="watch_symbol")

            try:
                notified = bool(sender(title, body))
                if not notified:
                    notification_error = "sender_returned_false"
            except Exception as e:
                notification_error = str(e)
                logger.error("opportunity_scan_daily: 盯盘群通知失败", error=str(e))

        details = {
            "scanned": len(symbols),
            "scored": scored,
            "candidates": len(candidates),
            "created": created,
            "skipped": skipped,
            "failed": failed,
            "auto_create_rules": auto_create,
            "rule_results": rule_results,
            "notified": notified,
            "notification_error": notification_error,
            "diagnostics": diagnostics,
        }
        message = (f"机会扫描完成：{len(symbols)} 只，候选 {len(candidates)} 个，"
                   f"新建规则 {created} 条，跳过 {skipped} 条，失败 {failed} 条")
        errors = []
        if failed:
            errors.append(f"{failed} 条盯盘规则创建失败")
        if notification_error:
            errors.append(f"盯盘群通知失败：{notification_error}")
        if errors:
            return JobResult(
                success=False, action=self.name, message=message,
                details=details, error="；".join(errors),
            )
        return JobResult.ok(self.name, message=message, **details)


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
            return svc.update_performance(lookback_days=params.get('lookback_days'))

        try:
            result = await asyncio.to_thread(_run)
            updated = result.get('updated', 0)
            if not result.get('complete', True):
                return JobResult(
                    success=False,
                    action=self.name,
                    error='到期信号仍存在缺 K 线或非法信号，未完整回填',
                    details={'result': result},
                )
            return JobResult.ok(self.name, message=f"信号回填完成：更新 {updated} 条", details=result)
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有内置调度的信号类任务。
# SignalPerfBackfillJob 保留为手工执行实现，但不进入内置注册表：
# 生产唯一调度所有者是 Agent OS 的同名 webhook（signal_tracking.py），
# 双注册曾导致每日 15:45 同一回填并发执行两次。
SIGNAL_JOBS = [
    SignalGenerateJob(),
    SignalExecutionDailyJob(),
    OpportunityScanDailyJob(),
    FundFlowUpdateJob(),
]
