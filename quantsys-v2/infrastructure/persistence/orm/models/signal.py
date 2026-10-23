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
from sqlalchemy.orm import relationship, validates
from datetime import datetime

from ..base import Base
from .action_norm import normalize_signal_action, signal_action_type

__all__ = ['Signal', 'SignalExecution']


def _derive_action_type(ctx=None):
    """quant.signals.action_type 的列缺省值：由同一条 INSERT 的 action 推导。

    为什么把缺省值放在**模型**上（2026-09-15 实测缺陷）：
    原先只有 signal_repository.create_signal 一处会推导 action_type，任何**别的**
    ORM 写入漏传它就撞 NotNullViolation（null value in column action_type of
    relation signals）。实测后果：test_heatmap_service（10）+
    test_heatmap_repository_events（7）共 **17 个用例 ERROR** —— 夹具直接构造
    Signal(...) 而不传 action_type 即全灭。

    放在列上 = 写入方不可能忘（与 ORM @validates 强制 action 大小写同一思路）。
    注意 DB 侧该列 NOT NULL 且**无 server default**（2026-09-15 生产实测），
    故这里只是 Python 侧缺省，不改变任何 DDL；显式传入的 action_type 永远优先。
    """
    params = getattr(ctx, 'current_parameters', None) or {}
    return signal_action_type(params.get('action'))


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
        # action 大写契约（2026-08-13 统一，见 models/action_norm.py）
        CheckConstraint("action IN ('BUY','SELL','HOLD')", name='signals_action_check'),
        # Schema
        {'schema': 'quant'}
    )

    @validates('action')
    def _normalize_action(self, key, value):
        return normalize_signal_action(value)

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
    action = Column(Text, nullable=False, comment='操作类型(BUY/SELL/HOLD，大写契约)')
    action_type = Column(
        Integer,
        nullable=False,
        default=_derive_action_type,
        comment='操作类型代码(BUY=1/SELL=2，缺省由 action 推导)'
    )
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

    2026-10-23 重建（模型与真实表脱节）：原模型只有 id/signal_id/executed_at/
    execution_price/execution_amount/execution_volume/status/error_message，
    缺 execution_date / quantity（两者在表里都是 NOT NULL）/ commission / pnl /
    close_date / close_price / created_at / updated_at。后果全部静默：
      - create_execution(execution_date=..., quantity=...) 构造即 TypeError，
        被仓储 except 吞成 None → **执行记录永远建不出来**；
      - get_all_executions  ORDER BY created_at → AttributeError → 恒返回 []；
      - close_execution 写 close_date/pnl → AttributeError → 恒 False；
      - get_execution_stats 过滤 execution_date → AttributeError → 恒 {}。
    （同 risk_repository 里记录过的 RiskMetric EAV 错建事故，属同类）
    """
    __tablename__ = 'signal_executions'
    __table_args__ = (
        # 索引（与库内实际索引对齐：signal_id + execution_date DESC）
        Index('idx_quant_signal_executions_signal_id', 'signal_id'),
        Index('idx_quant_signal_executions_execution_date_desc', 'execution_date'),
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

    # 执行信息（真实表 NOT NULL 列）
    execution_date = Column(Date, nullable=False, comment='执行日期')
    execution_price = Column(Float, nullable=False, comment='执行价格')
    quantity = Column(Integer, nullable=False, comment='成交数量')
    commission = Column(Float, default=0.0, comment='佣金')

    # 状态
    status = Column(
        String(20),
        default='pending',
        comment='执行状态(pending/executed/cancelled/expired)'
    )

    # 平仓结果
    pnl = Column(Float, comment='已实现盈亏')
    close_date = Column(Date, comment='平仓日期')
    close_price = Column(Float, comment='平仓价格')

    # 审计时间
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, comment='创建时间')
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment='更新时间'
    )

    # 历史/兼容列（表内存在，非必填）
    executed_at = Column(DateTime, nullable=True, comment='执行时间（兼容列）')
    execution_amount = Column(Float, comment='执行数量（兼容列，语义同 quantity）')
    execution_volume = Column(Float, comment='执行金额（兼容列）')
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
            'execution_date': self.execution_date.isoformat() if self.execution_date else None,
            'execution_price': self.execution_price,
            'quantity': self.quantity,
            'commission': self.commission,
            'status': self.status,
            'pnl': self.pnl,
            'close_date': self.close_date.isoformat() if self.close_date else None,
            'close_price': self.close_price,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'execution_amount': self.execution_amount,
            'execution_volume': self.execution_volume,
            'error_message': self.error_message,
        }
