"""
信号相关Model

包含：
1. Signal - 交易信号
2. SignalExecution - 信号执行记录
"""
from sqlalchemy import (
    Column, String, Float, Date, DateTime, BigInteger, Integer,
    Index, ForeignKey, Text, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime

from ..base import Base

__all__ = ['Signal', 'SignalExecution']


class Signal(Base):
    """交易信号表

    对应数据库表：quant.signals
    主键：id
    唯一约束：(symbol, signal_date, strategy_id)
    """
    __tablename__ = 'signals'
    __table_args__ = (
        # 索引
        Index('idx_signals_symbol', 'symbol'),
        Index('idx_signals_signal_date', 'signal_date'),
        Index('idx_signals_strategy', 'strategy_id'),
        Index('idx_signals_status', 'status'),
        Index('idx_signals_action_type', 'action_type'),
        Index('idx_signals_created_at', 'created_at'),
        Index('idx_signals_indicators_gin', 'indicators', postgresql_using='gin'),
        # 唯一约束
        Index('unique_symbol_date_strategy', 'symbol', 'signal_date', 'strategy_id', unique=True),
        # Schema
        {'schema': 'quant'}
    )

    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='信号ID')

    # 基础信息
    signal_date = Column(Date, nullable=False, comment='信号日期')
    symbol = Column(
        Text,
        ForeignKey('quant.stocks.symbol', ondelete='CASCADE'),
        nullable=False,
        comment='股票代码'
    )
    name = Column(Text, nullable=False, comment='股票名称')
    strategy_id = Column(Text, nullable=False, comment='策略ID')

    # 信号详情
    action = Column(Text, nullable=False, comment='操作类型(buy/sell)')
    action_type = Column(Integer, nullable=False, comment='操作类型代码')
    price = Column(Float, comment='信号价格')
    confidence = Column(Float, comment='置信度(0-1)')
    reason = Column(Text, comment='信号原因')

    # 指标数据（JSON格式）
    indicators = Column(JSONB, comment='指标数据')

    # 状态管理
    status = Column(
        String(20),
        default='pending',
        comment='状态(pending/executed/rejected/expired)'
    )
    reject_reason = Column(Text, comment='拒绝原因')
    error_description = Column(Text, comment='错误描述')

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment='创建时间'
    )
    updated_at = Column(
        DateTime(timezone=False),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment='更新时间'
    )

    # 关系映射
    stock = relationship('Stock', back_populates='signals')
    executions = relationship(
        'SignalExecution',
        back_populates='signal',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return (
            f"<Signal(id={self.id}, symbol='{self.symbol}', "
            f"action='{self.action}', status='{self.status}')>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'signal_date': self.signal_date.isoformat() if self.signal_date else None,
            'symbol': self.symbol,
            'name': self.name,
            'strategy_id': self.strategy_id,
            'action': self.action,
            'action_type': self.action_type,
            'price': self.price,
            'confidence': self.confidence,
            'reason': self.reason,
            'indicators': self.indicators,
            'status': self.status,
            'reject_reason': self.reject_reason,
            'error_description': self.error_description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SignalExecution(Base):
    """信号执行记录表

    对应数据库表：quant.signal_executions
    主键：id
    """
    __tablename__ = 'signal_executions'
    __table_args__ = (
        # 索引
        Index('idx_signal_executions_signal_id', 'signal_id'),
        Index('idx_signal_executions_executed_at', 'executed_at'),
        Index('idx_signal_executions_status', 'status'),
        # Schema
        {'schema': 'quant'}
    )

    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='执行ID')

    # 关联信号
    signal_id = Column(
        BigInteger,
        ForeignKey('quant.signals.id', ondelete='CASCADE'),
        nullable=False,
        comment='信号ID'
    )

    # 执行信息
    executed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment='执行时间'
    )
    execution_price = Column(Float, comment='执行价格')
    execution_amount = Column(Float, comment='执行数量')
    execution_volume = Column(Float, comment='执行金额')

    # 状态
    status = Column(
        String(20),
        default='pending',
        comment='执行状态(pending/success/failed)'
    )
    error_message = Column(Text, comment='错误信息')

    # 关系映射
    signal = relationship('Signal', back_populates='executions')

    def __repr__(self):
        return (
            f"<SignalExecution(id={self.id}, signal_id={self.signal_id}, "
            f"status='{self.status}')>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'signal_id': self.signal_id,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'execution_price': self.execution_price,
            'execution_amount': self.execution_amount,
            'execution_volume': self.execution_volume,
            'status': self.status,
            'error_message': self.error_message,
        }
