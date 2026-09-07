"""
Stock & DailyKline 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from infrastructure.persistence.orm.models import Stock, DailyKline
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import date
import structlog

logger = structlog.get_logger(__name__)


class StockAsyncRepository(AsyncBaseORMRepository[Stock]):
    """异步股票Repository"""

    model = Stock

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_stock(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票信息

        Args:
            symbol: 股票代码

        Returns:
            股票字典或None
        """
        try:
            stock = await self.get_by_id(symbol)
            if not stock:
                return None

            return self._stock_to_dict(stock)

        except Exception as e:
            logger.error(f"Error getting stock {symbol}: {e}")
            return None

    async def list_stocks(
        self,
        market: Optional[str] = None,
        industry: Optional[str] = None,
        is_suspended: Optional[bool] = None,
        is_st: Optional[bool] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """列出股票

        Args:
            market: 市场（A/HK）
            industry: 行业
            is_suspended: 是否停牌
            is_st: 是否ST
            limit: 返回数量

        Returns:
            股票列表
        """
        try:
            stmt = select(Stock)

            if market:
                stmt = stmt.where(Stock.market == market)
            if industry:
                stmt = stmt.where(Stock.industry == industry)
            if is_suspended is not None:
                stmt = stmt.where(Stock.is_suspended == is_suspended)
            if is_st is not None:
                stmt = stmt.where(Stock.is_st == is_st)

            stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            stocks = result.scalars().all()

            return [self._stock_to_dict(s) for s in stocks]

        except Exception as e:
            logger.error(f"Error listing stocks: {e}")
            return []

    async def get_active_stocks(self, market: str = 'A') -> List[Dict[str, Any]]:
        """获取活跃股票（非停牌、非ST）

        Args:
            market: 市场

        Returns:
            活跃股票列表
        """
        return await self.list_stocks(
            market=market,
            is_suspended=False,
            is_st=False
        )

    async def search_by_name(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """按名称搜索股票

        Args:
            keyword: 关键词
            limit: 返回数量

        Returns:
            股票列表
        """
        try:
            stmt = select(Stock).where(
                Stock.name.like(f'%{keyword}%')
            ).limit(limit)

            result = await self.session.execute(stmt)
            stocks = result.scalars().all()

            return [self._stock_to_dict(s) for s in stocks]

        except Exception as e:
            logger.error(f"Error searching stocks by name: {e}")
            return []

    def _stock_to_dict(self, stock: Stock) -> Dict[str, Any]:
        """将Stock对象转换为字典"""
        return {
            'symbol': stock.symbol,
            'name': stock.name,
            'market': stock.market,
            'industry': stock.industry,
            'sector': stock.sector,
            'list_date': stock.list_date.isoformat() if stock.list_date else None,
            'is_st': stock.is_st,
            'is_suspended': stock.is_suspended,
            'updated_at': stock.updated_at.isoformat() if stock.updated_at else None,
        }


class DailyKlineAsyncRepository(AsyncBaseORMRepository[DailyKline]):
    """异步日K线Repository"""

    model = DailyKline

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_klines(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 250
    ) -> List[Dict[str, Any]]:
        """获取K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量

        Returns:
            K线数据列表
        """
        try:
            stmt = select(DailyKline).where(DailyKline.symbol == symbol)

            if start_date:
                stmt = stmt.where(DailyKline.trade_date >= start_date)
            if end_date:
                stmt = stmt.where(DailyKline.trade_date <= end_date)

            stmt = stmt.order_by(desc(DailyKline.trade_date)).limit(limit)

            result = await self.session.execute(stmt)
            klines = result.scalars().all()

            return [self._kline_to_dict(k) for k in klines]

        except Exception as e:
            logger.error(f"Error getting klines for {symbol}: {e}")
            return []

    async def get_latest_kline(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取最新K线

        Args:
            symbol: 股票代码

        Returns:
            K线数据或None
        """
        try:
            stmt = select(DailyKline).where(
                DailyKline.symbol == symbol
            ).order_by(desc(DailyKline.trade_date)).limit(1)

            result = await self.session.execute(stmt)
            kline = result.scalars().first()

            return self._kline_to_dict(kline) if kline else None

        except Exception as e:
            logger.error(f"Error getting latest kline for {symbol}: {e}")
            return None

    def _kline_to_dict(self, kline: DailyKline) -> Dict[str, Any]:
        """将DailyKline对象转换为字典"""
        return {
            'symbol': kline.symbol,
            'trade_date': kline.trade_date.isoformat() if kline.trade_date else None,
            'open': kline.open,
            'high': kline.high,
            'low': kline.low,
            'close': kline.close,
            'volume': kline.volume,
            'amount': kline.amount,
            'turnover_rate': kline.turnover_rate,
        }


__all__ = ['StockAsyncRepository', 'DailyKlineAsyncRepository']
