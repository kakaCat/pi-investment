"""
Factor 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from infrastructure.persistence.orm.models import FactorValue
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import date
import structlog

logger = structlog.get_logger(__name__)


class FactorAsyncRepository(AsyncBaseORMRepository[FactorValue]):
    """异步因子Repository"""

    model = FactorValue

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_factor_values(
        self,
        symbol: Optional[str] = None,
        factor_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """获取因子值

        Args:
            symbol: 股票代码（可选）
            factor_name: 因子名称（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 返回数量

        Returns:
            因子值列表
        """
        try:
            stmt = select(FactorValue)

            if symbol:
                stmt = stmt.where(FactorValue.symbol == symbol)
            if factor_name:
                stmt = stmt.where(FactorValue.factor_name == factor_name)
            if start_date:
                stmt = stmt.where(FactorValue.factor_date >= start_date)
            if end_date:
                stmt = stmt.where(FactorValue.factor_date <= end_date)

            stmt = stmt.order_by(desc(FactorValue.factor_date)).limit(limit)

            result = await self.session.execute(stmt)
            factors = result.scalars().all()

            return [self._factor_to_dict(f) for f in factors]

        except Exception as e:
            logger.error(f"Error getting factor values: {e}")
            return []

    async def get_latest_factors(
        self,
        symbol: str,
        factor_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """获取最新因子值

        Args:
            symbol: 股票代码
            factor_names: 因子名称列表（可选）

        Returns:
            因子字典 {factor_name: factor_value}
        """
        try:
            stmt = select(FactorValue).where(FactorValue.symbol == symbol)

            if factor_names:
                stmt = stmt.where(FactorValue.factor_name.in_(factor_names))

            stmt = stmt.order_by(desc(FactorValue.factor_date))

            result = await self.session.execute(stmt)
            factors = result.scalars().all()

            # 取每个因子的最新值
            latest_factors = {}
            seen_factors = set()
            for factor in factors:
                if factor.factor_name not in seen_factors:
                    latest_factors[factor.factor_name] = factor.factor_value
                    seen_factors.add(factor.factor_name)

            return latest_factors

        except Exception as e:
            logger.error(f"Error getting latest factors for {symbol}: {e}")
            return {}

    async def batch_save_factors(
        self,
        factors_data: List[Dict[str, Any]]
    ) -> int:
        """批量保存因子值

        Args:
            factors_data: 因子数据列表

        Returns:
            成功保存的数量
        """
        try:
            success_count = 0
            for factor_data in factors_data:
                factor = await self.create(factor_data)
                if factor:
                    success_count += 1

            return success_count

        except Exception as e:
            logger.error(f"Error batch saving factors: {e}")
            return 0

    async def get_factor_by_date(
        self,
        symbol: str,
        factor_name: str,
        factor_date: str
    ) -> Optional[float]:
        """获取指定日期的因子值

        Args:
            symbol: 股票代码
            factor_name: 因子名称
            factor_date: 日期

        Returns:
            因子值或None
        """
        try:
            stmt = select(FactorValue).where(
                and_(
                    FactorValue.symbol == symbol,
                    FactorValue.factor_name == factor_name,
                    FactorValue.factor_date == factor_date
                )
            )

            result = await self.session.execute(stmt)
            factor = result.scalars().first()

            return factor.factor_value if factor else None

        except Exception as e:
            logger.error(f"Error getting factor by date: {e}")
            return None

    def _factor_to_dict(self, factor: FactorValue) -> Dict[str, Any]:
        """将FactorValue对象转换为字典"""
        return {
            'symbol': factor.symbol,
            'factor_date': factor.factor_date.isoformat() if factor.factor_date else None,
            'factor_name': factor.factor_name,
            'factor_value': factor.factor_value,
        }


__all__ = ['FactorAsyncRepository']
