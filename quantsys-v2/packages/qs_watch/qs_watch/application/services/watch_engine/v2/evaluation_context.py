"""V2 条件求值上下文：价格历史与按需外部数据。"""
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional

from qs_trading.domain.trading.services.market_session_policy import MarketSessionPolicy

from ..rules.conditions import EvalContext


def _conditions(value) -> Iterable[dict]:
    if isinstance(value, dict):
        value = [value]
    for cond in value or []:
        if not isinstance(cond, dict):
            continue
        yield cond
        if cond.get('type') == 'combined':
            yield from _conditions((cond.get('params') or {}).get('conditions'))


class EvaluationContextFactory:
    def __init__(self, avg_volume_evaluator=None, kline_closes_provider=None,
                 fund_flow_provider=None, history_minutes: int = 30):
        self._avg_volume = avg_volume_evaluator
        self._kline_closes = kline_closes_provider
        self._fund_flow = fund_flow_provider
        self._history_minutes = int(history_minutes)
        self._history: Dict[str, list] = {}
        self._lock = threading.RLock()

    def prepare(self, quotes, now: datetime) -> None:
        """每轮每个 symbol 追加一个价格点，供 velocity 与 staged hold 使用。"""
        with self._lock:
            for symbol, quote in quotes.items():
                if quote is None:
                    continue
                try:
                    price = float(quote.price)
                except (TypeError, ValueError):
                    continue
                points = self._history.setdefault(symbol, [])
                if points and points[-1][0] == now:
                    points[-1] = (now, price)
                else:
                    points.append((now, price))
                cutoff = now - timedelta(minutes=self._history_minutes)
                self._history[symbol] = [(ts, p) for ts, p in points if ts >= cutoff]

    def build(self, rule, quote, now: datetime) -> EvalContext:
        conditions = list(_conditions(getattr(rule, 'conditions', None)))
        needs_volume = any(
            cond.get('type') == 'volume_surge'
            or (cond.get('type') == 'staged_break'
                and ((cond.get('params') or {}).get('confirm') or {}).get('kind') == 'volume')
            for cond in conditions)
        needs_closes = any(cond.get('type') in ('ma_break', 'rsi') for cond in conditions)
        needs_fund_flow = any(cond.get('type') == 'fund_flow' for cond in conditions)
        symbol = getattr(rule, 'symbol', None)
        with self._lock:
            history = tuple(self._history.get(symbol, ()))

        try:
            cost = float(getattr(rule, 'cost_price', None))
        except (TypeError, ValueError):
            cost = None
        avg_volume = None
        if needs_volume and self._avg_volume is not None:
            avg_volume = self._avg_volume.get_avg_volume(symbol, now)
        closes = ()
        if needs_closes and self._kline_closes is not None:
            try:
                closes = tuple(self._kline_closes(symbol) or ())
            except Exception:  # noqa: BLE001 - 数据缺失由 DSL 标记 degraded
                closes = ()
        fund_flow = None
        if needs_fund_flow and self._fund_flow is not None:
            try:
                fund_flow = self._fund_flow(symbol)
            except Exception:  # noqa: BLE001
                fund_flow = None
        return EvalContext(
            cost_price=cost,
            price_history=history,
            avg_volume_20d=avg_volume,
            elapsed_fraction=MarketSessionPolicy.session_progress(
                now.time(), is_trading_day=True),
            daily_closes=closes,
            fund_flow=fund_flow,
        )

    def shutdown(self) -> None:
        if self._avg_volume is not None:
            self._avg_volume.shutdown()
