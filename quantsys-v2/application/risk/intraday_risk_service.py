"""Intraday risk monitoring service.

Watches all open positions during trading hours (scheduled every 30 minutes
between 10:00 and 14:30) and enforces per-position risk rules:

- **Fixed stop loss**: ``current_price / avg_price - 1 < stop_loss_pct``
- **Trailing stop**: ``current_price / peak_price - 1 < trailing_stop_pct``

Triggered positions are sold via the injected trader and each action is
reported to Feishu. All thresholds are configurable via the engine config's
``risk`` section.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from qs_notification.application import get_notification_facade

__all__ = ["IntradayRiskService"]

logger = logging.getLogger(__name__)

#: Default risk thresholds (negative returns).
DEFAULT_STOP_LOSS_PCT = -0.12
DEFAULT_TRAILING_STOP_PCT = -0.08


class IntradayRiskService:
    """Monitor open positions intraday and execute stop-loss orders.

    Infrastructure dependencies (position repository, trader, engine) are
    injected, keeping the service free of construction-time side effects and
    testable.
    """

    def __init__(
        self,
        position_repo: Any,
        trader: Any,
        engine: Any,
        stop_loss_pct: Optional[float] = None,
        trailing_stop_pct: Optional[float] = None,
        price_provider: Any = None,
        price_observer: Any = None,
    ) -> None:
        """
        Args:
            position_repo: Repository exposing ``get_all_positions(account_name)``.
            trader: Execution adapter exposing ``sell(symbol, quantity, price)``.
            engine: Trading engine; when it exposes a dict ``config`` attribute,
                the config's ``risk`` section supplies fallback thresholds.
            stop_loss_pct: Explicit fixed stop-loss threshold; overrides engine config.
            trailing_stop_pct: Explicit trailing-stop threshold; overrides engine config.
            price_provider: Optional ``callable(symbol) -> float | None`` used before
                cached position prices. When injected, a missing quote is a failure.
            price_observer: Optional ``callable(symbol, price)`` invoked for every
                successfully resolved price so callers can persist current/peak prices.
        """
        self.position_repo = position_repo
        self.trader = trader
        self.engine = engine
        self.price_provider = price_provider
        self.price_observer = price_observer

        engine_config = getattr(engine, "config", None)
        self._config: Dict[str, Any] = engine_config if isinstance(engine_config, dict) else {}

        risk_config = self._config.get("risk") or {}
        self.stop_loss_pct = float(
            stop_loss_pct
            if stop_loss_pct is not None
            else risk_config.get("stop_loss_pct", DEFAULT_STOP_LOSS_PCT)
        )
        self.trailing_stop_pct = float(
            trailing_stop_pct
            if trailing_stop_pct is not None
            else risk_config.get("trailing_stop_pct", DEFAULT_TRAILING_STOP_PCT)
        )

        self.account_name = getattr(engine, "account_name", None) or "default"
        # 2026-09-11（w-23c70356）：统一走 NotificationFacade（原直连旁路已删除）
        self.feishu_notifier = get_notification_facade()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def check_positions(self, date: str = None) -> Dict[str, Any]:
        """Check every open position against the intraday risk rules.

        Args:
            date: Trading date (``YYYY-MM-DD``); defaults to today.

        Returns:
            Summary dict with ``date``, ``checked`` count, ``actions`` taken,
            ``quote_failures``, and an overall ``success`` flag. Any missing
            quote or failed/skipped sell makes ``success`` false.
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        summary: Dict[str, Any] = {
            "date": date,
            "account_name": self.account_name,
            "checked": 0,
            "quote_failures": 0,
            "position_fetch_failed": False,
            "actions": [],
            "success": True,
        }

        positions = self._get_all_positions()
        if positions is None:
            summary["position_fetch_failed"] = True
            summary["success"] = False
            logger.error(
                "IntradayRiskService: failed to fetch positions for %s",
                self.account_name,
            )
            return summary

        summary["checked"] = len(positions)

        for position in positions:
            try:
                trigger = self._check_position_risk(position)
            except Exception as exc:  # noqa: BLE001 - one bad position must not block the rest
                logger.error("IntradayRiskService: risk check failed for %r: %s", position, exc)
                summary["success"] = False
                continue

            if trigger is None:
                continue

            if trigger.get("error") == "quote_unavailable":
                summary["quote_failures"] += 1
                summary["success"] = False
                logger.error(
                    "IntradayRiskService: no usable quote for %s on %s",
                    self._get(position, "symbol"),
                    self.account_name,
                )
                continue

            action = self._execute_stop_loss(position, trigger)
            action["trigger"] = trigger
            summary["actions"].append(action)
            if action.get("status") != "executed":
                summary["success"] = False
            self._send_alert(position, trigger["reason"], action)

        if summary["actions"]:
            logger.warning(
                "IntradayRiskService: %d stop-loss action(s) on %s",
                len(summary["actions"]),
                date,
            )
        else:
            logger.info(
                "IntradayRiskService: %d position(s) checked on %s, no triggers",
                summary["checked"],
                date,
            )
        return summary

    # ------------------------------------------------------------------
    # Position access
    # ------------------------------------------------------------------
    def _get_all_positions(self) -> Optional[List[Any]]:
        """Fetch all open positions for the account (failures return ``None``)."""
        try:
            return list(self.position_repo.get_all_positions(self.account_name) or [])
        except Exception as exc:  # noqa: BLE001 - position fetch must not crash the flow
            logger.error(
                "IntradayRiskService: failed to fetch positions for %s: %s",
                self.account_name,
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # Risk rules
    # ------------------------------------------------------------------
    def _check_position_risk(self, position: Any) -> Optional[Dict[str, Any]]:
        """Check one position against the stop-loss and trailing-stop rules.

        Returns:
            A trigger dict (``reason``, ``rule``, ``current_price``,
            ``return_pct``) when a rule fires, an error dict when the latest
            quote is unavailable, otherwise ``None``.
        """
        symbol = self._get(position, "symbol")
        avg_price = float(self._get(position, "avg_price", "avg_cost") or 0)
        current_price = self._current_price(position)

        if not symbol or avg_price <= 0:
            return None
        if current_price is None or current_price <= 0:
            return {"error": "quote_unavailable", "symbol": symbol}

        if self.price_observer is not None:
            try:
                self.price_observer(symbol, current_price)
            except Exception as exc:  # noqa: BLE001 - observation must not block risk control
                logger.error(
                    "IntradayRiskService: price observer failed for %s: %s",
                    symbol,
                    exc,
                )

        # Rule 1: fixed stop loss vs average cost.
        return_pct = current_price / avg_price - 1
        if return_pct < self.stop_loss_pct:
            return {
                "rule": "stop_loss",
                "reason": (
                    f"单票止损: 现价 {current_price:.2f} 较成本 {avg_price:.2f} "
                    f"亏损 {return_pct * 100:.2f}% (阈值 {self.stop_loss_pct * 100:.0f}%)"
                ),
                "current_price": current_price,
                "return_pct": return_pct,
            }

        # Rule 2: trailing stop vs peak price since entry.
        peak_price = float(self._get(position, "peak_price", "highest_price") or 0)
        if peak_price > 0:
            drawdown_from_peak = current_price / peak_price - 1
            if drawdown_from_peak < self.trailing_stop_pct:
                return {
                    "rule": "trailing_stop",
                    "reason": (
                        f"移动止损: 现价 {current_price:.2f} 较高点 {peak_price:.2f} "
                        f"回撤 {drawdown_from_peak * 100:.2f}% "
                        f"(阈值 {self.trailing_stop_pct * 100:.0f}%)"
                    ),
                    "current_price": current_price,
                    "return_pct": drawdown_from_peak,
                }

        return None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _execute_stop_loss(self, position: Any, trigger: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a stop-loss sell order for the full position (failures captured)."""
        symbol = self._get(position, "symbol")
        quantity = int(
            self._get(position, "shares_available", "shares_total", "shares", "quantity") or 0
        )
        price = float(trigger.get("current_price") or 0)
        reason = trigger["reason"]

        action: Dict[str, Any] = {
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "reason": reason,
            "account_name": self.account_name,
        }

        if quantity <= 0:
            action["status"] = "skipped"
            action["result"] = {"status": "skipped", "reason": "no sellable shares"}
            return action

        try:
            action["result"] = self.trader.sell(symbol, quantity, price)
            action["status"] = "executed"
        except Exception as exc:  # noqa: BLE001 - a failed sell must not block other positions
            logger.error("IntradayRiskService: stop-loss sell for %s failed: %s", symbol, exc)
            action["status"] = "failed"
            action["result"] = {"status": "failed", "error": str(exc)}

        return action

    # ------------------------------------------------------------------
    # Notification
    # ------------------------------------------------------------------
    def _send_alert(self, position: Any, reason: str, action: Dict[str, Any]) -> None:
        """Send a Feishu risk alert for an executed stop-loss action."""
        notifier = self.feishu_notifier
        if notifier is None:
            logger.debug("IntradayRiskService: no Feishu notifier configured; skipping alert")
            return

        symbol = action.get("symbol") or self._get(position, "symbol")
        result = action.get("result") or {}
        status = result.get("status", "executed") if isinstance(result, dict) else "executed"

        message = (
            "🚨 盘中风控止损\n"
            f"股票: {symbol}\n"
            f"原因: {reason}\n"
            f"数量: {action.get('quantity')}\n"
            f"价格: {action.get('price')}\n"
            f"执行状态: {status}\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        try:
            send_text = getattr(notifier, "send_text", None)
            if callable(send_text):
                send_text(message)
            else:
                notifier.send_risk_alert({"trigger": reason, "losing_stocks": [symbol]})
        except Exception as exc:  # noqa: BLE001 - notification failure must not break the flow
            logger.error("IntradayRiskService: Feishu alert for %s failed: %s", symbol, exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _current_price(self, position: Any) -> Optional[float]:
        """Resolve the latest tradable price for a position.

        When an explicit price provider is injected it is authoritative: a
        missing quote must fail the check rather than silently falling back to
        stale cached prices. Without an injected provider, retain the legacy
        engine-hook/cached-price behaviour for backwards compatibility.
        """
        symbol = self._get(position, "symbol")

        if self.price_provider is not None and symbol:
            try:
                value = self.price_provider(symbol)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "IntradayRiskService: price_provider failed for %s: %s",
                    symbol,
                    exc,
                )
                return None
            return float(value) if value is not None and float(value) > 0 else None

        for hook_name in ("get_price", "price_provider"):
            hook = getattr(self.engine, hook_name, None)
            if callable(hook) and symbol:
                try:
                    value = hook(symbol)
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "IntradayRiskService: engine.%s failed for %s: %s",
                        hook_name,
                        symbol,
                        exc,
                    )
                    continue
                if value:
                    return float(value)

        price = self._get(position, "current_price")
        return float(price) if price else None

    @staticmethod
    def _get(position: Any, *names: str) -> Any:
        """Read the first present attribute/key among ``names`` (entity or dict)."""
        for name in names:
            if isinstance(position, dict):
                if position.get(name) is not None:
                    return position[name]
            else:
                value = getattr(position, name, None)
                if value is not None:
                    return value
        return None
