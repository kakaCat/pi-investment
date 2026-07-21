"""
MarketStyle 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Date, Text, DateTime, JSON, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.persistence.orm.base import Base
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class MarketStyleState(Base):
    """市场风格状态ORM模型"""
    __tablename__ = 'market_style_state'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(Integer, primary_key=True)
    state_date = Column(Date)
    style_name = Column(String(50))
    style_value = Column(Float)
    style_data = Column(JSON)
    created_at = Column(DateTime)


class MarketStyleAsyncRepository(AsyncBaseORMRepository[MarketStyleState]):
    """异步市场风格Repository"""

    model = MarketStyleState

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_market_styles(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        style_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取市场风格数据

        Args:
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            style_name: 风格名称（可选）
            limit: 返回数量

        Returns:
            市场风格数据列表
        """
        try:
            stmt = select(MarketStyleState)

            if start_date:
                stmt = stmt.where(MarketStyleState.state_date >= start_date)
            if end_date:
                stmt = stmt.where(MarketStyleState.state_date <= end_date)
            if style_name:
                stmt = stmt.where(MarketStyleState.style_name == style_name)

            stmt = stmt.order_by(desc(MarketStyleState.state_date)).limit(limit)

            result = await self.session.execute(stmt)
            styles = result.scalars().all()

            return [self._style_to_dict(s) for s in styles]

        except Exception as e:
            logger.error(f"Error getting market styles: {e}")
            return []

    async def get_latest_style(self) -> Optional[Dict[str, Any]]:
        """获取最新市场风格

        Returns:
            市场风格字典或None
        """
        try:
            stmt = select(MarketStyleState).order_by(
                desc(MarketStyleState.state_date)
            ).limit(1)

            result = await self.session.execute(stmt)
            style = result.scalars().first()

            return self._style_to_dict(style) if style else None

        except Exception as e:
            logger.error(f"Error getting latest style: {e}")
            return None

    async def save_style(self, style_data: Dict[str, Any]) -> Optional[int]:
        """保存市场风格数据

        Args:
            style_data: 风格数据

        Returns:
            ID或None
        """
        try:
            style = await self.create(style_data)
            return style.id if style else None

        except Exception as e:
            logger.error(f"Error saving market style: {e}")
            return None

    def _style_to_dict(self, style: MarketStyleState) -> Dict[str, Any]:
        """将MarketStyleState对象转换为字典"""
        return {
            'id': style.id,
            'state_date': style.state_date.isoformat() if style.state_date else None,
            'style_name': style.style_name,
            'style_value': style.style_value,
            'style_data': style.style_data,
            'created_at': style.created_at.isoformat() if style.created_at else None,
        }


__all__ = ['MarketStyleAsyncRepository', 'MarketStyleState']
