"""Database wrapper for the data pipeline."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psycopg2
except ImportError:  # pragma: no cover - exercised when optional dependency is absent
    psycopg2 = None  # type: ignore[assignment]


DEFAULT_DB_PATH = ".pi-invest/stock-db/stocks.db"


def normalize_symbol(symbol: str) -> str:
    """Strip common exchange suffixes/prefixes from a stock symbol."""
    value = str(symbol).strip()
    for suffix in (".SH", ".SZ", ".BJ", ".HK"):
        if value.upper().endswith(suffix):
            value = value[: -len(suffix)]
            break
    for prefix in ("sh", "sz", "bj"):
        if value.lower().startswith(prefix) and len(value) > 6:
            value = value[2:]
            break
    return value


class Database:
    """Encapsulate pipeline stock and kline persistence."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, connect: bool = True) -> None:
        """Create the configured database connection and ensure schema compatibility.

        Set connect=False to defer connection (e.g., when used with context manager).
        """
        self.provider = os.environ.get("QUANT_DB_PROVIDER", "sqlite").strip().lower()

        if self.provider not in {"postgres", "sqlite"}:
            self.provider = "sqlite"

        self.db_path: Optional[Path] = None
        self.conn: Any | None = None
        self._schema: str | None = None

        if connect:
            if self.provider == "sqlite":
                self._init_sqlite(db_path)
            else:
                self._init_postgres()

    def __enter__(self) -> "Database":
        """Enter the context manager — connect if not already connected."""
        if self.conn is None:
            if self.provider == "sqlite":
                self._init_sqlite(str(self.db_path) if self.db_path else DEFAULT_DB_PATH)
            else:
                self._init_postgres()
        return self

    @property
    def schema(self) -> str | None:
        """Return the active schema name for provider-aware table references."""
        if self._schema is not None:
            return self._schema
        if self.provider == "postgres":
            return os.environ.get("QUANT_PG_SCHEMA", "quant")
        return None

    @schema.setter
    def schema(self, value: str | None) -> None:
        self._schema = value

    def get_connection(self) -> Any:
        """Return the raw database connection (public wrapper for _get_connection)."""
        if self.conn is None:
            self.__enter__()
        return self._get_connection()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context manager — close the connection."""
        self.close()

    def _init_sqlite(self, db_path: str) -> None:
        """Create the SQLite connection used by the data pipeline."""
        import sqlite3
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def _init_postgres(self) -> None:
        """Create the PostgreSQL connection used by the data pipeline."""
        if psycopg2 is None:
            raise RuntimeError("psycopg2-binary is required when QUANT_DB_PROVIDER=postgres")

        dsn = (
            os.environ.get("QUANT_DATABASE_URL")
            or os.environ.get("DATABASE_URL")
            or os.environ.get("POSTGRES_DSN")
        )

        try:
            self.conn = psycopg2.connect(dsn) if dsn else psycopg2.connect(dbname=os.environ.get("PGDATABASE", "quant_investment"))
            self._migrate()
        except Exception as exc:
            self.close()
            raise RuntimeError(f"Failed to initialize PostgreSQL database: {exc}") from exc

    def _get_connection(self) -> Any:
        """Return the active connection or raise if the database is closed."""
        if self.conn is None:
            raise RuntimeError("Database connection is closed")
        return self.conn

    def _migrate(self) -> None:
        """Create base tables and add missing stock analytics columns."""
        self._migrate_postgres()

    def _migrate_sqlite(self) -> None:
        """Create SQLite base tables and add missing stock analytics columns."""
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

                CREATE TABLE IF NOT EXISTS factor_values (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    factor_name TEXT NOT NULL,
                    factor_value REAL,
                    PRIMARY KEY (symbol, date, factor_name)
                );

                CREATE INDEX IF NOT EXISTS idx_stocks_market ON stocks(market);
                CREATE INDEX IF NOT EXISTS idx_stocks_updated_at ON stocks(updated_at);
                CREATE INDEX IF NOT EXISTS idx_daily_klines_symbol ON daily_klines(symbol);
                CREATE INDEX IF NOT EXISTS idx_daily_klines_date ON daily_klines(date);
                CREATE INDEX IF NOT EXISTS idx_factor_symbol_date ON factor_values(symbol, date);
                CREATE INDEX IF NOT EXISTS idx_factor_date ON factor_values(date);

                CREATE TABLE IF NOT EXISTS trading_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    signal_date TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    confidence REAL,
                    price REAL,
                    reason TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(symbol, signal_date, strategy_name)
                );

                CREATE TABLE IF NOT EXISTS signal_factors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER NOT NULL REFERENCES trading_signals(id) ON DELETE CASCADE,
                    factor_name TEXT NOT NULL,
                    factor_value REAL,
                    factor_weight REAL,
                    trigger_condition TEXT,
                    is_primary INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_trading_signals_symbol ON trading_signals(symbol);
                CREATE INDEX IF NOT EXISTS idx_trading_signals_date ON trading_signals(signal_date);
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

    def _migrate_postgres(self) -> None:
        """Create the PostgreSQL tables required by the ETL writer."""
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                CREATE SCHEMA IF NOT EXISTS quant;

                CREATE TABLE IF NOT EXISTS quant.stocks (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    industry TEXT,
                    sector TEXT,
                    market_cap DOUBLE PRECISION,
                    pe DOUBLE PRECISION,
                    pb DOUBLE PRECISION,
                    total_mv DOUBLE PRECISION,
                    circulating_mv DOUBLE PRECISION,
                    is_st BOOLEAN NOT NULL DEFAULT FALSE,
                    is_suspended BOOLEAN NOT NULL DEFAULT FALSE,
                    list_date DATE,
                    roe DOUBLE PRECISION,
                    net_profit_growth DOUBLE PRECISION,
                    gross_margin DOUBLE PRECISION,
                    debt_ratio DOUBLE PRECISION,
                    avg_turnover_rate DOUBLE PRECISION,
                    avg_volume DOUBLE PRECISION,
                    avg_amount DOUBLE PRECISION,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE TABLE IF NOT EXISTS quant.daily_klines (
                    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
                    trade_date DATE NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    amount DOUBLE PRECISION,
                    turnover_rate DOUBLE PRECISION,
                    PRIMARY KEY (symbol, trade_date)
                );

                CREATE TABLE IF NOT EXISTS quant.factor_values (
                    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
                    factor_date DATE NOT NULL,
                    factor_name TEXT NOT NULL,
                    factor_value DOUBLE PRECISION,
                    PRIMARY KEY (symbol, factor_date, factor_name)
                );

                CREATE TABLE IF NOT EXISTS quant.trading_signals (
                    id BIGSERIAL PRIMARY KEY,
                    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
                    signal_date DATE NOT NULL,
                    signal_type TEXT NOT NULL CHECK (signal_type IN ('BUY', 'SELL', 'HOLD')),
                    strategy_name TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    price DOUBLE PRECISION NOT NULL,
                    reason TEXT,
                    metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (symbol, signal_date, strategy_name)
                );

                CREATE TABLE IF NOT EXISTS quant.signal_factors (
                    id BIGSERIAL PRIMARY KEY,
                    signal_id BIGINT NOT NULL REFERENCES quant.trading_signals(id) ON DELETE CASCADE,
                    factor_name TEXT NOT NULL,
                    factor_value DOUBLE PRECISION NOT NULL,
                    factor_weight DOUBLE PRECISION,
                    trigger_condition TEXT,
                    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE TABLE IF NOT EXISTS quant.signal_executions (
                    id BIGSERIAL PRIMARY KEY,
                    signal_id BIGINT NOT NULL REFERENCES quant.trading_signals(id) ON DELETE CASCADE,
                    execution_date DATE NOT NULL,
                    execution_price DOUBLE PRECISION NOT NULL,
                    quantity INTEGER NOT NULL,
                    commission DOUBLE PRECISION,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'executed', 'cancelled', 'expired')),
                    pnl DOUBLE PRECISION,
                    close_date DATE,
                    close_price DOUBLE PRECISION,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE INDEX IF NOT EXISTS idx_quant_stocks_market ON quant.stocks(market);
                CREATE INDEX IF NOT EXISTS idx_quant_stocks_updated_at ON quant.stocks(updated_at);
                CREATE INDEX IF NOT EXISTS idx_quant_daily_klines_symbol_date_desc
                    ON quant.daily_klines(symbol, trade_date DESC);
                CREATE INDEX IF NOT EXISTS idx_quant_factor_values_symbol_date
                    ON quant.factor_values(symbol, factor_date);
                CREATE INDEX IF NOT EXISTS idx_quant_factor_values_factor_date
                    ON quant.factor_values(factor_date);
                CREATE INDEX IF NOT EXISTS idx_quant_trading_signals_symbol_date_desc
                    ON quant.trading_signals(symbol, signal_date DESC);
                CREATE INDEX IF NOT EXISTS idx_quant_trading_signals_signal_date_desc
                    ON quant.trading_signals(signal_date DESC);
                CREATE INDEX IF NOT EXISTS idx_quant_trading_signals_strategy_name
                    ON quant.trading_signals(strategy_name);
                CREATE INDEX IF NOT EXISTS idx_quant_trading_signals_signal_type
                    ON quant.trading_signals(signal_type);
                CREATE INDEX IF NOT EXISTS idx_quant_signal_factors_signal_id
                    ON quant.signal_factors(signal_id);
                CREATE INDEX IF NOT EXISTS idx_quant_signal_factors_factor_name
                    ON quant.signal_factors(factor_name);
                CREATE INDEX IF NOT EXISTS idx_quant_signal_executions_signal_id
                    ON quant.signal_executions(signal_id);
                CREATE INDEX IF NOT EXISTS idx_quant_signal_executions_execution_date_desc
                    ON quant.signal_executions(execution_date DESC);
                """
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to migrate PostgreSQL schema: {exc}") from exc
        finally:
            cursor.close()

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
            if self.provider == "postgres":
                self._upsert_stocks_postgres(rows)
            else:
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
        except Exception as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to upsert stock records: {exc}") from exc

    def _upsert_stocks_postgres(self, rows: List[tuple[Any, ...]]) -> None:
        """Insert or update stock rows in PostgreSQL."""
        connection = self._get_connection()
        cursor = connection.cursor()
        postgres_rows = [
            (
                *row[:17],
                bool(row[17]),
                bool(row[18]),
                *row[19:],
            )
            for row in rows
        ]
        try:
            cursor.executemany(
                """
                INSERT INTO quant.stocks (
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
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    market = excluded.market,
                    industry = COALESCE(excluded.industry, quant.stocks.industry),
                    sector = COALESCE(excluded.sector, quant.stocks.sector),
                    market_cap = COALESCE(excluded.market_cap, quant.stocks.market_cap),
                    pe = COALESCE(excluded.pe, quant.stocks.pe),
                    pb = COALESCE(excluded.pb, quant.stocks.pb),
                    total_mv = COALESCE(excluded.total_mv, quant.stocks.total_mv),
                    circulating_mv = COALESCE(excluded.circulating_mv, quant.stocks.circulating_mv),
                    roe = COALESCE(excluded.roe, quant.stocks.roe),
                    net_profit_growth = COALESCE(excluded.net_profit_growth, quant.stocks.net_profit_growth),
                    gross_margin = COALESCE(excluded.gross_margin, quant.stocks.gross_margin),
                    debt_ratio = COALESCE(excluded.debt_ratio, quant.stocks.debt_ratio),
                    avg_turnover_rate = COALESCE(excluded.avg_turnover_rate, quant.stocks.avg_turnover_rate),
                    avg_volume = COALESCE(excluded.avg_volume, quant.stocks.avg_volume),
                    avg_amount = COALESCE(excluded.avg_amount, quant.stocks.avg_amount),
                    is_st = excluded.is_st,
                    is_suspended = excluded.is_suspended,
                    list_date = COALESCE(excluded.list_date, quant.stocks.list_date),
                    updated_at = excluded.updated_at
                """,
                postgres_rows,
            )
            connection.commit()
        finally:
            cursor.close()

    def upsert_daily_klines(self, klines: List[Dict[str, Any]]) -> int:
        """Insert or update daily kline rows."""
        if not klines:
            return 0

        rows = []
        for kline in klines:
            rows.append(
                (
                    str(kline["symbol"]),
                    str(kline["date"]),
                    kline.get("open"),
                    kline.get("high"),
                    kline.get("low"),
                    kline.get("close"),
                    kline.get("volume"),
                    kline.get("amount"),
                    kline.get("turnover_rate"),
                )
            )

        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                try:
                    cursor.executemany(
                        """
                        INSERT INTO quant.daily_klines
                        (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(symbol, trade_date) DO UPDATE SET
                            open = excluded.open,
                            high = excluded.high,
                            low = excluded.low,
                            close = excluded.close,
                            volume = excluded.volume,
                            amount = excluded.amount,
                            turnover_rate = COALESCE(excluded.turnover_rate, quant.daily_klines.turnover_rate)
                        """,
                        rows,
                    )
                    connection.commit()
                finally:
                    cursor.close()
            else:
                connection.executemany(
                    """
                    INSERT OR REPLACE INTO daily_klines
                    (symbol, date, open, high, low, close, volume, amount, turnover_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                connection.commit()
            return len(rows)
        except Exception as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to upsert daily kline records: {exc}") from exc

    def upsert_minute_klines(self, klines: List[Dict[str, Any]]) -> int:
        """Insert or update minute kline rows."""
        if not klines:
            return 0

        rows = []
        for kline in klines:
            rows.append(
                (
                    str(kline["symbol"]),
                    kline["ts"],
                    kline.get("open"),
                    kline.get("high"),
                    kline.get("low"),
                    kline.get("close"),
                    kline.get("volume"),
                    kline.get("amount"),
                )
            )

        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                try:
                    cursor.executemany(
                        """
                        INSERT INTO quant.minute_klines
                        (symbol, ts, open, high, low, close, volume, amount)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(symbol, ts) DO UPDATE SET
                            open = excluded.open,
                            high = excluded.high,
                            low = excluded.low,
                            close = excluded.close,
                            volume = excluded.volume,
                            amount = excluded.amount
                        """,
                        rows,
                    )
                    connection.commit()
                finally:
                    cursor.close()
            else:
                raise RuntimeError("SQLite is no longer supported for minute klines")
            return len(rows)
        except Exception as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to upsert minute kline records: {exc}") from exc

    def get_all_symbols(
        self,
        market: Optional[str] = None,
        exclude_st: bool = False,
        exclude_suspended: bool = False,
    ) -> List[str]:
        """Return all stock symbols, optionally filtered by market and tradeability."""
        connection = self._get_connection()

        try:
            conditions = []
            params = []

            if market:
                if self.provider == "postgres":
                    conditions.append("market = %s")
                else:
                    conditions.append("market = ?")
                params.append(market)

            if exclude_st:
                if self.provider == "postgres":
                    conditions.append("is_st = FALSE")
                else:
                    conditions.append("is_st = 0")

            if exclude_suspended:
                if self.provider == "postgres":
                    conditions.append("is_suspended = FALSE")
                else:
                    conditions.append("is_suspended = 0")

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    f"SELECT symbol FROM quant.stocks {where_clause} ORDER BY symbol ASC",
                    params,
                )
                rows = cursor.fetchall()
                cursor.close()
            else:
                cursor = connection.execute(
                    f"SELECT symbol FROM stocks {where_clause} ORDER BY symbol ASC",
                    params,
                )
                rows = cursor.fetchall()

            return [str(row[0]) for row in rows]
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch stock symbols: {exc}") from exc

    def get_stock_rows(self, market: Optional[str] = None, has_data: bool = False) -> List[Dict[str, Any]]:
        """Return stock identity rows, optionally limited to symbols with K-line data."""
        connection = self._get_connection()

        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                if has_data:
                    query = """
                        SELECT DISTINCT s.symbol, s.name, s.market
                        FROM quant.stocks s
                        INNER JOIN quant.daily_klines k ON s.symbol = k.symbol
                    """
                else:
                    query = "SELECT s.symbol, s.name, s.market FROM quant.stocks s"
                params: tuple[Any, ...] = ()
                if market:
                    query += " WHERE s.market = %s"
                    params = (market,)
                query += " ORDER BY s.symbol"
                cursor.execute(query, params)
                rows = cursor.fetchall()
                cursor.close()
            else:
                if has_data:
                    query = """
                        SELECT DISTINCT s.symbol, s.name, s.market
                        FROM stocks s
                        INNER JOIN daily_klines k ON s.symbol = k.symbol
                    """
                else:
                    query = "SELECT s.symbol, s.name, s.market FROM stocks s"
                params = ()
                if market:
                    query += " WHERE s.market = ?"
                    params = (market,)
                query += " ORDER BY s.symbol"
                rows = connection.execute(query, params).fetchall()
            return [
                {"symbol": str(row[0]), "name": row[1], "market": row[2]}
                for row in rows
            ]
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch stock rows: {exc}") from exc

    def get_stock_identity_rows(self, market: Optional[str] = None) -> List[Dict[str, str]]:
        """Return stock symbol/name rows for API task selection."""
        rows = self.get_stock_rows(market=market, has_data=False)
        return [
            {"symbol": str(row["symbol"]), "name": str(row.get("name") or "")}
            for row in rows
        ]

    def get_kline_coverage(self, symbol: str) -> Dict[str, Any]:
        """Return existing K-line coverage for one symbol."""
        normalized_symbol = normalize_symbol(symbol)
        connection = self._get_connection()

        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*), MIN(trade_date)::text, MAX(trade_date)::text
                    FROM quant.daily_klines
                    WHERE symbol = %s
                    """,
                    (normalized_symbol,),
                )
                row = cursor.fetchone()
                cursor.close()
            else:
                row = connection.execute(
                    """
                    SELECT COUNT(*), MIN(date), MAX(date)
                    FROM daily_klines
                    WHERE symbol = ?
                    """,
                    (normalized_symbol,),
                ).fetchone()

            if row and row[0]:
                return {"existing_days": int(row[0]), "first_date": row[1], "last_date": row[2]}
            return {"existing_days": 0, "first_date": None, "last_date": None}
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch kline coverage for {symbol}: {exc}") from exc

    def count_stocks(self, market: Optional[str] = None) -> int:
        """Return the number of stocks in the database."""
        connection = self._get_connection()

        try:
            if market:
                if self.provider == "postgres":
                    cursor = connection.cursor()
                    cursor.execute("SELECT COUNT(*) FROM quant.stocks WHERE market = %s", (market,))
                    row = cursor.fetchone()
                    cursor.close()
                else:
                    row = connection.execute(
                        "SELECT COUNT(*) FROM stocks WHERE market = ?",
                        (market,),
                    ).fetchone()
            else:
                if self.provider == "postgres":
                    cursor = connection.cursor()
                    cursor.execute("SELECT COUNT(*) FROM quant.stocks")
                    row = cursor.fetchone()
                    cursor.close()
                else:
                    row = connection.execute("SELECT COUNT(*) FROM stocks").fetchone()
            return int(row[0]) if row else 0
        except Exception as exc:
            raise RuntimeError(f"Failed to count stocks: {exc}") from exc

    def get_market(self, symbol: str) -> Optional[str]:
        """Return the market for one symbol, if known."""
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute("SELECT market FROM quant.stocks WHERE symbol = %s", (symbol,))
                row = cursor.fetchone()
                cursor.close()
            else:
                row = connection.execute(
                    "SELECT market FROM stocks WHERE symbol = ?",
                    (symbol,),
                ).fetchone()
            return str(row[0]).upper() if row and row[0] else None
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch market for {symbol}: {exc}") from exc

    def print_status(self) -> None:
        """Print a concise summary of current stock and kline coverage."""
        connection = self._get_connection()

        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute("SELECT COUNT(DISTINCT symbol) FROM quant.daily_klines")
                kline_row = cursor.fetchone()
                cursor.execute("SELECT MAX(updated_at) FROM quant.stocks")
                update_row = cursor.fetchone()
                cursor.close()
            else:
                kline_row = connection.execute(
                    "SELECT COUNT(DISTINCT symbol) FROM daily_klines"
                ).fetchone()
                update_row = connection.execute(
                    "SELECT MAX(updated_at) FROM stocks"
                ).fetchone()
        except Exception as exc:
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
            if self.provider == "postgres":
                query = "SELECT symbol, trade_date::text AS date, open, high, low, close, volume, amount, turnover_rate FROM quant.daily_klines WHERE symbol = %s ORDER BY trade_date ASC LIMIT %s"
            else:
                query = "SELECT symbol, date, open, high, low, close, volume, amount, turnover_rate FROM daily_klines WHERE symbol = ? ORDER BY date ASC LIMIT ?"
            return pd.read_sql_query(query, connection, params=(symbol, limit))
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch klines: {exc}") from exc

    def get_recent_klines(self, symbol: str, limit: int = 20):
        """Return latest K-line rows in descending date order for technical calculations."""
        import pandas as pd
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                query = """
                    SELECT volume, amount, turnover_rate
                    FROM quant.daily_klines
                    WHERE symbol = %s
                    ORDER BY trade_date DESC
                    LIMIT %s
                """
            else:
                query = """
                    SELECT volume, amount, turnover_rate
                    FROM daily_klines
                    WHERE symbol = ?
                    ORDER BY date DESC
                    LIMIT ?
                """
            return pd.read_sql_query(query, connection, params=(symbol, limit))
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch recent klines for {symbol}: {exc}") from exc

    def update_stock_technicals(self, symbol: str, metrics: Dict[str, Any]) -> None:
        """Persist stock-level technical summary metrics."""
        connection = self._get_connection()
        params = (
            metrics.get("avg_turnover_rate"),
            metrics.get("avg_volume"),
            metrics.get("avg_amount"),
            symbol,
        )
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                try:
                    cursor.execute(
                        """
                        UPDATE quant.stocks
                        SET avg_turnover_rate = %s,
                            avg_volume = %s,
                            avg_amount = %s
                        WHERE symbol = %s
                        """,
                        params,
                    )
                    connection.commit()
                finally:
                    cursor.close()
            else:
                connection.execute(
                    """
                    UPDATE stocks
                    SET avg_turnover_rate = ?,
                        avg_volume = ?,
                        avg_amount = ?
                    WHERE symbol = ?
                    """,
                    params,
                )
                connection.commit()
        except Exception as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to update technicals for {symbol}: {exc}") from exc

    def upsert_factor_values(self, records: List[tuple[Any, ...]]) -> int:
        """Insert or replace factor values."""
        if not records:
            return 0

        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                try:
                    cursor.executemany(
                        """
                        INSERT INTO quant.factor_values (symbol, factor_date, factor_name, factor_value)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT(symbol, factor_date, factor_name) DO UPDATE SET
                            factor_value = excluded.factor_value
                        """,
                        records,
                    )
                    connection.commit()
                finally:
                    cursor.close()
            else:
                connection.executemany(
                    """
                    INSERT OR REPLACE INTO factor_values (symbol, date, factor_name, factor_value)
                    VALUES (?, ?, ?, ?)
                    """,
                    records,
                )
                connection.commit()
            return len(records)
        except Exception as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to upsert factor values: {exc}") from exc

    def replace_factor_values_for_dates(self, records: List[tuple[Any, ...]]) -> int:
        """Replace factor values for the symbol/date pairs present in records."""
        if not records:
            return 0

        connection = self._get_connection()
        keys = sorted({(str(symbol), str(date)) for symbol, date, *_ in records})
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                try:
                    cursor.executemany(
                        "DELETE FROM quant.factor_values WHERE symbol = %s AND factor_date = %s",
                        keys,
                    )
                finally:
                    cursor.close()
            else:
                connection.executemany(
                    "DELETE FROM factor_values WHERE symbol = ? AND date = ?",
                    keys,
                )
            return self.upsert_factor_values(records)
        except Exception as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to replace factor values: {exc}") from exc

    def get_factor_stats(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Return aggregate factor table statistics."""
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                if date:
                    cursor.execute(
                        """
                        SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT factor_name), COUNT(*),
                               COUNT(DISTINCT factor_date),
                               MIN(factor_date)::text, MAX(factor_date)::text
                        FROM quant.factor_values
                        WHERE factor_date = %s
                        """,
                        (date,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT factor_name), COUNT(*),
                               COUNT(DISTINCT factor_date),
                               MIN(factor_date)::text, MAX(factor_date)::text
                        FROM quant.factor_values
                        """
                    )
                row = cursor.fetchone()
                cursor.close()
            else:
                if date:
                    row = connection.execute(
                        """
                        SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT factor_name), COUNT(*),
                               COUNT(DISTINCT date),
                               MIN(date), MAX(date)
                        FROM factor_values
                        WHERE date = ?
                        """,
                        (date,),
                    ).fetchone()
                else:
                    row = connection.execute(
                        """
                        SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT factor_name), COUNT(*),
                               COUNT(DISTINCT date),
                               MIN(date), MAX(date)
                        FROM factor_values
                        """
                    ).fetchone()

            return {
                "stocks": int(row[0]) if row and row[0] is not None else 0,
                "factors": int(row[1]) if row and row[1] is not None else 0,
                "records": int(row[2]) if row and row[2] is not None else 0,
                "dates": int(row[3]) if row and row[3] is not None else 0,
                "min_date": row[4] if row else None,
                "max_date": row[5] if row else None,
            }
        except Exception as exc:
            raise RuntimeError(f"Failed to get factor stats: {exc}") from exc

    def get_kline_stats(self) -> Dict[str, Any]:
        """Return aggregate daily K-line table statistics."""
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date)::text, MAX(trade_date)::text
                    FROM quant.daily_klines
                    """
                )
                row = cursor.fetchone()
                cursor.close()
            else:
                row = connection.execute(
                    """
                    SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(date), MAX(date)
                    FROM daily_klines
                    """
                ).fetchone()
            return {
                "records": int(row[0]) if row and row[0] is not None else 0,
                "symbols": int(row[1]) if row and row[1] is not None else 0,
                "min_date": row[2] if row else None,
                "max_date": row[3] if row else None,
            }
        except Exception as exc:
            raise RuntimeError(f"Failed to get kline stats: {exc}") from exc

    def get_latest_kline_date(self) -> Optional[str]:
        """Return the latest available daily kline date."""
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute("SELECT MAX(trade_date)::text FROM quant.daily_klines")
                row = cursor.fetchone()
                cursor.close()
            else:
                row = connection.execute("SELECT MAX(date) FROM daily_klines").fetchone()
            return str(row[0]) if row and row[0] is not None else None
        except Exception as exc:
            raise RuntimeError(f"Failed to get latest kline date: {exc}") from exc

    def get_prev_trading_date(self, date: str) -> Optional[str]:
        """Return the most recent trading date before the given date."""
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT MAX(trade_date)::text FROM quant.daily_klines WHERE trade_date < %s",
                    (date,),
                )
                row = cursor.fetchone()
                cursor.close()
            else:
                row = connection.execute(
                    "SELECT MAX(date) FROM daily_klines WHERE date < ?", (date,)
                ).fetchone()
            return str(row[0]) if row and row[0] is not None else None
        except Exception as exc:
            raise RuntimeError(f"Failed to get prev trading date before {date}: {exc}") from exc

    def get_latest_factor_date_for_symbol(self, symbol: str) -> Optional[str]:
        """Return the latest available factor date for one symbol."""
        normalized_symbol = normalize_symbol(symbol)
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT MAX(factor_date)::text FROM quant.factor_values WHERE symbol = %s",
                    (normalized_symbol,),
                )
                row = cursor.fetchone()
                cursor.close()
            else:
                row = connection.execute(
                    "SELECT MAX(date) FROM factor_values WHERE symbol = ?",
                    (normalized_symbol,),
                ).fetchone()
            return str(row[0]) if row and row[0] is not None else None
        except Exception as exc:
            raise RuntimeError(f"Failed to get latest factor date for {symbol}: {exc}") from exc

    def replace_trading_signals_for_date(
        self,
        signal_date: str,
        signals: List[Dict[str, Any]],
        signal_factors: List[Dict[str, Any]],
        symbols: Optional[List[str]] = None,
    ) -> int:
        """Replace trading signals and their factor details for one date, optionally scoped to symbols."""
        if self.provider not in ("postgres", "sqlite"):
            raise RuntimeError("Trading signal persistence requires PostgreSQL or SQLite")

        normalized_date = str(signal_date)
        normalized_symbols = sorted({normalize_symbol(symbol) for symbol in (symbols or []) if symbol})
        signal_rows = [dict(signal) for signal in signals]
        factor_rows = [dict(factor) for factor in signal_factors]
        signal_by_key = {
            (
                normalize_symbol(str(signal["symbol"])),
                str(signal["signal_date"]),
                str(signal["strategy_name"]),
            ): signal
            for signal in signal_rows
        }

        connection = self._get_connection()
        cursor = connection.cursor()

        # Ensure SQLite tables exist (no-op for postgres)
        self._migrate_sqlite()

        try:
            # Delete old signals for this date
            if self.provider == "postgres":
                if normalized_symbols:
                    cursor.execute(
                        "DELETE FROM quant.trading_signals WHERE signal_date = %s AND symbol = ANY(%s)",
                        (normalized_date, normalized_symbols),
                    )
                else:
                    cursor.execute(
                        "DELETE FROM quant.trading_signals WHERE signal_date = %s",
                        (normalized_date,),
                    )
            else:
                if normalized_symbols:
                    placeholders = ",".join("?" for _ in normalized_symbols)
                    cursor.execute(
                        f"DELETE FROM trading_signals WHERE signal_date = ? AND symbol IN ({placeholders})",
                        (normalized_date, *normalized_symbols),
                    )
                else:
                    cursor.execute(
                        "DELETE FROM trading_signals WHERE signal_date = ?",
                        (normalized_date,),
                    )

            # Insert/update signals
            if signal_rows:
                if self.provider == "postgres":
                    cursor.executemany(
                        """
                        INSERT INTO quant.trading_signals (
                            symbol, signal_date, signal_type, strategy_name,
                            confidence, price, reason, metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(symbol, signal_date, strategy_name) DO UPDATE SET
                            signal_type = excluded.signal_type,
                            confidence = excluded.confidence,
                            price = excluded.price,
                            reason = excluded.reason,
                            metadata = excluded.metadata
                        """,
                        [
                            (
                                normalize_symbol(str(s["symbol"])), str(s["signal_date"]),
                                str(s["signal_type"]), str(s["strategy_name"]),
                                s.get("confidence"), s.get("price"),
                                s.get("reason"), s.get("metadata"),
                            )
                            for s in signal_rows
                        ],
                    )
                else:
                    for s in signal_rows:
                        cursor.execute(
                            """
                            INSERT INTO trading_signals (
                                symbol, signal_date, signal_type, strategy_name,
                                confidence, price, reason, metadata
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(symbol, signal_date, strategy_name) DO UPDATE SET
                                signal_type = excluded.signal_type,
                                confidence = excluded.confidence,
                                price = excluded.price,
                                reason = excluded.reason,
                                metadata = excluded.metadata
                            """,
                            (
                                normalize_symbol(str(s["symbol"])), str(s["signal_date"]),
                                str(s["signal_type"]), str(s["strategy_name"]),
                                s.get("confidence"), s.get("price"),
                                s.get("reason"), s.get("metadata"),
                            ),
                        )

            # Fetch inserted signal IDs
            inserted_ids: Dict[tuple[str, str, str], int] = {}
            if signal_rows:
                if self.provider == "postgres":
                    if normalized_symbols:
                        cursor.execute(
                            "SELECT id, symbol, signal_date::text, strategy_name FROM quant.trading_signals "
                            "WHERE signal_date = %s AND symbol = ANY(%s)",
                            (normalized_date, normalized_symbols),
                        )
                    else:
                        cursor.execute(
                            "SELECT id, symbol, signal_date::text, strategy_name FROM quant.trading_signals "
                            "WHERE signal_date = %s",
                            (normalized_date,),
                        )
                    for row in cursor.fetchall():
                        key = (normalize_symbol(str(row[1])), str(row[2]), str(row[3]))
                        if key in signal_by_key:
                            inserted_ids[key] = int(row[0])
                else:
                    if normalized_symbols:
                        placeholders = ",".join("?" for _ in normalized_symbols)
                        cursor.execute(
                            f"SELECT id, symbol, signal_date, strategy_name FROM trading_signals "
                            f"WHERE signal_date = ? AND symbol IN ({placeholders})",
                            (normalized_date, *normalized_symbols),
                        )
                    else:
                        cursor.execute(
                            "SELECT id, symbol, signal_date, strategy_name FROM trading_signals "
                            "WHERE signal_date = ?",
                            (normalized_date,),
                        )
                    for row in cursor.fetchall():
                        key = (normalize_symbol(str(row["symbol"])), str(row["signal_date"]), str(row["strategy_name"]))
                        if key in signal_by_key:
                            inserted_ids[key] = int(row["id"])

            # Insert signal factors
            factor_payload = []
            for factor in factor_rows:
                key = (
                    normalize_symbol(str(factor["symbol"])),
                    str(factor["signal_date"]),
                    str(factor["strategy_name"]),
                )
                signal_id = inserted_ids.get(key)
                if signal_id is None:
                    continue
                factor_payload.append(
                    (
                        signal_id,
                        str(factor["factor_name"]),
                        factor.get("factor_value"),
                        factor.get("factor_weight"),
                        factor.get("trigger_condition"),
                        bool(factor.get("is_primary", False)),
                    )
                )

            if factor_payload:
                if self.provider == "postgres":
                    cursor.executemany(
                        "INSERT INTO quant.signal_factors (signal_id, factor_name, factor_value, factor_weight, trigger_condition, is_primary) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        factor_payload,
                    )
                else:
                    cursor.executemany(
                        "INSERT INTO signal_factors (signal_id, factor_name, factor_value, factor_weight, trigger_condition, is_primary) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        factor_payload,
                    )

            connection.commit()
            return len(signal_rows)
        except Exception as exc:
            connection.rollback()
            raise RuntimeError(f"Failed to replace trading signals for {signal_date}: {exc}") from exc
        finally:
            cursor.close()

    def get_trading_signals(
        self,
        date: Optional[str] = None,
        signal_type: Optional[str] = None,
        min_confidence: float = 0.0,
        strategy_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return trading signals joined with stock names and ordered by confidence/date."""
        if self.provider not in ("postgres", "sqlite"):
            raise RuntimeError("Trading signal queries require PostgreSQL or SQLite")

        connection = self._get_connection()
        clauses = []
        params: List[Any] = []

        if date:
            clauses.append("ts.signal_date = %s")
            params.append(date)
        if signal_type:
            clauses.append("ts.signal_type = %s")
            params.append(str(signal_type).upper())
        clauses.append("ts.confidence >= %s")
        params.append(float(min_confidence))
        if strategy_name:
            clauses.append("ts.strategy_name = %s")
            params.append(strategy_name)

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_clause = ""
        if limit is not None:
            limit_clause = " LIMIT %s"
            params.append(int(limit))

        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                SELECT
                    ts.id,
                    ts.symbol,
                    COALESCE(st.name, '') AS name,
                    ts.signal_date::text,
                    ts.signal_type,
                    ts.strategy_name,
                    ts.confidence,
                    ts.price,
                    ts.reason,
                    ts.metadata,
                    ts.created_at::text
                FROM quant.trading_signals ts
                LEFT JOIN quant.stocks st ON st.symbol = ts.symbol
                {where_clause}
                ORDER BY ts.signal_date DESC, ts.confidence DESC, ts.symbol ASC, ts.strategy_name ASC
                {limit_clause}
                """,
                tuple(params),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": int(row[0]),
                    "symbol": str(row[1]),
                    "name": str(row[2] or ""),
                    "date": str(row[3]),
                    "signal": str(row[4]),
                    "strategy": str(row[5]),
                    "strategy_name": str(row[5]),
                    "confidence": float(row[6]) if row[6] is not None else 0.0,
                    "price": float(row[7]) if row[7] is not None else 0.0,
                    "reason": row[8],
                    "metadata": row[9],
                    "timestamp": row[10],
                }
                for row in rows
            ]
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch trading signals: {exc}") from exc
        finally:
            cursor.close()

    def get_signal_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Return recent trading signals for dashboard/history use."""
        if self.provider not in ("postgres", "sqlite"):
            raise RuntimeError("Trading signal queries require PostgreSQL or SQLite")

        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    ts.id,
                    ts.symbol,
                    COALESCE(st.name, '') AS name,
                    ts.signal_date::text,
                    ts.signal_type,
                    ts.strategy_name,
                    ts.confidence,
                    ts.price,
                    ts.reason,
                    ts.metadata,
                    ts.created_at::text
                FROM quant.trading_signals ts
                LEFT JOIN quant.stocks st ON st.symbol = ts.symbol
                WHERE ts.signal_date >= (
                    COALESCE((SELECT MAX(signal_date) FROM quant.trading_signals), CURRENT_DATE) - (%s::int - 1) * INTERVAL '1 day'
                )
                ORDER BY ts.signal_date DESC, ts.confidence DESC, ts.symbol ASC, ts.strategy_name ASC
                """,
                (max(int(days), 1),),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": int(row[0]),
                    "symbol": str(row[1]),
                    "name": str(row[2] or ""),
                    "date": str(row[3]),
                    "signal": str(row[4]),
                    "strategy": str(row[5]),
                    "strategy_name": str(row[5]),
                    "confidence": float(row[6]) if row[6] is not None else 0.0,
                    "price": float(row[7]) if row[7] is not None else 0.0,
                    "reason": row[8],
                    "metadata": row[9],
                    "timestamp": row[10],
                }
                for row in rows
            ]
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch signal history: {exc}") from exc
        finally:
            cursor.close()

    def get_trading_dates(self, days: int) -> List[str]:
        """Return recent distinct trading dates in ascending order."""
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT DISTINCT trade_date::text
                    FROM quant.daily_klines
                    ORDER BY trade_date DESC
                    LIMIT %s
                    """,
                    (days,),
                )
                rows = cursor.fetchall()
                cursor.close()
            else:
                rows = connection.execute(
                    """
                    SELECT DISTINCT date
                    FROM daily_klines
                    ORDER BY date DESC
                    LIMIT ?
                    """,
                    (days,),
                ).fetchall()
            return sorted(str(row[0]) for row in rows)
        except Exception as exc:
            raise RuntimeError(f"Failed to get trading dates: {exc}") from exc

    def get_symbols_with_kline_count(self, min_count: int = 60) -> List[str]:
        """Return symbols with at least min_count daily kline rows."""
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT symbol
                    FROM quant.daily_klines
                    GROUP BY symbol
                    HAVING COUNT(*) >= %s
                    ORDER BY symbol
                    """,
                    (min_count,),
                )
                rows = cursor.fetchall()
                cursor.close()
            else:
                rows = connection.execute(
                    """
                    SELECT symbol
                    FROM daily_klines
                    GROUP BY symbol
                    HAVING COUNT(*) >= ?
                    ORDER BY symbol
                    """,
                    (min_count,),
                ).fetchall()
            return [str(row[0]) for row in rows]
        except Exception as exc:
            raise RuntimeError(f"Failed to get symbols with kline count: {exc}") from exc

    def get_stock_klines_until_date(self, symbol: str, end_date: str, limit: int = 100):
        """Return latest K-line rows up to end_date in ascending date order."""
        import pandas as pd
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                query = """
                    SELECT trade_date::text AS date, open, high, low, close, volume, amount
                    FROM quant.daily_klines
                    WHERE symbol = %s AND trade_date <= %s
                    ORDER BY trade_date DESC
                    LIMIT %s
                """
                params = (symbol, end_date, limit)
            else:
                query = """
                    SELECT date, open, high, low, close, volume, amount
                    FROM daily_klines
                    WHERE symbol = ? AND date <= ?
                    ORDER BY date DESC
                    LIMIT ?
                """
                params = (symbol, end_date, limit)
            frame = pd.read_sql_query(query, connection, params=params)
            if frame.empty:
                return frame
            return frame.sort_values("date").reset_index(drop=True)
        except Exception as exc:
            raise RuntimeError(f"Failed to get stock klines until {end_date} for {symbol}: {exc}") from exc

    def get_klines_between(self, symbol: str, start_date: str, end_date: str):
        """Return OHLCV rows between dates for backtesting."""
        import pandas as pd
        normalized_symbol = normalize_symbol(symbol)
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                query = """
                    SELECT trade_date::text AS timestamp, symbol, open, high, low, close, volume
                    FROM quant.daily_klines
                    WHERE symbol = %s AND trade_date >= %s AND trade_date <= %s
                    ORDER BY trade_date ASC
                """
                params = (normalized_symbol, start_date, end_date)
            else:
                query = """
                    SELECT date AS timestamp, symbol, open, high, low, close, volume
                    FROM daily_klines
                    WHERE symbol = ? AND date >= ? AND date <= ?
                    ORDER BY date ASC
                """
                params = (normalized_symbol, start_date, end_date)
            return pd.read_sql_query(query, connection, params=params)
        except Exception as exc:
            raise RuntimeError(f"Failed to get klines between dates for {symbol}: {exc}") from exc

    def get_backtest_klines(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ):
        """Return OHLCVA rows for script-level strategy backtests."""
        import pandas as pd

        normalized_symbol = normalize_symbol(symbol)
        connection = self._get_connection()

        try:
            if self.provider == "postgres":
                date_column = "trade_date"
                placeholder = "%s"
                query = """
                    SELECT trade_date::text AS timestamp, symbol, open, high, low, close, volume, amount
                    FROM quant.daily_klines
                    WHERE symbol = %s
                """
            else:
                date_column = "date"
                placeholder = "?"
                query = """
                    SELECT date AS timestamp, symbol, open, high, low, close, volume, amount
                    FROM daily_klines
                    WHERE symbol = ?
                """

            params: list[Any] = [normalized_symbol]
            if start_date:
                query += f" AND {date_column} >= {placeholder}"
                params.append(start_date)
            if end_date:
                query += f" AND {date_column} <= {placeholder}"
                params.append(end_date)

            if limit:
                query += f" ORDER BY {date_column} DESC LIMIT {placeholder}"
                params.append(limit)
                frame = pd.read_sql_query(query, connection, params=tuple(params))
                if frame.empty:
                    return frame
                return frame.sort_values("timestamp").reset_index(drop=True)

            if start_date or end_date:
                query += f" ORDER BY {date_column} ASC"
                return pd.read_sql_query(query, connection, params=tuple(params))

            raise ValueError("start_date/end_date or limit is required")
        except Exception as exc:
            raise RuntimeError(f"Failed to get backtest klines for {symbol}: {exc}") from exc

    def get_close_for_label(self, symbol: str, date: str, direction: str) -> Optional[float]:
        """Return nearest close for ML return labeling."""
        normalized_symbol = normalize_symbol(symbol)
        connection = self._get_connection()
        if direction not in {"forward", "backward"}:
            raise ValueError("direction must be 'forward' or 'backward'")

        comparator = ">=" if direction == "forward" else "<="
        order = "ASC" if direction == "forward" else "DESC"
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    f"""
                    SELECT close
                    FROM quant.daily_klines
                    WHERE symbol = %s AND trade_date {comparator} %s
                    ORDER BY trade_date {order}
                    LIMIT 1
                    """,
                    (normalized_symbol, date),
                )
                row = cursor.fetchone()
                cursor.close()
            else:
                row = connection.execute(
                    f"""
                    SELECT close
                    FROM daily_klines
                    WHERE symbol = ? AND date {comparator} ?
                    ORDER BY date {order}
                    LIMIT 1
                    """,
                    (normalized_symbol, date),
                ).fetchone()
            return float(row[0]) if row and row[0] is not None else None
        except Exception as exc:
            raise RuntimeError(f"Failed to get close for {symbol} on {date}: {exc}") from exc

    def get_factor_values(self, symbol: str, date: str) -> Dict[str, Any]:
        """Return factor values for one symbol/date."""
        normalized_symbol = normalize_symbol(symbol)
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT factor_name, factor_value
                    FROM quant.factor_values
                    WHERE symbol = %s AND factor_date = %s
                    """,
                    (normalized_symbol, date),
                )
                rows = cursor.fetchall()
                cursor.close()
            else:
                rows = connection.execute(
                    """
                    SELECT factor_name, factor_value
                    FROM factor_values
                    WHERE symbol = ? AND date = ?
                    """,
                    (normalized_symbol, date),
                ).fetchall()
            return {str(row[0]): row[1] for row in rows}
        except Exception as exc:
            raise RuntimeError(f"Failed to get factor values for {symbol} on {date}: {exc}") from exc

    def get_price_on_date(self, symbol: str, date: str) -> Optional[Dict[str, Any]]:
        """Return OHLCV price data for one symbol/date."""
        normalized_symbol = normalize_symbol(symbol)
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                cursor = connection.cursor()
                cursor.execute(
                    """
                    SELECT open, high, low, close, volume
                    FROM quant.daily_klines
                    WHERE symbol = %s AND trade_date = %s
                    """,
                    (normalized_symbol, date),
                )
                row = cursor.fetchone()
                cursor.close()
            else:
                row = connection.execute(
                    """
                    SELECT open, high, low, close, volume
                    FROM daily_klines
                    WHERE symbol = ? AND date = ?
                    """,
                    (normalized_symbol, date),
                ).fetchone()

            if not row:
                return None
            return {
                "open": row[0],
                "high": row[1],
                "low": row[2],
                "close": row[3],
                "volume": row[4],
            }
        except Exception as exc:
            raise RuntimeError(f"Failed to get price for {symbol} on {date}: {exc}") from exc

    def load_model_training_frames(self, cutoff_date: str):
        """Return kline and factor frames used by ML retraining."""
        import pandas as pd
        connection = self._get_connection()
        try:
            if self.provider == "postgres":
                klines_query = """
                    SELECT symbol, trade_date::text AS date, open, high, low, close, volume, amount, turnover_rate
                    FROM quant.daily_klines
                    WHERE trade_date >= %s
                    ORDER BY symbol, trade_date
                """
                factors_query = """
                    SELECT symbol, factor_date::text AS date, factor_name, factor_value
                    FROM quant.factor_values
                    WHERE factor_date >= %s
                    ORDER BY symbol, factor_date, factor_name
                """
            else:
                klines_query = """
                    SELECT symbol, date, open, high, low, close, volume, amount, turnover_rate
                    FROM daily_klines
                    WHERE date >= ?
                    ORDER BY symbol, date
                """
                factors_query = """
                    SELECT symbol, date, factor_name, factor_value
                    FROM factor_values
                    WHERE date >= ?
                    ORDER BY symbol, date, factor_name
                """

            klines_df = pd.read_sql_query(klines_query, connection, params=(cutoff_date,))
            factors_df = pd.read_sql_query(factors_query, connection, params=(cutoff_date,))
            return klines_df, factors_df
        except Exception as exc:
            raise RuntimeError(f"Failed to load model training frames since {cutoff_date}: {exc}") from exc

    def load_confidence_calibration_frames(self, factor_names: List[str], lookback_days: Optional[int] = None):
        """Return price and factor frames used by confidence calibration."""
        import pandas as pd

        if not factor_names:
            raise ValueError("factor_names is required")
        if lookback_days is not None and lookback_days <= 0:
            raise ValueError("lookback_days must be positive")

        connection = self._get_connection()
        try:
            placeholders = ", ".join(["%s" if self.provider == "postgres" else "?"] * len(factor_names))
            if self.provider == "postgres":
                cursor = connection.cursor()
                if lookback_days:
                    cursor.execute(
                        """
                        SELECT (MAX(factor_date) - (%s::int - 1) * INTERVAL '1 day')::date::text,
                               MAX(factor_date)::text
                        FROM quant.factor_values
                        """,
                        (lookback_days,),
                    )
                else:
                    cursor.execute("SELECT MIN(factor_date)::text, MAX(factor_date)::text FROM quant.factor_values")
                row = cursor.fetchone()
                cursor.close()

                klines_query = """
                    SELECT symbol, trade_date::text AS date, close
                    FROM quant.daily_klines
                    WHERE trade_date >= %s AND trade_date <= %s
                    ORDER BY symbol, trade_date
                """
                factors_query = f"""
                    SELECT symbol, factor_date::text AS date, factor_name, factor_value
                    FROM quant.factor_values
                    WHERE factor_date >= %s AND factor_date <= %s
                      AND factor_name IN ({placeholders})
                    ORDER BY symbol, factor_date
                """
            else:
                if lookback_days:
                    row = connection.execute(
                        """
                        SELECT date(MAX(date), '-' || (? - 1) || ' day'), MAX(date)
                        FROM factor_values
                        """,
                        (lookback_days,),
                    ).fetchone()
                else:
                    row = connection.execute("SELECT MIN(date), MAX(date) FROM factor_values").fetchone()

                klines_query = """
                    SELECT symbol, date, close
                    FROM daily_klines
                    WHERE date >= ? AND date <= ?
                    ORDER BY symbol, date
                """
                factors_query = f"""
                    SELECT symbol, date, factor_name, factor_value
                    FROM factor_values
                    WHERE date >= ? AND date <= ?
                      AND factor_name IN ({placeholders})
                    ORDER BY symbol, date
                """

            min_date = row[0] if row else None
            max_date = row[1] if row else None
            if not min_date or not max_date:
                raise ValueError("factor_values 表为空")

            klines_df = pd.read_sql_query(klines_query, connection, params=(min_date, max_date))
            factors_df = pd.read_sql_query(factors_query, connection, params=(min_date, max_date, *factor_names))
            return str(min_date), str(max_date), klines_df, factors_df
        except Exception as exc:
            raise RuntimeError(f"Failed to load confidence calibration frames: {exc}") from exc

    def close(self) -> None:
        """Close the database connection safely."""
        if self.conn is None:
            return

        try:
            self.conn.close()
        except Exception as exc:
            raise RuntimeError(f"Failed to close database connection: {exc}") from exc
        finally:
            self.conn = None
