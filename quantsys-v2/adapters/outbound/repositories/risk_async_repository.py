"""
Risk 异步ORM Repository

迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from sqlalchemy import Column, BigInteger, String, Float, Date, select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.persistence.orm.base import Base
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class RiskMetric(Base):
    """风险指标ORM模型"""
    __tablename__ = 'risk_metrics'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(20))
    metric_date = Column(Date)
    metric_name = Column(String(50))
    metric_value = Column(Float)


class RiskAsyncRepository(AsyncBaseORMRepository[RiskMetric]):
    """异步风险Repository"""

    model = RiskMetric

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_risk_metrics(
        self,
        symbol: Optional[str] = None,
        metric_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取风险指标

        Args:
            symbol: 股票代码（可选）
            metric_name: 指标名称（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 返回数量

        Returns:
            风险指标列表
        """
        try:
            stmt = select(RiskMetric)

            if symbol:
                stmt = stmt.where(RiskMetric.symbol == symbol)
            if metric_name:
                stmt = stmt.where(RiskMetric.metric_name == metric_name)
            if start_date:
                stmt = stmt.where(RiskMetric.metric_date >= start_date)
            if end_date:
                stmt = stmt.where(RiskMetric.metric_date <= end_date)

            stmt = stmt.order_by(desc(RiskMetric.metric_date)).limit(limit)

            result = await self.session.execute(stmt)
            metrics = result.scalars().all()

            return [self._metric_to_dict(m) for m in metrics]

        except Exception as e:
            logger.error(f"Error getting risk metrics: {e}")
            return []

    async def save_risk_metrics(self, metrics_data: Dict[str, Any]) -> Optional[int]:
        """保存风险指标

        Args:
            metrics_data: 指标数据

        Returns:
            指标ID或None
        """
        try:
            metric = await self.create(metrics_data)
            return metric.id if metric else None

        except Exception as e:
            logger.error(f"Error saving risk metrics: {e}")
            return None

    async def get_latest_metrics(
        self,
        symbol: str,
        metric_names: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """获取最新风险指标

        Args:
            symbol: 股票代码
            metric_names: 指标名称列表（可选）

        Returns:
            指标字典 {metric_name: metric_value}
        """
        try:
            stmt = select(RiskMetric).where(RiskMetric.symbol == symbol)

            if metric_names:
                stmt = stmt.where(RiskMetric.metric_name.in_(metric_names))

            stmt = stmt.order_by(desc(RiskMetric.metric_date))

            result = await self.session.execute(stmt)
            metrics = result.scalars().all()

            # 取每个指标的最新值
            latest_metrics = {}
            seen_metrics = set()
            for metric in metrics:
                if metric.metric_name not in seen_metrics:
                    latest_metrics[metric.metric_name] = metric.metric_value
                    seen_metrics.add(metric.metric_name)

            return latest_metrics

        except Exception as e:
            logger.error(f"Error getting latest metrics for {symbol}: {e}")
            return {}

    def _metric_to_dict(self, metric: RiskMetric) -> Dict[str, Any]:
        """将RiskMetric对象转换为字典"""
        return {
            'id': metric.id,
            'symbol': metric.symbol,
            'metric_date': metric.metric_date.isoformat() if metric.metric_date else None,
            'metric_name': metric.metric_name,
            'metric_value': metric.metric_value,
        }


__all__ = ['RiskAsyncRepository', 'RiskMetric']
