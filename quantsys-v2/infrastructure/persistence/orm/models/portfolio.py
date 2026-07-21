"""
持仓相关Model

包含：
1. PortfolioHolding - 持仓记录
"""
from sqlalchemy import (
    Column, String, Integer, Float, Date, DateTime, BigInteger,
    Index, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime

from ..base import Base

__all__ = ['PortfolioHolding']


class PortfolioHolding(Base):
    """持仓记录表

    对应数据库表：quant.portfolio_holdings
    主键：id
    唯一约束：symbol
    """
    __tablename__ = 'portfolio_holdings'
    __table_args__ = (
        # 索引
        Index('idx_portfolio_holdings_market', 'market'),
        Index('idx_portfolio_holdings_sector', 'sector'),
        Index('idx_portfolio_holdings_added_date', 'added_date'),
        # 唯一约束
        Index('portfolio_holdings_symbol_key', 'symbol', unique=True),
        # Schema
        {'schema': 'quant'}
    )

    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='持仓ID')

    # 股票信息
    symbol = Column(
        Text,
        ForeignKey('quant.stocks.symbol'),
        nullable=False,
        unique=True,
        comment='股票代码'
    )
    name = Column(Text, nullable=False, comment='股票名称')

    # 持仓数量和成本
    quantity = Column(Integer, nullable=False, comment='持仓数量')
    avg_cost = Column(Float, nullable=False, comment='平均成本')
    original_cost = Column(Float, comment='原始成本')
    total_invested = Column(Float, nullable=False, comment='总投入')

    # 分类信息
    market = Column(Text, nullable=False, comment='市场(A/HK)')
    sector = Column(Text, comment='行业')

    # 策略信息
    added_date = Column(Date, nullable=False, comment='建仓日期')
    stop_loss = Column(Float, comment='止损价')
    target_price = Column(Float, comment='目标价')
    buy_reason = Column(Text, comment='买入理由')
    notes = Column(Text, comment='备注')

    # 时间戳
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment='更新时间'
    )

    # 关系映射
    stock = relationship('Stock', foreign_keys=[symbol])

    def __repr__(self):
        return (
            f"<PortfolioHolding(id={self.id}, symbol='{self.symbol}', "
            f"quantity={self.quantity})>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'name': self.name,
            'quantity': self.quantity,
            'avg_cost': self.avg_cost,
            'original_cost': self.original_cost,
            'total_invested': self.total_invested,
            'market': self.market,
            'sector': self.sector,
            'added_date': self.added_date.isoformat() if self.added_date else None,
            'stop_loss': self.stop_loss,
            'target_price': self.target_price,
            'buy_reason': self.buy_reason,
            'notes': self.notes,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
