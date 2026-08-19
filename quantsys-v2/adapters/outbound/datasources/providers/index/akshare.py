"""Akshare 指数成分股 provider。

获取逻辑来自原 infrastructure/jobs/index_constituents_update_job.py
（Phase 3 数据访问治理：提取到统一数据源层，job 与服务共享同一实现）。

数据源策略：中证指数官网（csindex）优先，新浪 fallback——均不依赖东财，
规避东财 WAF 封 IP 风险。
"""
import logging
from typing import Optional
from datetime import datetime

from adapters.outbound.datasources.models import StockData

logger = logging.getLogger(__name__)


class AkshareIndexProvider:
    """Akshare 指数成分股 provider（csindex 优先 + sina 兜底）"""

    @property
    def name(self) -> str:
        return 'akshare-index'

    def get_index_constituents(self, index_code: str) -> Optional[StockData]:
        """获取指数成分股代码列表

        Args:
            index_code: 指数裸代码（如 '000300' 沪深300、'000688' 科创50、'399006' 创业板指）

        Returns:
            StockData(data=[{'symbol': '600519'}, ...]) or None if failed
        """
        symbols = self._fetch_constituents(index_code)
        if not symbols:
            return None

        return StockData(
            symbol=index_code,
            data_type='index_constituents',
            data=[{'symbol': s} for s in symbols],
            total=len(symbols),
            source=self.name,
            timestamp=datetime.now().isoformat()
        )

    def _fetch_constituents(self, code: str) -> list:
        """获取单个指数的成分股代码列表（裸 6 位代码）"""
        import akshare as ak

        # 中证系指数优先走官网
        try:
            df = ak.index_stock_cons_csindex(symbol=code)
            if df is not None and not df.empty:
                return [str(c).zfill(6) for c in df['成分券代码'].tolist()]
        except Exception as e:
            logger.warning(f"csindex 获取 {code} 失败: {type(e).__name__} {str(e)[:80]}")

        # fallback：新浪
        try:
            df = ak.index_stock_cons_sina(symbol=code)
            if df is not None and not df.empty:
                return [str(c).zfill(6) for c in df['code'].tolist()]
        except Exception as e:
            logger.warning(f"sina 获取 {code} 失败: {type(e).__name__} {str(e)[:80]}")

        return []
