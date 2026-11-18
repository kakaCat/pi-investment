"""交易计划、账户计划项、执行状态和归因闭环 ORM（REQ-261026140857-c192）

对应迁移：
- infrastructure/persistence/migrations/20261105_trading_plan.py
- infrastructure/persistence/migrations/20261105d_account_trading_plan.py

账户级新模型：
  · trading_plans               账户级持续主计划 + 旧单标历史
  · trading_plan_versions       每日/修改 revision（active 行不可变）
  · trading_plan_items          跨 revision 稳定计划项
  · trading_plan_item_versions  每 revision 的不可变计划项决策
  · trading_plan_item_states    独立可变执行状态与迁移基线
  · trading_plan_conditions     计划项版本的 entry/stop_loss/reduce 条件
  · trading_plan_runs           生成/readiness/对账/迁移运行历史
  · trading_plan_fill_receipts  成交推进幂等凭证
"""

from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from ..base import Base

__all__ = [
    "TradingPlan",
    "TradingPlanVersion",
    "TradingPlanRule",
    "TradingPlanEvent",
    "PlanReflection",
    "TradingPlanItem",
    "TradingPlanItemVersion",
    "TradingPlanItemState",
    "TradingPlanCondition",
    "TradingPlanRun",
    "TradingPlanFillReceipt",
]


class TradingPlan(Base):
    """计划本体。新账户主计划与旧单标历史共用表，以 plan_kind 区分。"""

    __tablename__ = "trading_plans"
    __table_args__ = {"schema": "quant"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    account = Column(String(60), nullable=False, comment="归属账户")
    name = Column(String(120), nullable=False)
    horizon = Column(String(16), nullable=True, comment="旧单标历史字段；账户级计划为空")
    status = Column(
        String(16),
        nullable=False,
        default="draft",
        comment="draft/reviewing/active/paused/closed/archived；旧行另有 holding/closing",
    )
    spec = Column(JSONB, nullable=True, comment="旧单标历史快照；账户级计划为空，不作为执行事实")
    draft_spec = Column(JSONB, nullable=True, comment="旧单标 PATCH 暂存；账户级计划为空")
    version = Column(
        Integer, nullable=False, default=1, comment="旧模型当前版本；新模型以 revision 为准"
    )
    stats = Column(JSONB, nullable=True, comment="命中率/盈亏/时延缓存（系统写）")
    review_interval_days = Column(Integer, default=1)
    review_due_at = Column(DateTime(timezone=True), nullable=True)
    last_reflected_at = Column(DateTime(timezone=True), nullable=True)
    reflection_overdue_count = Column(Integer, nullable=False, default=0)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    close_reason = Column(Text, nullable=True)
    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    plan_kind = Column(
        String(16), nullable=False, default="legacy_single", comment="legacy_single / account"
    )
    current_revision_id = Column(Integer, nullable=True, comment="当前激活 revision")
    draft_revision_id = Column(Integer, nullable=True, comment="当前草稿 revision")
    migrated_to_plan_id = Column(Integer, nullable=True, comment="旧计划迁移到的账户主计划")
    lock_version = Column(Integer, nullable=False, default=1, comment="主计划乐观锁")


class TradingPlanVersion(Base):
    """版本行。账户级模型中 revision.active 后不可变。"""

    __tablename__ = "trading_plan_versions"
    __table_args__ = {"schema": "quant"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False)
    spec = Column(JSONB, nullable=True, comment="旧模型版本快照；新模型为空")
    baseline = Column(JSONB, nullable=True, comment="修改前冻结基线指标")
    window_days = Column(Integer, default=10)
    window_ends_at = Column(Date, nullable=True)
    change_reason = Column(Text, nullable=True)
    hypothesis = Column(JSONB, nullable=True, comment="假设卡 change/evidence/expected")
    created_by = Column(String(50), nullable=False)
    decision_audit_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    trade_date = Column(Date, nullable=True, comment="账户级计划交易日")
    status = Column(
        String(16), nullable=True, comment="draft/reviewing/approved/active/superseded/rejected"
    )
    data_as_of = Column(DateTime(timezone=True), nullable=True, comment="行情事实时点")
    market_gate = Column(JSONB, nullable=True, comment="市场闸只读快照")
    risk_budget = Column(JSONB, nullable=True, comment="总敞口、现金和亏损限制")
    generation_key = Column(String(120), nullable=True, comment="每日初始生成幂等键")
    reviewed_by = Column(String(50), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    superseded_at = Column(DateTime(timezone=True), nullable=True)


class TradingPlanRule(Base):
    """编译产物映射：旧 (plan_id, role, symbol, batch) 与新 item 归因共存。"""

    __tablename__ = "trading_plan_rules"
    __table_args__ = {"schema": "quant"}

    plan_id = Column(Integer, primary_key=True)
    role = Column(String(24), primary_key=True)
    symbol = Column(String(20), primary_key=True)
    batch = Column(Integer, primary_key=True, default=0)
    rule_id = Column(Integer, nullable=False, comment="→ quant.watch_rules.id")
    item_id = Column(Integer, nullable=True, comment="→ trading_plan_items.id")
    plan_version = Column(Integer, nullable=True, comment="编译时的 revision 版本")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TradingPlanEvent(Base):
    """计划与计划项事件留痕。"""

    __tablename__ = "trading_plan_events"
    __table_args__ = {"schema": "quant"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, nullable=False)
    item_id = Column(Integer, nullable=True)
    plan_version = Column(Integer, nullable=True)
    kind = Column(
        String(24),
        nullable=False,
        comment="status_change/spec_change/compile/drift/reflection/fill",
    )
    from_status = Column(String(16), nullable=True)
    to_status = Column(String(16), nullable=True)
    detail = Column(JSONB, nullable=True)
    reason = Column(Text, nullable=True)
    actor = Column(String(50), nullable=False, comment="agent/user/system")
    decision_audit_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlanReflection(Base):
    """反思报告 + 材料包快照。账户级 item_id=NULL，item 级可精确归因。"""

    __tablename__ = "plan_reflections"
    __table_args__ = {"schema": "quant"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, nullable=False)
    item_id = Column(Integer, nullable=True)
    plan_version = Column(Integer, nullable=True)
    kind = Column(String(16), nullable=False, comment="daily/weekly/due/event")
    period = Column(String(16), nullable=False, comment="周期标识")
    version = Column(Integer, nullable=False, default=1)
    evidence_pack = Column(JSONB, nullable=False, comment="材料包快照")
    answers = Column(JSONB, nullable=False, comment="五问作答")
    verdict = Column(String(16), nullable=False, comment="keep/adjust/close/observe")
    reasoning = Column(Text, nullable=True)
    actions = Column(JSONB, nullable=True, comment="修改提案数组")
    knowledge_updates = Column(JSONB, nullable=True, comment="进化层消费段")
    agent_session_id = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TradingPlanItem(Base):
    """稳定计划项身份，跨 revision 延续。"""

    __tablename__ = "trading_plan_items"
    __table_args__ = {"schema": "quant"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, nullable=False)
    symbol = Column(String(20), nullable=False)
    legacy_plan_id = Column(Integer, nullable=True, comment="旧单标计划来源")
    opened_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)


class TradingPlanItemVersion(Base):
    """每个 revision 中计划项的不可变决策。"""

    __tablename__ = "trading_plan_item_versions"
    __table_args__ = {"schema": "quant"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    revision_id = Column(Integer, nullable=False, comment="→ trading_plan_versions.id")
    item_id = Column(Integer, nullable=False, comment="→ trading_plan_items.id")
    action = Column(
        String(12), nullable=False, comment="buy/add/observe/sell/reduce_risk/hold/avoid"
    )
    setup_type = Column(
        String(32), nullable=True, comment="交易场景：breakout/pullback/trend_follow 等"
    )
    horizon = Column(String(16), nullable=False, comment="day/swing")
    target_weight = Column(Numeric(9, 6), nullable=True)
    max_weight = Column(Numeric(9, 6), nullable=True)
    target_qty = Column(BigInteger, nullable=True)
    execution_batch = Column(Integer, nullable=True, comment="组合执行批次号")
    max_chase_pct = Column(Numeric(6, 3), nullable=True, comment="相对入场阈值的最大追高幅度（%）")
    entry_combinator = Column(String(8), nullable=False, default="all_of", comment="all_of/any_of")
    thesis = Column(Text, nullable=False)
    invalidation = Column(Text, nullable=False)
    entry_valid_until = Column(DateTime(timezone=True), nullable=True)
    evidence = Column(JSONB, nullable=True, comment="非核心证据快照")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TradingPlanItemState(Base):
    """计划项当前执行状态；初始数量保存旧计划迁移基线。"""

    __tablename__ = "trading_plan_item_states"
    __table_args__ = {"schema": "quant"}

    item_id = Column(Integer, primary_key=True)
    state = Column(
        String(16),
        nullable=False,
        comment="planned/ready/entering/holding/reducing/exited/cancelled",
    )
    target_qty = Column(BigInteger, nullable=True)
    filled_qty = Column(BigInteger, nullable=False, default=0)
    remaining_qty = Column(BigInteger, nullable=True)
    initial_position_qty = Column(BigInteger, nullable=False, default=0)
    initial_sold_qty = Column(BigInteger, nullable=False, default=0)
    last_fill_at = Column(DateTime(timezone=True), nullable=True)
    lock_version = Column(Integer, nullable=False, default=1)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class TradingPlanCondition(Base):
    """计划项条件。关联、角色与批次使用关系列，params 只存 DSL 参数。"""

    __tablename__ = "trading_plan_conditions"
    __table_args__ = {"schema": "quant"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_version_id = Column(Integer, nullable=False, comment="→ trading_plan_item_versions.id")
    role = Column(String(16), nullable=False, comment="entry/stop_loss/reduce")
    batch = Column(Integer, nullable=False, default=0)
    sequence = Column(Integer, nullable=False, default=0)
    condition_type = Column(String(40), nullable=False, comment="复用 WatchEngine DSL")
    params = Column(JSONB, nullable=False, comment="条件参数")
    invalidation_threshold_pct = Column(
        Numeric(6, 2), nullable=True, comment="V2 失效偏离阈值（%）"
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TradingPlanRun(Base):
    """计划任务运行历史。重试递增 attempt，首次失败历史保留。"""

    __tablename__ = "trading_plan_runs"
    __table_args__ = {"schema": "quant"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account = Column(String(60), nullable=False)
    trade_date = Column(Date, nullable=False)
    run_kind = Column(
        String(24), nullable=False, comment="generate/review/readiness/reconcile/migrate"
    )
    idempotency_key = Column(String(160), nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    plan_id = Column(Integer, nullable=True)
    revision_id = Column(Integer, nullable=True)
    status = Column(
        String(16),
        nullable=False,
        default="running",
        comment="running/succeeded/failed/degraded/interrupted",
    )
    reasons = Column(JSONB, nullable=False, default=[])
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)


class TradingPlanFillReceipt(Base):
    """成交推进幂等凭证；trade_id 主键防止重复推进。"""

    __tablename__ = "trading_plan_fill_receipts"
    __table_args__ = {"schema": "quant"}

    trade_id = Column(String(120), primary_key=True)
    plan_id = Column(Integer, nullable=False)
    item_id = Column(Integer, nullable=False)
    plan_version = Column(Integer, nullable=False)
    side = Column(String(4), nullable=False, comment="buy/sell")
    qty = Column(BigInteger, nullable=False)
    remaining_qty = Column(BigInteger, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
