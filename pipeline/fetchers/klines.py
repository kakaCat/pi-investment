"""Daily kline fetcher for persisted stock symbols."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

try:
    import akshare as ak
except ImportError:
    class _AkShareUnavailable:
        """Fallback stub that preserves patchable attributes in tests."""

        @staticmethod
        def stock_zh_a_hist(**_: Any) -> pd.DataFrame:
            """Raise a clear error when AkShare is unavailable."""
            raise ImportError("akshare is required to fetch A-share kline data")

        @staticmethod
        def stock_hk_hist(**_: Any) -> pd.DataFrame:
            """Raise a clear error when AkShare is unavailable."""
            raise ImportError("akshare is required to fetch Hong Kong kline data")

    ak = _AkShareUnavailable()

try:
    from pipeline.db import Database
except ImportError:  # pragma: no cover - allows script-relative imports
    from db import Database


class KlineFetcher:
    """Fetch and persist recent daily kline data for tracked symbols."""

    _DEFAULT_BATCH_SIZE = 50

    def __init__(self, db: Database) -> None:
        """Store the database dependency used for reads and writes."""
        self.db = db

    def run(self, symbols: list[str] | None = None, days: int = 730, market: str | None = None) -> None:
        """Batch update recent daily klines for the requested symbols."""
        target_symbols = symbols or self.db.get_all_symbols(market)
        total = len(target_symbols)
        success = 0

        print(f"[Klines] 开始更新 {total} 只股票的K线数据...")

        for index, symbol in enumerate(target_symbols, start=1):
            try:
                count = self._update_symbol(symbol, days)
                success += 1
                print(f"[{index}/{total}] {symbol} 更新 {count} 条")
            except Exception as exc:
                print(f"[{index}/{total}] {symbol} 失败: {exc}")

        print(f"[Klines] 完成，成功 {success}/{total}")

    def _update_symbol(self, symbol: str, days: int) -> int:
        """Fetch one symbol's recent daily history and upsert it into SQLite."""
        market = self._resolve_market(symbol)
        frame = self._fetch_history(symbol=symbol, market=market, days=days)
        if frame.empty:
            return 0

        connection = self.db._get_connection()
        rows = [
            (
                symbol,
                self._require_value(row, "日期"),
                self._to_float(row.get("开盘")),
                self._to_float(row.get("最高")),
                self._to_float(row.get("最低")),
                self._to_float(row.get("收盘")),
                self._to_float(row.get("成交量")),
                self._to_float(row.get("成交额")),
            )
            for _, row in frame.iterrows()
        ]

        try:
            connection.executemany(
                """
                INSERT OR REPLACE INTO daily_klines
                (symbol, date, open, high, low, close, volume, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()
            return len(rows)
        except sqlite3.Error as exc:
            connection.rollback()
            raise RuntimeError(f"{symbol} K线写入数据库失败: {exc}") from exc

    def _fetch_history(self, symbol: str, market: str, days: int) -> pd.DataFrame:
        """Fetch the symbol's daily kline history for the requested date range."""
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        fetch_fn = ak.stock_hk_hist if market == "HK" else ak.stock_zh_a_hist
        return fetch_fn(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )

    def _resolve_market(self, symbol: str) -> str:
        """Read the symbol market from SQLite and fall back to a simple heuristic."""
        try:
            connection = self.db._get_connection()
            row = connection.execute(
                "SELECT market FROM stocks WHERE symbol = ?",
                (symbol,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise RuntimeError(f"查询 {symbol} 市场类型失败: {exc}") from exc

        if row and row[0]:
            return str(row[0]).upper()

        return "HK" if len(symbol.strip()) <= 5 else "A"

    def _require_value(self, row: pd.Series, field_name: str) -> str:
        """Return a required text value from one AkShare row."""
        value = row.get(field_name)
        if value is None or pd.isna(value):
            raise RuntimeError(f"K线数据缺少必需字段: {field_name}")
        return str(value)

    def _to_float(self, value: Any) -> float | None:
        """Convert numeric-like values into floats while preserving missing values."""
        if value is None or pd.isna(value):
            return None
        return float(value)
