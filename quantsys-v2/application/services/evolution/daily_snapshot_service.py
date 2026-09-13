"""每日净值快照服务（全账户稠密化地基，行为进化 Phase 1 前置）

背景：simulation_equity_snapshot 此前只在交易日由 account_trading_service 写入，
且 daily_return 恒为默认 0——非交易日无快照、交易日收益失真，
双侧捕获适应度（evolution_fitness）因此缺输入。

本服务提供：
1. snapshot_all_accounts：收盘后逐账户按当日收盘价重估持仓写快照（每日调度）
2. backfill_account：按交易回放 + 历史收盘价重估，补历史快照（一次性运维）

近似声明（回填）：忽略日内择时，交易按当日收盘生效；费用取 total_cost/total_revenue
（含佣金印花税），缺省退化为 amount；个股当日缺K线用最近可得收盘价。
"""
from domain.ports import IKlineRepository, ISimulationRepository
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Mapping, Optional

import structlog

logger = structlog.get_logger(__name__)

PriceMap = Mapping[str, Mapping[str, float]]  # {symbol: {date_str: close}}
PriceProvider = Callable[[List[str], date, date], PriceMap]


class DailySnapshotService:
    def __init__(
        self,
        sim_repo=None,
        price_provider: Optional[PriceProvider] = None,
    ):
        if sim_repo is None:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            sim_repo = EnhancedServiceFactory.resolve(ISimulationRepository)
        self.sim_repo = sim_repo
        self._price_provider = price_provider or self._default_price_provider

    @staticmethod
    def _default_price_provider(symbols: List[str], start: date, end: date) -> PriceMap:
        """默认价格源：本地 kline 库（不走网络）。返回 {symbol: {date_str: close}}"""
        from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
        repo = EnhancedServiceFactory.resolve(IKlineRepository)
        result: Dict[str, Dict[str, float]] = {}
        batch = repo.batch_get_kline(symbols, start.isoformat(), end.isoformat())
        for symbol, df in batch.items():
            if df is None or df.is_empty():
                continue
            rows = df.select(['trade_date', 'close']).to_dicts()
            result[symbol] = {str(r['trade_date'])[:10]: float(r['close']) for r in rows}
        return result

    # ------------------------------------------------------------------
    # 每日快照（调度入口）
    # ------------------------------------------------------------------

    def snapshot_all_accounts(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        target_date = target_date or date.today()
        written = skipped = 0
        accounts = self.sim_repo.list_accounts(status='active')
        all_symbols = sorted({
            p.symbol for acct in accounts
            for p in self.sim_repo.get_all_positions(acct.account_name)
        })
        # 取 10 天价格缓冲，停牌/缺口时用最近可得收盘价
        prices = dict(self._price_provider(
            all_symbols, target_date - timedelta(days=10), target_date)) if all_symbols else {}
        for acct in accounts:
            try:
                self._snapshot_one(acct, target_date, prices)
                written += 1
            except Exception as e:
                logger.error('daily snapshot failed', account=acct.account_name, error=str(e))
                skipped += 1
        logger.info('daily snapshots written', date=str(target_date),
                    written=written, skipped=skipped)
        return {'written': written, 'skipped': skipped, 'date': str(target_date)}

    def _snapshot_one(self, acct, target_date: date, prices: PriceMap) -> None:
        positions = self.sim_repo.get_all_positions(acct.account_name)
        position_value = sum(
            p.shares_total * self._close_at(prices.get(p.symbol, {}), target_date)
            for p in positions
        )
        cash = float(acct.cash_available or 0) + float(acct.cash_frozen or 0)
        total = cash + position_value
        initial = float(acct.initial_capital or 0)
        cumulative = (total / initial - 1) if initial > 0 else 0.0
        peak = max(float(acct.peak_value or 0), total)
        drawdown = (total / peak - 1) if peak > 0 else 0.0
        self.sim_repo.upsert_equity_snapshot(
            account_name=acct.account_name,
            cash=cash,
            position_value=position_value,
            total_value=total,
            # daily_return 不再自算：由 repo 按上一交易日有效快照统一计算（含残缺行跳过、
            # 成立资金剔除、|r|>15% 告警）；无基准写 NULL 而非 0.0（2026-09-11, w-8f2c4cc5）
            cumulative_return=cumulative,
            drawdown=drawdown,
            snapshot_date=target_date,
        )

    @staticmethod
    def _close_at(symbol_prices: Mapping[str, float], target: date, default: float = 0.0) -> float:
        """target 当日收盘价；缺则用之前最近可得收盘价"""
        if not symbol_prices:
            return default
        key = target.isoformat()
        if key in symbol_prices:
            return symbol_prices[key]
        earlier = [d for d in symbol_prices if d < key]
        return symbol_prices[max(earlier)] if earlier else default

    # ------------------------------------------------------------------
    # 历史回填（一次性运维）
    # ------------------------------------------------------------------

    def backfill_account(
        self,
        account_name: str,
        start: date,
        end: date,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """按交易回放重估 [start, end] 每个交易日的净值快照（近似，见模块 docstring）。

        默认不覆盖已有快照日（生产真实快照优先于回放近似值）。
        """
        account = self.sim_repo.get_account(account_name)
        if account is None:
            return {'written': 0, 'error': f'account {account_name} not found'}
        trades = sorted(
            self.sim_repo.get_trades_by_account(account_name),
            key=lambda t: (t.trade_date, t.id or 0),
        )
        trades = [t for t in trades if t.trade_date <= end]
        if not trades:
            return {'written': 0, 'reason': 'no_trades'}

        symbols = sorted({t.symbol for t in trades})
        prices = dict(self._price_provider(symbols, start, end))
        calendar = sorted({d for sp in prices.values() for d in sp if start.isoformat() <= d <= end.isoformat()})
        existing = {
            s.snapshot_date
            for s in self.sim_repo.get_equity_snapshots(account_name, limit=400)
            if start <= s.snapshot_date <= end
        }

        cash = float(account.initial_capital or 0)
        holdings: Dict[str, int] = {}
        prev_total: Optional[float] = None
        written = 0
        initial = float(account.initial_capital or 0)
        peak = initial
        for day_str in calendar:
            day = date.fromisoformat(day_str)
            for t in trades:
                if t.trade_date != day:
                    continue
                if t.action == 'BUY':  # action 大写契约（08-13 统一）
                    cash -= float(t.total_cost or t.amount or 0)
                    holdings[t.symbol] = holdings.get(t.symbol, 0) + t.shares
                elif t.action == 'SELL':
                    cash += float(t.total_revenue or t.amount or 0)
                    holdings[t.symbol] = holdings.get(t.symbol, 0) - t.shares
            position_value = sum(
                sh * self._close_at(prices.get(sym, {}), day,
                                    default=self._last_known(prices.get(sym, {}), day))
                for sym, sh in holdings.items() if sh > 0
            )
            total = cash + position_value
            peak = max(peak, total)
            if overwrite or day not in existing:
                self.sim_repo.upsert_equity_snapshot(
                    account_name=account_name,
                    cash=cash,
                    position_value=position_value,
                    total_value=total,
                    # 同上：daily_return 由 repo 统一计算（此处回放序列的基准=DB 中上一交易日快照）
                    cumulative_return=(total / initial - 1) if initial > 0 else 0.0,
                    drawdown=(total / peak - 1) if peak > 0 else 0.0,
                    snapshot_date=day,
                )
                written += 1
        logger.info('backfill done', account=account_name, written=written,
                    start=str(start), end=str(end))
        return {'written': written}

    @staticmethod
    def _last_known(symbol_prices: Mapping[str, float], day: date) -> float:
        earlier = [d for d in symbol_prices if d <= day.isoformat()]
        return symbol_prices[max(earlier)] if earlier else 0.0


# --------------------------------------------------------------------------- #
# 每日净值稠密化定时任务（2026-09-13 w-a9ec14d7 从 scripts/snapshot_daily.py 上迁）
#
# 为什么需要：quant.simulation_equity_snapshot 只在账户发生交易/估值活动时写入；
# DailySnapshotService.snapshot_all_accounts 的 docstring 自称「收盘后逐账户……（每日调度）」，
# 但全仓检索无任何生产调用方 → **无活动的交易日就没有快照**。
# 实测 agent_virtual：窗口内 59 个交易日只有 55 条快照（缺 08-10/08-24/08-26/08-27/08-31），
# 而 risk_metrics 的波动率/alpha/IR 由「相邻快照差分的日收益」算出，
# 缺口会让跨日涨跌被当成单日收益 → 风险指标失真。
#
# 为什么是 job 而不是脚本：用户 2026-09-13 裁定「脚本不能写进 v2 项目，脚本只能测试用」。
# 本能力此前只有一个 scripts/ 入口 + 一个 tools/ CLI，都不构成**生产调度**；
# 上迁为 JobRegistry 任务后由 v2 调度器在工作日收盘后驱动，不再依赖任何脚本。
# --------------------------------------------------------------------------- #

# 参考标的：流动性好、几乎每个交易日都有 K 线（用于"今天到底有没有收盘数据"的判定）
_SNAPSHOT_REF_SYMBOL = "600519"


class EquitySnapshotJob:
    """每日净值快照稠密化（工作日 15:35，收盘后）

    关键防护（原脚本的立项理由，必须保留）：目标日若尚无 K 线（未收盘或非交易日），
    snapshot_all_accounts 会用「最近可得收盘价」估值 → 写出「旧价标新日」的**假快照**，
    比缺快照更糟（会污染日收益序列）。故此处显式跳过：宁可当日不写，也不写错。
    """

    def __init__(self, service=None):
        self._name = "equity_snapshot_daily"
        self._service = service

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "每日净值快照稠密化：收盘后逐账户重估写快照（无 K 线则跳过，不写假快照）"

    @property
    def timeout_seconds(self) -> int:
        return 600

    def _has_bar(self, target: date) -> bool:
        from domain.ports import IKlineRepository
        from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
        try:
            klines = EnhancedServiceFactory.resolve(IKlineRepository).get_daily_klines(
                symbol=_SNAPSHOT_REF_SYMBOL,
                start_date=target.isoformat(), end_date=target.isoformat())
        finally:
            # 只读查询也必须归还会话（2026-09-13 18:26，w-32314d00，看板事件 a6780ec3）：
            # kline_repository 的读走 self.session，autobegin 的事务不结束就把连接挂在
            # idle in transaction（337s 后被 DB 强杀 → session_leak_detected）。
            # 按会话来源聚合 40 次泄漏：本路径是**其余来源修完后唯一剩下的**
            #（其余 6 条末次出现均停在各自修前）。
            try:
                from infrastructure.persistence.orm import close_session
                close_session()
            except Exception:  # noqa: BLE001 - 归还会话失败不应影响 has_bar 判定
                pass
        if klines is None:
            return False
        if hasattr(klines, "is_empty"):
            return not klines.is_empty()
        try:
            return len(klines) > 0
        except TypeError:
            return True

    def run(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """同步执行（供 job 与测试调用）。返回 {skipped_reason|result}。"""
        from infrastructure.services.service_registry import register_all_services
        register_all_services()
        target = target_date or date.today()
        if not self._has_bar(target):
            return {"skipped": True, "target_date": target.isoformat(),
                    "reason": "no kline for %s（非交易日或尚未收盘），跳过以免写入旧价标新日的假快照"
                              % target.isoformat()}
        svc = self._service or DailySnapshotService()
        return {"skipped": False, "target_date": target.isoformat(),
                "result": svc.snapshot_all_accounts(target_date=target_date)}

    async def execute(self, params=None):
        import asyncio
        from application.jobs.job_protocol import JobResult, result_from_dict
        try:
            out = await asyncio.to_thread(self.run)
        except Exception as exc:  # noqa: BLE001 —— 失败必须显式（调度器据此标红）
            logger.exception("equity_snapshot_daily failed")
            return JobResult.fail(self._name, "%s: %s" % (type(exc).__name__, exc))
        if out.get("skipped"):
            return result_from_dict(self._name, "equity snapshot skipped: " + out["reason"],
                                    {"skipped": True, "target_date": out["target_date"]})
        return result_from_dict(self._name, "equity snapshot done: %s" % out.get("result"),
                                {"skipped": False, "target_date": out["target_date"],
                                 "result": out.get("result")})


def build_equity_snapshot_jobs():
    """构造净值快照任务（组合根在 main.py 注册进 JobRegistry）"""
    return [EquitySnapshotJob()]
