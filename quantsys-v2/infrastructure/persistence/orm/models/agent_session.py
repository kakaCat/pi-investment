"""Agent 会话与事件表（quant.agent_sessions / quant.agent_session_events）。

建立背景（2026-09-14，w-32314d00，REQ-24e15d B3）：
    这两张表此前**没有 ORM 模型**，读写全部散在
    `application/services/session_service.py` 里以 db_cursor + 裸 SQL 形式存在
    （13 处，含一处 f-string 拼列名做计数器自增）。收口后：
      · 表名/列名由模型唯一确定（写错在导入期即 UndefinedTable，而不是运行时静默失败）；
      · 计数器自增的列名走白名单（列名无法参数化）；
      · 服务层只剩编排与文案。

语义要点：
    · agent_session_events 的 **UNIQUE(session_key, seq)** 是幂等键 —— 重复投递同一 seq
      必须 DO NOTHING（不是报错，也不算 accepted）；
    · 事件表对 agent_sessions 有外键，故摄入事件前必须先 upsert 会话行；
    · last_active_at 取 **GREATEST(旧值, 新值)**，乱序投递不会让时间倒退。
"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from ..base import Base

__all__ = ['AgentSession', 'AgentSessionEvent']

# 允许被"计数器自增"更新的列（session_service._COUNTER_MAP 的取值集合）。
# 列名无法用绑定参数，白名单是唯一正解；放常量里便于测试直接断言。
SESSION_COUNTER_COLUMNS = frozenset({'message_count', 'tool_call_count', 'error_count'})


class AgentSession(Base):
    """Agent 会话（每 session_key 一行）

    对应数据库表：quant.agent_sessions
    主键：session_key
    """
    __tablename__ = 'agent_sessions'
    __table_args__ = {'schema': 'quant'}

    session_key = Column(Text, primary_key=True, comment='会话标识')
    channel = Column(String, nullable=False, comment='来源渠道')
    peer_id = Column(String, nullable=False, comment='对端标识')
    agent_id = Column(String, nullable=False, comment='agent 标识')
    started_at = Column(DateTime(timezone=True), nullable=False)
    last_active_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False)
    message_count = Column(Integer, nullable=True)
    tool_call_count = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)
    ai_diagnosis = Column(JSONB, nullable=True)
    ai_diagnosis_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<AgentSession(key='{self.session_key}', channel='{self.channel}')>"


class AgentSessionEvent(Base):
    """Agent 会话事件（seq 在会话内递增）

    对应数据库表：quant.agent_session_events
    主键：id；幂等键：UNIQUE(session_key, seq)
    """
    __tablename__ = 'agent_session_events'
    __table_args__ = (
        Index('agent_session_events_session_key_seq_key', 'session_key', 'seq', unique=True),
        {'schema': 'quant'},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_key = Column(
        Text,
        ForeignKey('quant.agent_sessions.session_key'),
        nullable=False,
    )
    seq = Column(Integer, nullable=False, comment='会话内序号（幂等键之一）')
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<AgentSessionEvent(key='{self.session_key}', seq={self.seq}, type='{self.event_type}')>"
