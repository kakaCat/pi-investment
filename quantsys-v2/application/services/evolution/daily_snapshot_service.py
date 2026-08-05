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
            from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
            sim_repo = SimulationORMRepository()
        self.sim_repo = sim_repo
        self._price_provider = price_provider or self._default_price_provider

    @staticmethod
    def _default_price_provider(symbols: List[str], start: date, end: date) -> PriceMap:
        """默认价格源：本地 kline 库（不走网络）。返回 {symbol: {date_str: close}}"""
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        repo = KlineORMRepository()
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
        prev = self.sim_repo.get_equity_snapshots(acct.account_name, limit=1)
        prev = [s for s in prev if s.snapshot_date < target_date]
        daily_return = (total / float(prev[0].total_value) - 1) if prev and float(
            prev[0].total_value or 0) > 0 else 0.0
        initial = float(acct.initial_capital or 0)
        cumulative = (total / initial - 1) if initial > 0 else 0.0
        peak = max(float(acct.peak_value or 0), total)
        drawdown = (total / peak - 1) if peak > 0 else 0.0
        self.sim_repo.upsert_equity_snapshot(
            account_name=acct.account_name,
            cash=cash,
            position_value=position_value,
            total_value=total,
            daily_return=daily_return,
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
                if t.action == 'buy':
                    cash -= float(t.total_cost or t.amount or 0)
                    holdings[t.symbol] = holdings.get(t.symbol, 0) + t.shares
                elif t.action == 'sell':
                    cash += float(t.total_revenue or t.amount or 0)
                    holdings[t.symbol] = holdings.get(t.symbol, 0) - t.shares
            position_value = sum(
                sh * self._close_at(prices.get(sym, {}), day,
                                    default=self._last_known(prices.get(sym, {}), day))
                for sym, sh in holdings.items() if sh > 0
            )
            total = cash + position_value
            daily_return = (total / prev_total - 1) if prev_total else 0.0
            peak = max(peak, total)
            if overwrite or day not in existing:
                self.sim_repo.upsert_equity_snapshot(
                    account_name=account_name,
                    cash=cash,
                    position_value=position_value,
                    total_value=total,
                    daily_return=daily_return,
                    cumulative_return=(total / initial - 1) if initial > 0 else 0.0,
                    drawdown=(total / peak - 1) if peak > 0 else 0.0,
                    snapshot_date=day,
                )
                written += 1
            prev_total = total
        logger.info('backfill done', account=account_name, written=written,
                    start=str(start), end=str(end))
        return {'written': written}

    @staticmethod
    def _last_known(symbol_prices: Mapping[str, float], day: date) -> float:
        earlier = [d for d in symbol_prices if d <= day.isoformat()]
        return symbol_prices[max(earlier)] if earlier else 0.0
