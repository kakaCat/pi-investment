"""
Trade ORM Model

交易记录表的SQLAlchemy模型定义
对应数据库表: quant.trades
"""
from sqlalchemy import Column, BigInteger, Text, Float, Integer, Date, DateTime, CheckConstraint
from sqlalchemy.orm import validates
from sqlalchemy.sql import func
from infrastructure.persistence.orm import Base
from .action_norm import normalize_action

__all__ = ['Trade']


class Trade(Base):
    """交易记录模型

    对应数据库表: quant.trades

    记录所有实盘和模拟盘的交易执行记录
    """

    __tablename__ = 'trades'
    __table_args__ = (
        CheckConstraint("action IN ('BUY', 'SELL')", name='trades_action_check'),
        CheckConstraint('price > 0', name='trades_price_check'),
        CheckConstraint('quantity > 0', name='trades_quantity_check'),
        {'schema': 'quant'}
    )

    @validates('action')
    def _normalize_action(self, key, value):
        return normalize_action(value)

    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='交易ID')

    # 股票信息
    symbol = Column(Text, nullable=False, index=True, comment='股票代码')
    name = Column(Text, nullable=False, comment='股票名称')

    # 交易信息
    action = Column(Text, nullable=False, index=True, comment='交易方向: BUY/SELL (大写契约)')
    price = Column(Float, nullable=False, comment='成交价格')
    quantity = Column(Integer, nullable=False, comment='成交数量')
    amount = Column(Float, nullable=False, comment='成交金额')

    # 费用
    fee = Column(Float, default=0, comment='手续费')
    stamp_duty = Column(Float, default=0, comment='印花税')

    # 时间和关联
    trade_date = Column(Date, nullable=False, index=True, comment='成交日期')
    order_id = Column(BigInteger, index=True, comment='关联订单ID')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='创建时间')

    # 损益（卖出时计算）
    pnl = Column(Float, comment='盈亏金额')
    pnl_percent = Column(Float, comment='盈亏百分比')

    # 备注
    reason = Column(Text, comment='交易原因/备注')

    def __repr__(self):
        return f"<Trade(id={self.id}, symbol={self.symbol}, action={self.action}, price={self.price}, quantity={self.quantity}, date={self.trade_date})>"

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'name': self.name,
            'action': self.action,
            'price': float(self.price) if self.price else 0.0,
            'quantity': self.quantity,
            'amount': float(self.amount) if self.amount else 0.0,
            'fee': float(self.fee) if self.fee else 0.0,
            'stamp_duty': float(self.stamp_duty) if self.stamp_duty else 0.0,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'order_id': self.order_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'pnl': float(self.pnl) if self.pnl else None,
            'pnl_percent': float(self.pnl_percent) if self.pnl_percent else None,
            'reason': self.reason,
        }
