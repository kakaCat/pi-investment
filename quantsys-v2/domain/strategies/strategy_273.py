"""
策略273：宽松动量策略 v1.0（规则版）

买入条件（更宽松）：
1. RSI < 60
2. 价格突破MA5（>0.5%）
3. MACD > -0.5（允许轻微回调）
4. 成交量放大（>1.2倍）
"""
from typing import Optional, Dict, List
from datetime import datetime
from domain.strategies.base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)


class Strategy273(BaseStrategy):
    """策略273：宽松的动量策略"""

    def __init__(self):
        super().__init__(
            strategy_id=273,
            name='策略273',
            description='宽松动量策略 v1.0 - 捕捉更多信号'
        )

    def check_signal(self, symbol: str, klines: List[Dict]) -> Optional[Dict]:
        """
        检查策略273信号

        Args:
            symbol: 股票代码
            klines: K线数据

        Returns:
            信号详情或None
        """
        try:
            # 1. 计算技术指标
            indicators = self._calculate_indicators(klines)

            rsi = indicators['rsi']
            macd = indicators['macd']
            ma5 = indicators['ma5']
            current_price = indicators['current_price']
            vol_ratio = indicators['vol_ratio']

            # 2. 检查买入条件（宽松）
            buy_signal = (
                rsi < 60 and                        # 更宽松
                current_price > ma5 * 1.005 and     # 轻微突破即可
                macd > -0.5 and                     # 允许轻微回调
                vol_ratio > 1.2                     # 轻度放量
            )

            if not buy_signal:
                return None

            # 3. 计算评分
            score = 70  # 基础分

            # RSI加分
            if rsi < 50:
                score += 5

            # 成交量加分
            if vol_ratio > 1.5:
                score += 5

            # 4. 返回信号
            return {
                'symbol': symbol,
                'strategy_id': self.strategy_id,
                'strategy_name': self.name,
                'score': min(score, 100),
                'indicators': {
                    'rsi': round(rsi, 2),
                    'macd': round(macd, 2),
                    'ma5': round(ma5, 2),
                    'price': round(current_price, 2),
                    'vol_ratio': round(vol_ratio, 2)
                },
                'scan_time': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f'策略273检查信号失败 {symbol}: {e}')
            return None
