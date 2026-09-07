"""East Money (东方财富) market data adapter.

Provides comprehensive market data including quotes, sectors, and fund flow.
"""

from __future__ import annotations

import logging
import requests
import json
from datetime import datetime
from typing import Any
from .base_adapter import BaseMarketAdapter

logger = logging.getLogger(__name__)


class EastMoneyAdapter(BaseMarketAdapter):
    """East Money adapter for comprehensive market data.

    Primary use: Comprehensive data (quotes, sectors, fund flow)
    Coverage: A-share, indices, sectors

    Usage::
        adapter = EastMoneyAdapter()
        quotes = adapter.get_realtime_quote(["600000.SH"])
        sectors = adapter.get_sector_list()
    """

    # 多个 eastmoney 主机（按优先级）。实时 push2 主机可能被 eastmoney WAF
    # 按 IP 限流（TCP 连接被重置），自动回退到 push2delay（延时行情）。
    BASE_URLS = [
        "https://17.push2.eastmoney.com/api",
        "https://82.push2.eastmoney.com/api",
        "http://push2.eastmoney.com/api",
        "https://push2delay.eastmoney.com/api",
    ]
    # 兼容旧引用（保留单一 BASE_URL 语义）
    BASE_URL = BASE_URLS[2]
    QUOTE_PATH = "/qt/stock/get"
    CLIST_PATH = "/qt/clist/get"

    def __init__(self):
        self.session = requests.Session()
        # 国内数据源直连：忽略 HTTP(S)_PROXY 环境变量。
        # 经本地代理（如 ClashX 127.0.0.1:7890）访问国内行情接口会被重置/极慢。
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def _get_json(self, path: str, params: dict, timeout: int = 10) -> dict:
        """按优先级尝试多个 eastmoney 主机发起 GET，返回 JSON。

        单个主机连接失败（被重置/超时）自动尝试下一个；全部失败抛出最后一个异常。
        """
        last_err = None
        for base in self.BASE_URLS:
            try:
                response = self.session.get(f"{base}{path}", params=params, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                last_err = e
                logger.warning("eastmoney %s failed on %s: %s", path, base, e)
        raise last_err or RuntimeError("eastmoney: all hosts failed")

    def _symbol_to_secid(self, symbol: str) -> str:
        """Convert internal symbol to East Money secid format.

        Examples:
            600000.SH → 1.600000
            000001.SZ → 0.000001
        """
        code, exchange = self.internal_to_clean(symbol)

        if exchange == "SH":
            return f"1.{code}"
        elif exchange == "SZ":
            return f"0.{code}"
        elif exchange == "HK":
            return f"116.{code}"
        else:
            # Default to SZ
            prefix = self.exchange_prefix(code)
            market = "1" if prefix == "sh" else "0"
            return f"{market}.{code}"

    def get_stock_info(self, symbol: str) -> dict:
        """Get stock information from East Money."""
        try:
            secid = self._symbol_to_secid(symbol)

            params = {
                'secid': secid,
                'fields': 'f57,f58,f84,f85,f86,f127,f116,f117',  # name, industry, list_date, etc.
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
            }

            response = self._get_json(self.QUOTE_PATH, params, timeout=10)

            data = response
            if data.get('rc') == 0 and data.get('data'):
                info_data = data['data']

                return {
                    'symbol': symbol,
                    'name': info_data.get('f58', ''),
                    'market': 'HK' if symbol.endswith('.HK') else 'A',
                    'industry': None,  # East Money doesn't provide industry in this API
                    'list_date': None  # Not in basic quote API
                }

            return {}

        except Exception:
            return {}

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Get K-line data from East Money.

        Note: East Money's K-line API is complex.
        For now, returning empty - use AkShare for historical data.
        """
        return []

    def get_realtime_quote(self, symbols: list[str]) -> dict:
        """Get real-time quotes from East Money.

        Args:
            symbols: List of internal symbols

        Returns:
            Dict mapping symbol to quote data
        """
        if not symbols:
            return {}

        result = {}

        # East Money API works best with individual requests
        for symbol in symbols:
            try:
                secid = self._symbol_to_secid(symbol)

                params = {
                    'secid': secid,
                    'fields': 'f57,f58,f43,f44,f45,f46,f47,f48,f60,f46,f169,f170,f60,f152',
                    'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
                }

                response = self._get_json(self.QUOTE_PATH, params, timeout=5)

                data = response
                if data.get('rc') == 0 and data.get('data'):
                    quote_data = data['data']
                    parsed = self._parse_quote_data(quote_data, symbol)
                    if parsed:
                        result[symbol] = parsed

            except Exception:
                continue

        return result

    def _scaled_price(self, value) -> float | None:
        """将 eastmoney「分」单位字段换算为元（未传 fltt=2 时价格类字段 ×100）。"""
        v = self._safe_float(value)
        return v / 100.0 if v is not None else None

    def _parse_quote_data(self, data: dict, symbol: str) -> dict | None:
        """Parse East Money quote data.

        Note: 未传 fltt=2 时 eastmoney 以「分」返回价格类字段
        (f43/f44/f45/f46/f60) 及涨跌幅 (f170)，需除以 100 换算为元/百分比。
        与 providers/quote/eastmoney.py 的换算口径保持一致。
        """
        try:
            name = data.get('f58', '')
            price = self._scaled_price(data.get('f43'))  # 当前价
            open_price = self._scaled_price(data.get('f46'))  # 开盘价
            high = self._scaled_price(data.get('f44'))  # 最高价
            low = self._scaled_price(data.get('f45'))  # 最低价
            pre_close = self._scaled_price(data.get('f60'))  # 昨收
            volume = self._safe_float(data.get('f47'))  # 成交量（手，不缩放）
            amount = self._safe_float(data.get('f48'))  # 成交额（元，不缩放）
            change_pct_raw = self._safe_float(data.get('f170'))  # 涨跌幅（×100）
            change_pct = change_pct_raw / 100.0 if change_pct_raw is not None else None

            if not price or not pre_close:
                return None

            change = round(price - pre_close, 2)

            return {
                'symbol': symbol,
                'name': name,
                'price': price,
                'open': open_price,
                'high': high,
                'low': low,
                'pre_close': pre_close,
                'volume': volume or 0.0,
                'amount': amount or 0.0,
                'change': change,
                'change_pct': change_pct or 0.0
            }

        except (KeyError, ValueError):
            return None

    def get_index_data(
        self,
        index_code: str,
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Get index data (not implemented yet)."""
        return []

    def get_sector_list(self) -> list[dict]:
        """Get sector/industry list from East Money.

        Returns:
            List of sectors with code and name
        """
        try:
            # Get industry sectors
            params = {
                'pn': '1',
                'pz': '100',
                'po': '1',
                'np': '1',
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': '2',
                'invt': '2',
                'fid': 'f3',
                'fs': 'm:90+t:2+f:!50',  # Industry sectors
                'fields': 'f12,f14,f3',
                '_': str(int(datetime.now().timestamp() * 1000))
            }

            response = self._get_json(self.CLIST_PATH, params, timeout=10)

            data = response
            if data.get('rc') == 0 and data.get('data', {}).get('diff'):
                sectors = []
                for item in data['data']['diff']:
                    sectors.append({
                        'code': item.get('f12', ''),
                        'name': item.get('f14', ''),
                        'type': 'industry'
                    })
                return sectors

            return []

        except Exception:
            return []

    def get_north_flow(
        self,
        start_date: str = "20200101",
        end_date: str = "20260101",
    ) -> list[dict]:
        """Get north flow data (complex API, not implemented yet)."""
        return []

    def get_market_news(self, symbol: str = "", limit: int = 20) -> list[dict]:
        """Get market news (not implemented yet)."""
        return []

    def get_financial_data(self, symbol: str) -> dict:
        """Get financial data (not implemented yet)."""
        return {}
