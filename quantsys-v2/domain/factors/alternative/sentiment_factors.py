"""
新闻情绪因子

使用NLP技术分析新闻文本，提取情绪信号
这是另类数据因子的典型示例
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class NewsSentimentFactor:
    """
    新闻情绪因子

    数据源：
    - 财经新闻API
    - 社交媒体
    - 公告文本

    方法：
    - 情感分析（正面/负面/中性）
    - 关键词提取
    - 事件分类
    """

    def __init__(self):
        self.sentiment_model = None
        self._init_sentiment_model()

    def _init_sentiment_model(self):
        """初始化情感分析模型"""
        # 简化版：使用关键词词典
        # 实际应用中应使用BERT等预训练模型
        self.positive_keywords = [
            '增长', '上涨', '盈利', '突破', '创新', '收购',
            '合作', '扩张', '利好', '超预期', '强劲', '领先'
        ]
        self.negative_keywords = [
            '下跌', '亏损', '风险', '违规', '调查', '诉讼',
            '裁员', '退市', '利空', '低于预期', '疲软', '滞后'
        ]
        logger.info("Sentiment model initialized (keyword-based)")

    def analyze_sentiment(self, text: str) -> float:
        """
        分析文本情感

        Args:
            text: 新闻文本

        Returns:
            情感分数 [-1, 1]，正数表示正面，负数表示负面
        """
        if not text:
            return 0.0

        # 统计正负面关键词
        positive_count = sum(1 for kw in self.positive_keywords if kw in text)
        negative_count = sum(1 for kw in self.negative_keywords if kw in text)

        total_count = positive_count + negative_count
        if total_count == 0:
            return 0.0

        # 计算情感分数
        sentiment = (positive_count - negative_count) / total_count
        return sentiment

    def fetch_news(
        self,
        symbol: str,
        days: int = 7
    ) -> List[Dict]:
        """
        获取新闻（模拟）

        实际应用中应调用新闻API

        Args:
            symbol: 股票代码
            days: 天数

        Returns:
            新闻列表
        """
        # 模拟新闻数据
        news = []
        for i in range(np.random.randint(5, 15)):
            news.append({
                'title': f'{symbol}公司新闻标题{i}',
                'content': self._generate_mock_content(),
                'timestamp': datetime.now() - timedelta(days=np.random.randint(0, days)),
                'importance': np.random.choice([1.0, 1.5, 2.0], p=[0.6, 0.3, 0.1])
            })
        return news

    def _generate_mock_content(self) -> str:
        """生成模拟新闻内容"""
        templates = [
            '公司业绩{sentiment}，营收{trend}',
            '新产品发布，市场反应{sentiment}',
            '管理层变动，投资者{sentiment}',
            '行业竞争{sentiment}，市场份额{trend}'
        ]

        sentiments = ['积极', '消极', '平稳']
        trends = ['增长', '下降', '持平']

        template = np.random.choice(templates)
        content = template.format(
            sentiment=np.random.choice(sentiments),
            trend=np.random.choice(trends)
        )

        # 添加关键词
        if '积极' in content or '增长' in content:
            content += '，' + np.random.choice(self.positive_keywords)
        elif '消极' in content or '下降' in content:
            content += '，' + np.random.choice(self.negative_keywords)

        return content

    def calculate(
        self,
        symbol: str,
        date: datetime,
        lookback_days: int = 7
    ) -> Dict[str, float]:
        """
        计算新闻情绪因子

        Args:
            symbol: 股票代码
            date: 计算日期
            lookback_days: 回溯天数

        Returns:
            因子值字典
        """
        # 1. 获取最近N天新闻
        news = self.fetch_news(symbol, days=lookback_days)

        if not news:
            return {
                'news_sentiment': 0.0,
                'sentiment_change': 0.0,
                'news_count': 0,
                'news_intensity': 0.0
            }

        # 2. 分析每条新闻情感
        sentiments = []
        weights = []
        for article in news:
            text = article['title'] + ' ' + article['content']
            sentiment = self.analyze_sentiment(text)
            importance = article.get('importance', 1.0)

            sentiments.append(sentiment)
            weights.append(importance)

        # 3. 计算加权平均情感
        avg_sentiment = np.average(sentiments, weights=weights)

        # 4. 计算情感变化率
        # 最近3天 vs 之前3天
        mid_point = len(sentiments) // 2
        if mid_point > 0:
            recent_sentiment = np.mean(sentiments[:mid_point])
            older_sentiment = np.mean(sentiments[mid_point:])
            sentiment_change = recent_sentiment - older_sentiment
        else:
            sentiment_change = 0.0

        # 5. 计算新闻强度（数量 × 平均重要性）
        news_intensity = len(news) * np.mean(weights)

        return {
            'news_sentiment': avg_sentiment,
            'sentiment_change': sentiment_change,
            'news_count': len(news),
            'news_intensity': news_intensity
        }

    def batch_calculate(
        self,
        symbols: List[str],
        date: datetime,
        lookback_days: int = 7
    ) -> pd.DataFrame:
        """
        批量计算新闻情绪因子

        Args:
            symbols: 股票代码列表
            date: 计算日期
            lookback_days: 回溯天数

        Returns:
            因子值DataFrame
        """
        results = []

        for symbol in symbols:
            try:
                factors = self.calculate(symbol, date, lookback_days)
                factors['symbol'] = symbol
                factors['date'] = date
                results.append(factors)
            except Exception as e:
                logger.error(f"Failed to calculate for {symbol}: {e}")

        df = pd.DataFrame(results)
        logger.info(f"Calculated news sentiment for {len(df)} symbols")
        return df


class SocialMediaFactor:
    """
    社交媒体热度因子

    数据源：
    - 微博
    - 雪球
    - 东方财富股吧

    指标：
    - 讨论量
    - 情绪倾向
    - 关注度变化
    """

    def __init__(self):
        self.platforms = ['weibo', 'xueqiu', 'eastmoney']

    def fetch_social_data(
        self,
        symbol: str,
        platform: str,
        days: int = 7
    ) -> List[Dict]:
        """
        获取社交媒体数据（模拟）

        Args:
            symbol: 股票代码
            platform: 平台名称
            days: 天数

        Returns:
            帖子列表
        """
        # 模拟社交媒体数据
        posts = []
        for i in range(np.random.randint(10, 50)):
            posts.append({
                'content': f'{symbol}讨论内容{i}',
                'views': np.random.randint(100, 10000),
                'comments': np.random.randint(0, 100),
                'shares': np.random.randint(0, 50),
                'sentiment': np.random.uniform(-1, 1),
                'timestamp': datetime.now() - timedelta(days=np.random.randint(0, days))
            })
        return posts

    def calculate_attention_score(self, posts: List[Dict]) -> float:
        """
        计算关注度分数

        考虑因素：
        - 帖子数量
        - 阅读量
        - 评论数
        - 转发数
        """
        if not posts:
            return 0.0

        total_posts = len(posts)
        total_views = sum(p.get('views', 0) for p in posts)
        total_comments = sum(p.get('comments', 0) for p in posts)
        total_shares = sum(p.get('shares', 0) for p in posts)

        # 归一化并加权
        attention_score = (
            np.log1p(total_posts) * 0.2 +
            np.log1p(total_views) * 0.3 +
            np.log1p(total_comments) * 0.3 +
            np.log1p(total_shares) * 0.2
        )

        return attention_score

    def calculate(
        self,
        symbol: str,
        date: datetime,
        lookback_days: int = 7
    ) -> Dict[str, float]:
        """
        计算社交媒体因子

        Args:
            symbol: 股票代码
            date: 计算日期
            lookback_days: 回溯天数

        Returns:
            因子值字典
        """
        all_posts = []

        # 1. 从各平台获取数据
        for platform in self.platforms:
            posts = self.fetch_social_data(symbol, platform, days=lookback_days)
            all_posts.extend(posts)

        if not all_posts:
            return {
                'social_attention': 0.0,
                'social_sentiment': 0.0,
                'attention_change': 0.0,
                'post_count': 0
            }

        # 2. 计算关注度
        attention = self.calculate_attention_score(all_posts)

        # 3. 计算情绪
        sentiments = [p.get('sentiment', 0) for p in all_posts]
        avg_sentiment = np.mean(sentiments)

        # 4. 计算热度变化
        mid_point = len(all_posts) // 2
        if mid_point > 0:
            recent_posts = all_posts[:mid_point]
            older_posts = all_posts[mid_point:]

            recent_attention = self.calculate_attention_score(recent_posts)
            older_attention = self.calculate_attention_score(older_posts)
            attention_change = recent_attention - older_attention
        else:
            attention_change = 0.0

        return {
            'social_attention': attention,
            'social_sentiment': avg_sentiment,
            'attention_change': attention_change,
            'post_count': len(all_posts)
        }


# 使用示例
def example_usage():
    """使用示例"""
    # 1. 新闻情绪因子
    news_factor = NewsSentimentFactor()

    symbol = '000001'
    date = datetime.now()

    factors = news_factor.calculate(symbol, date, lookback_days=7)
    print("News Sentiment Factors:")
    for key, value in factors.items():
        print(f"  {key}: {value:.4f}")

    # 2. 批量计算
    symbols = ['000001', '000002', '600000', '600036']
    df = news_factor.batch_calculate(symbols, date)
    print("\nBatch Calculation:")
    print(df)

    # 3. 社交媒体因子
    social_factor = SocialMediaFactor()
    social_factors = social_factor.calculate(symbol, date)
    print("\nSocial Media Factors:")
    for key, value in social_factors.items():
        print(f"  {key}: {value:.4f}")


if __name__ == "__main__":
    example_usage()
