"""盯盘闭环底座 ORM（REQ-c9f899 t1，2026-09-18）

对应迁移：infrastructure/persistence/migrations/20260918_watch_todo_loop.py

五张表（四张核心 + 一张运行态单行 meta）：
  · watch_todos          待办（闭环状态机的唯一载体：级别 × 流转态 × 归属 × SLA × 终态）
  · watch_runtime_state  运行态（闩锁 / 冷却基准，跨重启恢复用）
  · watch_runtime_meta   运行态单行 meta（心跳 / 当前日期 / 事件窗口水位 / 影子起始）
  · watch_rule_changes   规则变更审计（自愈与人工修复的可反向应用凭据）
  · watch_receipts       回执（升级即 / 处置后 / 超时 / 抑噪）
  · watch_runtime_dedup  去重窗（REQ-c9f899 返工 B：同标的同向窗内合并的持久化）
  · watch_trigger_events 触发事件窗口（返工 C：频率/共振统计的跨重启连续）
  · watch_price_history  价格历史（返工 C：velocity 条件的跨重启不冷启动）

约束与 data-model.md §2 一一对应；三条 CHECK 是"必有终态""ignored 必须给 NEXT""动作类必带审计"
的 DB 侧兜底——应用层校验之外的第二道闸门。
"""
from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, Float, Integer, String, Text,
    func, text,
)
from sqlalchemy.dialects.postgresql import JSONB

from ..base import Base

__all__ = [
    'WatchTodo', 'WatchRuntimeState', 'WatchRuntimeMeta',
    'WatchRuleChange', 'WatchReceipt',
    'WatchRuntimeDedup', 'WatchTriggerEvent', 'WatchPriceHistory',
]


class WatchTodo(Base):
    """盯盘待办（闭环状态机：L1 通知 → L2 待办 → L3 处置 → 终态）

    对应数据库表：quant.watch_todos
    """
    __tablename__ = 'watch_todos'
    __table_args__ = (
        CheckConstraint('level IN (\'P0\',\'P1\',\'P2\',\'P3\')', name='watch_todos_level_check'),
        CheckConstraint('(terminal IS NULL) = (closed_at IS NULL)', name='watch_todos_closed_pair'),
        {'schema': 'quant'},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger_id = Column(Integer, nullable=True, comment='来源触发 id（触发删除后置空，冗余保存 rule_id/symbol）')
    rule_id = Column(Integer, nullable=True, comment='来源规则 id（冗余，供触发删除后追溯）')
    symbol = Column(String(20), nullable=False, comment='标的代码')
    account = Column(String(64), nullable=True, comment='规则归属账户（空=数据缺陷）')
    level = Column(String(2), nullable=False, comment='级别 P0..P3（决定颜值与时效）')
    flow_state = Column(String(2), nullable=False, server_default=text("'L1'"), comment='流转态 L1/L2/L3')
    owner_kind = Column(String(8), nullable=True, comment='接手方 agent/user')
    owner_ref = Column(String(64), nullable=True, comment='agent 标识或用户标识')
    autonomy = Column(String(16), nullable=True, comment='授权等级 autonomous/remind_only')
    sla_seconds = Column(Integer, nullable=False, comment='该级别的时效上限（秒）')
    due_at = Column(DateTime(timezone=True), nullable=False, comment='晋升/超时判定基准')
    claimed_at = Column(DateTime(timezone=True), nullable=True, comment='被认领时间')
    closed_at = Column(DateTime(timezone=True), nullable=True, comment='收敛时间')
    terminal = Column(String(16), nullable=True, comment='终态 handled/ignored/expired（NULL=未收敛）')
    close_reason = Column(Text, nullable=True, comment='为什么不动 / 动了什么')
    next_condition = Column(Text, nullable=True, comment='ignored 必填：下次什么条件下才动')
    action_kind = Column(String(24), nullable=True, comment='trade/rule_change/observe/none')
    decision_audit_id = Column(String(64), nullable=True, comment='I4：动作类关闭必须带决策审计 id')
    escalate_count = Column(Integer, nullable=False, server_default=text('0'), comment='晋升次数')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return (f'<WatchTodo(id={self.id}, symbol={self.symbol}, level={self.level}, '
                f'flow={self.flow_state}, terminal={self.terminal})>')


class WatchRuntimeState(Base):
    """运行态（闩锁与冷却基准）——跨重启恢复，保证冷却是真的

    对应数据库表：quant.watch_runtime_state；主键 (rule_id, cond_idx)。
    """
    __tablename__ = 'watch_runtime_state'
    __table_args__ = {'schema': 'quant'}

    rule_id = Column(Integer, primary_key=True, comment='规则 id')
    cond_idx = Column(Integer, primary_key=True, comment='条件下标（同一规则多条件各自冷却）')
    latched = Column(Boolean, nullable=False, server_default=text('false'), comment='是否处于闩锁（电平保持不重复推）')
    last_triggered_at = Column(DateTime(timezone=True), nullable=True, comment='最近一次产出时间（冷却基准）')
    cooldown_effective_sec = Column(Integer, nullable=True, comment='自愈临时延长后的有效冷却（秒）')
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WatchRuntimeMeta(Base):
    """运行态单行 meta（心跳 / 当日 / 事件窗口水位）

    对应数据库表：quant.watch_runtime_meta，恒为 id=1。
    """
    __tablename__ = 'watch_runtime_meta'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, comment='固定为 1')
    heartbeat_at = Column(DateTime(timezone=True), nullable=True, comment='引擎最近一次心跳（存活告警依据）')
    state_date = Column(Date, nullable=True, comment='状态所属交易日（跨天重置判定；命名避开 PG 保留字 current_date）')
    event_watermark = Column(DateTime(timezone=True), nullable=True, comment='触发事件窗口裁剪水位')
    digest_shadow_since = Column(
        DateTime(timezone=True), nullable=True,
        comment='影子模式首次进入时间（跨重启保持，库优先 env 兜底）')
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WatchRuleChange(Base):
    """规则变更审计（自愈/人工修复留痕，可反向应用）

    对应数据库表：quant.watch_rule_changes（追加写）。
    """
    __tablename__ = 'watch_rule_changes'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, nullable=False, comment='被变更的规则 id')
    changed_by = Column(String(16), nullable=False, comment='agent/user/system')
    change_kind = Column(String(24), nullable=False,
                         comment='cooldown/threshold/split/merge/retire/suppress/unsuppress')
    before = Column(JSONB, nullable=True, comment='变更前（仅涉及字段）')
    after = Column(JSONB, nullable=True, comment='变更后（仅涉及字段）')
    reason = Column(Text, nullable=False, comment='变更理由（必填）')
    trigger_id = Column(Integer, nullable=True, comment='溯源触发 id')
    todo_id = Column(Integer, nullable=True, comment='溯源待办 id')
    decision_audit_id = Column(String(64), nullable=True, comment='agent 自主变更时必填')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WatchReceipt(Base):
    """回执（升级即 / 处置后 / 超时 / 抑噪）

    对应数据库表：quant.watch_receipts（追加写）；payload_digest 用于同一待办不重复发同一条回执。
    """
    __tablename__ = 'watch_receipts'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    todo_id = Column(Integer, nullable=False, comment='所属待办 id')
    kind = Column(String(16), nullable=False, comment='escalate/result/timeout/suppressed')
    channel = Column(String(32), nullable=True, comment='逻辑频道码')
    delivery_status = Column(String(16), nullable=True, comment='sent/failed')
    message_id = Column(String(64), nullable=True, comment='与 notification_logs 关联')
    payload_digest = Column(String(64), nullable=False, comment='渲染输入摘要（幂等去重）')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WatchRuntimeDedup(Base):
    """去重窗（REQ-c9f899 返工 B / R10）

    对应数据库表：quant.watch_price_history 的姊妹表 quant.watch_runtime_dedup。
    主键 (symbol, direction) = 引擎 dedup_key(rule, condition) 的归一化形态：
    「同一标的 + 同一方向」在 dedup_window_sec 内只通知一次。持久化的意义：
    重启后窗内**不再重复通知**（未持久化时窗清零，同一条当天会重推）。

    有界性：notified_at 早于窗口的行走仓库的 prune（DELETE），
    StateManager 启动恢复时也会按窗口过滤——双保险，落库侧不得无界增长。
    """
    __tablename__ = 'watch_runtime_dedup'
    __table_args__ = {'schema': 'quant'}

    symbol = Column(String(32), primary_key=True, comment='归一化标的（去交易所后缀）')
    direction = Column(String(32), primary_key=True, comment='方向（above/below 或条件类型）')
    notified_at = Column(DateTime(timezone=True), nullable=False, comment='最近一次通知时间（窗内判据）')
    trigger_id = Column(Integer, nullable=True, comment='合并到的触发 id（dup_of）')
    rule_id = Column(Integer, nullable=True, comment='最近通知的规则 id（跨规则重叠判定）')
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WatchTriggerEvent(Base):
    """触发事件窗口（REQ-c9f899 返工 C / R10）

    对应数据库表：quant.watch_trigger_events。事件日志是频率升级与多规则共振统计的
    **单一事实源**（见 StateManager.trigger_events），此前只在内存：重启后频率/共振
    从 0 起算，自愈阈值与升级判据被误判。持久化后恢复窗口内事件，统计连续。

    主键 (triggered_at, rule_id, symbol)：让「写失败重试」幂等（ON CONFLICT DO NOTHING）。
    代价是同一条规则在同一秒对同一标的的两次事件会合并为一条——mark_emitted 的闩锁/
    冷却保证同一 (rule, cond) 不会同秒重复，跨条件的同秒极端情形只影响计数 ±1，
    远小于"窗口清零"的量级偏差，故取此口径（可证伪：见 test_runtime_complete.py）。

    有界性：按 event_retention_min（默认 30 分钟）由 prune 删除。
    """
    __tablename__ = 'watch_trigger_events'
    __table_args__ = {'schema': 'quant'}

    triggered_at = Column(DateTime(timezone=True), primary_key=True, comment='触发时间')
    rule_id = Column(Integer, primary_key=True, comment='规则 id')
    symbol = Column(String(32), primary_key=True, comment='标的代码')


class WatchPriceHistory(Base):
    """价格历史（REQ-c9f899 返工 C / R10）

    对应数据库表：quant.watch_price_history。velocity 条件需要 ~30 分钟价格序列，
    此前只在内存 → 重启后有冷启动盲区（不判定）。持久化后按 symbols（启用规则宇宙）
    且有界恢复，消除盲区。

    主键 (symbol, ts)：同一 symbol 同一时刻一个价格，写失败重试幂等。
    有界性：按 history_retention_min（默认 30 分钟）由 prune 删除；恢复只取
    启用规则覆盖的 symbols 且窗口内的点。
    """
    __tablename__ = 'watch_price_history'
    __table_args__ = {'schema': 'quant'}

    symbol = Column(String(32), primary_key=True, comment='标的代码')
    ts = Column(DateTime(timezone=True), primary_key=True, comment='价格时间戳')
    price = Column(Float, nullable=False, comment='价格（元）')
