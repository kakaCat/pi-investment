"""
通用P2 异步Repository集合

包含多个低优先级的异步Repository
迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from sqlalchemy import Column, BigInteger, String, Float, Date, Text, DateTime, JSON, Integer, Boolean, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.persistence.orm.base import Base
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


# ==================== MLModel ====================
class MLModel(Base):
    """机器学习模型ORM"""
    __tablename__ = 'ml_models'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True)
    model_name = Column(String(100))
    model_type = Column(String(50))
    model_version = Column(String(20))
    model_data = Column(JSON)
    accuracy = Column(Float)
    created_at = Column(DateTime)


class MLModelAsyncRepository(AsyncBaseORMRepository[MLModel]):
    """异步ML模型Repository"""
    model = MLModel

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_models(
        self,
        model_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        try:
            if model_type:
                models = await self.find_by_condition(model_type=model_type)
            else:
                models = await self.list_all(limit=limit)
            return [{'id': m.id, 'model_name': m.model_name, 'model_type': m.model_type,
                     'accuracy': m.accuracy} for m in models]
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return []


# ==================== Position ====================
class Position(Base):
    """持仓ORM"""
    __tablename__ = 'positions'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True)
    account_id = Column(String(50))
    symbol = Column(String(20))
    quantity = Column(Integer)
    cost_price = Column(Float)
    current_price = Column(Float)
    updated_at = Column(DateTime)


class PositionAsyncRepository(AsyncBaseORMRepository[Position]):
    """异步持仓Repository"""
    model = Position

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_positions(
        self,
        account_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        try:
            if account_id:
                positions = await self.find_by_condition(account_id=account_id)
            else:
                positions = await self.list_all(limit=limit)
            return [{'id': p.id, 'symbol': p.symbol, 'quantity': p.quantity,
                     'cost_price': p.cost_price} for p in positions]
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []


# ==================== FundFlow ====================
class FundFlow(Base):
    """资金流向ORM（quant.stock_fund_flow，金额单位：万元）"""
    __tablename__ = 'stock_fund_flow'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20))
    trade_date = Column(Date)
    close_price = Column(Float)
    change_pct = Column(Float)
    main_net_inflow = Column(Float)
    large_net_inflow = Column(Float)
    big_net_inflow = Column(Float)
    medium_net_inflow = Column(Float)
    small_net_inflow = Column(Float)


class FundFlowAsyncRepository(AsyncBaseORMRepository[FundFlow]):
    """异步资金流向Repository"""
    model = FundFlow

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_flows(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        try:
            stmt = select(FundFlow)
            if symbol:
                stmt = stmt.where(FundFlow.symbol == symbol)
            if start_date:
                stmt = stmt.where(FundFlow.trade_date >= start_date)
            stmt = stmt.order_by(desc(FundFlow.trade_date)).limit(limit)

            result = await self.session.execute(stmt)
            flows = result.scalars().all()
            return [{'symbol': f.symbol, 'trade_date': f.trade_date.isoformat() if f.trade_date else None,
                     'close_price': f.close_price, 'change_pct': f.change_pct,
                     'main_net_inflow': f.main_net_inflow,
                     'large_net_inflow': f.large_net_inflow,
                     'big_net_inflow': f.big_net_inflow,
                     'medium_net_inflow': f.medium_net_inflow,
                     'small_net_inflow': f.small_net_inflow} for f in flows]
        except Exception as e:
            logger.error(f"Error getting flows: {e}")
            return []


# ==================== DataQuality ====================
class DataQuality(Base):
    """数据质量ORM"""
    __tablename__ = 'data_quality_checks'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True)
    check_date = Column(Date)
    table_name = Column(String(100))
    check_type = Column(String(50))
    passed = Column(Boolean)
    details = Column(JSON)


class DataQualityAsyncRepository(AsyncBaseORMRepository[DataQuality]):
    """异步数据质量Repository"""
    model = DataQuality

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_checks(
        self,
        table_name: Optional[str] = None,
        passed: Optional[bool] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        try:
            conditions = {}
            if table_name:
                conditions['table_name'] = table_name
            if passed is not None:
                conditions['passed'] = passed

            if conditions:
                checks = await self.find_by_condition(**conditions)
            else:
                checks = await self.list_all(limit=limit)

            return [{'id': c.id, 'table_name': c.table_name, 'check_type': c.check_type,
                     'passed': c.passed} for c in checks]
        except Exception as e:
            logger.error(f"Error getting checks: {e}")
            return []


# ==================== Automation ====================
class AutomationTask(Base):
    """自动化任务ORM"""
    __tablename__ = 'automation_tasks'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True)
    task_name = Column(String(100))
    task_type = Column(String(50))
    schedule = Column(String(50))
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime)


class AutomationAsyncRepository(AsyncBaseORMRepository[AutomationTask]):
    """异步自动化任务Repository"""
    model = AutomationTask

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_enabled_tasks(self) -> List[Dict[str, Any]]:
        try:
            tasks = await self.find_by_condition(enabled=True)
            return [{'id': t.id, 'task_name': t.task_name, 'schedule': t.schedule,
                     'last_run': t.last_run.isoformat() if t.last_run else None} for t in tasks]
        except Exception as e:
            logger.error(f"Error getting enabled tasks: {e}")
            return []


# ==================== AgentIntelligence ====================
class AgentIntelligence(Base):
    """智能体知识ORM"""
    __tablename__ = 'agent_intelligence'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True)
    knowledge_type = Column(String(50))
    knowledge_key = Column(String(100))
    knowledge_value = Column(JSON)
    confidence = Column(Float)
    created_at = Column(DateTime)


class AgentIntelligenceAsyncRepository(AsyncBaseORMRepository[AgentIntelligence]):
    """异步智能体知识Repository"""
    model = AgentIntelligence

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_knowledge(
        self,
        knowledge_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        try:
            if knowledge_type:
                knowledge = await self.find_by_condition(knowledge_type=knowledge_type)
            else:
                knowledge = await self.list_all(limit=limit)
            return [{'id': k.id, 'knowledge_type': k.knowledge_type, 'knowledge_key': k.knowledge_key,
                     'confidence': k.confidence} for k in knowledge]
        except Exception as e:
            logger.error(f"Error getting knowledge: {e}")
            return []


__all__ = [
    'MLModelAsyncRepository',
    'PositionAsyncRepository',
    'FundFlowAsyncRepository',
    'DataQualityAsyncRepository',
    'AutomationAsyncRepository',
    'AgentIntelligenceAsyncRepository',
]
