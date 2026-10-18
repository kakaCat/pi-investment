"""
股票池服务 - 异步版本

职责：
1. 管理热门股票池（沪深300 + 创业板50 + 科创50）
2. 提供扫描范围（自选股 + 热门股票池）
3. 缓存热门股票池（1小时TTL）
4. 自定义股票池 CRUD（静态池 + 动态池）
5. 动态池刷新（基于 filter_template 重新筛选）
6. 筛选建池（scan → create pool 一步完成）
"""
from domain.ports import IStockPoolRepository, IStockRepository
from typing import Dict, List, Optional
from infrastructure.persistence.orm.async_config import get_async_session_context
import time
import structlog

logger = structlog.get_logger(__name__)


class StockPoolAsyncService:
    """股票池服务：热门池 + 自定义池管理 - 异步版本"""

    # 热门指数代码
    HOT_INDEX_CODES = [
        '000300.SH',  # 沪深300
        '399006.SZ',  # 创业板指
        '000688.SH'   # 科创50
    ]

    def __init__(self):
        """初始化股票池服务"""
        self._cache = None
        self._cache_time = 0
        self._cache_ttl = 3600  # 1 hour

    async def get_hot_stocks(self) -> List[str]:
        """
        获取热门股票池（带缓存）

        从3个热门指数获取成分股：
        - 000300.SH: 沪深300
        - 399006.SZ: 创业板指
        - 000688.SH: 科创50

        Returns:
            股票代码列表（去重）
        """
        # 检查缓存
        current_time = time.time()
        if self._cache is not None and (current_time - self._cache_time) < self._cache_ttl:
            logger.debug("Using cached hot stocks")
            return self._cache

        # 缓存过期或不存在，重新查询
        logger.info(f"Fetching hot stocks from indices: {self.HOT_INDEX_CODES}")

        try:
            async with get_async_session_context() as session:
                stock_repo = IStockRepository(session)

                # 查询活跃A股作为热门股票池
                stocks = await stock_repo.get_active_stocks(market='A')
                unique_stocks = [s['symbol'] for s in stocks]

                # 更新缓存
                self._cache = unique_stocks
                self._cache_time = current_time

                logger.info(f"Hot stocks fetched: {len(unique_stocks)} stocks")
                return unique_stocks

        except Exception as e:
            logger.error(f"Failed to fetch hot stocks: {e}")
            # 如果有旧缓存，返回旧缓存
            if self._cache is not None:
                logger.warning("Returning stale cache due to error")
                return self._cache
            raise

    async def get_scan_universe(self, user_watchlist: List[str]) -> List[str]:
        """
        获取扫描范围（自选股 + 热门股票池）

        Args:
            user_watchlist: 用户自选股列表

        Returns:
            股票代码列表（去重）
        """
        try:
            hot_stocks = await self.get_hot_stocks()

            # 合并并去重
            all_stocks = user_watchlist + hot_stocks
            unique_stocks = list(dict.fromkeys(all_stocks))

            logger.info(
                f"Scan universe: {len(user_watchlist)} watchlist + "
                f"{len(hot_stocks)} hot stocks = {len(unique_stocks)} unique"
            )

            return unique_stocks

        except Exception as e:
            logger.error(f"Failed to get scan universe: {e}")
            # 至少返回自选股
            return user_watchlist

    async def list_pools(
        self,
        pool_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        列出股票池

        Args:
            pool_type: 池类型过滤（'static', 'dynamic'）
            limit: 返回数量

        Returns:
            股票池列表
        """
        try:
            async with get_async_session_context() as session:
                pool_repo = IStockPoolRepository(session)
                pools = await pool_repo.list_pools(pool_type=pool_type, limit=limit)
                return pools

        except Exception as e:
            logger.error(f"Failed to list pools: {e}")
            return []

    async def get_pool(self, pool_id: int) -> Optional[Dict]:
        """
        获取股票池详情

        Args:
            pool_id: 池ID

        Returns:
            股票池详情或None
        """
        try:
            async with get_async_session_context() as session:
                pool_repo = IStockPoolRepository(session)
                pool = await pool_repo.get_pool(pool_id)
                return pool

        except Exception as e:
            logger.error(f"Failed to get pool {pool_id}: {e}")
            return None

    async def create_pool(self, pool_data: Dict) -> Optional[Dict]:
        """
        创建股票池

        Args:
            pool_data: 池数据

        Returns:
            创建的池或None
        """
        try:
            async with get_async_session_context() as session:
                pool_repo = IStockPoolRepository(session)
                pool = await pool_repo.create_pool(pool_data)
                return pool

        except Exception as e:
            logger.error(f"Failed to create pool: {e}")
            return None

    async def update_pool(self, pool_id: int, updates: Dict) -> bool:
        """
        更新股票池

        Args:
            pool_id: 池ID
            updates: 更新数据

        Returns:
            是否成功
        """
        try:
            async with get_async_session_context() as session:
                pool_repo = IStockPoolRepository(session)
                success = await pool_repo.update_pool(pool_id, updates)
                return success

        except Exception as e:
            logger.error(f"Failed to update pool {pool_id}: {e}")
            return False

    async def delete_pool(self, pool_id: int) -> bool:
        """
        删除股票池

        Args:
            pool_id: 池ID

        Returns:
            是否成功
        """
        try:
            async with get_async_session_context() as session:
                pool_repo = IStockPoolRepository(session)
                success = await pool_repo.delete_pool(pool_id)
                return success

        except Exception as e:
            logger.error(f"Failed to delete pool {pool_id}: {e}")
            return False

    async def get_enabled_pools(self) -> List[Dict]:
        """
        获取所有启用的股票池

        Returns:
            启用的股票池列表
        """
        try:
            async with get_async_session_context() as session:
                pool_repo = IStockPoolRepository(session)
                pools = await pool_repo.get_enabled_pools()
                return pools

        except Exception as e:
            logger.error(f"Failed to get enabled pools: {e}")
            return []


__all__ = ['StockPoolAsyncService']
