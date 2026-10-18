"""市场数据服务 - 异步版本"""
from datetime import datetime
from typing import Dict, List

import structlog

from domain.ports.repository_ports_extended import IStockRepository
from infrastructure.persistence.orm.async_config import get_async_session_context

logger = structlog.get_logger(__name__)


class MarketDataAsyncService:
    """市场数据服务 - 异步版本"""

    async def get_active_stocks(self, market: str = 'A') -> List[Dict]:
        """获取活跃股票列表"""
        try:
            async with get_async_session_context() as session:
                stock_repo = IStockRepository(session)
                stocks = await stock_repo.get_active_stocks(market)
                return stocks
        except Exception as e:
            logger.error(f"获取活跃股票失败: {e}")
            return []

    async def search_stocks(self, keyword: str) -> List[Dict]:
        """搜索股票"""
        try:
            async with get_async_session_context() as session:
                stock_repo = IStockRepository(session)
                stocks = await stock_repo.search_by_name(keyword)
                return stocks
        except Exception as e:
            logger.error(f"搜索股票失败: {e}")
            return []

    async def get_market_overview(self) -> Dict:
        """获取市场概览"""
        stocks = await self.get_active_stocks()
        return {
            'total_stocks': len(stocks),
            'timestamp': datetime.now().isoformat()
        }
