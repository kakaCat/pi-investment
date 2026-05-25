"""Database manager for stock data storage.

This module provides a high-level interface for storing and retrieving
stock data from SQLite database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from quantsys.data.db import Database


class DBManager:
    """Manage stock data storage in SQLite database.

    This class wraps the existing Database class and provides additional
    functionality for the quantitative trading system.
    """

    def __init__(self, db_path: str = ".pi-invest/stock-db/stocks.db"):
        """Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db = Database(db_path)
        self.db_path = Path(db_path).expanduser()

    def save_klines(
        self,
        symbol: str,
        df: pd.DataFrame,
        replace: bool = True,
    ) -> int:
        """Save K-line data to database.

        Args:
            symbol: Stock symbol
            df: DataFrame with columns [date, open, high, low, close, volume, amount]
            replace: If True, replace existing data; if False, skip duplicates

        Returns:
            Number of rows saved

        Raises:
            ValueError: If required columns are missing
            RuntimeError: If database operation fails
        """
        required_cols = ["date", "open", "high", "low", "close"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        if df.empty:
            return 0

        rows = []

        for _, row in df.iterrows():
            rows.append(
                {
                    "symbol": symbol,
                    "date": str(row["date"]),
                    "open": self._to_float(row.get("open")),
                    "high": self._to_float(row.get("high")),
                    "low": self._to_float(row.get("low")),
                    "close": self._to_float(row.get("close")),
                    "volume": self._to_float(row.get("volume")),
                    "amount": self._to_float(row.get("amount")),
                    "turnover_rate": self._to_float(row.get("turnover_rate")),
                }
            )

        try:
            if replace or self.db.provider == "postgres":
                return self.db.upsert_daily_klines(rows)
            return self._insert_missing_klines_sqlite(rows)
        except Exception as exc:
            raise RuntimeError(f"Failed to save klines for {symbol}: {exc}") from exc

    def _insert_missing_klines_sqlite(self, rows: list[dict]) -> int:
        """Insert K-line rows while skipping duplicates for legacy SQLite callers."""
        connection = self.db._get_connection()
        payload = [
            (
                row["symbol"],
                row["date"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                row["amount"],
                row["turnover_rate"],
            )
            for row in rows
        ]
        try:
            connection.executemany(
                """
                INSERT OR IGNORE INTO daily_klines
                (symbol, date, open, high, low, close, volume, amount, turnover_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            connection.commit()
            return len(payload)
        except Exception as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to insert missing klines: {exc}") from exc

    def load_klines(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """Load K-line data from database.

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD or YYYYMMDD)
            end_date: End date (YYYY-MM-DD or YYYYMMDD)
            limit: Maximum number of rows to return

        Returns:
            DataFrame with K-line data

        Raises:
            RuntimeError: If database operation fails
        """
        connection = self.db._get_connection()

        try:
            if self.db.provider == "postgres":
                query = """
                    SELECT symbol, trade_date::text AS date, open, high, low, close, volume, amount, turnover_rate
                    FROM quant.daily_klines
                    WHERE symbol = %s
                """
                date_column = "trade_date"
                placeholder = "%s"
            else:
                query = """
                    SELECT symbol, date, open, high, low, close, volume, amount, turnover_rate
                    FROM daily_klines
                    WHERE symbol = ?
                """
                date_column = "date"
                placeholder = "?"
            params = [symbol]

            if start_date:
                query += f" AND {date_column} >= {placeholder}"
                params.append(self._normalize_date(start_date))

            if end_date:
                query += f" AND {date_column} <= {placeholder}"
                params.append(self._normalize_date(end_date))

            query += f" ORDER BY {date_column} ASC"

            if limit:
                query += f" LIMIT {limit}"

            return pd.read_sql_query(query, connection, params=params)
        except Exception as exc:
            raise RuntimeError(f"Failed to load klines for {symbol}: {exc}") from exc

    def load_klines_batch(
        self,
        symbols: list[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, pd.DataFrame]:
        """Load K-line data for multiple symbols.

        Args:
            symbols: List of stock symbols
            start_date: Start date
            end_date: End date

        Returns:
            Dict mapping symbol to DataFrame
        """
        results = {}
        for symbol in symbols:
            try:
                df = self.load_klines(symbol, start_date, end_date)
                results[symbol] = df
            except Exception as exc:
                print(f"Failed to load {symbol}: {exc}")
                results[symbol] = pd.DataFrame()

        return results

    def get_symbols(
        self,
        market: Optional[str] = None,
        min_market_cap: Optional[float] = None,
        exclude_st: bool = True,
        exclude_suspended: bool = True,
    ) -> list[str]:
        """Get list of stock symbols with filters.

        Args:
            market: Market filter ("A" or "HK")
            min_market_cap: Minimum market cap in yuan
            exclude_st: Exclude ST stocks
            exclude_suspended: Exclude suspended stocks

        Returns:
            List of stock symbols

        Raises:
            RuntimeError: If database operation fails
        """
        connection = self.db._get_connection()

        try:
            table = "quant.stocks" if self.db.provider == "postgres" else "stocks"
            placeholder = "%s" if self.db.provider == "postgres" else "?"
            query = f"SELECT symbol FROM {table} WHERE 1=1"
            params = []

            if market:
                query += f" AND market = {placeholder}"
                params.append(market)

            if min_market_cap:
                query += f" AND market_cap >= {placeholder}"
                params.append(min_market_cap)

            if exclude_st:
                query += " AND is_st = false" if self.db.provider == "postgres" else " AND is_st = 0"

            if exclude_suspended:
                query += " AND is_suspended = false" if self.db.provider == "postgres" else " AND is_suspended = 0"

            query += " ORDER BY symbol ASC"

            if self.db.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                cursor.close()
            else:
                cursor = connection.execute(query, params)
                rows = cursor.fetchall()
            return [str(row[0]) for row in rows]
        except Exception as exc:
            raise RuntimeError(f"Failed to get symbols: {exc}") from exc

    def get_stock_info(self, symbol: str) -> Optional[dict]:
        """Get stock information.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with stock info, or None if not found
        """
        connection = self.db._get_connection()

        try:
            if self.db.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT symbol, name, market, industry, sector, market_cap, pe, pb,
                           is_st, is_suspended, list_date::text
                    FROM quant.stocks
                    WHERE symbol = %s
                    """,
                    (symbol,),
                )
                row = cursor.fetchone()
                cursor.close()
            else:
                cursor = connection.execute(
                """
                SELECT symbol, name, market, industry, sector, market_cap, pe, pb,
                       is_st, is_suspended, list_date
                FROM stocks
                WHERE symbol = ?
                """,
                    (symbol,),
                )
                row = cursor.fetchone()

            if not row:
                return None

            return {
                "symbol": row[0],
                "name": row[1],
                "market": row[2],
                "industry": row[3],
                "sector": row[4],
                "market_cap": row[5],
                "pe": row[6],
                "pb": row[7],
                "is_st": bool(row[8]),
                "is_suspended": bool(row[9]),
                "list_date": row[10],
            }
        except Exception as exc:
            raise RuntimeError(f"Failed to get stock info for {symbol}: {exc}") from exc

    def get_date_range(self, symbol: str) -> Optional[tuple[str, str]]:
        """Get date range of available K-line data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Tuple of (start_date, end_date), or None if no data
        """
        connection = self.db._get_connection()

        try:
            if self.db.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT MIN(trade_date)::text, MAX(trade_date)::text
                    FROM quant.daily_klines
                    WHERE symbol = %s
                    """,
                    (symbol,),
                )
                row = cursor.fetchone()
                cursor.close()
            else:
                cursor = connection.execute(
                    """
                    SELECT MIN(date), MAX(date)
                    FROM daily_klines
                    WHERE symbol = ?
                    """,
                    (symbol,),
                )
                row = cursor.fetchone()

            if not row or not row[0]:
                return None

            return (str(row[0]), str(row[1]))
        except Exception as exc:
            raise RuntimeError(f"Failed to get date range for {symbol}: {exc}") from exc

    def delete_klines(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> int:
        """Delete K-line data for a symbol.

        Args:
            symbol: Stock symbol
            start_date: Start date (optional)
            end_date: End date (optional)

        Returns:
            Number of rows deleted
        """
        connection = self.db._get_connection()

        try:
            if self.db.provider == "postgres":
                query = "DELETE FROM quant.daily_klines WHERE symbol = %s"
                date_column = "trade_date"
                placeholder = "%s"
            else:
                query = "DELETE FROM daily_klines WHERE symbol = ?"
                date_column = "date"
                placeholder = "?"
            params = [symbol]

            if start_date:
                query += f" AND {date_column} >= {placeholder}"
                params.append(self._normalize_date(start_date))

            if end_date:
                query += f" AND {date_column} <= {placeholder}"
                params.append(self._normalize_date(end_date))

            if self.db.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(query, params)
                rowcount = cursor.rowcount
                cursor.close()
            else:
                cursor = connection.execute(query, params)
                rowcount = cursor.rowcount
            connection.commit()
            return rowcount
        except Exception as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to delete klines for {symbol}: {exc}") from exc

    def get_statistics(self) -> dict:
        """Get database statistics.

        Returns:
            Dict with statistics
        """
        connection = self.db._get_connection()

        try:
            stats = {
                "total_stocks": self.db.count_stocks(),
                "a_share_stocks": self.db.count_stocks("A"),
                "hk_stocks": self.db.count_stocks("HK"),
            }

            # Count stocks with K-line data
            if self.db.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute("SELECT COUNT(DISTINCT symbol) FROM quant.daily_klines")
                stats["stocks_with_klines"] = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM quant.daily_klines")
                stats["total_kline_records"] = cursor.fetchone()[0]

                cursor.execute("SELECT MAX(updated_at) FROM quant.stocks")
                row = cursor.fetchone()
                cursor.close()
            else:
                cursor = connection.execute(
                    "SELECT COUNT(DISTINCT symbol) FROM daily_klines"
                )
                stats["stocks_with_klines"] = cursor.fetchone()[0]

                cursor = connection.execute("SELECT COUNT(*) FROM daily_klines")
                stats["total_kline_records"] = cursor.fetchone()[0]

                cursor = connection.execute("SELECT MAX(updated_at) FROM stocks")
                row = cursor.fetchone()
            stats["last_update"] = row[0] if row and row[0] else None

            return stats
        except Exception as exc:
            raise RuntimeError(f"Failed to get statistics: {exc}") from exc

    def close(self):
        """Close database connection."""
        self.db.close()

    def _to_float(self, value) -> Optional[float]:
        """Convert value to float, handling None and NaN."""
        if value is None or pd.isna(value):
            return None
        return float(value)

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to YYYY-MM-DD format.

        Args:
            date_str: Date string (YYYY-MM-DD or YYYYMMDD)

        Returns:
            Normalized date string (YYYY-MM-DD)
        """
        date_str = date_str.strip()

        # Already in YYYY-MM-DD format
        if "-" in date_str:
            return date_str

        # Convert YYYYMMDD to YYYY-MM-DD
        if len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        return date_str
