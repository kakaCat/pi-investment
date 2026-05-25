"""Tushare data adapter implementation."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Optional

import pandas as pd

try:
    import tushare as ts
except ImportError:
    class _TushareUnavailable:
        """Fallback stub when Tushare is unavailable."""

        @staticmethod
        def pro_api(*args, **kwargs):
            raise ImportError("tushare is required. Install with: pip install tushare")

    ts = _TushareUnavailable()

from quantsys.data.data.sources.base_adapter import BaseDataAdapter


class TushareAdapter(BaseDataAdapter):
    """Tushare data source adapter.

    Provides unified interface to fetch stock data from Tushare Pro API.
    Supports A-share market with rate limiting.

    Note: Requires Tushare token. Get one at: https://tushare.pro/register
    Free tier: 200 requests/minute, 2000 requests/day
    """

    # Column mapping from Tushare to standard format
    COLUMN_MAP = {
        "trade_date": "date",
        "ts_code": "symbol",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "vol": "volume",
        "amount": "amount",
        "pct_chg": "change_pct",
        "change": "change",
    }

    def __init__(self, token: str, rate_limit: int = 200):
        """Initialize Tushare adapter.

        Args:
            token: Tushare API token
            rate_limit: Max requests per minute (default 200 for free tier)
        """
        if not token:
            raise ValueError("Tushare token is required")

        self.token = token
        self.rate_limit = rate_limit
        self.request_count = 0
        self.last_reset_time = time.time()

        try:
            self.pro = ts.pro_api(token)
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize Tushare API: {exc}") from exc

    def _check_rate_limit(self):
        """Check and enforce rate limiting."""
        current_time = time.time()
        elapsed = current_time - self.last_reset_time

        # Reset counter every minute
        if elapsed >= 60:
            self.request_count = 0
            self.last_reset_time = current_time

        # Wait if rate limit exceeded
        if self.request_count >= self.rate_limit:
            wait_time = 60 - elapsed
            if wait_time > 0:
                print(f"[Tushare] Rate limit reached, waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                self.request_count = 0
                self.last_reset_time = time.time()

        self.request_count += 1

    def _convert_symbol(self, symbol: str) -> str:
        """Convert symbol to Tushare format (e.g., 000001 -> 000001.SZ).

        Args:
            symbol: Stock symbol (6 digits)

        Returns:
            Tushare format symbol with exchange suffix
        """
        symbol = symbol.strip()

        # Shanghai: 6, 9 prefix
        if symbol.startswith(("6", "9")):
            return f"{symbol}.SH"

        # Shenzhen: 0, 2, 3 prefix
        if symbol.startswith(("0", "2", "3")):
            return f"{symbol}.SZ"

        # Beijing: 4, 8 prefix
        if symbol.startswith(("4", "8")):
            return f"{symbol}.BJ"

        # Default to Shenzhen
        return f"{symbol}.SZ"

    def _parse_symbol(self, ts_code: str) -> str:
        """Parse Tushare symbol to standard format (e.g., 000001.SZ -> 000001).

        Args:
            ts_code: Tushare format symbol

        Returns:
            Standard 6-digit symbol
        """
        return ts_code.split(".")[0] if "." in ts_code else ts_code

    def fetch_daily_klines(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """Fetch daily K-line data for a symbol.

        Args:
            symbol: Stock symbol (e.g., "000001")
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            adjust: Adjustment type - "qfq" (forward), "hfq" (backward), "" (none)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount

        Raises:
            ValueError: If symbol or date format is invalid
            RuntimeError: If data fetch fails
        """
        if not self.validate_date_format(start_date):
            raise ValueError(f"Invalid start_date format: {start_date}, expected YYYYMMDD")
        if not self.validate_date_format(end_date):
            raise ValueError(f"Invalid end_date format: {end_date}, expected YYYYMMDD")

        ts_code = self._convert_symbol(symbol)

        # Map adjust type
        adj_map = {"qfq": "qfq", "hfq": "hfq", "": None}
        adj = adj_map.get(adjust, "qfq")

        self._check_rate_limit()

        try:
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                adj=adj,
            )

            if df is None or df.empty:
                return pd.DataFrame()

            # Normalize columns
            df = self.normalize_columns(df, self.COLUMN_MAP)

            # Parse symbol
            if "symbol" in df.columns:
                df["symbol"] = df["symbol"].apply(self._parse_symbol)
            else:
                df["symbol"] = symbol

            # Convert volume from 手 (100 shares) to shares
            if "volume" in df.columns:
                df["volume"] = df["volume"] * 100

            # Convert amount from 千元 to 元
            if "amount" in df.columns:
                df["amount"] = df["amount"] * 1000

            # Sort by date ascending
            df = df.sort_values("date").reset_index(drop=True)

            # Select standard columns
            standard_cols = ["date", "open", "high", "low", "close", "volume", "amount"]
            available_cols = [col for col in standard_cols if col in df.columns]

            return df[available_cols]

        except Exception as exc:
            raise RuntimeError(f"Failed to fetch data from Tushare for {symbol}: {exc}") from exc

    def fetch_stock_list(self, market: str = "A") -> pd.DataFrame:
        """Fetch list of all stocks in a market.

        Args:
            market: Market type - "A" for A-share (HK not supported by Tushare)

        Returns:
            DataFrame with columns: symbol, name, market, industry, list_date

        Raises:
            ValueError: If market type is invalid
            RuntimeError: If data fetch fails
        """
        if market != "A":
            raise ValueError(f"Tushare only supports A-share market, got: {market}")

        self._check_rate_limit()

        try:
            # Fetch stock basic info
            df = self.pro.stock_basic(
                exchange="",
                list_status="L",  # Listed stocks only
                fields="ts_code,symbol,name,area,industry,market,list_date"
            )

            if df is None or df.empty:
                return pd.DataFrame()

            # Parse symbols
            df["symbol"] = df["ts_code"].apply(self._parse_symbol)

            # Rename columns
            df = df.rename(columns={
                "name": "name",
                "market": "market",
                "industry": "industry",
                "list_date": "list_date",
            })

            # Select standard columns
            result = df[["symbol", "name", "market", "industry", "list_date"]].copy()
            result["market"] = "A"  # All are A-share

            return result

        except Exception as exc:
            raise RuntimeError(f"Failed to fetch stock list from Tushare: {exc}") from exc

    def fetch_realtime_quote(self, symbol: str) -> dict:
        """Fetch real-time quote for a symbol.

        Note: Tushare free tier does not support real-time quotes.
        This method will raise NotImplementedError.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with keys: symbol, name, price, change, change_pct, volume, amount

        Raises:
            NotImplementedError: Real-time quotes require paid Tushare subscription
        """
        raise NotImplementedError(
            "Real-time quotes require Tushare paid subscription. "
            "Use AkShare adapter for free real-time data."
        )
