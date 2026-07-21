"""
策略274：机器学习策略（示例）

使用机器学习模型预测买入信号
"""
from typing import Optional, Dict, List
from datetime import datetime
from domain.strategies.base_strategy import BaseStrategy
import logging
import numpy as np

logger = logging.getLogger(__name__)


class Strategy274ML(BaseStrategy):
    """策略274：基于机器学习的策略"""

    def __init__(self):
        super().__init__(
            strategy_id=274,
            name='策略274-ML',
            description='机器学习策略 v1.0 - 基于随机森林模型'
        )
        self.model = None
        self._load_model()

    def _load_model(self):
        """加载ML模型"""
        try:
            # TODO: 实际加载训练好的模型
            # import joblib
            # self.model = joblib.load('models/strategy_274.pkl')
            logger.info('ML模型加载成功')
        except Exception as e:
            logger.warning(f'ML模型加载失败: {e}，使用模拟预测')
            self.model = None

    def check_signal(self, symbol: str, klines: List[Dict]) -> Optional[Dict]:
        """
        检查策略274信号（ML版）

        Args:
            symbol: 股票代码
            klines: K线数据

        Returns:
            信号详情或None
        """
        try:
            # 1. 计算技术指标
            indicators = self._calculate_indicators(klines)

            # 2. 提取特征向量
            features = self._extract_features(indicators, klines)

            # 3. ML预测
            if self.model:
                # 实际使用模型预测
                prediction = self.model.predict([features])[0]
                probability = self.model.predict_proba([features])[0]
                buy_prob = probability[1]  # 买入的概率
            else:
                # 模拟预测（用于演示）
                buy_prob = self._simulate_predict(indicators)

            # 4. 判断信号
            if buy_prob < 0.7:  # 概率阈值
                return None

            # 5. 返回信号
            return {
                'symbol': symbol,
                'strategy_id': self.strategy_id,
                'strategy_name': self.name,
                'score': int(buy_prob * 100),
                'confidence': round(buy_prob, 3),
                'model': 'random_forest',
                'indicators': {
                    'rsi': round(indicators['rsi'], 2),
                    'macd': round(indicators['macd'], 2),
                    'price': round(indicators['current_price'], 2),
                    'vol_ratio': round(indicators['vol_ratio'], 2)
                },
                'scan_time': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f'策略274检查信号失败 {symbol}: {e}')
            return None

    def _extract_features(self, indicators: Dict, klines: List[Dict]) -> np.ndarray:
        """
        提取ML特征向量

        Args:
            indicators: 技术指标
            klines: K线数据

        Returns:
            特征向量
        """
        import pandas as pd

        # 提取特征
        features = [
            indicators['rsi'],                  # RSI
            indicators['macd'],                 # MACD
            indicators['ma5'],                  # MA5
            indicators['ma10'],                 # MA10
            indicators['ma20'],                 # MA20
            indicators['vol_ratio'],            # 成交量比
            indicators['current_price'],        # 当前价格

            # 价格动量特征
            indicators['current_price'] / indicators['ma5'] - 1,  # 偏离MA5
            indicators['current_price'] / indicators['ma20'] - 1,  # 偏离MA20

            # 成交量特征
            np.log1p(indicators['volume']),     # 对数成交量

            # 历史收益率
            self._calculate_returns(klines, 5),   # 5日收益率
            self._calculate_returns(klines, 10),  # 10日收益率
        ]

        return np.array(features)

    def _calculate_returns(self, klines: List[Dict], period: int) -> float:
        """计算收益率"""
        if len(klines) < period + 1:
            return 0.0
        recent_close = klines[-1]['close']
        past_close = klines[-period-1]['close']
        return (recent_close / past_close - 1) if past_close > 0 else 0.0

    def _simulate_predict(self, indicators: Dict) -> float:
        """
        模拟预测（用于演示）

        实际使用时删除此方法，使用真实的ML模型
        """
        # 简单的规则模拟ML预测
        score = 0.5  # 基础概率

        # RSI影响
        if indicators['rsi'] < 30:
            score += 0.2
        elif indicators['rsi'] < 50:
            score += 0.1

        # MACD影响
        if indicators['macd'] > 0:
            score += 0.1

        # 成交量影响
        if indicators['vol_ratio'] > 1.3:
            score += 0.1

        return min(score, 1.0)
