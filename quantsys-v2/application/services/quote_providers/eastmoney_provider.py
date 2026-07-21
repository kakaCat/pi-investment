"""
EastmoneyQuoteProvider - 东方财富实时行情数据源
"""
import requests
from datetime import datetime
from typing import Optional
from .base import QuoteProvider, QuoteData


class EastmoneyQuoteProvider(QuoteProvider):
    """东方财富行情数据提供者

    数据源：东方财富网 push2.eastmoney.com
    优点：官方数据，稳定性好，返回 JSON 格式
    """

    @property
    def name(self) -> str:
        return "eastmoney"

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
            # Convert symbol to Eastmoney secid format
            secid = self._convert_to_secid(symbol)

            # Call Eastmoney API
            url = "http://push2.eastmoney.com/api/qt/stock/get"
            params = {
                'secid': secid,
                'fields': 'f43,f44,f45,f46,f47,f48,f57,f58,f60,f152,f168,f169,f170,f171'
            }

            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
                proxies={'http': None, 'https': None}
            )
            response.raise_for_status()

            data = response.json()

            # Check if data exists
            if not data or 'data' not in data or not data['data']:
                return None

            return self._parse_quote(symbol, data['data'])

        except Exception as e:
            raise Exception(f"东方财富查询失败: {e}") from e

    def _convert_to_secid(self, symbol: str) -> str:
        """
        Convert standard symbol to Eastmoney secid format

        Args:
            symbol: Standard symbol (e.g., "600519.SH", "000001.SZ")

        Returns:
            secid (e.g., "1.600519" for SH, "0.000001" for SZ, "116.00700" for HK)
        """
        if symbol.endswith('.HK'):
            # HK stock: market code = 116
            code = symbol.split('.')[0]
            return f"116.{code}"
        elif symbol.endswith('.SH'):
            # Shanghai: market code = 1
            code = symbol.split('.')[0]
            return f"1.{code}"
        elif symbol.endswith('.SZ'):
            # Shenzhen: market code = 0
            code = symbol.split('.')[0]
            return f"0.{code}"
        else:
            # Auto-detect by code prefix
            code = symbol.split('.')[0] if '.' in symbol else symbol
            if code.startswith('6'):
                return f"1.{code}"
            else:
                return f"0.{code}"

    def _parse_quote(self, symbol: str, data: dict) -> Optional[QuoteData]:
        """
        Parse Eastmoney API response

        Field mapping:
        f43 = 现价 (current price)
        f44 = 最高 (high)
        f45 = 最低 (low)
        f46 = 今开 (open)
        f47 = 成交量 (volume, in lots)
        f48 = 成交额 (amount)
        f57 = 股票代码 (code)
        f58 = 股票名称 (name)
        f60 = 昨收 (prev_close)
        f152 = 涨跌额 (change)
        f168 = 换手率 (turnover rate)
        f169 = 市盈率动态 (PE dynamic)
        f170 = 涨跌幅 (change_pct)
        f171 = 振幅 (amplitude)

        Args:
            symbol: Standard symbol
            data: API response data dict

        Returns:
            QuoteData object or None
        """
        try:
            # Extract fields (handle missing fields)
            # NOTE: Eastmoney returns prices in 分 (cents), need to divide by 100
            price = float(data.get('f43', 0)) / 100.0
            if price <= 0:
                return None

            name = data.get('f58', '')
            open_price = float(data.get('f46', 0)) / 100.0
            high = float(data.get('f44', 0)) / 100.0
            low = float(data.get('f45', 0)) / 100.0
            prev_close = float(data.get('f60', 0)) / 100.0
            volume = int(data.get('f47', 0)) * 100  # Convert lots to shares
            amount = float(data.get('f48', 0))

            # Calculate change (use f152 if available, otherwise calculate)
            # NOTE: f152 is also in 分 (cents)
            if 'f152' in data and data['f152'] is not None:
                change = float(data['f152']) / 100.0
            else:
                change = price - prev_close if prev_close > 0 else 0.0

            # Calculate change_pct (use f170 if available, otherwise calculate)
            # NOTE: f170 is already in percentage, but needs to be divided by 100 (e.g., 3 -> 0.03%)
            if 'f170' in data and data['f170'] is not None:
                change_pct = float(data['f170']) / 100.0
            else:
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

        except (KeyError, ValueError, TypeError) as e:
            raise Exception(f"东方财富行情解析失败: {e}") from e
