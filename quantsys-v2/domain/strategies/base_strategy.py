"""
Base strategy template built on domain value objects.

All concrete strategies inherit from :class:`BaseStrategy` and implement the
abstract methods. The template method :meth:`BaseStrategy.execute_daily_check`
orchestrates the daily trading workflow and delegates decision points to
abstract methods and hooks.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.strategies.value_objects import (
    Order,
    OrderSide,
    Signal,
    SignalAction,
    StrategyConfig,
)

__all__ = [
    "BaseStrategy",
    "Signal",
    "SignalAction",
    "StrategyConfig",
    "Order",
    "OrderSide",
]


class BaseStrategy(ABC):
    """Template-method base class for trading strategies.

    Construction takes an immutable :class:`StrategyConfig` that centralises
    every tunable parameter (rebalance cadence, position limits, risk
    controls, model paths, extra params).

    Daily workflow (template method :meth:`execute_daily_check`):

        1. Initialise once via :meth:`initialize` (which fires :meth:`_on_init`).
        2. Fire the per-trading-day hook :meth:`_on_trading_day`.
        3. Run :meth:`check_stop_loss` when positions exist.
        4. Decide whether to rebalance via :meth:`should_rebalance`.
        5. When rebalancing, call :meth:`calculate_signals`, filter them via
           :meth:`validate_signals`, then fire :meth:`_on_rebalance`.
        6. Translate signals to orders via :meth:`generate_orders`.
    """

    def __init__(self, config: StrategyConfig) -> None:
        if not isinstance(config, StrategyConfig):
            raise TypeError("config must be a StrategyConfig instance")
        self.config: StrategyConfig = config
        self.is_initialized: bool = False
        self.last_rebalance_date: Optional[str] = None

    # ------------------------------------------------------------------
    # Template method
    # ------------------------------------------------------------------
    def execute_daily_check(
        self,
        date: str,
        has_positions: bool = False,
        account_name: str = "default",
    ) -> Dict[str, Any]:
        """Run the daily strategy workflow.

        Args:
            date: Trading date in ``YYYY-MM-DD`` format.
            has_positions: Whether the account currently holds any positions.
            account_name: Account identifier passed through to hooks.

        Returns:
            A dict summarising the day's decisions: stop-loss signals,
            rebalance flag, new signals and generated orders.
        """
        # Step 1: initialise on first call.
        if not self.is_initialized:
            self.initialize()

        # Step 2: per-trading-day hook.
        self._on_trading_day(date, account_name)

        # Step 3: stop-loss check (only meaningful when holding positions).
        stop_loss_signals: List[Signal] = []
        if has_positions:
            stop_loss_signals = list(self.check_stop_loss(date) or [])

        # Step 4: decide whether to rebalance.
        rebalance_needed = self.should_rebalance(
            last_rebalance_date=self.last_rebalance_date,
            current_date=date,
            has_positions=has_positions,
        )

        # Step 5: calculate new signals when a rebalance is due.
        new_signals: List[Signal] = []
        if rebalance_needed:
            raw_signals = list(self.calculate_signals(date, account_name) or [])
            new_signals = self.validate_signals(raw_signals)
            self._on_rebalance(date, new_signals)
            self.last_rebalance_date = date

        # Step 6: translate signals into orders.
        orders = self.generate_orders(stop_loss_signals + new_signals)

        return {
            "date": date,
            "account_name": account_name,
            "rebalance": rebalance_needed,
            "stop_loss_signals": stop_loss_signals,
            "signals": new_signals,
            "orders": orders,
        }

    def initialize(self) -> None:
        """Initialise the strategy exactly once by firing the ``_on_init`` hook."""
        if not self.is_initialized:
            self._on_init()
            self.is_initialized = True

    # ------------------------------------------------------------------
    # Abstract methods - concrete strategies MUST implement these.
    # ------------------------------------------------------------------
    @abstractmethod
    def calculate_signals(
        self, date: str, account_name: str = "default"
    ) -> List[Signal]:
        """Compute new entry/exit signals for ``date``.

        Implementations should return a list of :class:`Signal` value
        objects. The base class will validate and normalise them via
        :meth:`validate_signals` before they are converted to orders.
        """
        raise NotImplementedError

    @abstractmethod
    def check_stop_loss(self, date: str) -> List[Signal]:
        """Inspect open positions and return SELL signals for any that
        trigger stop-loss rules. Return an empty list when nothing triggers.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Hooks - default no-ops, override as needed.
    # ------------------------------------------------------------------
    def _on_init(self) -> None:
        """Hook fired once before the first daily check (e.g. load models)."""

    def _on_trading_day(self, date: str, account_name: str = "default") -> None:
        """Hook fired at the start of every daily check."""

    def _on_rebalance(self, date: str, signals: List[Signal]) -> None:
        """Hook fired after a rebalance produces validated signals."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def should_rebalance(
        self,
        last_rebalance_date: Optional[str],
        current_date: str,
        has_positions: bool = True,
    ) -> bool:
        """Decide whether a rebalance is due on ``current_date``.

        Rules:
            * No prior rebalance -> rebalance.
            * Empty portfolio -> rebalance (look for entries every day).
            * Otherwise rebalance when ``rebalance_days`` have elapsed.
        """
        if not last_rebalance_date:
            return True
        if not has_positions:
            return True

        last_date = datetime.strptime(last_rebalance_date, "%Y-%m-%d")
        curr_date = datetime.strptime(current_date, "%Y-%m-%d")
        return (curr_date - last_date).days >= self.config.rebalance_days

    def validate_signals(self, signals: List[Signal]) -> List[Signal]:
        """Filter invalid signals, cap BUY count, and rescale weights.

        * Drops anything that is not a :class:`Signal` with BUY/SELL action.
        * Keeps at most ``config.max_positions`` BUY signals (highest score).
        * If the sum of BUY weights exceeds ``config.max_position_pct``,
          rescales them proportionally.
        """
        valid: List[Signal] = [
            s
            for s in signals
            if isinstance(s, Signal)
            and s.action in (SignalAction.BUY, SignalAction.SELL)
        ]

        buys = [s for s in valid if s.action is SignalAction.BUY]
        sells = [s for s in valid if s.action is SignalAction.SELL]

        if len(buys) > self.config.max_positions:
            buys = sorted(buys, key=lambda s: s.score, reverse=True)[
                : self.config.max_positions
            ]

        total_weight = sum(s.weight for s in buys)
        if total_weight > self.config.max_position_pct and total_weight > 0:
            scale = self.config.max_position_pct / total_weight
            buys = [
                Signal(
                    symbol=s.symbol,
                    action=s.action,
                    weight=s.weight * scale,
                    score=s.score,
                    reason=s.reason,
                    metadata=s.metadata,
                )
                for s in buys
            ]

        return buys + sells

    def generate_orders(self, signals: List[Signal]) -> List[Order]:
        """Translate validated signals into executable orders.

        The default implementation returns an empty list; concrete
        strategies typically override this to size orders against the
        account and current positions.
        """
        return []

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def get_metadata(self) -> Dict[str, Any]:
        """Return a JSON-serialisable metadata dict describing this strategy."""
        cfg = self.config
        return {
            "name": cfg.name,
            "version": cfg.version,
            "description": cfg.description,
            "rebalance_days": cfg.rebalance_days,
            "max_positions": cfg.max_positions,
            "max_position_pct": cfg.max_position_pct,
            "stop_loss_pct": cfg.stop_loss_pct,
            "trailing_stop_pct": cfg.trailing_stop_pct,
            "portfolio_stop_loss_pct": cfg.portfolio_stop_loss_pct,
            "model_path": cfg.model_path,
            "factors_path": cfg.factors_path,
            "params": cfg.params,
        }
