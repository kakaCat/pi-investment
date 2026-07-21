"""
TencentQuoteProvider - 腾讯财经实时行情数据源
"""
import requests
from datetime import datetime
from typing import Optional
from .base import QuoteProvider, QuoteData


class TencentQuoteProvider(QuoteProvider):
    """腾讯财经行情数据提供者

    数据源：腾讯财经 qt.gtimg.cn
    优点：免费，响应快
    """

    @property
    def name(self) -> str:
        return "tencent"

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
            # Convert symbol to Tencent format
            tencent_code = self._convert_to_tencent_code(symbol)

            # Call Tencent API
            url = f"http://qt.gtimg.cn/q={tencent_code}"
            response = requests.get(
                url,
                timeout=self.timeout,
                proxies={'http': None, 'https': None}
            )
            response.encoding = 'gbk'

            # Check for empty response
            if not response.text or '""' in response.text:
                return None

            return self._parse_quote(symbol, response.text)

        except Exception as e:
            raise Exception(f"腾讯财经查询失败: {e}") from e

    def _convert_to_tencent_code(self, symbol: str) -> str:
        """
        Convert standard symbol to Tencent code format

        Args:
            symbol: Standard symbol (e.g., "600519.SH", "000001.SZ")

        Returns:
            Tencent code (e.g., "sh600519", "sz000001")
        """
        if symbol.endswith('.SH'):
            code = symbol.split('.')[0]
            return f"sh{code}"
        elif symbol.endswith('.SZ'):
            code = symbol.split('.')[0]
            return f"sz{code}"
        else:
            # Auto-detect by code prefix
            code = symbol.split('.')[0] if '.' in symbol else symbol
            if code.startswith('6'):
                return f"sh{code}"
            else:
                return f"sz{code}"

    def _parse_quote(self, symbol: str, raw: str) -> Optional[QuoteData]:
        """
        Parse Tencent API response

        Response format example (002714):
        v_sz002714="51~牧原股份~002714~35.03~35.13~35.13~186173~87491~98646~...~-0.10~-0.28~35.63~34.85~..."

        Correct field positions (verified 2026-06-05):
        [1] = 股票名称 (name)
        [2] = 股票代码 (code)
        [3] = 当前价格 (price)
        [4] = 昨收 (prev_close)
        [5] = 今开 (open)
        [6] = 成交量(手) (volume in lots)
        [7] = 成交额(万元) (amount in 10k)
        [31] = 涨跌额 (change)
        [32] = 涨跌幅 (change_pct)
        [33] = 最高 (high)
        [34] = 最低 (low)

        Args:
            symbol: Standard symbol
            raw: Raw response text

        Returns:
            QuoteData object or None
        """
        try:
            # Extract data between quotes
            parts = raw.split('"')
            if len(parts) < 2:
                return None

            fields = parts[1].split('~')
            if len(fields) < 35:  # Need at least 35 fields
                return None

            # Extract and convert fields
            name = fields[1]
            price = float(fields[3])
            if price <= 0:
                return None

            prev_close = float(fields[4]) if fields[4] else price
            open_price = float(fields[5]) if fields[5] else 0.0
            volume = int(fields[6]) * 100  # Convert lots to shares
            amount = float(fields[7]) * 10000  # Convert 万元 to 元
            change = float(fields[31]) if fields[31] else 0.0
            change_pct = float(fields[32]) if fields[32] else 0.0
            high = float(fields[33]) if fields[33] else price
            low = float(fields[34]) if fields[34] else price

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

        except (IndexError, ValueError, TypeError) as e:
            raise Exception(f"腾讯财经行情解析失败: {e}") from e
