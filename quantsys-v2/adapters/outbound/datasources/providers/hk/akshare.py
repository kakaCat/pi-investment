"""Akshare 港股市场数据 provider

Phase 3 数据访问治理：集中 application/services/hk_market_data_service.py
中散落的港股 akshare 调用（指数现货/港股通持股/南向资金/人气排行/K线/财务指标）。
"""
import logging
from typing import Optional
from datetime import datetime

from adapters.outbound.datasources.models import StockData

logger = logging.getLogger(__name__)


class AkshareHKProvider:
    """Akshare 港股市场数据 provider"""

    @property
    def name(self) -> str:
        return 'akshare-hk'

    def _records(self, df) -> list:
        return df.where(df.notna(), None).to_dict('records')

    def get_hk_market_overview(self) -> Optional[StockData]:
        """港股市场概览（恒生指数现货 + 港股通持股）

        概览为双数据集，包装为单条 record 返回：
        data=[{'indices': [...], 'hk_connect': [...]}]
        """
        try:
            import akshare as ak

            hsi_df = ak.stock_hk_index_spot_em()
            hk_hold_df = ak.stock_hk_hold()

            overview = {
                'indices': self._records(hsi_df) if hsi_df is not None and not hsi_df.empty else [],
                'hk_connect': self._records(hk_hold_df.tail(10)) if hk_hold_df is not None and not hk_hold_df.empty else [],
            }

            return StockData(
                symbol='HK',
                data_type='hk_market_overview',
                data=[overview],
                total=1,
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_hk_market_overview failed: {e}")
            return None

    def get_south_flow(self) -> Optional[StockData]:
        """南向资金流向（stock_hk_fund_flow_em）"""
        try:
            import akshare as ak

            df = ak.stock_hk_fund_flow_em()
            if df is None or df.empty:
                return None

            records = self._records(df)
            return StockData(
                symbol='HK',
                data_type='south_flow',
                data=records,
                total=len(records),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_south_flow failed: {e}")
            return None

    def get_hk_hot_rank(self) -> Optional[StockData]:
        """港股人气排行（stock_hot_rank_em 港股吧）"""
        try:
            import akshare as ak

            df = ak.stock_hot_rank_em(symbol="港股")
            if df is None or df.empty:
                return None

            records = self._records(df)
            return StockData(
                symbol='HK',
                data_type='hk_hot_rank',
                data=records,
                total=len(records),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_hk_hot_rank failed: {e}")
            return None

    def get_hk_daily(self, symbol: str) -> Optional[StockData]:
        """港股日K（stock_hk_daily，前复权）"""
        try:
            import akshare as ak

            df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
            if df is None or df.empty:
                return None

            records = self._records(df)
            return StockData(
                symbol=symbol,
                data_type='hk_daily',
                data=records,
                total=len(records),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_hk_daily failed: {e}")
            return None

    def get_hk_financials(self, symbol: str) -> Optional[StockData]:
        """港股财务指标（stock_financial_hk_analysis_indicator_em）"""
        try:
            import akshare as ak

            df = ak.stock_financial_hk_analysis_indicator_em(symbol=symbol)
            if df is None or df.empty:
                return None

            records = self._records(df)
            return StockData(
                symbol=symbol,
                data_type='hk_financials',
                data=records,
                total=len(records),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_hk_financials failed: {e}")
            return None
