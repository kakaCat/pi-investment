"""
NeteaseQuoteProvider - 网易财经实时行情数据源
"""
import re
import json
import requests
from datetime import datetime
from typing import Optional
from .base import QuoteProvider, QuoteData


class NeteaseQuoteProvider(QuoteProvider):
    """网易财经行情数据提供者

    数据源：网易财经 api.money.126.net
    优点：返回 JSON 格式
    """

    @property
    def name(self) -> str:
        return "netease"

    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取实时行情数据

        Args:
            symbol: 股票代码 (e.g., "600519.SH", "000001.SZ")

        Returns:
            QuoteData if successful, None if empty response

        Raises:
            Exception: 网络错误或解析失败
        """
        try:
            # Convert symbol to Netease format
            netease_code = self._convert_to_netease_code(symbol)

            # Call Netease API
            url = f"http://api.money.126.net/data/feed/{netease_code}"
            response = requests.get(
                url,
                timeout=self.timeout,
                proxies={'http': None, 'https': None}
            )

            # Check for empty response
            if not response.text:
                return None

            return self._parse_quote(symbol, response.text, netease_code)

        except Exception as e:
            raise Exception(f"网易财经查询失败: {e}") from e

    def _convert_to_netease_code(self, symbol: str) -> str:
        """
        Convert standard symbol to Netease code format

        Args:
            symbol: Standard symbol (e.g., "600519.SH", "000001.SZ")

        Returns:
            Netease code (e.g., "0600519" for SH, "1000001" for SZ)
        """
        if symbol.endswith('.SH'):
            # Shanghai: prefix with "0"
            code = symbol.split('.')[0]
            return f"0{code}"
        elif symbol.endswith('.SZ'):
            # Shenzhen: prefix with "1"
            code = symbol.split('.')[0]
            return f"1{code}"
        else:
            # Auto-detect by code prefix
            code = symbol.split('.')[0] if '.' in symbol else symbol
            if code.startswith('6'):
                return f"0{code}"
            else:
                return f"1{code}"

    def _parse_quote(self, symbol: str, raw: str, netease_code: str) -> Optional[QuoteData]:
        """
        Parse Netease API response

        Response format (JSONP):
        _ntes_quote_callback({"0600519":{"code":"0600519","name":"贵州茅台","price":1295.00,...}});

        Args:
            symbol: Standard symbol
            raw: Raw response text
            netease_code: Netease code for extracting data

        Returns:
            QuoteData object or None
        """
        try:
            # Extract JSON from JSONP wrapper
            # Pattern: _ntes_quote_callback({...});
            match = re.search(r'_ntes_quote_callback\((.*)\)', raw)
            if not match:
                return None

            data_str = match.group(1)
            data = json.loads(data_str)

            # Extract quote data
            if netease_code not in data:
                return None

            quote = data[netease_code]

            # Extract and convert fields
            name = quote.get('name', '')
            price = float(quote.get('price', 0))
            if price <= 0:
                return None

            open_price = float(quote.get('open', 0))
            high = float(quote.get('high', 0))
            low = float(quote.get('low', 0))
            prev_close = float(quote.get('yestclose', 0))
            volume = int(quote.get('volume', 0))
            amount = float(quote.get('turnover', 0))

            # Calculate change
            change = price - prev_close if prev_close > 0 else 0.0
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0.0

            return QuoteData(
                symbol=symbol,
                name=name,
                price=price,
                open=open_price,
                high=high,
                low=low,
                prev_close=prev_close,
                volume=volume,
                amount=amount,
                change=change,
                change_pct=change_pct,
                timestamp=datetime.now().isoformat(),
                source=self.name
            )

        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
            raise Exception(f"网易财经行情解析失败: {e}") from e
