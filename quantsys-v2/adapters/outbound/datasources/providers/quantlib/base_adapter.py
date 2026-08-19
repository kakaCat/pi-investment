"""Abstract base class for market data adapters.

Every downstream data source (akshare, tushare, wind, etc.) must implement
this interface so that business logic never depends on a specific vendor API.
When a source changes its API, only the adapter needs updating — the rest of
the system is protected.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class BaseMarketAdapter(ABC):
    """Abstract market data adapter — the anti-corruption layer for third-party sources.

    All methods return standardised Python dicts / lists-of-dicts.  Adapters are
    responsible for:
      * Symbol-format conversion between internal representation and the vendor
      * Mapping vendor column names / JSON keys to the canonical names below
      * Graceful degradation when a source is unavailable (return empty/error
        dict rather than raising)
    """

    # ------------------------------------------------------------------
    # Symbol helpers (shared across adapters)
    # ------------------------------------------------------------------

    @staticmethod
    def internal_to_clean(symbol: str) -> tuple[str, str]:
        """Split internal symbol "000001.SZ" → ("000001", "SZ").

        Returns (code, exchange_suffix) where exchange_suffix is one of
        "SZ", "SH", "HK", or "".
        """
        s = symbol.strip().upper()
        for suffix in (".SZ", ".SH", ".HK"):
            if s.endswith(suffix):
                return s[: -len(suffix)], suffix[1:]
        # No suffix — try to infer from code
        if len(s) == 6 and s.isdigit():
            if s.startswith(("6", "9")):
                return s, "SH"
            return s, "SZ"
        if len(s) <= 5 and s.isdigit():
            return s, "HK"
        return s, ""

    @staticmethod
    def clean_to_internal(code: str, exchange: str = "SZ") -> str:
        """Construct internal symbol from clean parts, e.g. ("000001", "SZ") → "000001.SZ"."""
        return f"{code}.{exchange.upper()}"

    @staticmethod
    def exchange_prefix(code: str) -> str:
        """Return the exchange identifier for a raw 6-digit code: "sh", "sz", "bj"."""
        c = code.strip()
        if c.startswith(("4", "8", "43", "92")):
            return "bj"
        if c.startswith(("6", "9")):
            return "sh"
        if c.startswith(("0", "2", "3")):
            return "sz"
        return "sz"

    @staticmethod
    def internal_to_akshare(symbol: str) -> tuple[str, str]:
        """Convert internal "000001.SZ" to akshare-friendly (code, prefix).

        Returns ("000001", "sz") for Shenzhen, ("600000", "sh") for Shanghai,
        ("00700", "hk") for Hong Kong.
        """
        code, exchange = BaseMarketAdapter.internal_to_clean(symbol)
        if exchange == "HK":
            return code, "hk"
        prefix = BaseMarketAdapter.exchange_prefix(code)
        return code, prefix

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def get_stock_info(self, symbol: str) -> dict:
        """Return stock metadata for *symbol*.

        Canonical keys:
            symbol    – internal symbol (e.g. "000001.SZ")
            name      – Chinese name
            market    – "A" or "HK"
            industry  – industry classification string
            list_date – listing date (YYYY-MM-DD or None)

        Returns an empty dict on failure.
        """
        ...

    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Return OHLCV klines as a list of standardised dicts.

        Each dict:
            {"symbol": str, "date": str (YYYY-MM-DD),
             "open": float, "high": float, "low": float,
             "close": float, "volume": float, "amount": float}

        *period*: "daily" | "weekly" | "monthly"
        *start_date* / *end_date*: YYYYMMDD or YYYY-MM-DD

        Returns an empty list on failure.
        """
        ...

    @abstractmethod
    def get_realtime_quote(self, symbols: list[str]) -> dict:
        """Return real-time quotes keyed by internal symbol.

        Each value:
            {"symbol": str, "name": str, "price": float,
             "change": float, "change_pct": float,
             "volume": float, "amount": float,
             "high": float, "low": float, "open": float,
             "pre_close": float | None}

        Unavailable symbols are omitted from the result.
        """
        ...

    @abstractmethod
    def get_index_data(
        self,
        index_code: str,
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Return OHLCV data for a market index.

        Same dict shape as *get_klines* minus the "amount" key.
        *index_code* examples: "000001" (上证指数), "399001" (深证成指).
        """
        ...

    @abstractmethod
    def get_sector_list(self) -> list[dict]:
        """Return available industry sectors / concept boards.

        Each dict:
            {"code": str, "name": str, "type": "industry" | "concept"}
        """
        ...

    @abstractmethod
    def get_north_flow(
        self,
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Return northbound capital flow (北向资金) history.

        Each dict:
            {"date": str (YYYY-MM-DD), "net_flow": float (亿元)}
        """
        ...

    @abstractmethod
    def get_market_news(self, symbol: str = "", limit: int = 20) -> list[dict]:
        """Return recent market news / announcements for *symbol*.

        If *symbol* is empty, return broad market news.
        Each dict:
            {"title": str, "time": str, "source": str, "url": str}
        """
        ...

    @abstractmethod
    def get_financial_data(self, symbol: str) -> dict:
        """Return financial indicators for *symbol*.

        Canonical keys:
            {"symbol": str, "report_date": str,
             "revenue": float | None, "net_profit": float | None,
             "roe": float | None, "eps": float | None,
             "total_assets": float | None, "total_liabilities": float | None,
             "pe": float | None, "pb": float | None}
        """
        ...

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_date(d: str) -> str:
        """Accept YYYYMMDD or YYYY-MM-DD; always return YYYYMMDD."""
        return d.replace("-", "")

    @staticmethod
    def _normalise_date_display(d: str) -> str:
        """Convert YYYYMMDD → YYYY-MM-DD for standardised output."""
        clean = d.replace("-", "")
        if len(clean) == 8:
            return f"{clean[:4]}-{clean[4:6]}-{clean[6:8]}"
        return d

    @staticmethod
    def _safe_float(value) -> float | None:
        """Coerce *value* to float; return None if it cannot be coerced."""
        if value is None:
            return None
        try:
            v = float(value)
            if v != v:  # NaN check
                return None
            return v
        except (ValueError, TypeError):
            return None
