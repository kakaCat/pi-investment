"""Daily kline fetcher for persisted stock symbols."""

from __future__ import annotations

from dataclasses import dataclass
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

from quantsys.data.db import Database


@dataclass(frozen=True)
class KlineFetchResult:
    """Summary of one batch kline fetch run."""

    total: int
    succeeded: int
    failed: int
    failures: list[dict[str, str]]


class KlineFetcher:
    """Fetch and persist recent daily kline data for tracked symbols."""

    _DEFAULT_BATCH_SIZE = 50

    def __init__(self, db: Database) -> None:
        """Store the database dependency used for reads and writes."""
        self.db = db

    def run(
        self,
        symbols: list[str] | None = None,
        days: int = 730,
        market: str | None = None,
        period: str = "daily",
    ) -> KlineFetchResult:
        """Batch update recent klines for the requested symbols.

        Args:
            symbols: List of stock symbols to fetch. If None, fetch all symbols.
            days: Number of days to fetch (for daily/weekly/monthly periods)
            market: Market filter ('A', 'HK', etc.)
            period: Period type - 'daily', 'weekly', or 'monthly'
        """
        if period not in ("daily", "weekly", "monthly"):
            raise ValueError(f"period must be 'daily', 'weekly', or 'monthly', got {period}")

        target_symbols = symbols or self.db.get_all_symbols(market)
        total = len(target_symbols)
        success = 0
        failures = []

        period_cn = {"daily": "日线", "weekly": "周线", "monthly": "月线"}[period]
        print(f"[Klines] 开始更新 {total} 只股票的{period_cn}数据...")

        for index, symbol in enumerate(target_symbols, start=1):
            try:
                count = self._update_symbol(symbol, days, period)
                success += 1
                print(f"[{index}/{total}] {symbol} 更新 {count} 条 ({period_cn})")
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})
                print(f"[{index}/{total}] {symbol} 失败: {exc}")

        print(f"[Klines] 完成，成功 {success}/{total}")
        return KlineFetchResult(
            total=total,
            succeeded=success,
            failed=len(failures),
            failures=failures,
        )

    def _update_symbol(self, symbol: str, days: int, period: str = "daily") -> int:
        """Fetch one symbol's recent history and upsert it into the database."""
        market = self._resolve_market(symbol)
        frame = self._fetch_history(symbol=symbol, market=market, days=days, period=period)
        if frame.empty:
            return 0

        # Normalize column names — support both Chinese (East Money) and English (Tencent)
        col_map = {
            "日期": "date", "date": "date",
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
            date_val = row.get("date")
            if date_val is None or pd.isna(date_val):
                raise RuntimeError(f"{symbol} K线数据缺少必需字段: date")
            rows.append(
                {
                    "symbol": symbol,
                    "date": str(date_val),
                    "open": self._to_float(row.get("open")),
                    "high": self._to_float(row.get("high")),
                    "low": self._to_float(row.get("low")),
                    "close": self._to_float(row.get("close")),
                    "volume": self._to_float(row.get("volume")),
                    "amount": self._to_float(row.get("amount")),
                }
            )

        try:
            return self.db.upsert_daily_klines(rows)
        except Exception as exc:
            raise RuntimeError(f"{symbol} K线写入数据库失败: {exc}") from exc

    def _fetch_history(self, symbol: str, market: str, days: int, period: str = "daily") -> pd.DataFrame:
        """Fetch the symbol's kline history for the requested date range and period.

        Priority: East Money (ak.stock_zh_a_hist) -> Tencent (ak.stock_zh_a_hist_tx)
        East Money is preferred because it includes volume/amount columns.

        Note: Tencent source has different column format:
        - 'amount' in Tencent = volume (成交量)
        - No separate amount (成交额) column

        Args:
            symbol: Stock symbol
            market: Market type ('A', 'HK', etc.)
            days: Number of days to fetch
            period: Period type - 'daily', 'weekly', or 'monthly'
        """
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        if market == "HK":
            return ak.stock_hk_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )

        # A-share: try East Money first, fall back to Tencent
        try:
            return ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
        except Exception as exc:
            # Tencent needs sz/sh prefix
            tx_symbol = self._to_tx_symbol(symbol)
            print(f"[Klines] {symbol} 东财接口失败，降级到腾讯源: {exc}")
            df = ak.stock_zh_a_hist_tx(
                symbol=tx_symbol,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
            # Fix Tencent data format: their 'amount' is actually volume
            if 'amount' in df.columns and 'volume' not in df.columns:
                df = df.rename(columns={'amount': 'volume'})
            return df

    @staticmethod
    def _to_tx_symbol(symbol: str) -> str:
        """Add exchange prefix for Tencent API (e.g. 000001 -> sz000001, 600000 -> sh600000)."""
        code = symbol.strip()
        # 北交所: 4, 8, 92 开头 (920xxx 是北交所的新代码)
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

    def _resolve_market(self, symbol: str) -> str:
        """Read the symbol market from the database and fall back to a simple heuristic."""
        try:
            market = self.db.get_market(symbol)
        except Exception as exc:
            raise RuntimeError(f"查询 {symbol} 市场类型失败: {exc}") from exc

        if market:
            return market

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
