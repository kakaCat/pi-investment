"""交易计划与反思闭环 ORM（REQ-261021222905-6dff t2，2026-10-22）

对应迁移：infrastructure/persistence/migrations/20261105_trading_plan.py

五张表（与 design/data-model.md 逐字段对齐）：
  · trading_plans          计划本体（spec / status / version / 反思周期）
  · trading_plan_versions  版本快照（行不可变，修改对照的基线来源）
  · trading_plan_rules     编译产物映射（plan_id + role + symbol → rule_id，即幂等键）
  · trading_plan_events    状态/修改留痕（时间线）
  · plan_reflections       反思报告 + 材料包快照（同周期重写 = version+1 新行）

值域口径：status / role / kind / verdict 一律由应用层把守（不加 CHECK），
与 data-model.md「不加 CHECK 枚举约束」一致——给未来扩枚举留余地。
"""
from sqlalchemy import (
    Column, Date, DateTime, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB

from ..base import Base

__all__ = [
    'TradingPlan', 'TradingPlanVersion', 'TradingPlanRule',
    'TradingPlanEvent', 'PlanReflection',
]


class TradingPlan(Base):
    """计划本体。对应数据库表：quant.trading_plans"""
    __tablename__ = 'trading_plans'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    account = Column(String(60), nullable=False, comment='归属账户（单计划单账户）')
    name = Column(String(120), nullable=False)
    horizon = Column(String(16), nullable=False, comment='day / swing')
    status = Column(String(16), nullable=False, default='draft',
                    comment='draft/active/holding/closing/closed/archived/paused')
    spec = Column(JSONB, nullable=False, comment='targets/entry/exit/monitoring/schedule')
    draft_spec = Column(JSONB, nullable=True, comment='PATCH 暂存（apply 后清空）')
    version = Column(Integer, nullable=False, default=1)
    stats = Column(JSONB, nullable=True, comment='命中率/盈亏/时延缓存（系统写）')
    review_interval_days = Column(Integer, default=1)
    review_due_at = Column(DateTime(timezone=True), nullable=True)
    last_reflected_at = Column(DateTime(timezone=True), nullable=True)
    reflection_overdue_count = Column(Integer, nullable=False, default=0)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    close_reason = Column(Text, nullable=True)
    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now(), onupdate=func.now())


class TradingPlanVersion(Base):
    """版本快照（行只插不改）。对应表：quant.trading_plan_versions"""
    __tablename__ = 'trading_plan_versions'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    spec = Column(JSONB, nullable=False)
    baseline = Column(JSONB, nullable=True, comment='修改前冻结基线指标')
    window_days = Column(Integer, default=10)
    window_ends_at = Column(Date, nullable=True)
    change_reason = Column(Text, nullable=True)
    hypothesis = Column(JSONB, nullable=True, comment='假设卡 change/evidence/expected')
    created_by = Column(String(50), nullable=False)
    decision_audit_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TradingPlanRule(Base):
    """编译产物映射。对应表：quant.trading_plan_rules（PK = 幂等键）"""
    __tablename__ = 'trading_plan_rules'
    __table_args__ = {'schema': 'quant'}

    plan_id = Column(Integer, primary_key=True)
    role = Column(String(24), primary_key=True)
    symbol = Column(String(20), primary_key=True)
    batch = Column(Integer, primary_key=True, default=0,
                   comment='同标的多批减仓的批次号（非批次角色恒 0）')
    rule_id = Column(Integer, nullable=False, comment='→ quant.watch_rules.id')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TradingPlanEvent(Base):
    """状态/修改留痕。对应表：quant.trading_plan_events"""
    __tablename__ = 'trading_plan_events'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, nullable=False)
    kind = Column(String(24), nullable=False,
                  comment='status_change/spec_change/compile/drift/reflection/fill')
    from_status = Column(String(16), nullable=True)
    to_status = Column(String(16), nullable=True)
    detail = Column(JSONB, nullable=True)
    reason = Column(Text, nullable=True)
    actor = Column(String(50), nullable=False, comment='agent/user/system')
    decision_audit_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlanReflection(Base):
    """反思报告 + 材料包快照。对应表：quant.plan_reflections

    (plan_id, kind, period) 再写时 version+1 新行——旧报告保留可查。
    """
    __tablename__ = 'plan_reflections'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, nullable=False)
    kind = Column(String(16), nullable=False, comment='daily/weekly/due/event')
    period = Column(String(16), nullable=False, comment='周期标识（如 2026-10-21）')
    version = Column(Integer, nullable=False, default=1)
    evidence_pack = Column(JSONB, nullable=False, comment='材料包快照（四输入）')
    answers = Column(JSONB, nullable=False, comment='五问作答')
    verdict = Column(String(16), nullable=False, comment='keep/adjust/close/observe')
    reasoning = Column(Text, nullable=True)
    actions = Column(JSONB, nullable=True, comment='修改提案数组')
    knowledge_updates = Column(JSONB, nullable=True, comment='进化层消费段')
    agent_session_id = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
