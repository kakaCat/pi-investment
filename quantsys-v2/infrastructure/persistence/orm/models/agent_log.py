"""Agent 操作日志表（quant.agent_logs）。

建立背景（2026-09-14，w-32314d00，REQ-24e15d B4-c4）：
    该表此前**没有 ORM 模型**，全仓唯一的读写入口是
    `adapters/inbound/fastapi_app/routes/signals_async.py` 的 `/api/agent/logs` ——
    路由层直接 `db_cursor()` + f-string 拼 WHERE 子句（取值是绑定的，但结构在路由里）。
    收口后：表名/列名由模型唯一确定（写错列名在导入期即 UndefinedColumn，而不是运行时 500），
    路由层只剩展示映射。

语义要点：
    · 主键 id 是 UUID，由数据库 `gen_random_uuid()` 生成（应用侧不赋值）；
    · details / result 是 **NOT NULL** 的 jsonb —— 查询时不会出现 NULL，
      但历史行可能是空对象 `{}`，下游按 `or {}` 兜底；
    · timestamp 是 timestamptz，`/api/agent/logs` 的区间过滤按 **date** 语义
      （start >= date、end < date + 1 day），不是按时刻；
    · action_type / status 都有 **CHECK 约束**（见下，取值来自 pg_constraint，是唯一真源）——
      写错的取值会在落库时被数据库拒绝，而不是静默写入。
"""
from sqlalchemy import CheckConstraint, Column, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from ..base import Base

__all__ = ['AgentLog']


class AgentLog(Base):
    """Agent 操作日志

    对应数据库表：quant.agent_logs
    主键：id（uuid，服务端 gen_random_uuid()）
    """
    __tablename__ = 'agent_logs'
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('analysis','signal_generation','order_creation',"
            "'position_update','risk_check')",
            name='agent_logs_action_type_check',
        ),
        CheckConstraint(
            "status IN ('success','failed','partial')",
            name='agent_logs_status_check',
        ),
        {'schema': 'quant'},
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True,
                server_default=text('gen_random_uuid()'),
                comment='日志ID')
    timestamp = Column(DateTime(timezone=True), nullable=False, comment='发生时间')
    action_type = Column(Text, nullable=False, comment='动作类型')
    symbol = Column(Text, nullable=False, comment='标的代码')
    details = Column(JSONB, nullable=False, comment='动作详情')
    result = Column(JSONB, nullable=False, comment='执行结果')
    status = Column(Text, nullable=False, comment='状态')
    duration_ms = Column(Integer, nullable=True, comment='耗时（毫秒）')
    data_snapshot_id = Column(PG_UUID(as_uuid=True), nullable=True, comment='数据快照ID')
    created_at = Column(DateTime(timezone=True), nullable=True, server_default=text('now()'))

    def __repr__(self):
        return f"<AgentLog(id='{self.id}', action='{self.action_type}', symbol='{self.symbol}')>"
