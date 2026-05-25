"""Technical indicator calculation for persisted daily kline data."""

from __future__ import annotations

from typing import Any, Dict

from quantsys.data.db import Database


class TechnicalCalculator:
    """Calculate simple rolling technical metrics from recent daily klines."""

    _WINDOW_SIZE = 20

    def __init__(self, db: Database) -> None:
        """Store the database dependency used for reads and updates."""
        self.db = db

    def calculate_and_update(self, symbol: str) -> Dict[str, Any]:
        """Calculate recent averages for one symbol and persist them to `stocks`."""
        try:
            frame = self.db.get_recent_klines(symbol, self._WINDOW_SIZE)
            if len(frame.index) < self._WINDOW_SIZE:
                return {}

            metrics = self._build_metrics(frame.to_dict("records"))
            self.db.update_stock_technicals(symbol, metrics)
            return metrics
        except Exception as exc:
            raise RuntimeError(
                f"Failed to calculate technicals for {symbol}: {exc}"
            ) from exc

    def _build_metrics(self, rows: list[dict[str, Any]]) -> Dict[str, Any]:
        """Calculate averages from the fetched rows."""
        avg_volume = self._mean(float(row["volume"]) for row in rows if row["volume"] is not None)
        avg_amount = self._mean(float(row["amount"]) for row in rows if row["amount"] is not None)
        avg_turnover_rate = self._mean(
            float(row["turnover_rate"])
            for row in rows
            if row.get("turnover_rate") is not None
        )

        return {
            "avg_turnover_rate": avg_turnover_rate,
            "avg_volume": avg_volume,
            "avg_amount": None if avg_amount is None else avg_amount / 10000,
        }

    def _mean(self, values: Any) -> float | None:
        """Return the arithmetic mean for an iterable of numeric values."""
        numbers = list(values)
        if not numbers:
            return None
        return sum(numbers) / len(numbers)
