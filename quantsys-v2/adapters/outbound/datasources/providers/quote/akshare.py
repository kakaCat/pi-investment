"""
AkShare quote provider implementation
"""
import os
import akshare as ak
import pandas as pd
from datetime import datetime
from typing import Optional
from unittest.mock import patch

from application.services.quote_providers.base import QuoteProvider, QuoteData


class AkshareQuoteProvider(QuoteProvider):
    """Quote provider using AkShare data source"""

    @property
    def name(self) -> str:
        """Provider name"""
        return "akshare"

    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        Get real-time quote for a stock

        Args:
            symbol: Stock symbol (6-digit for A-shares, 1-5 digits or .HK suffix for HK stocks)

        Returns:
            QuoteData if found, None if not found

        Raises:
            Exception: If akshare API call fails
        """
        # Disable proxy by patching environment variables before akshare makes requests
        # This ensures akshare's internal requests session doesn't use proxy
        env_patch = {
            'HTTP_PROXY': '',
            'HTTPS_PROXY': '',
            'http_proxy': '',
            'https_proxy': ''
        }

        try:
            with patch.dict(os.environ, env_patch, clear=False):
                # Detect A-share vs HK stock
                # A-share: 6-digit code (e.g., 600000)
                # HK stock: 1-5 digits (e.g., 00700) or .HK suffix (e.g., 0700.HK)
                if symbol.endswith('.HK') or (symbol.isdigit() and len(symbol) <= 5):
                    return self._get_hk_quote(symbol)
                else:
                    return self._get_a_quote(symbol)
        except Exception as e:
            raise Exception(f"akshare 查询失败: {e}") from e

    def _get_a_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        Get A-share quote using akshare.stock_zh_a_spot_em()

        Args:
            symbol: 6-digit A-share code (e.g., 600000)

        Returns:
            QuoteData if found, None if not found
        """
        # Remove any suffix for A-shares
        clean_symbol = symbol.split('.')[0]

        # Get all A-share quotes
        df = ak.stock_zh_a_spot_em()

        # Filter by symbol
        row = df[df['代码'] == clean_symbol]

        if row.empty:
            return None

        # Extract data from first row
        data = row.iloc[0]

        try:
            return QuoteData(
                symbol=clean_symbol,
                name=str(data['名称']),
                price=float(data['最新价']),
                open=float(data['今开']),
                high=float(data['最高']),
                low=float(data['最低']),
                prev_close=float(data['昨收']),
                volume=int(data['成交量']),
                amount=float(data['成交额']),
                change_pct=float(data['涨跌幅']),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )
        except KeyError as e:
            raise Exception(f"akshare A股数据格式变化，缺少字段: {e}") from e

    def _get_hk_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        Get HK stock quote using akshare.stock_hk_spot_em()

        Args:
            symbol: HK stock code (e.g., 00700 or 0700.HK)

        Returns:
            QuoteData if found, None if not found
        """
        # Remove .HK suffix if present
        clean_symbol = symbol.replace('.HK', '')

        # Pad to 5 digits with leading zeros
        clean_symbol = clean_symbol.zfill(5)

        # Get all HK stock quotes
        df = ak.stock_hk_spot_em()

        # Filter by symbol
        row = df[df['代码'] == clean_symbol]

        if row.empty:
            return None

        # Extract data from first row
        data = row.iloc[0]

        try:
            return QuoteData(
                symbol=clean_symbol,
                name=str(data['名称']),
                price=float(data['最新价']),
                open=float(data['今开']),
                high=float(data['最高']),
                low=float(data['最低']),
                prev_close=float(data['昨收']),
                volume=int(data['成交量']),
                amount=None,  # HK data doesn't have 成交额
                change_pct=float(data['涨跌幅']),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )
        except KeyError as e:
            raise Exception(f"akshare 港股数据格式变化，缺少字段: {e}") from e
