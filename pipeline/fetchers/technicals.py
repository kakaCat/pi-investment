"""Technical indicator calculation for persisted daily kline data."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict

try:
    from pipeline.db import Database
except ImportError:  # pragma: no cover - allows script-relative imports
    from db import Database


class TechnicalCalculator:
    """Calculate simple rolling technical metrics from recent daily klines."""

    _WINDOW_SIZE = 20

    def __init__(self, db: Database) -> None:
        """Store the database dependency used for reads and updates."""
        self.db = db

    def calculate_and_update(self, symbol: str) -> Dict[str, Any]:
        """Calculate recent averages for one symbol and persist them to `stocks`."""
        connection = self.db._get_connection()

        try:
            cursor = connection.cursor()
            has_turnover_rate = self._has_turnover_rate_column(cursor)
            rows = self._fetch_recent_klines(cursor, symbol, has_turnover_rate)
            if len(rows) < self._WINDOW_SIZE:
                return {}

            metrics = self._build_metrics(rows, has_turnover_rate)
            cursor.execute(
                """
                UPDATE stocks
                SET avg_turnover_rate = ?,
                    avg_volume = ?,
                    avg_amount = ?
                WHERE symbol = ?
                """,
                (
                    metrics["avg_turnover_rate"],
                    metrics["avg_volume"],
                    metrics["avg_amount"],
                    symbol,
                ),
            )
            connection.commit()
            return metrics
        except sqlite3.Error as exc:
            self._rollback_quietly(connection)
            raise RuntimeError(
                f"Failed to calculate technicals for {symbol}: {exc}"
            ) from exc
        except RuntimeError as exc:
            raise RuntimeError(
                f"Failed to calculate technicals for {symbol}: {exc}"
            ) from exc

    def _has_turnover_rate_column(self, cursor: sqlite3.Cursor) -> bool:
        """Return whether `daily_klines` currently includes `turnover_rate`."""
        columns = cursor.execute("PRAGMA table_info(daily_klines)").fetchall()
        return any(str(row[1]) == "turnover_rate" for row in columns)

    def _fetch_recent_klines(
        self,
        cursor: sqlite3.Cursor,
        symbol: str,
        has_turnover_rate: bool,
    ) -> list[sqlite3.Row]:
        """Fetch the latest 20 daily kline rows for one symbol."""
        select_fields = "volume, amount, turnover_rate" if has_turnover_rate else "volume, amount"
        query = f"""
            SELECT {select_fields}
            FROM daily_klines
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT {self._WINDOW_SIZE}
        """
        return cursor.execute(query, (symbol,)).fetchall()

    def _build_metrics(
        self,
        rows: list[sqlite3.Row],
        has_turnover_rate: bool,
    ) -> Dict[str, Any]:
        """Calculate averages from the fetched rows."""
        avg_volume = self._mean(float(row["volume"]) for row in rows if row["volume"] is not None)
        avg_amount = self._mean(float(row["amount"]) for row in rows if row["amount"] is not None)
        avg_turnover_rate = None

        if has_turnover_rate:
            avg_turnover_rate = self._mean(
                float(row["turnover_rate"])
                for row in rows
                if row["turnover_rate"] is not None
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

    def _rollback_quietly(self, connection: sqlite3.Connection) -> None:
        """Best-effort rollback for failed update flows."""
        try:
            connection.rollback()
        except sqlite3.Error:
            return
