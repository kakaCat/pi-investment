"""
因子相关Model

包含：
1. FactorValue - 因子值
"""
from sqlalchemy import (
    Column, Float, Date, Index, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from ..base import Base

__all__ = ['FactorValue']


class FactorValue(Base):
    """因子值表

    对应数据库表：quant.factor_values
    主键：(symbol, factor_date, factor_name)
    """
    __tablename__ = 'factor_values'
    __table_args__ = (
        # 索引
        Index('idx_factor_values_symbol_date', 'symbol', 'factor_date'),
        Index('idx_factor_values_name_date', 'factor_name', 'factor_date'),
        Index('idx_factor_values_factor_date', 'factor_date'),
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
    factor_date = Column(Date, primary_key=True, comment='因子日期')
    factor_name = Column(Text, primary_key=True, comment='因子名称')

    # 因子值
    factor_value = Column(Float, comment='因子值')

    # 关系映射
    stock = relationship('Stock', foreign_keys=[symbol])

    def __repr__(self):
        return (
            f"<FactorValue(symbol='{self.symbol}', date='{self.factor_date}', "
            f"name='{self.factor_name}', value={self.factor_value})>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'factor_date': self.factor_date.isoformat() if self.factor_date else None,
            'factor_name': self.factor_name,
            'factor_value': self.factor_value,
        }
