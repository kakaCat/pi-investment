"""
SinaQuoteProvider - 新浪财经实时行情数据源
"""
import requests
from datetime import datetime
from typing import Optional
from adapters.outbound.datasources.base import QuoteProvider
from adapters.outbound.datasources.models import QuoteData


class SinaQuoteProvider(QuoteProvider):
    """新浪财经行情数据提供者"""

    @property
    def name(self) -> str:
        """Provider name"""
        return "sina"

    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取实时行情数据

        Args:
            symbol: 股票代码 (e.g., "600000.SH", "00700.HK")

        Returns:
            QuoteData if successful, None if empty response

        Raises:
            Exception: 网络错误或解析失败
        """
        try:
            # Convert symbol to Sina format
            sina_code = self._convert_to_sina_code(symbol)

            # Call Sina API (disable proxy for domestic data sources)
            url = f"https://hq.sinajs.cn/list={sina_code}"
            response = requests.get(url, timeout=self.timeout, proxies={'http': None, 'https': None})
            response.encoding = 'gbk'

            # Check for empty response
            if not response.text or '""' in response.text:
                return None

            # Parse based on market
            if symbol.endswith('.HK'):
                return self._parse_sina_hk_quote(symbol, response.text)
            else:
                return self._parse_sina_a_quote(symbol, response.text)

        except Exception as e:
            raise Exception(f"新浪财经查询失败: {e}") from e

    def _convert_to_sina_code(self, symbol: str) -> str:
        """
        Convert standard symbol to Sina code format

        Args:
            symbol: Standard symbol (e.g., "600000.SH", "00700.HK")

        Returns:
            Sina code (e.g., "1600000", "hk00700")
        """
        if symbol.endswith('.HK'):
            # HK stock: prefix with "hk"
            code = symbol.split('.')[0]
            return f"hk{code}"
        else:
            # A-share: prefix with "1" (60xxxx) or "0" (00xxxx, 30xxxx)
            code = symbol.split('.')[0]
            if code.startswith('6'):
                return f"1{code}"
            else:
                return f"0{code}"

    def _parse_sina_a_quote(self, symbol: str, raw: str) -> Optional[QuoteData]:
        """
        Parse A-share quote response

        Response format:
        var hq_str_1600000="name,open,prev_close,price,high,low,bid,ask,volume,amount,..."

        Fields:
        [0]=name, [1]=open, [2]=prev_close, [3]=price, [4]=high, [5]=low,
        [8]=volume, [9]=amount
        """
        try:
            # Extract data between quotes
            parts = raw.split('"')
            if len(parts) < 2:
                return None

            fields = parts[1].split(',')
            if len(fields) < 32:  # A-share response should have 32+ fields
                return None

            # Extract and convert fields
            name = fields[0]
            open_price = float(fields[1])
            prev_close = float(fields[2])
            price = float(fields[3])
            high = float(fields[4])
            low = float(fields[5])
            volume = int(fields[8])
            amount = float(fields[9])

            # Calculate change
            change = price - prev_close
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

        except (IndexError, ValueError) as e:
            raise Exception(f"A股行情解析失败: {e}") from e

    def _parse_sina_hk_quote(self, symbol: str, raw: str) -> Optional[QuoteData]:
        """
        Parse HK stock quote response

        Response format:
        var hq_str_hk00700="code,name,open,prev_close,high,low,price,..."

        Fields:
        [1]=name, [2]=open, [3]=prev_close, [4]=high, [5]=low, [6]=price
        """
        try:
            # Extract data between quotes
            parts = raw.split('"')
            if len(parts) < 2:
                return None

            fields = parts[1].split(',')
            if len(fields) < 7:  # HK response needs at least 7 fields for basic quote
                return None

            # Extract and convert fields
            name = fields[1]
            open_price = float(fields[2])
            prev_close = float(fields[3])
            high = float(fields[4])
            low = float(fields[5])
            price = float(fields[6])

            # HK stocks don't always have volume/amount in same position
            # Set to 0 if not available
            volume = 0
            amount = 0.0

            # Calculate change
            change = price - prev_close
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

        except (IndexError, ValueError) as e:
            raise Exception(f"港股行情解析失败: {e}") from e
