"""
分钟K线Model

包含：
1. MinuteKline - 分钟级K线数据
"""
from sqlalchemy import (
    Column, String, Float, DateTime, Index, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from ..base import Base

__all__ = ['MinuteKline']


class MinuteKline(Base):
    """分钟K线数据表

    对应数据库表：quant.minute_klines
    主键：(symbol, trade_datetime)
    """
    __tablename__ = 'minute_klines'
    __table_args__ = (
        # 索引
        Index('idx_minute_klines_datetime', 'trade_datetime'),
        Index('idx_minute_klines_recent', 'symbol', 'trade_datetime'),
        # Schema
        {'schema': 'quant'}
    )

    # 联合主键
    symbol = Column(
        Text,
        ForeignKey('quant.stocks.symbol', ondelete='CASCADE'),
        primary_key=True,
        comment='股票代码'
    )
    trade_datetime = Column(
        DateTime(timezone=False),
        primary_key=True,
        comment='交易时间'
    )

    # OHLCV数据
    open = Column(Float, comment='开盘价')
    high = Column(Float, comment='最高价')
    low = Column(Float, comment='最低价')
    close = Column(Float, comment='收盘价')
    volume = Column(Float, comment='成交量')
    amount = Column(Float, comment='成交额')

    # 关系映射
    stock = relationship('Stock', back_populates='minute_klines')

    def __repr__(self):
        return (
            f"<MinuteKline(symbol='{self.symbol}', "
            f"datetime='{self.trade_datetime}', close={self.close})>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'trade_datetime': self.trade_datetime.isoformat() if self.trade_datetime else None,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'amount': self.amount,
        }
