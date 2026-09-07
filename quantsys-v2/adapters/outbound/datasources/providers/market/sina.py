"""新浪 market data provider（备用源：龙虎榜）

2026-09-01 新增：东财龙虎榜接口异常时，新浪 stock_lhb_detail_daily_sina
作为 failover 源（已验证 2026-08-31 返回 84 条）。
"""
import logging
from typing import Optional
from datetime import datetime

from adapters.outbound.datasources.base import MarketProvider
from adapters.outbound.datasources.models import MarketData

logger = logging.getLogger(__name__)


class SinaMarketProvider(MarketProvider):
    """新浪市场数据 provider（经 akshare 封装）

    定位：备用源。东财龙虎榜接口异常时接管。
    注意：新浪龙虎榜字段与东财不同（无净买额分列），记录原样透传。
    """

    @property
    def name(self) -> str:
        return 'sina'

    def get_market_overview(self) -> Optional[MarketData]:
        return None  # 主源 akshare 负责

    def get_lhb_stock(self, symbol: str, date: str) -> Optional[MarketData]:
        """个股龙虎榜：拉当日全市场榜单后按代码筛选"""
        try:
            import akshare as ak

            df = ak.stock_lhb_detail_daily_sina(date=date.replace('-', ''))

            if df is None or df.empty:
                return None

            bare = symbol.split('.')[0]
            code_col = '股票代码' if '股票代码' in df.columns else None
            if code_col:
                df = df[df[code_col].astype(str).str.replace('.', '').str.contains(bare, na=False)]

            if df.empty:
                return None

            records = df.astype(object).where(df.notna(), None).to_dict('records')
            return MarketData(
                data_type='lhb',
                data={'symbol': symbol, 'date': date, 'records': records},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_lhb_stock failed: {e}")
            return None

    def get_lhb_daily(self, date: str) -> Optional[MarketData]:
        """每日全市场龙虎榜（新浪源）"""
        try:
            import akshare as ak

            df = ak.stock_lhb_detail_daily_sina(date=date.replace('-', ''))

            if df is None or df.empty:
                return None

            records = df.astype(object).where(df.notna(), None).to_dict('records')
            return MarketData(
                data_type='lhb_daily',
                data={'date': date, 'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_lhb_daily failed: {e}")
            return None
