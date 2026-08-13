"""AKShare market data adapter for Agent OS

Simplified adapter that wraps AKShare API calls and standardizes output format.
Based on quantsys-v2/domain/quantlib/adapters/akshare_adapter.py
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

try:
    import akshare as ak
except ImportError:
    class _AkShareUnavailable:
        """Stub when akshare is not installed."""
        _AK_UNAVAILABLE_MSG = "akshare is not installed — install with: pip install akshare"

        def __getattr__(self, _name: str) -> Any:
            def _raise(*_a: Any, **_kw: Any) -> pd.DataFrame:
                raise ImportError(self._AK_UNAVAILABLE_MSG)
            return _raise

    ak = _AkShareUnavailable()


class AkShareMarketAdapter:
    """AKShare market data adapter"""

    @staticmethod
    def _safe_float(val: Any) -> float:
        """Convert value to float safely"""
        if val is None or pd.isna(val):
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _normalise_date(date_str: str) -> str:
        """Normalize date string to YYYYMMDD format"""
        date_str = date_str.strip().replace("-", "").replace("/", "")
        return date_str[:8]

    @staticmethod
    def _normalise_date_display(date_str: str) -> str:
        """Normalize date to YYYY-MM-DD display format"""
        date_str = date_str.strip().replace("-", "").replace("/", "")
        if len(date_str) >= 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str

    @staticmethod
    def internal_to_akshare(symbol: str) -> tuple[str, str]:
        """Convert internal symbol (600519.SH) to AKShare format"""
        if "." not in symbol:
            return symbol, ""

        code, exchange = symbol.split(".", 1)
        return code, exchange

    @staticmethod
    def internal_to_clean(symbol: str) -> tuple[str, str]:
        """Convert internal symbol to (code, exchange)"""
        if "." not in symbol:
            return symbol, ""
        return symbol.split(".", 1)

    @staticmethod
    def exchange_prefix(code: str) -> str:
        """Get exchange prefix for Tencent format (sz/sh)"""
        if code.startswith(("000", "001", "002", "003", "300")):
            return "sz"
        return "sh"

    @staticmethod
    def _market_char(symbol: str) -> str:
        """Return 'A' or 'HK' for a given internal symbol"""
        _, exchange = AkShareMarketAdapter.internal_to_clean(symbol)
        return "HK" if exchange == "HK" else "A"

    def get_realtime_quote(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch real-time quotes for multiple symbols

        Args:
            symbols: List of internal symbols (e.g., ["600519.SH", "000858.SZ"])

        Returns:
            Dict keyed by symbol with quote data
        """
        if not symbols:
            return {}

        result: Dict[str, Dict] = {}
        a_symbols: set[str] = set()
        hk_symbols: set[str] = set()

        for s in symbols:
            if self._market_char(s) == "HK":
                hk_symbols.add(s)
            else:
                a_symbols.add(s)

        try:
            if a_symbols:
                result.update(self._fetch_a_spot(a_symbols))
        except Exception:
            pass

        try:
            if hk_symbols:
                result.update(self._fetch_hk_spot(hk_symbols))
        except Exception:
            pass

        return result

    def _fetch_a_spot(self, symbols: set[str]) -> Dict[str, Dict]:
        """Query A-share spot market for symbols"""
        df = ak.stock_zh_a_spot_em()
        return self._spot_frame_to_dict(symbols, df, "A")

    def _fetch_hk_spot(self, symbols: set[str]) -> Dict[str, Dict]:
        """Query HK spot market for symbols"""
        df = ak.stock_hk_spot_em()
        return self._spot_frame_to_dict(symbols, df, "HK")

    def _spot_frame_to_dict(
        self, symbols: set[str], df: pd.DataFrame, market: str
    ) -> Dict[str, Dict]:
        """Extract requested symbols from a spot-market DataFrame"""
        if df is None or df.empty:
            return {}

        # Build a lookup of raw code → index
        code_col = "代码" if "代码" in df.columns else ("code" if "code" in df.columns else None)
        if code_col is None:
            return {}

        # Map raw codes back to internal symbols
        code_to_internal: Dict[str, str] = {}
        for sym in symbols:
            code, _exchange = self.internal_to_clean(sym)
            code_to_internal[code] = sym

        result: Dict[str, Dict] = {}
        for _, row in df.iterrows():
            raw_code = str(row.get(code_col, "")).strip()
            if raw_code not in code_to_internal:
                continue
            internal = code_to_internal[raw_code]

            result[internal] = {
                "symbol": internal,
                "name": str(row.get("名称", row.get("name", ""))),
                "price": self._safe_float(row.get("最新价", row.get("price"))) or 0.0,
                "change": self._safe_float(row.get("涨跌额", row.get("change"))) or 0.0,
                "change_pct": self._safe_float(row.get("涨跌幅", row.get("change_pct"))) or 0.0,
                "volume": self._safe_float(row.get("成交量", row.get("volume"))) or 0.0,
                "amount": self._safe_float(row.get("成交额", row.get("amount"))) or 0.0,
                "high": self._safe_float(row.get("最高", row.get("high"))),
                "low": self._safe_float(row.get("最低", row.get("low"))),
                "open": self._safe_float(row.get("今开", row.get("open"))),
                "pre_close": self._safe_float(row.get("昨收", row.get("pre_close"))),
            }
        return result

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> List[Dict[str, Any]]:
        """Fetch klines from akshare

        Args:
            symbol: Internal symbol (e.g., 600519.SH)
            period: "daily", "weekly", "monthly"
            start_date: YYYYMMDD format
            end_date: YYYYMMDD format

        Returns:
            List of kline dicts
        """
        start = self._normalise_date(start_date)
        end = self._normalise_date(end_date)
        period_ak = self._map_period(period)
        market_char = self._market_char(symbol)

        try:
            if market_char == "HK":
                return self._fetch_hk_klines(symbol, period_ak, start, end)
            return self._fetch_a_share_klines(symbol, period_ak, start, end)
        except Exception:
            return []

    def _fetch_a_share_klines(
        self, symbol: str, period: str, start: str, end: str
    ) -> List[Dict]:
        """Fetch A-share klines with East Money → Tencent fallback"""
        code, _prefix = self.internal_to_akshare(symbol)

        # Try East Money first
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            return self._frame_to_kline_list(symbol, df)
        except Exception:
            pass

        # Fall back to Tencent
        try:
            prefix = self.exchange_prefix(code)
            tx_symbol = f"{prefix}{code}"
            df = ak.stock_zh_a_hist_tx(
                symbol=tx_symbol,
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            return self._frame_to_kline_list(symbol, df)
        except Exception:
            return []

    def _fetch_hk_klines(
        self, symbol: str, period: str, start: str, end: str
    ) -> List[Dict]:
        """Fetch Hong Kong klines"""
        code, _prefix = self.internal_to_akshare(symbol)
        try:
            df = ak.stock_hk_hist(
                symbol=code,
                period=period,
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            return self._frame_to_kline_list(symbol, df)
        except Exception:
            return []

    def _frame_to_kline_list(self, symbol: str, df: pd.DataFrame) -> List[Dict]:
        """Convert a DataFrame to standard kline list"""
        if df is None or df.empty:
            return []

        # Normalize column names
        col_map = {
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        required = {"date", "open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            return []

        rows: List[Dict] = []
        for _, row in df.iterrows():
            date_raw = row.get("date")
            if date_raw is None or pd.isna(date_raw):
                continue
            date_str = str(date_raw)[:10]
            rows.append({
                "symbol": symbol,
                "date": self._normalise_date_display(date_str),
                "open": self._safe_float(row.get("open")),
                "high": self._safe_float(row.get("high")),
                "low": self._safe_float(row.get("low")),
                "close": self._safe_float(row.get("close")),
                "volume": self._safe_float(row.get("volume")),
                "amount": self._safe_float(row.get("amount")),
            })
        return rows

    @staticmethod
    def _map_period(period: str) -> str:
        """Map user-friendly period to akshare period string"""
        mapping = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "日线": "daily",
            "周线": "weekly",
            "月线": "monthly",
        }
        return mapping.get(period, "daily")
