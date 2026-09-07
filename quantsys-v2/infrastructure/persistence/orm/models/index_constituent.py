"""
指数成分股 Model

包含：
- IndexConstituent: 指数成分股数据
"""
from sqlalchemy import Column, String, Float, DateTime, Text
from datetime import datetime

from ..base import Base

__all__ = ['IndexConstituent']


class IndexConstituent(Base):
    """指数成分股表

    对应数据库表：quant.index_constituents
    主键：(index_code, symbol)
    """
    __tablename__ = 'index_constituents'
    __table_args__ = {'schema': 'quant'}

    # 联合主键
    index_code = Column(Text, primary_key=True, comment='指数代码')
    symbol = Column('constituent_symbol', Text, primary_key=True, comment='成分股代码')

    # 权重信息
    weight = Column(Float, default=0.0, comment='权重')

    # 时间戳
    update_time = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        comment='更新时间'
    )

    def __repr__(self):
        return (
            f"<IndexConstituent(index='{self.index_code}', "
            f"symbol='{self.symbol}', weight={self.weight})>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'index_code': self.index_code,
            'symbol': self.symbol,
            'weight': self.weight,
            'update_time': self.update_time.isoformat() if self.update_time else None,
        }
