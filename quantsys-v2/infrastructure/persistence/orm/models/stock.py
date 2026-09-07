"""
股票相关Model - Stock, DailyKline

包含：
1. Stock - 股票基础信息
2. DailyKline - 日K线数据
"""
from sqlalchemy import (
    Column, String, Float, Date, Boolean, DateTime, Index,
    CheckConstraint, ForeignKey, Numeric, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime

from ..base import Base

__all__ = ['Stock', 'DailyKline']


class Stock(Base):
    """股票基础信息表

    对应数据库表：quant.stocks
    主键：symbol（股票代码）
    """
    __tablename__ = 'stocks'
    __table_args__ = (
        # 索引
        Index('idx_stocks_market', 'market'),
        Index('idx_stocks_industry', 'industry'),
        Index('idx_stocks_sector', 'sector'),
        Index('idx_stocks_is_st', 'is_st'),
        Index('idx_stocks_is_suspended', 'is_suspended'),
        Index('idx_stocks_market_suspended_st', 'market', 'is_suspended', 'is_st'),
        Index('idx_stocks_updated_at', 'updated_at'),
        # 约束
        CheckConstraint("market IN ('A', 'HK')", name='chk_stocks_market'),
        # Schema
        {'schema': 'quant'}
    )

    # 基础信息
    symbol = Column(Text, primary_key=True, comment='股票代码')
    name = Column(Text, nullable=False, comment='股票名称')
    market = Column(Text, nullable=False, comment='市场类型(A/HK)')
    industry = Column(Text, comment='行业')
    sector = Column(Text, comment='板块')
    list_date = Column(Date, comment='上市日期')

    # 市值相关
    market_cap = Column(Float, comment='市值')
    total_mv = Column(Float, comment='总市值')
    circulating_mv = Column(Float, comment='流通市值')

    # 估值指标
    pe = Column(Float, comment='市盈率')
    pb = Column(Float, comment='市净率')

    # 财务指标
    roe = Column(Float, comment='净资产收益率(%)')
    net_profit_growth = Column(Float, comment='净利润增长率(%)')
    revenue_growth = Column(Numeric, comment='营收增长率(%)')
    gross_margin = Column(Float, comment='毛利率(%)')
    debt_ratio = Column(Float, comment='资产负债率(%)')

    # 交易指标
    avg_turnover_rate = Column(Float, comment='平均换手率(%)')
    avg_volume = Column(Float, comment='平均成交量')
    avg_amount = Column(Float, comment='平均成交额')

    # 状态标记
    is_st = Column(Boolean, nullable=False, default=False, comment='是否ST股票')
    is_suspended = Column(Boolean, nullable=False, default=False, comment='是否停牌/退市')
    is_delisted = Column(Boolean, nullable=False, default=False, comment='是否已退市（2026-08-02 新增，K线更新/选股直接过滤）')
    delist_date = Column(Date, comment='退市日期')

    # 时间戳
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment='更新时间'
    )

    # 关系映射
    daily_klines = relationship(
        'DailyKline',
        back_populates='stock',
        lazy='dynamic',  # 避免N+1查询
        cascade='all, delete-orphan'
    )
    minute_klines = relationship(
        'MinuteKline',
        back_populates='stock',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    signals = relationship(
        'Signal',
        back_populates='stock',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return (
            f"<Stock(symbol='{self.symbol}', name='{self.name}', "
            f"market='{self.market}', is_st={self.is_st})>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'name': self.name,
            'market': self.market,
            'industry': self.industry,
            'sector': self.sector,
            'list_date': self.list_date.isoformat() if self.list_date else None,
            'market_cap': self.market_cap,
            'total_mv': self.total_mv,
            'circulating_mv': self.circulating_mv,
            'pe': self.pe,
            'pb': self.pb,
            'roe': self.roe,
            'net_profit_growth': self.net_profit_growth,
            'revenue_growth': float(self.revenue_growth) if self.revenue_growth else None,
            'gross_margin': self.gross_margin,
            'debt_ratio': self.debt_ratio,
            'avg_turnover_rate': self.avg_turnover_rate,
            'avg_volume': self.avg_volume,
            'avg_amount': self.avg_amount,
            'is_st': self.is_st,
            'is_suspended': self.is_suspended,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class DailyKline(Base):
    """日K线数据表

    对应数据库表：quant.daily_klines
    主键：(symbol, trade_date)
    """
    __tablename__ = 'daily_klines'
    __table_args__ = (
        # 索引
        Index('idx_daily_klines_symbol', 'symbol'),
        Index('idx_daily_klines_date', 'trade_date'),
        Index('idx_daily_klines_symbol_date', 'symbol', 'trade_date'),
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
    trade_date = Column(Date, primary_key=True, comment='交易日期')

    # OHLCV数据
    open = Column(Float, comment='开盘价')
    high = Column(Float, comment='最高价')
    low = Column(Float, comment='最低价')
    close = Column(Float, comment='收盘价')
    volume = Column(Float, comment='成交量')
    amount = Column(Float, comment='成交额')

    # 额外指标
    turnover_rate = Column(Float, comment='换手率(%)')
    remark = Column(Text, comment='备注')
    source = Column(String(50), nullable=True, comment='数据来源: sina, tencent, eastmoney, akshare, baostock')

    # 关系映射
    stock = relationship('Stock', back_populates='daily_klines')

    def __repr__(self):
        return (
            f"<DailyKline(symbol='{self.symbol}', date='{self.trade_date}', "
            f"close={self.close})>"
        )

    def to_dict(self):
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'amount': self.amount,
            'turnover_rate': self.turnover_rate,
            'remark': self.remark,
            'source': self.source,
        }
