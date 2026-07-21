"""
Sentiment 异步ORM Repository

迁移状态：✅ 异步版本

注: sentiment相关表暂未找到，创建临时模型占位
"""
from infrastructure.persistence.orm.async_base import AsyncBaseORMRepository
from sqlalchemy import Column, BigInteger, String, Float, Date, Text, DateTime, JSON, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.persistence.orm.base import Base
from typing import List, Optional, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class SentimentData(Base):
    """情绪数据ORM模型（临时）"""
    __tablename__ = 'sentiment_data'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True)
    symbol = Column(String(20))
    sentiment_date = Column(Date)
    sentiment_type = Column(String(50))  # 'bullish', 'bearish', 'neutral'
    sentiment_score = Column(Float)
    sentiment_data = Column(JSON)
    created_at = Column(DateTime)


class SentimentAsyncRepository(AsyncBaseORMRepository[SentimentData]):
    """异步情绪数据Repository"""

    model = SentimentData

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_sentiments(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sentiment_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取情绪数据

        Args:
            symbol: 股票代码（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            sentiment_type: 情绪类型（可选）
            limit: 返回数量

        Returns:
            情绪数据列表
        """
        try:
            stmt = select(SentimentData)

            if symbol:
                stmt = stmt.where(SentimentData.symbol == symbol)
            if start_date:
                stmt = stmt.where(SentimentData.sentiment_date >= start_date)
            if end_date:
                stmt = stmt.where(SentimentData.sentiment_date <= end_date)
            if sentiment_type:
                stmt = stmt.where(SentimentData.sentiment_type == sentiment_type)

            stmt = stmt.order_by(desc(SentimentData.sentiment_date)).limit(limit)

            result = await self.session.execute(stmt)
            sentiments = result.scalars().all()

            return [self._sentiment_to_dict(s) for s in sentiments]

        except Exception as e:
            logger.error(f"Error getting sentiments: {e}")
            return []

    async def get_latest_sentiment(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取最新情绪数据

        Args:
            symbol: 股票代码

        Returns:
            情绪数据字典或None
        """
        try:
            stmt = select(SentimentData).where(
                SentimentData.symbol == symbol
            ).order_by(desc(SentimentData.sentiment_date)).limit(1)

            result = await self.session.execute(stmt)
            sentiment = result.scalars().first()

            return self._sentiment_to_dict(sentiment) if sentiment else None

        except Exception as e:
            logger.error(f"Error getting latest sentiment for {symbol}: {e}")
            return None

    async def save_sentiment(self, sentiment_data: Dict[str, Any]) -> Optional[int]:
        """保存情绪数据

        Args:
            sentiment_data: 情绪数据

        Returns:
            ID或None
        """
        try:
            sentiment = await self.create(sentiment_data)
            return sentiment.id if sentiment else None

        except Exception as e:
            logger.error(f"Error saving sentiment: {e}")
            return None

    async def get_market_sentiment_summary(
        self,
        date: str
    ) -> Dict[str, Any]:
        """获取市场整体情绪汇总

        Args:
            date: 日期

        Returns:
            情绪汇总字典
        """
        try:
            stmt = select(SentimentData).where(
                SentimentData.sentiment_date == date
            )

            result = await self.session.execute(stmt)
            sentiments = result.scalars().all()

            # 计算各类情绪占比
            total = len(sentiments)
            if total == 0:
                return {'bullish': 0, 'bearish': 0, 'neutral': 0, 'total': 0}

            bullish = sum(1 for s in sentiments if s.sentiment_type == 'bullish')
            bearish = sum(1 for s in sentiments if s.sentiment_type == 'bearish')
            neutral = sum(1 for s in sentiments if s.sentiment_type == 'neutral')

            return {
                'date': date,
                'bullish': bullish / total,
                'bearish': bearish / total,
                'neutral': neutral / total,
                'total': total,
                'avg_score': sum(s.sentiment_score for s in sentiments if s.sentiment_score) / total,
            }

        except Exception as e:
            logger.error(f"Error getting market sentiment summary: {e}")
            return {}

    def _sentiment_to_dict(self, sentiment: SentimentData) -> Dict[str, Any]:
        """将SentimentData对象转换为字典"""
        return {
            'id': sentiment.id,
            'symbol': sentiment.symbol,
            'sentiment_date': sentiment.sentiment_date.isoformat() if sentiment.sentiment_date else None,
            'sentiment_type': sentiment.sentiment_type,
            'sentiment_score': sentiment.sentiment_score,
            'sentiment_data': sentiment.sentiment_data,
            'created_at': sentiment.created_at.isoformat() if sentiment.created_at else None,
        }


__all__ = ['SentimentAsyncRepository', 'SentimentData']
