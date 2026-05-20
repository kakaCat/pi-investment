"""AkShare data adapter implementation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

import pandas as pd

try:
    import akshare as ak
except ImportError:
    class _AkShareUnavailable:
        """Fallback stub when AkShare is unavailable."""

        @staticmethod
        def stock_zh_a_hist(**_: Any) -> pd.DataFrame:
            raise ImportError("akshare is required to fetch A-share data")

        @staticmethod
        def stock_zh_a_hist_tx(**_: Any) -> pd.DataFrame:
            raise ImportError("akshare is required to fetch A-share data")

        @staticmethod
        def stock_hk_hist(**_: Any) -> pd.DataFrame:
            raise ImportError("akshare is required to fetch Hong Kong data")

        @staticmethod
        def stock_zh_a_spot_em(**_: Any) -> pd.DataFrame:
            raise ImportError("akshare is required to fetch A-share spot data")

        @staticmethod
        def stock_hk_spot_em(**_: Any) -> pd.DataFrame:
            raise ImportError("akshare is required to fetch Hong Kong spot data")

    ak = _AkShareUnavailable()

from quantsys.data.data.sources.base_adapter import BaseDataAdapter


class AkShareAdapter(BaseDataAdapter):
    """AkShare data source adapter.

    Provides unified interface to fetch stock data from AkShare library.
    Supports both A-share and Hong Kong markets.
    """

    # Column mapping from AkShare to standard format
    COLUMN_MAP_EASTMONEY = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "涨跌幅": "change_pct",
        "涨跌额": "change",
        "换手率": "turnover_rate",
    }

    COLUMN_MAP_TENCENT = {
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "amount": "amount",
    }

    def __init__(self, retry_count: int = 2, timeout: int = 10):
        """Initialize AkShare adapter.

        Args:
            retry_count: Number of retries on failure
            timeout: Request timeout in seconds
        """
        self.retry_count = retry_count
        self.timeout = timeout

    def fetch_daily_klines(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """Fetch daily K-line data from AkShare.

        Args:
            symbol: Stock symbol
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            adjust: "qfq" (forward), "hfq" (backward), "" (none)

        Returns:
            DataFrame with standardized columns

        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If data fetch fails
        """
        if not self.validate_date_format(start_date):
            raise ValueError(f"Invalid start_date format: {start_date}. Expected YYYYMMDD")

        if not self.validate_date_format(end_date):
            raise ValueError(f"Invalid end_date format: {end_date}. Expected YYYYMMDD")

        if adjust not in ["qfq", "hfq", ""]:
            raise ValueError(f"Invalid adjust type: {adjust}. Must be 'qfq', 'hfq', or ''")

        market = self.resolve_market(symbol)

        if market == "HK":
            return self._fetch_hk_klines(symbol, start_date, end_date, adjust)
        else:
            return self._fetch_a_share_klines(symbol, start_date, end_date, adjust)

    def _fetch_a_share_klines(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        """Fetch A-share K-line data with fallback strategy.

        Priority: East Money API -> Tencent API
        """
        # Try East Money first (preferred, has more data)
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            return self.normalize_columns(df, self.COLUMN_MAP_EASTMONEY)
        except Exception as exc:
            # Fall back to Tencent API
            try:
                tx_symbol = self._to_tx_symbol(symbol)
                df = ak.stock_zh_a_hist_tx(
                    symbol=tx_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                )
                return self.normalize_columns(df, self.COLUMN_MAP_TENCENT)
            except Exception as tx_exc:
                raise RuntimeError(
                    f"Failed to fetch A-share data for {symbol}: "
                    f"EastMoney error: {exc}, Tencent error: {tx_exc}"
                ) from tx_exc

    def _fetch_hk_klines(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame:
        """Fetch Hong Kong stock K-line data."""
        try:
            df = ak.stock_hk_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            return self.normalize_columns(df, self.COLUMN_MAP_EASTMONEY)
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch HK data for {symbol}: {exc}") from exc

    def fetch_stock_list(self, market: str = "A") -> pd.DataFrame:
        """Fetch list of all stocks in a market.

        Args:
            market: "A" for A-share, "HK" for Hong Kong

        Returns:
            DataFrame with columns: symbol, name, market, industry, list_date

        Raises:
            ValueError: If market type is invalid
            RuntimeError: If data fetch fails
        """
        if market not in ["A", "HK"]:
            raise ValueError(f"Invalid market: {market}. Must be 'A' or 'HK'")

        try:
            if market == "A":
                df = ak.stock_zh_a_spot_em()
                # Map columns
                result = pd.DataFrame({
                    "symbol": df["代码"],
                    "name": df["名称"],
                    "market": "A",
                    "industry": df.get("行业", None),
                    "list_date": None,  # Not available in spot data
                })
            else:  # HK
                df = ak.stock_hk_spot_em()
                result = pd.DataFrame({
                    "symbol": df["代码"],
                    "name": df["名称"],
                    "market": "HK",
                    "industry": None,
                    "list_date": None,
                })

            return result
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch {market} stock list: {exc}") from exc

    def fetch_realtime_quote(self, symbol: str) -> dict:
        """Fetch real-time quote for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with quote data

        Raises:
            RuntimeError: If data fetch fails
        """
        market = self.resolve_market(symbol)

        try:
            if market == "A":
                df = ak.stock_zh_a_spot_em()
                row = df[df["代码"] == symbol]
            else:
                df = ak.stock_hk_spot_em()
                row = df[df["代码"] == symbol]

            if row.empty:
                raise RuntimeError(f"Symbol {symbol} not found in {market} market")

            row = row.iloc[0]
            return {
                "symbol": symbol,
                "name": str(row["名称"]),
                "price": float(row["最新价"]),
                "change": float(row.get("涨跌额", 0)),
                "change_pct": float(row.get("涨跌幅", 0)),
                "volume": float(row.get("成交量", 0)),
                "amount": float(row.get("成交额", 0)),
            }
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch realtime quote for {symbol}: {exc}") from exc

    def _to_tx_symbol(self, symbol: str) -> str:
        """Convert symbol to Tencent format (with exchange prefix).

        Args:
            symbol: 6-digit stock code

        Returns:
            Symbol with exchange prefix (e.g., "sz000001", "sh600000")
        """
        prefix = self.get_exchange_prefix(symbol)
        return f"{prefix}{symbol}"

    def fetch_klines_batch(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> dict[str, pd.DataFrame]:
        """Fetch K-line data for multiple symbols.

        Args:
            symbols: List of stock symbols
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            adjust: Adjustment type

        Returns:
            Dict mapping symbol to DataFrame
        """
        results = {}
        for symbol in symbols:
            try:
                df = self.fetch_daily_klines(symbol, start_date, end_date, adjust)
                results[symbol] = df
            except Exception as exc:
                print(f"Failed to fetch {symbol}: {exc}")
                results[symbol] = pd.DataFrame()

        return results

    def fetch_recent_klines(
        self,
        symbol: str,
        days: int = 730,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """Fetch recent K-line data for a symbol.

        Args:
            symbol: Stock symbol
            days: Number of days to fetch
            adjust: Adjustment type

        Returns:
            DataFrame with K-line data
        """
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        return self.fetch_daily_klines(symbol, start_date, end_date, adjust)
