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
    """机器学习模型ORM（对齐线上 quant.ml_models 真实结构）

    2026-09-10 修复（错误事件 ffc221de 根因，w-8f2c4cc5）：原声明 model_name /
    model_version / model_data / accuracy / created_at 五列在线上表中**不存在**，
    而 __table_args__ 用了 extend_existing=True —— 同名 Table 已存在时会**把不存在的
    列追加到该 Table 对象**上，污染 ml_model_repository.MlModel.__table__；后者
    _to_dict 遍历 table.columns 取值时撞上未被映射的 model_name →
    AttributeError → /api/ml/models 恒返回空且日志持续刷错（launchd-stdout.log）。
    现按线上表列对齐（与 ml_model_repository.MlModel 列集完全一致，杜绝同名表分叉）。
    """
    __tablename__ = 'ml_models'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(Integer, primary_key=True)
    model_type = Column(String(50))
    version = Column(String(50))
    model_path = Column(Text)
    train_accuracy = Column(Float)
    test_accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    roc_auc = Column(Float)
    feature_count = Column(Integer)
    train_samples = Column(Integer)
    feature_importance = Column(Text, default='{}')
    training_params = Column(Text, default='{}')
    training_report = Column(Text, default='{}')
    status = Column(String(20), default='ready')
    train_date = Column(DateTime(timezone=True))


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
            return [{'id': m.id, 'model_type': m.model_type, 'version': m.version,
                     'test_accuracy': m.test_accuracy, 'status': m.status,
                     'train_date': m.train_date.isoformat() if m.train_date else None}
                    for m in models]
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return []


# ==================== Position ====================
class Position(Base):
    """持仓ORM（对齐线上 quant.positions 真实结构）

    2026-09-10 修复（错误事件 f00fd8fe 连带）：原映射 id=BigInteger、成本列 cost_price
    与线上表（id 为 uuid、成本列 cost_basis）不一致，select 抛 UndefinedColumn 后被
    AsyncBaseORMRepository 吞掉 → /api/positions 恒返回 success:true + 空列表（静默空数据）。
    """
    __tablename__ = 'positions'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(String(36), primary_key=True)   # uuid 列
    account_id = Column(String(50))
    symbol = Column(String(20))
    name = Column(String(50))
    quantity = Column(Integer)
    cost_basis = Column(Float)                  # 线上列名（原误写 cost_price）
    current_price = Column(Float)
    market_value = Column(Float)
    unrealized_pnl = Column(Float)
    unrealized_pnl_pct = Column(Float)
    status = Column(String(20))
    updated_at = Column(DateTime(timezone=True))


class PositionAsyncRepository(AsyncBaseORMRepository[Position]):
    """异步持仓Repository"""
    model = Position

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_positions(
        self,
        account_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        stmt = select(Position)
        if account_id:
            stmt = stmt.where(Position.account_id == account_id)
        if status:
            stmt = stmt.where(Position.status == status)
        stmt = stmt.order_by(desc(Position.symbol)).limit(limit)

        result = await self.session.execute(stmt)
        positions = result.scalars().all()
        return [{'id': str(p.id), 'account_id': p.account_id, 'symbol': p.symbol,
                 'name': p.name, 'quantity': p.quantity, 'cost_basis': p.cost_basis,
                 'current_price': p.current_price, 'market_value': p.market_value,
                 'unrealized_pnl': p.unrealized_pnl,
                 'unrealized_pnl_pct': p.unrealized_pnl_pct,
                 'status': p.status,
                 'updated_at': p.updated_at.isoformat() if p.updated_at else None}
                for p in positions]


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
    """数据质量ORM（对齐线上 quant.data_quality_records）

    2026-09-10 修复（错误事件 f00fd8fe 连带）：原映射指向不存在的 quant.data_quality_checks
    （线上真表为 data_quality_records，列也完全不同），查询抛 UndefinedTable 后被基类吞掉
    → /api/data-quality/report 恒返回 success:true + checks:[]（静默空数据）。
    """
    __tablename__ = 'data_quality_records'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(20))
    period = Column(String(20))
    check_date = Column(Date)
    original_count = Column(Integer)
    cleaned_count = Column(Integer)
    removed_count = Column(Integer)
    fixed_count = Column(Integer)
    error_count = Column(Integer)
    warning_count = Column(Integer)
    completeness_score = Column(Float)
    consistency_score = Column(Float)
    accuracy_score = Column(Float)
    overall_score = Column(Float)
    grade = Column(String(10))
    duration_ms = Column(Integer)
    created_at = Column(DateTime)


class DataQualityAsyncRepository(AsyncBaseORMRepository[DataQuality]):
    """异步数据质量Repository"""
    model = DataQuality

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_checks(
        self,
        symbol: Optional[str] = None,
        period: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        stmt = select(DataQuality)
        if symbol:
            stmt = stmt.where(DataQuality.symbol == symbol)
        if period:
            stmt = stmt.where(DataQuality.period == period)
        stmt = stmt.order_by(desc(DataQuality.check_date), desc(DataQuality.id)).limit(limit)

        result = await self.session.execute(stmt)
        checks = result.scalars().all()
        return [{'id': c.id, 'symbol': c.symbol, 'period': c.period,
                 'check_date': c.check_date.isoformat() if c.check_date else None,
                 'original_count': c.original_count, 'cleaned_count': c.cleaned_count,
                 'error_count': c.error_count, 'warning_count': c.warning_count,
                 'overall_score': c.overall_score, 'grade': c.grade}
                for c in checks]


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
