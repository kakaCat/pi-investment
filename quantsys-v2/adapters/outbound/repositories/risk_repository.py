"""
风险管理ORM Repository

迁移状态：✅ 已完成ORM迁移
"""
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import structlog

from sqlalchemy import desc
from infrastructure.persistence.orm import BaseORMRepository, get_session
from sqlalchemy import Column, Integer, String, Float, Date, Text, BigInteger, DateTime
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)

# 临时Model定义
class RiskMetric(Base):
    __tablename__ = 'risk_metrics'
    __table_args__ = {'schema': 'quant'}

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(20))
    metric_date = Column(Date)
    metric_name = Column(String(50))
    metric_value = Column(Float)


class AccountBalance(Base):
    __tablename__ = 'account_balance'
    __table_args__ = {'schema': 'quant'}

    id = Column(BigInteger, primary_key=True)
    balance_date = Column(Date, nullable=False, unique=True)
    cash = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    total_assets = Column(Float, nullable=False)
    daily_pnl = Column(Float)
    daily_return = Column(Float)
    total_pnl = Column(Float)
    total_return = Column(Float)
    position_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True))

from domain.ports import IRiskRepository

class RiskORMRepository(BaseORMRepository[RiskMetric], IRiskRepository):
    """风险管理ORM Repository"""
    model = RiskMetric

    def get_risk_metrics(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取风险指标（IRiskRepository接口实现）"""
        try:
            query = self.session.query(RiskMetric)

            if symbol:
                query = query.filter(RiskMetric.symbol == symbol)
            if start_date:
                query = query.filter(RiskMetric.metric_date >= start_date)
            if end_date:
                query = query.filter(RiskMetric.metric_date <= end_date)

            metrics = query.all()
            return [{
                'id': m.id,
                'symbol': m.symbol,
                'metric_date': m.metric_date.isoformat() if m.metric_date else None,
                'metric_name': m.metric_name,
                'metric_value': m.metric_value,
            } for m in metrics]

        except Exception as e:
            logger.error(f"Error getting risk metrics: {e}")
            return []

    def save_risk_metrics(self, metrics: Dict[str, Any]) -> int:
        """保存风险指标（IRiskRepository接口实现）"""
        try:
            metric = RiskMetric(
                symbol=metrics.get('symbol'),
                metric_date=metrics.get('metric_date'),
                metric_name=metrics.get('metric_name'),
                metric_value=metrics.get('metric_value'),
            )
            self.session.add(metric)
            self.session.commit()
            return metric.id if metric.id else 0

        except Exception as e:
            logger.error(f"Error saving risk metrics: {e}")
            self.session.rollback()
            return 0

    def get_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """获取账户余额历史记录

        Args:
            days: 查询的天数，默认30天

        Returns:
            账户余额历史记录列表，按日期升序排列
        """
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)

            query = self.session.query(AccountBalance).filter(
                AccountBalance.balance_date >= start_date,
                AccountBalance.balance_date <= end_date
            ).order_by(AccountBalance.balance_date.asc())

            balances = query.all()
            return [{
                'balance_date': b.balance_date,
                'cash': b.cash,
                'market_value': b.market_value,
                'total_assets': b.total_assets,
                'daily_pnl': b.daily_pnl,
                'daily_return': b.daily_return,
                'total_pnl': b.total_pnl,
                'total_return': b.total_return,
                'position_count': b.position_count,
            } for b in balances]

        except Exception as e:
            logger.error(f"Error getting account balance history: {e}", exc_info=True)
            return []

    def get_latest_balance(self) -> Optional[Dict[str, Any]]:
        """获取最新的账户余额记录

        Returns:
            最新的账户余额记录，如果没有记录则返回None
        """
        try:
            balance = self.session.query(AccountBalance).order_by(
                AccountBalance.balance_date.desc()
            ).first()

            if not balance:
                return None

            return {
                'balance_date': balance.balance_date,
                'cash': balance.cash,
                'market_value': balance.market_value,
                'total_assets': balance.total_assets,
                'daily_pnl': balance.daily_pnl,
                'daily_return': balance.daily_return,
                'total_pnl': balance.total_pnl,
                'total_return': balance.total_return,
                'position_count': balance.position_count,
                'created_at': balance.created_at,
            }

        except Exception as e:
            logger.error(f"Error getting latest balance: {e}", exc_info=True)
            return None

    def get_latest_risk_metrics(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取指定股票的最新风险指标

        Args:
            symbol: 股票代码

        Returns:
            最新的风险指标记录，如果没有记录则返回None
        """
        try:
            # 查询该股票最新日期的所有风险指标
            latest_date = self.session.query(RiskMetric.metric_date).filter(
                RiskMetric.symbol == symbol
            ).order_by(RiskMetric.metric_date.desc()).first()

            if not latest_date:
                return None

            # 获取该日期的所有指标
            metrics = self.session.query(RiskMetric).filter(
                RiskMetric.symbol == symbol,
                RiskMetric.metric_date == latest_date[0]
            ).all()

            if not metrics:
                return None

            # 将指标转换为字典格式 {metric_name: metric_value}
            result = {
                'symbol': symbol,
                'metric_date': latest_date[0].isoformat() if latest_date[0] else None,
            }

            for m in metrics:
                result[m.metric_name] = m.metric_value

            return result

        except Exception as e:
            logger.error(f"Error getting latest risk metrics for {symbol}: {e}", exc_info=True)
            return None
