"""
通用P2 异步Repository集合

包含多个低优先级的异步Repository
迁移状态：✅ 异步版本
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from sqlalchemy import Column, BigInteger, String, Float, Date, Text, DateTime, JSON, Integer, Boolean, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import structlog

# ---------------------------------------------------------------------------
# 唯一事实源：本文件的模型一律从各自仓储 import，**不再重复声明同名表**。
#
# 为什么必须这样（本仓已因此发生三次线上静默故障）：
#   「同名表 + extend_existing=True」在第二次声明时会把新列**追加**到已存在的
#   Table 对象上，污染第一个模型的 __table__；查询遍历 table.columns 时撞上
#   未被映射的列 → AttributeError / UndefinedColumn → 被 except 吞掉 → 接口恒空。
#     · ffc221de  /api/ml/models 恒返回空
#     · f00fd8fe  /api/positions、/api/data-quality/report 恒返回空列表
#     · risk_repository 曾被建成 EAV 错结构（metric_name/metric_value）
#
# 2026-09-14（w-2129d492）：删除本文件的 4 份重复定义，改为 import 权威模型。
# ---------------------------------------------------------------------------
from adapters.outbound.repositories.data_quality_repository import DataQualityRecord as DataQuality
from adapters.outbound.repositories.fund_flow_repository import FundFlow
from adapters.outbound.repositories.ml_model_repository import MlModel as MLModel
from adapters.outbound.repositories.position_repository import Position

logger = structlog.get_logger(__name__)


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


# ==================== 【已删除】Automation / AgentIntelligence ====================
# 2026-09-14（w-2129d492）：删掉重复定义的两个模型类及其 async 仓储。
# 删除理由：它们是"同名表 + extend_existing=True"的第二份声明，用到它们的两个只读路由
# （/api/automation/tasks、/api/agent-intelligence/knowledge）已确认是死接口：
#   · AutomationTask 的列名与真库不符（enabled/last_run/schedule vs is_enabled/last_run_at/
#     schedule_config）→ 查询报 UndefinedColumn 被 except 吞掉 → 恒返回空（假成功）；
#   · AgentIntelligence 的 quant.agent_intelligence 表在库中从未存在过 → 同样恒返回空。
# 本仓已有同因先例：2026-09-10 MLModel 因同一写法造成 /api/ml/models 恒空，当时是**对齐列名**修好的。
# 这里选择删除而非对齐，因为**没有消费者、也没有执行器**（详见 p2_batch1_async.py 顶部注释）。
# ⚠️ 注意区分：adapters/outbound/repositories/agent_intelligence_repository.py 是**活代码**，
#    它映射的是 quant.agent_decisions（决策审计/评分/教训），与本次删除无关。


__all__ = [
    'MLModelAsyncRepository',
    'PositionAsyncRepository',
    'FundFlowAsyncRepository',
    'DataQualityAsyncRepository',
]
