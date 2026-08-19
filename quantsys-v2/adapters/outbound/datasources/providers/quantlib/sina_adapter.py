"""Sina Finance (新浪财经) market data adapter.

Provides real-time quotes and basic market data from Sina Finance API.
"""

from __future__ import annotations

import re
import requests
from datetime import datetime
from typing import Any
from .base_adapter import BaseMarketAdapter


class SinaAdapter(BaseMarketAdapter):
    """Sina Finance adapter for real-time quotes.

    Primary use: Real-time quotes (fast and reliable)
    Coverage: A-share, HK stocks

    Usage::
        adapter = SinaAdapter()
        quotes = adapter.get_realtime_quote(["600000.SH", "00700.HK"])
    """

    BASE_URL_A = "https://hq.sinajs.cn/list="
    BASE_URL_HK = "https://hq.sinajs.cn/list="

    def __init__(self):
        self.session = requests.Session()
        # Enhanced headers to bypass anti-crawler
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://finance.sina.com.cn',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        })

    def _symbol_to_sina(self, symbol: str) -> str:
        """Convert internal symbol to Sina format.

        Examples:
            600000.SH → sh600000
            000001.SZ → sz000001
            00700.HK → hk00700
        """
        code, exchange = self.internal_to_clean(symbol)

        if exchange == "HK":
            return f"hk{code}"
        elif exchange == "SH":
            return f"sh{code}"
        elif exchange == "SZ":
            return f"sz{code}"
        else:
            # Default to SZ
            prefix = self.exchange_prefix(code)
            return f"{prefix}{code}"

    def get_stock_info(self, symbol: str) -> dict:
        """Get basic stock info (limited from Sina).

        Sina primarily provides quotes, not detailed stock info.
        Returns basic info extracted from quote data.
        """
        quotes = self.get_realtime_quote([symbol])
        if symbol in quotes:
            quote = quotes[symbol]
            return {
                'symbol': symbol,
                'name': quote.get('name', ''),
                'market': 'HK' if symbol.endswith('.HK') else 'A',
                'industry': None,  # Sina doesn't provide industry
                'list_date': None  # Sina doesn't provide list date
            }
        return {}

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Get K-line data.

        Note: Sina's K-line API is not as reliable as quotes.
        Consider using other sources for historical data.
        """
        # Sina's historical data API is complex and not well documented
        # Returning empty list - use AkShare or other sources for klines
        return []

    def get_realtime_quote(self, symbols: list[str]) -> dict:
        """Get real-time quotes from Sina.

        This is Sina's strength - fast and reliable real-time data.

        Args:
            symbols: List of internal symbols

        Returns:
            Dict mapping symbol to quote data
        """
        if not symbols:
            return {}

        # Convert to Sina format
        sina_symbols = [self._symbol_to_sina(s) for s in symbols]
        sina_str = ",".join(sina_symbols)

        try:
            response = self.session.get(
                f"{self.BASE_URL_A}{sina_str}",
                timeout=5
            )
            response.raise_for_status()

            # Fix encoding - Sina returns GB2312 encoded data
            response.encoding = 'gb2312'

            # Parse response
            result = {}
            lines = response.text.strip().split('\n')

            for i, line in enumerate(lines):
                if i >= len(symbols):
                    break

                symbol = symbols[i]
                parsed = self._parse_quote_line(line, symbol)
                if parsed:
                    result[symbol] = parsed

            return result

        except Exception:
            return {}

    def _parse_quote_line(self, line: str, symbol: str) -> dict | None:
        """Parse a single quote line from Sina response."""
        # Extract data between quotes
        match = re.search(r'"([^"]*)"', line)
        if not match:
            return None

        data = match.group(1)
        if not data or data == "":
            return None

        fields = data.split(',')

        # Check if HK or A-share based on field count
        if symbol.endswith('.HK'):
            return self._parse_hk_quote(fields, symbol)
        else:
            return self._parse_a_quote(fields, symbol)

    def _parse_a_quote(self, fields: list[str], symbol: str) -> dict | None:
        """Parse A-share quote fields."""
        if len(fields) < 32:
            return None

        try:
            name = fields[0]
            open_price = self._safe_float(fields[1])
            prev_close = self._safe_float(fields[2])
            price = self._safe_float(fields[3])
            high = self._safe_float(fields[4])
            low = self._safe_float(fields[5])
            volume = self._safe_float(fields[8])
            amount = self._safe_float(fields[9])

            change = round(price - prev_close, 2) if price and prev_close else 0.0
            change_pct = round(change / prev_close * 100, 2) if prev_close and prev_close != 0 else 0.0

            return {
                'symbol': symbol,
                'name': name,
                'price': price or 0.0,
                'open': open_price,
                'high': high,
                'low': low,
                'pre_close': prev_close,
                'volume': volume or 0.0,
                'amount': amount or 0.0,
                'change': change,
                'change_pct': change_pct
            }
        except (IndexError, ValueError):
            return None

    def _parse_hk_quote(self, fields: list[str], symbol: str) -> dict | None:
        """Parse HK stock quote fields."""
        if len(fields) < 20:
            return None

        try:
            name = fields[1]
            open_price = self._safe_float(fields[2])
            prev_close = self._safe_float(fields[3])
            high = self._safe_float(fields[4])
            low = self._safe_float(fields[5])
            price = self._safe_float(fields[6])
            volume = self._safe_float(fields[12])
            amount = self._safe_float(fields[13])

            change = round(price - prev_close, 2) if price and prev_close else 0.0
            change_pct = round(change / prev_close * 100, 2) if prev_close and prev_close != 0 else 0.0

            return {
                'symbol': symbol,
                'name': name,
                'price': price or 0.0,
                'open': open_price,
                'high': high,
                'low': low,
                'pre_close': prev_close,
                'volume': volume or 0.0,
                'amount': amount or 0.0,
                'change': change,
                'change_pct': change_pct
            }
        except (IndexError, ValueError):
            return None

    def get_index_data(
        self,
        index_code: str,
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Get index data (not well supported by Sina)."""
        return []

    def get_sector_list(self) -> list[dict]:
        """Get sector list (not supported by Sina)."""
        return []

    def get_north_flow(
        self,
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Get north flow data (not supported by Sina)."""
        return []

    def get_market_news(self, symbol: str = "", limit: int = 20) -> list[dict]:
        """Get market news (not well supported by Sina)."""
        return []

    def get_financial_data(self, symbol: str) -> dict:
        """Get financial data (not well supported by Sina)."""
        return {}
