"""
XGBoost multi-factor strategy — pure algorithm implementation.

This module contains ONLY the algorithm: model/factor loading, factor
alignment, return prediction, ranking, top-N selection, single-stock
stop-loss checks, and signal → order translation.

All data access (factor values, positions, prices) is injected via provider
callables, so the strategy has zero dependencies on ``live_trading``,
``simulation_trader``, infrastructure layers, databases, or external
services. Wiring providers to real data sources is the responsibility of the
application/adapter layer.

Provider contracts
------------------
factor_provider: ``callable(date: str) -> pd.DataFrame``
    Returns the latest factor snapshot for the whole stock universe on
    ``date``. Must contain a ``symbol`` column plus one column per factor.
position_provider: ``callable(date: str) -> dict[str, dict]``
    Returns open positions keyed by symbol. Each entry should carry
    ``avg_price`` (or ``cost_price``) and ``quantity`` (or ``shares``), and
    may carry a fallback price under ``current_price``/``last_price``.
price_provider: ``callable(symbol: str, date: str) -> float | None``
    Returns the latest tradable price for ``symbol`` on ``date``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from domain.strategies.base_strategy import BaseStrategy
from domain.strategies.value_objects import (
    Order,
    OrderSide,
    Signal,
    SignalAction,
    StrategyConfig,
)

__all__ = ["XGBoostStrategy"]

logger = logging.getLogger(__name__)

FactorProvider = Callable[[str], pd.DataFrame]
PositionProvider = Callable[[str], Dict[str, Dict[str, Any]]]
PriceProvider = Callable[[str, str], Optional[float]]


class XGBoostStrategy(BaseStrategy):
    """Pure XGBoost multi-factor stock-selection strategy.

    Algorithm:
        1. On first use, load the XGBoost model and the valid-factor list
           (hook :meth:`_on_init`).
        2. :meth:`calculate_signals` predicts expected returns for the whole
           universe, ranks them, and emits BUY signals for the top N names.
        3. :meth:`check_stop_loss` flags any held position whose loss exceeds
           ``config.stop_loss_pct`` with a SELL signal.
        4. :meth:`generate_orders` translates signals into :class:`Order`
           value objects (full exit for SELL, weight-sized lots for BUY).

    Construction takes an immutable :class:`StrategyConfig` plus optional
    data providers. With no providers wired the strategy still works as a
    pure predictor: feed factor frames directly to :meth:`_predict_returns`.
    """

    def __init__(
        self,
        config: StrategyConfig,
        factor_provider: Optional[FactorProvider] = None,
        position_provider: Optional[PositionProvider] = None,
        price_provider: Optional[PriceProvider] = None,
    ) -> None:
        super().__init__(config)
        self.factor_provider = factor_provider
        self.position_provider = position_provider
        self.price_provider = price_provider
        self.model: Any = None
        self.factors: List[str] = []
        self._last_signal_date: Optional[str] = None

    # ------------------------------------------------------------------
    # Initialisation hook
    # ------------------------------------------------------------------
    def _on_init(self) -> None:
        """Load the XGBoost model and factor definitions (fired once)."""
        self._load_model()
        self._load_factors()

    def _load_model(self) -> None:
        """Load the trained XGBoost regressor from ``config.model_path``.

        The xgboost import is deferred so this module stays importable in
        environments without xgboost installed. Loading failures are logged
        and leave ``self.model`` as ``None`` (predictions disabled).
        """
        model_path = self.config.model_path
        if not model_path:
            logger.warning("XGBoostStrategy: no model_path configured; predictions disabled")
            self.model = None
            return

        path = Path(model_path)
        if not path.exists():
            logger.warning("XGBoostStrategy: model file not found: %s", path)
            self.model = None
            return

        try:
            import xgboost as xgb

            model = xgb.XGBRegressor(n_jobs=1)  # single thread: avoids segfaults seen in prod
            model.load_model(str(path))
            self.model = model
            logger.info("XGBoostStrategy: model loaded from %s", path)
        except Exception as exc:  # noqa: BLE001 - never let a bad model kill init
            logger.error("XGBoostStrategy: failed to load model %s: %s", path, exc)
            self.model = None

    def _load_factors(self) -> None:
        """Load the ordered valid-factor list from ``config.factors_path``.

        The file must be a JSON list of factor-name strings in the exact
        column order used at training time.
        """
        factors_path = self.config.factors_path
        if not factors_path:
            logger.warning("XGBoostStrategy: no factors_path configured")
            self.factors = []
            return

        path = Path(factors_path)
        if not path.exists():
            logger.warning("XGBoostStrategy: factors file not found: %s", path)
            self.factors = []
            return

        try:
            with open(path, "r", encoding="utf-8") as fh:
                factors = json.load(fh)
            if not isinstance(factors, list) or not all(isinstance(f, str) for f in factors):
                raise ValueError("factors file must contain a JSON list of strings")
            self.factors = list(factors)
            logger.info("XGBoostStrategy: %d factors loaded from %s", len(self.factors), path)
        except Exception as exc:  # noqa: BLE001
            logger.error("XGBoostStrategy: failed to load factors %s: %s", path, exc)
            self.factors = []

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def _predict_returns(self, factor_data: pd.DataFrame) -> pd.Series:
        """Predict expected returns for every row of ``factor_data``.

        The frame is reindexed to the training-time factor order; missing
        factor columns are filled with 0 so a partially unavailable factor
        set degrades gracefully instead of crashing the model.

        Args:
            factor_data: Factor snapshot; one row per stock.

        Returns:
            A ``pd.Series`` of predicted returns aligned with the input index.

        Raises:
            RuntimeError: If the model or factor list is not loaded.
            ValueError: If none of the required factors are present.
        """
        if self.model is None:
            raise RuntimeError("XGBoostStrategy: model not loaded")
        if not self.factors:
            raise RuntimeError("XGBoostStrategy: factor list not loaded")
        if factor_data is None or factor_data.empty:
            return pd.Series(dtype=float, name="predicted_return")

        available = [f for f in self.factors if f in factor_data.columns]
        if not available:
            raise ValueError(
                "XGBoostStrategy: none of the %d required factors are present in factor_data"
                % len(self.factors)
            )
        missing = len(self.factors) - len(available)
        if missing:
            logger.warning(
                "XGBoostStrategy: %d/%d factors missing from input; filled with 0",
                missing,
                len(self.factors),
            )

        features = (
            factor_data.reindex(columns=self.factors)
            .apply(pd.to_numeric, errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
        )
        predictions = self.model.predict(features)
        return pd.Series(predictions, index=factor_data.index, name="predicted_return")

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------
    def calculate_signals(self, date: str, account_name: str = "default") -> List[Signal]:
        """Predict returns for the universe and emit top-N BUY signals.

        Args:
            date: Trading date in ``YYYY-MM-DD`` format.
            account_name: Account identifier (recorded in signal metadata).

        Returns:
            BUY signals ranked by predicted return, capped at
            ``params['top_n']`` (default ``config.max_positions``).
        """
        if not self.is_initialized:
            self.initialize()
        self._last_signal_date = date

        if self.factor_provider is None:
            logger.warning("XGBoostStrategy: no factor_provider wired; returning no signals")
            return []

        factor_data = self.factor_provider(date)
        if factor_data is None or factor_data.empty:
            logger.info("XGBoostStrategy: no factor data for %s", date)
            return []
        if "symbol" not in factor_data.columns:
            raise ValueError("factor_data must contain a 'symbol' column")

        predictions = self._predict_returns(factor_data)

        scored = pd.DataFrame(
            {
                "symbol": factor_data["symbol"].astype(str).to_numpy(),
                "predicted_return": predictions.to_numpy(),
            }
        )

        min_score = float(self.config.params.get("min_score", 0.0))
        scored = scored[scored["predicted_return"] > min_score]
        scored = scored.sort_values("predicted_return", ascending=False)

        top_n = int(self.config.params.get("top_n", self.config.max_positions))
        top_n = max(1, min(top_n, self.config.max_positions))
        selected = scored.head(top_n)
        if selected.empty:
            return []

        default_weight = self.config.max_position_pct / len(selected)
        weight = float(self.config.params.get("single_stock_weight", default_weight))

        signals: List[Signal] = []
        for rank, (_, row) in enumerate(selected.iterrows(), start=1):
            symbol = row["symbol"]
            predicted_return = float(row["predicted_return"])
            metadata: Dict[str, Any] = {
                "strategy": self.config.name,
                "version": self.config.version,
                "date": date,
                "account_name": account_name,
                "rank": rank,
                "predicted_return": predicted_return,
                "factor_count": len(self.factors),
            }
            price = self._lookup_price(symbol, date)
            if price is not None:
                metadata["price"] = price
            signals.append(
                Signal(
                    symbol=symbol,
                    action=SignalAction.BUY,
                    weight=weight,
                    score=predicted_return,
                    reason=(
                        f"xgboost top-{rank} pick: predicted_return={predicted_return:.4f}"
                    ),
                    metadata=metadata,
                )
            )
        return signals

    def check_stop_loss(self, date: str) -> List[Signal]:
        """Emit SELL signals for positions breaching ``config.stop_loss_pct``.

        Each open position from the injected ``position_provider`` is checked
        individually via :meth:`_check_single_stop_loss`. Returns an empty
        list when no provider is wired or nothing triggers.
        """
        if self.position_provider is None:
            return []
        self._last_signal_date = date

        positions = self.position_provider(date) or {}
        signals: List[Signal] = []
        for symbol, position in positions.items():
            cost_price = self._extract_cost_price(position)
            quantity = self._extract_quantity(position)
            if cost_price is None or cost_price <= 0 or quantity <= 0:
                continue

            current_price = self._lookup_price(symbol, date, position)
            if current_price is None or current_price <= 0:
                logger.warning("XGBoostStrategy: no price for %s; skip stop-loss check", symbol)
                continue

            if self._check_single_stop_loss(cost_price, current_price):
                pnl_pct = current_price / cost_price - 1.0
                signals.append(
                    Signal(
                        symbol=symbol,
                        action=SignalAction.SELL,
                        weight=1.0,  # full exit
                        score=abs(pnl_pct),
                        reason=(
                            f"stop-loss triggered: pnl={pnl_pct:.2%} "
                            f"<= -{abs(self.config.stop_loss_pct):.2%}"
                        ),
                        metadata={
                            "trigger": "stop_loss",
                            "date": date,
                            "cost_price": cost_price,
                            "current_price": current_price,
                            "pnl_pct": pnl_pct,
                            "quantity": quantity,
                        },
                    )
                )
        return signals

    def _check_single_stop_loss(self, cost_price: float, current_price: float) -> bool:
        """Return True when one position's loss breaches the stop threshold."""
        if cost_price <= 0:
            return False
        return (current_price / cost_price - 1.0) <= -abs(self.config.stop_loss_pct)

    # ------------------------------------------------------------------
    # Signal -> order translation
    # ------------------------------------------------------------------
    def generate_orders(self, signals: List[Signal]) -> List[Order]:
        """Convert signals into :class:`Order` value objects.

        SELL signals exit the full held quantity (from the position provider
        or ``signal.metadata['quantity']``). BUY signals are sized as
        ``weight * reference_capital / price`` rounded down to whole lots
        (``params['lot_size']``, default 100). Signals that cannot be sized
        (unknown price, zero quantity, HOLD action) are skipped with a
        warning.
        """
        orders: List[Order] = []
        if not signals:
            return orders

        lot_size = int(self.config.params.get("lot_size", 100))
        reference_capital = float(self.config.params.get("reference_capital", 1_000_000.0))
        date = self._last_signal_date or ""

        positions: Dict[str, Dict[str, Any]] = {}
        if self.position_provider is not None:
            try:
                positions = self.position_provider(date) or {}
            except Exception as exc:  # noqa: BLE001
                logger.warning("XGBoostStrategy: position_provider failed: %s", exc)

        for signal in signals:
            if signal.action not in (SignalAction.BUY, SignalAction.SELL):
                continue

            side = OrderSide.BUY if signal.action is SignalAction.BUY else OrderSide.SELL
            position = positions.get(signal.symbol, {})

            price = self._resolve_order_price(signal, date, position)
            if price is None or price <= 0:
                logger.warning(
                    "XGBoostStrategy: cannot size %s order for %s without a price; skipped",
                    side.value,
                    signal.symbol,
                )
                continue

            if side is OrderSide.SELL:
                quantity = self._extract_quantity(position)
                if quantity <= 0:
                    quantity = float(signal.metadata.get("quantity", 0.0) or 0.0)
            else:
                raw_quantity = (signal.weight * reference_capital) / price
                quantity = float(int(raw_quantity // lot_size) * lot_size) if lot_size > 1 else raw_quantity

            if quantity <= 0:
                logger.warning(
                    "XGBoostStrategy: %s order for %s sized to zero; skipped",
                    side.value,
                    signal.symbol,
                )
                continue

            orders.append(
                Order(
                    symbol=signal.symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    reason=signal.reason,
                    metadata={
                        **signal.metadata,
                        "signal_score": signal.score,
                        "signal_weight": signal.weight,
                    },
                )
            )
        return orders

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _lookup_price(
        self, symbol: str, date: str, position: Optional[Dict[str, Any]] = None
    ) -> Optional[float]:
        """Resolve the latest price for ``symbol`` (provider, then position fallback)."""
        if self.price_provider is not None:
            try:
                price = self.price_provider(symbol, date)
            except Exception as exc:  # noqa: BLE001
                logger.warning("XGBoostStrategy: price_provider failed for %s: %s", symbol, exc)
            else:
                if price is not None and float(price) > 0:
                    return float(price)
        if position:
            for key in ("current_price", "last_price", "price"):
                value = position.get(key)
                if value is not None and float(value) > 0:
                    return float(value)
        return None

    def _resolve_order_price(
        self, signal: Signal, date: str, position: Dict[str, Any]
    ) -> Optional[float]:
        """Order pricing: signal metadata first, then the price provider."""
        meta_price = signal.metadata.get("price")
        if meta_price is not None and float(meta_price) > 0:
            return float(meta_price)
        return self._lookup_price(signal.symbol, date, position)

    @staticmethod
    def _extract_cost_price(position: Dict[str, Any]) -> Optional[float]:
        for key in ("avg_price", "cost_price", "avg_cost"):
            value = position.get(key)
            if value is not None and float(value) > 0:
                return float(value)
        return None

    @staticmethod
    def _extract_quantity(position: Dict[str, Any]) -> float:
        for key in ("quantity", "shares", "volume"):
            value = position.get(key)
            if value is not None and float(value) > 0:
                return float(value)
        return 0.0
