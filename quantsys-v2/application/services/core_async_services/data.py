"""数据服务 - 异步版本"""
from typing import Dict, List, Optional

import structlog

from qs_kernel.infrastructure.persistence.orm.async_config import get_async_session_context
# 2026-09-11 修复（w-f4aa1f6a）：IAsyncKlineRepository 是 domain 层 ABC 端口，
# 直接 IAsyncKlineRepository(session) 会抛 "takes no arguments"，导致
# DataAsyncService.get_klines / get_latest_price 静默返回空
#（实证：error_event 8957c9b8，2026-09-11 01:17:12，core_async_services.py:155）。
# 异步实现是 DailyKlineAsyncRepository（日期过滤已正确处理可选参数）/ StockAsyncRepository。
from adapters.outbound.repositories.stock_async_repository import DailyKlineAsyncRepository, StockAsyncRepository

logger = structlog.get_logger(__name__)


class DataAsyncService:
    """数据服务 - 异步版本"""

    async def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """获取股票信息"""
        try:
            async with get_async_session_context() as session:
                stock_repo = StockAsyncRepository(session)
                stock = await stock_repo.get_stock(symbol.split('.')[0])
                return stock
        except Exception as e:
            logger.error(f"获取股票信息失败: {e}")
            return None

    async def get_klines(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 250
    ) -> List[Dict]:
        """获取K线数据"""
        try:
            async with get_async_session_context() as session:
                kline_repo = DailyKlineAsyncRepository(session)
                klines = await kline_repo.get_klines(symbol, start_date, end_date, limit)
                return klines
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return []

    async def get_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        try:
            async with get_async_session_context() as session:
                kline_repo = DailyKlineAsyncRepository(session)
                latest = await kline_repo.get_latest_kline(symbol)
                return latest.get('close') if latest else None
        except Exception as e:
            logger.error(f"获取最新价格失败: {e}")
            return None

    async def batch_get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """批量获取价格"""
        prices = {}
        for symbol in symbols:
            price = await self.get_latest_price(symbol)
            if price:
                prices[symbol] = price
        return prices
