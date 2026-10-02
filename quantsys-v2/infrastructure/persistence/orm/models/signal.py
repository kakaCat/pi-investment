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
    """
    __tablename__ = 'signal_executions'
    __table_args__ = (
        # 索引
        Index('idx_signal_executions_signal_id', 'signal_id'),
        # 2026-10-02（REQ-...）：原为 executed_at 建索引，而**生产库没有该列** → 一并去除
        Index('idx_signal_executions_execution_date', 'execution_date'),
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

    execution_price = Column(Float, comment='执行价格')

    # ─────────────────────────────────────────────────────────────────────────
    # 2026-10-02（REQ-261001145152-3982 审查）：**补齐与生产库一致的真实列**。
    #
    # 本模型此前声明的 `executed_at` / `execution_amount` / `execution_volume` /
    # `error_message` **生产库没有**（那是模型单方面的命名）；而生产库的
    # `execution_date` / `quantity` 是 **NOT NULL**，模型又没声明它们 ——
    # 于是任何 INSERT 都失败：仓库 `create_execution(...)` 传 `execution_date=` 直接
    # `TypeError: 'execution_date' is an invalid keyword argument`，即使不传该参数
    # 也会撞 `execution_date`/`quantity` 的 NOT NULL 约束。
    # 实测该方法**每次都返回 None**（异常被 except 吞掉），线上
    # `POST /api/signal-executions`（executions_async）因此建不出执行记录。
    #
    # 谁对：**仓库与生产库一致**（`signal_id, execution_date, execution_price, quantity,
    # commission, status`），模型是脱节的一方 —— 故按生产库补列，而不是改仓库。
    # ⚠️ 保留上面那 4 个"模型单方面"的列（测试库里有、可空），避免牵动其它引用。
    # ─────────────────────────────────────────────────────────────────────────
    execution_date = Column(Date, nullable=False, comment='执行日期（生产库 NOT NULL）')
    quantity = Column(Integer, nullable=False, comment='数量（生产库 NOT NULL）')
    commission = Column(Float, comment='佣金')
    pnl = Column(Float, comment='盈亏')
    close_date = Column(Date, comment='平仓日期')
    close_price = Column(Float, comment='平仓价格')
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, comment='更新时间')

    # 状态
    status = Column(
        String(20),
        default='pending',
        comment='执行状态(pending/success/failed)'
    )

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
        }
