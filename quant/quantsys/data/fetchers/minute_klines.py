"""Minute-level kline fetcher for intraday stock data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

try:
    import akshare as ak
except ImportError:
    class _AkShareUnavailable:
        """Fallback stub that preserves patchable attributes in tests."""

        @staticmethod
        def stock_zh_a_minute(**_: Any) -> pd.DataFrame:
            """Raise a clear error when AkShare is unavailable."""
            raise ImportError("akshare is required to fetch minute-level kline data")

    ak = _AkShareUnavailable()

from quantsys.data.db import Database


@dataclass(frozen=True)
class MinuteKlineFetchResult:
    """Summary of one batch minute kline fetch run."""

    total: int
    succeeded: int
    failed: int
    failures: list[dict[str, str]]


class MinuteKlineFetcher:
    """Fetch and persist minute-level kline data for tracked symbols."""

    VALID_PERIODS = ['1', '5', '15', '30', '60']

    def __init__(self, db: Database) -> None:
        """Store the database dependency used for reads and writes."""
        self.db = db

    def run(
        self,
        symbols: list[str] | None = None,
        period: str = '1',
        market: str | None = None,
    ) -> MinuteKlineFetchResult:
        """Batch update minute klines for the requested symbols.

        Args:
            symbols: List of stock symbols to fetch. If None, fetch all symbols.
            period: Minute period - one of '1', '5', '15', '30', '60'
            market: Market filter ('A', 'HK', etc.)
        """
        if period not in self.VALID_PERIODS:
            raise ValueError(f"period must be one of {self.VALID_PERIODS}, got {period}")

        target_symbols = symbols or self.db.get_all_symbols(market)
        total = len(target_symbols)
        success = 0
        failures = []

        print(f"[MinuteKlines] 开始更新 {total} 只股票的{period}分钟K线数据...")

        for index, symbol in enumerate(target_symbols, start=1):
            try:
                count = self._update_symbol(symbol, period)
                success += 1
                print(f"[{index}/{total}] {symbol} 更新 {count} 条 ({period}分钟)")
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})
                print(f"[{index}/{total}] {symbol} 失败: {exc}")

        print(f"[MinuteKlines] 完成，成功 {success}/{total}")
        return MinuteKlineFetchResult(
            total=total,
            succeeded=success,
            failed=len(failures),
            failures=failures,
        )

    def _update_symbol(self, symbol: str, period: str) -> int:
        """Fetch one symbol's minute history and upsert it into the database."""
        frame = self._fetch_history(symbol=symbol, period=period)
        if frame.empty:
            return 0

        # Normalize column names
        col_map = {
            "day": "date",
            "时间": "time",
            "开盘": "open", "open": "open",
            "最高": "high", "high": "high",
            "最低": "low", "low": "low",
            "收盘": "close", "close": "close",
            "成交量": "volume", "volume": "volume",
            "成交额": "amount", "amount": "amount",
        }
        renamed = {}
        for col in frame.columns:
            if col in col_map:
                renamed[col] = col_map[col]
        frame = frame.rename(columns=renamed)

        rows = []
        for _, row in frame.iterrows():
            # Combine date and time into timestamp
            date_val = row.get("date")
            time_val = row.get("time")

            if date_val is None or pd.isna(date_val):
                continue

            # Parse timestamp
            if time_val and not pd.isna(time_val):
                ts_str = f"{date_val} {time_val}"
            else:
                ts_str = str(date_val)

            try:
                ts = pd.to_datetime(ts_str)
            except Exception:
                continue

            rows.append(
                {
                    "symbol": symbol,
                    "ts": ts,
                    "open": self._to_float(row.get("open")),
                    "high": self._to_float(row.get("high")),
                    "low": self._to_float(row.get("low")),
                    "close": self._to_float(row.get("close")),
                    "volume": self._to_float(row.get("volume")),
                    "amount": self._to_float(row.get("amount")),
                }
            )

        if not rows:
            return 0

        try:
            return self.db.upsert_minute_klines(rows)
        except Exception as exc:
            raise RuntimeError(f"{symbol} 分钟K线写入数据库失败: {exc}") from exc

    def _fetch_history(self, symbol: str, period: str) -> pd.DataFrame:
        """Fetch the symbol's minute kline history.

        Note: akshare's stock_zh_a_minute only returns recent data (typically last 5 trading days).
        For historical minute data, you may need other data sources.
        """
        # Convert symbol to sina format (e.g., 600519 -> sh600519)
        sina_symbol = self._to_sina_symbol(symbol)

        try:
            return ak.stock_zh_a_minute(
                symbol=sina_symbol,
                period=period,
                adjust="qfq",
            )
        except Exception as exc:
            raise RuntimeError(f"获取{symbol}的{period}分钟K线失败: {exc}") from exc

    @staticmethod
    def _to_sina_symbol(symbol: str) -> str:
        """Add exchange prefix for Sina API (e.g. 000001 -> sz000001, 600000 -> sh600000)."""
        code = symbol.strip()
        # 北交所: 4, 8, 92 开头
        if code.startswith(("4", "8", "92")) or code.startswith("43"):
            return f"bj{code}"
        # 科创板: 688 开头
        if code.startswith("688"):
            return f"sh{code}"
        # 上交所: 6, 9 开头 (不含 92)
        if code.startswith(("6", "9")):
            return f"sh{code}"
        # 深交所: 0, 3, 2 开头
        if code.startswith(("0", "2", "3", "30")):
            return f"sz{code}"
        return f"sz{code}"

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Convert a value to float, returning None for invalid values."""
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
