"""
V13 strategy use case — application-level orchestration.

This module is the anti-corruption layer: the ONLY place where the pure
domain algorithm (:class:`XGBoostStrategy`) is wired to infrastructure
(trader, Feishu notifier, position repository, audit log). It contains NO
business logic — all decision rules (signal calculation, stop-loss, order
sizing) live in the domain strategy.

Daily workflow (:meth:`XGBoostStrategyUseCase.execute`):

    1. Get (or lazily create) the ``XGBoostStrategy`` bound to the config.
    2. Fetch current positions from the DB via the injected repository.
    3. Run ``strategy.execute_daily_check(date, has_positions, account_name)``.
    4. Execute any generated orders via the injected trader.
    5. Send Feishu notifications (rebalance details + stop-loss alerts).
    6. Persist the decision to the ``audit_log`` table (best effort).
    7. Return the result dict.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from domain.strategies.value_objects import Order, OrderSide, StrategyConfig
from domain.strategies.xgboost_strategy import XGBoostStrategy
from utils.feishu_notifier import create_notifier_from_config

from application.strategies.v13_config import V13_CONFIG

__all__ = ["XGBoostStrategyUseCase", "V13StrategyUseCase"]

logger = logging.getLogger(__name__)


class XGBoostStrategyUseCase:
    """Orchestration for XGBoost-based strategies (V13/V14 share the flow).

    Subclasses set :attr:`CONFIG` to their immutable ``StrategyConfig``.
    All infrastructure dependencies are injected, keeping the use case
    testable and free of construction-time side effects.
    """

    #: Overridden by subclasses (V13_CONFIG / V14_CONFIG).
    CONFIG: StrategyConfig

    def __init__(
        self,
        trader: Any,
        feishu_notifier: Any,
        position_repo: Any,
        account_name: str,
        factor_provider: Optional[Callable[[str], Any]] = None,
        price_provider: Optional[Callable[[str, str], Optional[float]]] = None,
    ) -> None:
        """
        Args:
            trader: Execution adapter (duck-typed: ``execute_order(order)``
                or ``buy/sell(symbol, quantity, price)``).
            feishu_notifier: ``FeishuNotifier`` instance or None. Build one
                from app config via :func:`create_notifier_from_config`.
            position_repo: Position repository exposing
                ``get_all_positions(account_name)``.
            account_name: Account identifier used for positions and audit.
            factor_provider: Optional factor snapshot provider forwarded to
                the domain strategy.
            price_provider: Optional price provider forwarded to the domain
                strategy.
        """
        self.trader = trader
        self.feishu_notifier = feishu_notifier
        self.position_repo = position_repo
        self.account_name = account_name
        self.factor_provider = factor_provider
        self.price_provider = price_provider
        self._strategy: Optional[XGBoostStrategy] = None

    @classmethod
    def from_config(
        cls,
        trader: Any,
        position_repo: Any,
        account_name: str,
        config: Dict[str, Any],
        **kwargs: Any,
    ) -> "XGBoostStrategyUseCase":
        """Build a use case from an app config dict (Feishu section included)."""
        notifier = create_notifier_from_config(config)
        return cls(
            trader=trader,
            feishu_notifier=notifier,
            position_repo=position_repo,
            account_name=account_name,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def execute(self, date: str) -> Dict[str, Any]:
        """Run the full daily workflow for ``date`` (``YYYY-MM-DD``)."""
        strategy = self._get_strategy()

        positions = self._get_positions(self.account_name)
        result = strategy.execute_daily_check(
            date=date,
            has_positions=bool(positions),
            account_name=self.account_name,
        )

        orders: List[Order] = list(result.get("orders") or [])
        result["executions"] = (
            self._execute_orders(orders, self.account_name) if orders else []
        )

        self._send_notification(result)
        self._log_to_db(result)
        return result

    # ------------------------------------------------------------------
    # Infrastructure wiring
    # ------------------------------------------------------------------
    def _get_strategy(self) -> XGBoostStrategy:
        """Return the cached domain strategy, creating it on first use.

        The instance is cached so ``last_rebalance_date`` (rebalance cadence
        state) survives across daily executions within this process.
        """
        if self._strategy is None:
            self._strategy = XGBoostStrategy(
                config=self.CONFIG,
                factor_provider=self.factor_provider,
                position_provider=lambda _date: self._positions_as_map(
                    self._get_positions(self.account_name)
                ),
                price_provider=self.price_provider,
            )
        return self._strategy

    def _get_positions(self, account_name: str) -> list:
        """Fetch current positions from the DB via the injected repository."""
        try:
            return list(self.position_repo.get_all_positions(account_name) or [])
        except Exception as exc:  # noqa: BLE001 - position fetch must not crash the flow
            logger.error(
                "%s: failed to fetch positions for %s: %s",
                type(self).__name__,
                account_name,
                exc,
            )
            return []

    @staticmethod
    def _positions_as_map(positions: list) -> Dict[str, Dict[str, Any]]:
        """Normalise Position entities/dicts to the domain provider contract."""
        mapped: Dict[str, Dict[str, Any]] = {}
        for position in positions:
            if isinstance(position, dict):
                symbol = position.get("symbol")
                entry = dict(position)
            else:
                symbol = getattr(position, "symbol", None)
                entry = {
                    "avg_price": getattr(position, "avg_cost", 0.0),
                    "quantity": (
                        getattr(position, "shares_available", 0)
                        or getattr(position, "shares_total", 0)
                    ),
                    "current_price": getattr(position, "current_price", 0.0),
                }
            if symbol:
                mapped[str(symbol)] = entry
        return mapped

    def _execute_orders(self, orders: List[Order], account_name: str) -> List[Dict[str, Any]]:
        """Execute orders via the injected trader (failures are captured, not raised)."""
        executions: List[Dict[str, Any]] = []
        for order in orders:
            record: Dict[str, Any] = {
                "symbol": order.symbol,
                "side": order.side.value,
                "quantity": order.quantity,
                "price": order.price,
                "account_name": account_name,
            }
            try:
                execute_order = getattr(self.trader, "execute_order", None)
                if callable(execute_order):
                    record["result"] = execute_order(order)
                elif order.side is OrderSide.BUY and callable(getattr(self.trader, "buy", None)):
                    record["result"] = self.trader.buy(order.symbol, order.quantity, order.price)
                elif order.side is OrderSide.SELL and callable(getattr(self.trader, "sell", None)):
                    record["result"] = self.trader.sell(order.symbol, order.quantity, order.price)
                else:
                    logger.warning(
                        "%s: trader %r has no execution interface; %s order for %s skipped",
                        type(self).__name__,
                        self.trader,
                        order.side.value,
                        order.symbol,
                    )
                    record["result"] = {"status": "skipped", "reason": "no trader interface"}
            except Exception as exc:  # noqa: BLE001 - one bad order must not block the rest
                logger.error(
                    "%s: %s order for %s failed: %s",
                    type(self).__name__,
                    order.side.value,
                    order.symbol,
                    exc,
                )
                record["result"] = {"status": "failed", "error": str(exc)}
            executions.append(record)
        return executions

    def _send_notification(self, result: Dict[str, Any]) -> None:
        """Send Feishu notifications: rebalance details and stop-loss alerts."""
        notifier = self.feishu_notifier
        if notifier is None:
            logger.debug("%s: no Feishu notifier configured; skipping", type(self).__name__)
            return

        orders: List[Order] = list(result.get("orders") or [])
        buy_trades = [
            (o.symbol, o.quantity, o.price) for o in orders if o.side is OrderSide.BUY
        ]
        sell_trades = [
            (o.symbol, o.quantity, o.price) for o in orders if o.side is OrderSide.SELL
        ]

        if buy_trades or sell_trades:
            top_stocks = [
                (s.symbol, s.score, s.weight, s.reason)
                for s in (result.get("signals") or [])
            ]
            try:
                notifier.send_rebalance_notification(
                    {
                        "date": result.get("date"),
                        "positions": len(self._get_positions(self.account_name)),
                        "top_stocks": top_stocks,
                        "buy_trades": buy_trades,
                        "sell_trades": sell_trades,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("%s: rebalance notification failed: %s", type(self).__name__, exc)

        stop_loss_signals = list(result.get("stop_loss_signals") or [])
        if stop_loss_signals:
            try:
                notifier.send_risk_alert(
                    {
                        "trigger": "stop_loss",
                        "losing_stocks": [s.symbol for s in stop_loss_signals],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("%s: risk alert notification failed: %s", type(self).__name__, exc)

    def _log_to_db(self, result: Dict[str, Any]) -> None:
        """Persist the day's decision to the ``audit_log`` table (best effort).

        Delegates to ``position_repo.log_decision`` when the repository
        provides it; otherwise falls back to a raw insert. Persistence
        failures are logged but never break the workflow.
        """
        record = {
            "date": result.get("date"),
            "account_name": result.get("account_name"),
            "strategy": self.CONFIG.name,
            "version": self.CONFIG.version,
            "rebalance": bool(result.get("rebalance")),
            "signal_count": len(result.get("signals") or []),
            "stop_loss_count": len(result.get("stop_loss_signals") or []),
            "orders": [
                {
                    "symbol": o.symbol,
                    "side": o.side.value,
                    "quantity": o.quantity,
                    "price": o.price,
                    "reason": o.reason,
                }
                for o in (result.get("orders") or [])
            ],
            "executions": result.get("executions") or [],
        }
        try:
            log_decision = getattr(self.position_repo, "log_decision", None)
            if callable(log_decision):
                log_decision(record)
                return

            from infrastructure.persistence.database.engine import get_engine
            from sqlalchemy import text

            with get_engine().connect() as conn:
                conn.execute(
                    text(
                        "INSERT INTO audit_log "
                        "(event_type, account_name, strategy, version, event_date, payload, created_at) "
                        "VALUES (:event_type, :account_name, :strategy, :version, :event_date, :payload, NOW())"
                    ),
                    {
                        "event_type": "strategy_daily_check",
                        "account_name": record["account_name"],
                        "strategy": record["strategy"],
                        "version": record["version"],
                        "event_date": record["date"],
                        "payload": json.dumps(record, ensure_ascii=False, default=str),
                    },
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: audit_log persist failed (non-fatal): %s", type(self).__name__, exc)


class V13StrategyUseCase(XGBoostStrategyUseCase):
    """V13 daily workflow: XGBoost multi-factor, 5-day rebalance, 8 positions."""

    CONFIG = V13_CONFIG
