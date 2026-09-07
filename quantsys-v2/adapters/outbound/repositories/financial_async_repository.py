"""
Financial 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from sqlalchemy import Column, BigInteger, String, Float, Date, Text, DateTime, JSON, select
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.persistence.orm.base import Base
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class Financial(Base):
    """财务数据ORM模型"""
    __tablename__ = 'financials'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(20))
    report_date = Column(Date)
    financial_data = Column(JSON)
    created_at = Column(DateTime)


class FinancialAsyncRepository(AsyncBaseORMRepository[Financial]):
    """异步财务数据Repository"""

    model = Financial

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_financials(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取财务数据

        Args:
            symbol: 股票代码（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 返回数量

        Returns:
            财务数据列表
        """
        try:
            stmt = select(Financial)

            if symbol:
                stmt = stmt.where(Financial.symbol == symbol)
            if start_date:
                stmt = stmt.where(Financial.report_date >= start_date)
            if end_date:
                stmt = stmt.where(Financial.report_date <= end_date)

            stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            financials = result.scalars().all()

            return [self._financial_to_dict(f) for f in financials]

        except Exception as e:
            logger.error(f"Error getting financials: {e}")
            return []

    async def get_latest_financial(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取最新财务数据

        Args:
            symbol: 股票代码

        Returns:
            财务数据字典或None
        """
        try:
            stmt = select(Financial).where(
                Financial.symbol == symbol
            ).order_by(Financial.report_date.desc()).limit(1)

            result = await self.session.execute(stmt)
            financial = result.scalars().first()

            return self._financial_to_dict(financial) if financial else None

        except Exception as e:
            logger.error(f"Error getting latest financial for {symbol}: {e}")
            return None

    def _financial_to_dict(self, financial: Financial) -> Dict[str, Any]:
        """将Financial对象转换为字典"""
        return {
            'id': financial.id,
            'symbol': financial.symbol,
            'report_date': financial.report_date.isoformat() if financial.report_date else None,
            'financial_data': financial.financial_data,
            'created_at': financial.created_at.isoformat() if financial.created_at else None,
        }


__all__ = ['FinancialAsyncRepository', 'Financial']
