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
        """DataFrame → JSON 兼容 records 列表

        2026-09-05 修复：原实现 df.where(df.notna(), None).to_dict('records') 两个缺陷——
        ① 缺 astype(object)：float 列 NaN 在 to_dict 时复活（None 被转回 nan），route 层
        raw json.dumps 报 'Out of range float values ... nan'；② date 列（如 hist_em 的
        '日期'）保持 datetime.date 对象无法 json 序列化。统一：先转 object 再逐值清洗
        （nan/inf→None、date/datetime→iso str），与 market provider 的清洗惯例一致。
        """
        import math
        from datetime import date, datetime

        cleaned = []
        for rec in df.astype(object).where(df.notna(), None).to_dict('records'):
            row = {}
            for k, v in (rec or {}).items():
                if isinstance(v, float) and not math.isfinite(v):
                    v = None
                elif isinstance(v, (datetime, date)):
                    v = v.isoformat()
                row[k] = v
            cleaned.append(row)
        return cleaned

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
        """南向资金流向（stock_hsgt_hist_em 南向资金，2026-09-05 修复）

        2026-09-05 修复：上游接口 stock_hk_fund_flow_em 在现装 akshare(1.18.81) 已不存在
        （AttributeError 被下方 except 吞掉 → 南向资金永远返回空），改走东财沪深港通历史的
        官方南向资金序列接口 stock_hsgt_hist_em(symbol='南向资金')，语义一致且日期为 str。
        """
        try:
            import akshare as ak

            df = ak.stock_hsgt_hist_em(symbol="南向资金")
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
