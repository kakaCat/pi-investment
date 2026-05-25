"""Base data adapter interface for quantitative trading system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import pandas as pd


class BaseDataAdapter(ABC):
    """Abstract base class for data source adapters.

    All data adapters must implement this interface to ensure consistent
    data access patterns across different data sources (akshare, tushare, etc).
    """

    @abstractmethod
    def fetch_daily_klines(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """Fetch daily K-line data for a symbol.

        Args:
            symbol: Stock symbol (e.g., "000001" for A-share, "00700" for HK)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            adjust: Adjustment type - "qfq" (forward), "hfq" (backward), "" (none)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount

        Raises:
            ValueError: If symbol or date format is invalid
            RuntimeError: If data fetch fails
        """
        pass

    @abstractmethod
    def fetch_stock_list(self, market: str = "A") -> pd.DataFrame:
        """Fetch list of all stocks in a market.

        Args:
            market: Market type - "A" for A-share, "HK" for Hong Kong

        Returns:
            DataFrame with columns: symbol, name, market, industry, list_date

        Raises:
            ValueError: If market type is invalid
            RuntimeError: If data fetch fails
        """
        pass

    @abstractmethod
    def fetch_realtime_quote(self, symbol: str) -> dict:
        """Fetch real-time quote for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with keys: symbol, name, price, change, change_pct, volume, amount

        Raises:
            ValueError: If symbol is invalid
            RuntimeError: If data fetch fails
        """
        pass

    def normalize_columns(self, df: pd.DataFrame, column_map: dict) -> pd.DataFrame:
        """Normalize DataFrame column names to standard format.

        Args:
            df: Input DataFrame
            column_map: Mapping from source columns to standard columns

        Returns:
            DataFrame with normalized column names
        """
        renamed = {}
        for col in df.columns:
            if col in column_map:
                renamed[col] = column_map[col]
        return df.rename(columns=renamed)

    def validate_date_format(self, date_str: str) -> bool:
        """Validate date string is in YYYYMMDD format.

        Args:
            date_str: Date string to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            datetime.strptime(date_str, "%Y%m%d")
            return True
        except ValueError:
            return False

    def resolve_market(self, symbol: str) -> str:
        """Resolve market type from symbol format.

        Args:
            symbol: Stock symbol

        Returns:
            "A" for A-share, "HK" for Hong Kong stock
        """
        symbol = symbol.strip()
        # HK stocks typically have 5 digits or less
        if len(symbol) <= 5:
            return "HK"
        # A-share stocks have 6 digits
        return "A"

    def get_exchange_prefix(self, symbol: str) -> str:
        """Get exchange prefix for a symbol (sh/sz/bj).

        Args:
            symbol: Stock symbol (6 digits)

        Returns:
            Exchange prefix: "sh", "sz", or "bj"
        """
        code = symbol.strip()

        # Beijing Stock Exchange: 4, 8, 43, 92 prefix
        if code.startswith(("4", "8", "43", "92")):
            return "bj"

        # Shanghai: 6, 9 prefix (excluding 92)
        if code.startswith(("6", "9")) and not code.startswith("92"):
            return "sh"

        # Shenzhen: 0, 2, 3 prefix
        if code.startswith(("0", "2", "3")):
            return "sz"

        # Default to Shenzhen
        return "sz"
