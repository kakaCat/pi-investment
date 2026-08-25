"""
M1 市场感知相关 Model（RFC 007）

包含：
1. MarketRegime - 每日市场 regime 判定
2. MarketSentimentDaily - 每日情绪时间序列
3. MarketTheme - 每日涨停聚类主线
"""
from sqlalchemy import (
    Column, Integer, BigInteger, Float, Boolean, Date, Text, String,
    Index, UniqueConstraint, DateTime
)
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from ..base import Base

__all__ = ['MarketRegime', 'MarketSentimentDaily', 'MarketTheme']


class MarketRegime(Base):
    """每日市场 regime 判定表

    对应数据库表：quant.market_regime
    主键：trade_date
    """
    __tablename__ = 'market_regime'
    __table_args__ = (
        {'schema': 'quant'}
    )

    trade_date = Column(Date, primary_key=True, comment='交易日')
    regime = Column(String(20), nullable=False,
                    comment='regime: trend_up/trend_down/range/panic/euphoria')
    index_trend_score = Column(Float, comment='指数趋势得分 [-1,1]')
    sentiment_score = Column(Float, comment='情绪分 [0,100]')
    volume_ratio = Column(Float, comment='量能比')
    ad_ratio = Column(Float, comment='涨跌家数比')
    reason = Column(Text, nullable=False, comment='判定依据（含全部指标值）')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    def __repr__(self):
        return f"<MarketRegime(date='{self.trade_date}', regime='{self.regime}')>"

    def to_dict(self):
        return {
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'regime': self.regime,
            'index_trend_score': self.index_trend_score,
            'sentiment_score': self.sentiment_score,
            'volume_ratio': self.volume_ratio,
            'ad_ratio': self.ad_ratio,
            'reason': self.reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MarketSentimentDaily(Base):
    """每日情绪时间序列表

    对应数据库表：quant.market_sentiment_daily
    主键：trade_date
    """
    __tablename__ = 'market_sentiment_daily'
    __table_args__ = (
        {'schema': 'quant'}
    )

    trade_date = Column(Date, primary_key=True, comment='交易日')
    up_count = Column(Integer, comment='上涨家数')
    down_count = Column(Integer, comment='下跌家数')
    flat_count = Column(Integer, comment='平盘家数')
    ad_ratio = Column(Float, comment='涨跌家数比')
    new_high_count = Column(Integer, comment='新高家数')
    new_low_count = Column(Integer, comment='新低家数')
    volume_ratio = Column(Float, comment='量能比（近5日 vs 近20日）')
    total_turnover = Column(Float, comment='总成交额')
    volatility = Column(Float, comment='波动率')
    fear_greed_index = Column(Float, comment='恐慌贪婪指数 [0,100]')
    coverage = Column(Integer, comment='样本覆盖数（自查：up+down+flat）')
    partial = Column(Boolean, default=False,
                     comment='coverage < 4000 时为 true（K线同步未完成）')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    def __repr__(self):
        return (
            f"<MarketSentimentDaily(date='{self.trade_date}', "
            f"fgi={self.fear_greed_index}, coverage={self.coverage})>"
        )

    def to_dict(self):
        return {
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'up_count': self.up_count,
            'down_count': self.down_count,
            'flat_count': self.flat_count,
            'ad_ratio': self.ad_ratio,
            'new_high_count': self.new_high_count,
            'new_low_count': self.new_low_count,
            'volume_ratio': self.volume_ratio,
            'total_turnover': self.total_turnover,
            'volatility': self.volatility,
            'fear_greed_index': self.fear_greed_index,
            'coverage': self.coverage,
            'partial': self.partial,
        }


class MarketTheme(Base):
    """每日涨停聚类主线表

    对应数据库表：quant.market_theme
    主键：id；唯一约束：(trade_date, rank)
    """
    __tablename__ = 'market_theme'
    __table_args__ = (
        UniqueConstraint('trade_date', 'rank', name='uq_market_theme_date_rank'),
        Index('idx_market_theme_date', 'trade_date'),
        {'schema': 'quant'}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, comment='交易日')
    rank = Column(Integer, nullable=False, comment='排名 1/2/3')
    theme = Column(String(100), comment='主题名（初始=sector，LLM 回写优化）')
    sector = Column(String(100), nullable=False, comment='所属行业（聚类依据）')
    limit_up_count = Column(Integer, nullable=False, comment='涨停只数')
    stocks = Column(JSONB, nullable=False, comment='成分股列表 [{symbol,name,change_pct}]')
    fund_flow = Column(Float, comment='封板资金合计（亿）')
    catalyst = Column(Text, comment='催化剂（盘后例程 LLM 回写）')
    confidence = Column(Float, default=0.5, comment='置信度 [0,1]')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    def __repr__(self):
        return (
            f"<MarketTheme(date='{self.trade_date}', rank={self.rank}, "
            f"theme='{self.theme}', count={self.limit_up_count})>"
        )

    def to_dict(self):
        return {
            'id': self.id,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'rank': self.rank,
            'theme': self.theme,
            'sector': self.sector,
            'limit_up_count': self.limit_up_count,
            'stocks': self.stocks,
            'fund_flow': self.fund_flow,
            'catalyst': self.catalyst,
            'confidence': self.confidence,
        }
