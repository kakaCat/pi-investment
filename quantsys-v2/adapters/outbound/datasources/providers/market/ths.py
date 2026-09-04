"""同花顺 market data provider（备用源：板块资金流）

2026-09-01 新增：东财 WAF 封禁本机 IP 期间（fund-flow/sector-flow 接口
ConnectionError），同花顺接口（stock_fund_flow_industry）仍可用，
作为板块资金流的 failover 源。
"""
import logging
from typing import Optional
from datetime import datetime

from adapters.outbound.datasources.base import MarketProvider
from adapters.outbound.datasources.models import MarketData

logger = logging.getLogger(__name__)


class ThsMarketProvider(MarketProvider):
    """同花顺市场数据 provider（经 akshare 封装）

    定位：备用源。东财接口被 WAF 封禁时接管板块资金流。
    """

    @property
    def name(self) -> str:
        return 'ths'

    def get_market_overview(self) -> Optional[MarketData]:
        return None  # 主源 akshare 负责

    def get_lhb_stock(self, symbol: str, date: str) -> Optional[MarketData]:
        return None  # 主源 akshare 负责

    def get_lhb_daily(self, date: str) -> Optional[MarketData]:
        return None  # 主源 akshare 负责，新浪为备用

    def get_sector_fund_flow(self, indicator: str = '今日') -> Optional[MarketData]:
        """行业资金流向排行（同花顺 stock_fund_flow_industry）

        东财 stock_sector_fund_flow_rank 被封时的替代。
        同花顺字段：行业/行业指数/行业-涨跌幅/流入资金/流出资金/净额/公司家数/领涨股

        Args:
            indicator: '今日' | '即时'（同花顺接口用 symbol 参数，统一传'即时'）

        Returns:
            MarketData(data={'records': [...]}) or None if failed
        """
        try:
            import os
            from unittest.mock import patch
            import akshare as ak

            # 禁用代理（与 akshare 主源一致：避免代理导致连接失败）
            env_patch = {'HTTP_PROXY': '', 'HTTPS_PROXY': '', 'http_proxy': '', 'https_proxy': ''}
            with patch.dict(os.environ, env_patch, clear=False):
                df = ak.stock_fund_flow_industry(symbol='即时')

            if df is None or df.empty:
                return None

            records = df.astype(object).where(df.notna(), None).to_dict('records')
            return MarketData(
                data_type='sector_fund_flow',
                data={'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_sector_fund_flow failed: {e}")
            return None
