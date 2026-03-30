"""SQLite database wrapper for the data pipeline."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_DB_PATH = ".pi-invest/stock-db/stocks.db"


class Database:
    """Encapsulate SQLite access for pipeline stock and kline data."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        """Create the SQLite connection and ensure schema compatibility."""
        self.db_path = Path(db_path).expanduser()
        self.conn: Optional[sqlite3.Connection] = None

        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self._migrate()
        except sqlite3.Error as exc:
            self.close()
            raise RuntimeError(f"Failed to initialize database {self.db_path}: {exc}") from exc
        except OSError as exc:
            self.close()
            raise RuntimeError(f"Failed to prepare database directory for {self.db_path}: {exc}") from exc

    def _get_connection(self) -> sqlite3.Connection:
        """Return the active connection or raise if the database is closed."""
        if self.conn is None:
            raise RuntimeError("Database connection is closed")
        return self.conn

    def _migrate(self) -> None:
        """Create base tables and add missing stock analytics columns."""
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS stocks (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    industry TEXT,
                    market_cap REAL,
                    pe REAL,
                    pb REAL,
                    total_mv REAL,
                    circulating_mv REAL,
                    is_st INTEGER DEFAULT 0,
                    is_suspended INTEGER DEFAULT 0,
                    list_date TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS daily_klines (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    amount REAL,
                    turnover_rate REAL,
                    PRIMARY KEY (symbol, date)
                );

                CREATE INDEX IF NOT EXISTS idx_stocks_market ON stocks(market);
                CREATE INDEX IF NOT EXISTS idx_stocks_updated_at ON stocks(updated_at);
                CREATE INDEX IF NOT EXISTS idx_daily_klines_symbol ON daily_klines(symbol);
                CREATE INDEX IF NOT EXISTS idx_daily_klines_date ON daily_klines(date);
                """
            )

            cursor.execute("PRAGMA table_info(stocks)")
            existing_columns = {str(row[1]) for row in cursor.fetchall()}

            new_columns = {
                "total_mv": "REAL",
                "circulating_mv": "REAL",
                "is_suspended": "INTEGER DEFAULT 0",
                "sector": "TEXT",
                "roe": "REAL",
                "net_profit_growth": "REAL",
                "gross_margin": "REAL",
                "debt_ratio": "REAL",
                "avg_turnover_rate": "REAL",
                "avg_volume": "REAL",
                "avg_amount": "REAL",
            }

            for column, column_type in new_columns.items():
                if column not in existing_columns:
                    cursor.execute(f"ALTER TABLE stocks ADD COLUMN {column} {column_type}")

            cursor.execute("PRAGMA table_info(daily_klines)")
            existing_kline_columns = {str(row[1]) for row in cursor.fetchall()}
            if "turnover_rate" not in existing_kline_columns:
                cursor.execute("ALTER TABLE daily_klines ADD COLUMN turnover_rate REAL")

            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to migrate database schema: {exc}") from exc

    def upsert_stocks(self, stocks: List[Dict[str, Any]]) -> int:
        """Insert or update stock rows in a single transaction."""
        if not stocks:
            return 0

        connection = self._get_connection()
        timestamp = datetime.now().isoformat(timespec="seconds")
        rows: List[tuple[Any, ...]] = []

        for stock in stocks:
            symbol = str(stock.get("symbol") or "").strip()
            if not symbol:
                raise ValueError("Stock entry missing required field: symbol")

            name = str(stock.get("name") or symbol).strip()
            market = str(stock.get("market") or "A").strip() or "A"
            stock_name = str(stock.get("name") or name)
            is_st = int(stock.get("is_st")) if stock.get("is_st") is not None else int("ST" in stock_name.upper())

            rows.append(
                (
                    symbol,
                    name,
                    market,
                    stock.get("industry"),
                    stock.get("sector"),
                    stock.get("market_cap"),
                    stock.get("pe"),
                    stock.get("pb"),
                    stock.get("total_mv"),
                    stock.get("circulating_mv"),
                    stock.get("roe"),
                    stock.get("net_profit_growth"),
                    stock.get("gross_margin"),
                    stock.get("debt_ratio"),
                    stock.get("avg_turnover_rate"),
                    stock.get("avg_volume"),
                    stock.get("avg_amount"),
                    is_st,
                    stock.get("is_suspended", 0),
                    stock.get("list_date"),
                    timestamp,
                )
            )

        try:
            connection.executemany(
                """
                INSERT INTO stocks (
                    symbol,
                    name,
                    market,
                    industry,
                    sector,
                    market_cap,
                    pe,
                    pb,
                    total_mv,
                    circulating_mv,
                    roe,
                    net_profit_growth,
                    gross_margin,
                    debt_ratio,
                    avg_turnover_rate,
                    avg_volume,
                    avg_amount,
                    is_st,
                    is_suspended,
                    list_date,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    market = excluded.market,
                    industry = COALESCE(excluded.industry, stocks.industry),
                    sector = COALESCE(excluded.sector, stocks.sector),
                    market_cap = COALESCE(excluded.market_cap, stocks.market_cap),
                    pe = COALESCE(excluded.pe, stocks.pe),
                    pb = COALESCE(excluded.pb, stocks.pb),
                    total_mv = COALESCE(excluded.total_mv, stocks.total_mv),
                    circulating_mv = COALESCE(excluded.circulating_mv, stocks.circulating_mv),
                    roe = COALESCE(excluded.roe, stocks.roe),
                    net_profit_growth = COALESCE(excluded.net_profit_growth, stocks.net_profit_growth),
                    gross_margin = COALESCE(excluded.gross_margin, stocks.gross_margin),
                    debt_ratio = COALESCE(excluded.debt_ratio, stocks.debt_ratio),
                    avg_turnover_rate = COALESCE(excluded.avg_turnover_rate, stocks.avg_turnover_rate),
                    avg_volume = COALESCE(excluded.avg_volume, stocks.avg_volume),
                    avg_amount = COALESCE(excluded.avg_amount, stocks.avg_amount),
                    is_st = excluded.is_st,
                    is_suspended = excluded.is_suspended,
                    list_date = COALESCE(excluded.list_date, stocks.list_date),
                    updated_at = excluded.updated_at
                """,
                rows,
            )
            connection.commit()
            return len(rows)
        except sqlite3.Error as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to upsert stock records: {exc}") from exc

    def get_all_symbols(self, market: Optional[str] = None) -> List[str]:
        """Return all stock symbols, optionally filtered by market."""
        connection = self._get_connection()

        try:
            if market:
                cursor = connection.execute(
                    "SELECT symbol FROM stocks WHERE market = ? ORDER BY symbol ASC",
                    (market,),
                )
            else:
                cursor = connection.execute("SELECT symbol FROM stocks ORDER BY symbol ASC")
            return [str(row[0]) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            raise RuntimeError(f"Failed to fetch stock symbols: {exc}") from exc

    def count_stocks(self, market: Optional[str] = None) -> int:
        """Return the number of stocks in the database."""
        connection = self._get_connection()

        try:
            if market:
                row = connection.execute(
                    "SELECT COUNT(*) FROM stocks WHERE market = ?",
                    (market,),
                ).fetchone()
            else:
                row = connection.execute("SELECT COUNT(*) FROM stocks").fetchone()
            return int(row[0]) if row else 0
        except sqlite3.Error as exc:
            raise RuntimeError(f"Failed to count stocks: {exc}") from exc

    def print_status(self) -> None:
        """Print a concise summary of current stock and kline coverage."""
        connection = self._get_connection()

        try:
            kline_row = connection.execute(
                "SELECT COUNT(DISTINCT symbol) FROM daily_klines"
            ).fetchone()
            update_row = connection.execute(
                "SELECT MAX(updated_at) FROM stocks"
            ).fetchone()
        except sqlite3.Error as exc:
            raise RuntimeError(f"Failed to read database status: {exc}") from exc

        print("=" * 50)
        print("数据库状态")
        print("=" * 50)
        print(f"A股数量: {self.count_stocks('A')}")
        print(f"港股数量: {self.count_stocks('HK')}")
        print(f"K线数据覆盖股票数: {int(kline_row[0]) if kline_row and kline_row[0] is not None else 0}")
        print(f"最后更新时间: {update_row[0] if update_row and update_row[0] else '未更新'}")
        print("=" * 50)

    def get_klines(self, symbol: str, limit: int = 500):
        """Get K-line data for a symbol."""
        import pandas as pd
        connection = self._get_connection()
        try:
            query = "SELECT symbol, date, open, high, low, close, volume, amount, turnover_rate FROM daily_klines WHERE symbol = ? ORDER BY date ASC LIMIT ?"
            return pd.read_sql_query(query, connection, params=(symbol, limit))
        except sqlite3.Error as exc:
            raise RuntimeError(f"Failed to fetch klines: {exc}") from exc

    def close(self) -> None:
        """Close the SQLite connection safely."""
        if self.conn is None:
            return

        try:
            self.conn.close()
        except sqlite3.Error as exc:
            raise RuntimeError(f"Failed to close database connection: {exc}") from exc
        finally:
            self.conn = None
