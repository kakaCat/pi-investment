"""
日常编排器状态 ORM 模型

持久化每日投资循环的状态机，支持进程重启后断点续跑。
表：quant.daily_orchestrator_state
"""
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, JSON, Numeric, Index
)
from datetime import datetime

from ..base import Base


class DailyOrchestratorState(Base):
    """日常编排器状态表

    每个交易日一行记录，追踪当天各阶段完成情况。
    唯一约束：(orchestrator_name, trade_date)
    """
    __tablename__ = 'daily_orchestrator_state'
    __table_args__ = (
        Index('orchestrator_state_name_date_key',
              'orchestrator_name', 'trade_date', unique=True),
        {'schema': 'quant'}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 编排器标识
    orchestrator_name = Column(
        String(50), nullable=False, default='main',
        comment='编排器名称（支持多实例）'
    )

    # 交易日期
    trade_date = Column(Date, nullable=False, comment='交易日期')

    # 状态机
    current_phase = Column(
        String(30), nullable=False, default='IDLE',
        comment='当前阶段: IDLE/PRE_MARKET/MARKET_OPEN/INTRADAY/MARKET_CLOSE/POST_MARKET/REVIEW'
    )

    # 各阶段完成标记
    phases_completed = Column(
        JSON, nullable=False, default=dict,
        comment='已完成阶段详情 {phase: {status, started_at, finished_at, result}}'
    )

    # 当日上下文数据（市场风格、策略决策等）
    context = Column(
        JSON, nullable=True, default=dict,
        comment='当日运行上下文（市场风格、轮动决策、Agent指令等）'
    )

    # 错误信息
    last_error = Column(String(500), nullable=True, comment='最后错误信息')
    error_count = Column(Integer, nullable=False, default=0, comment='累计错误次数')

    # 时间戳
    created_at = Column(DateTime(timezone=False), default=datetime.now, comment='创建时间')
    updated_at = Column(
        DateTime(timezone=False), default=datetime.now,
        onupdate=datetime.now, comment='更新时间'
    )

    def __repr__(self):
        return (
            f"<DailyOrchestratorState(name='{self.orchestrator_name}', "
            f"date={self.trade_date}, phase={self.current_phase})>"
        )

    def to_dict(self):
        return {
            'id': self.id,
            'orchestrator_name': self.orchestrator_name,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'current_phase': self.current_phase,
            'phases_completed': self.phases_completed or {},
            'context': self.context or {},
            'last_error': self.last_error,
            'error_count': self.error_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
