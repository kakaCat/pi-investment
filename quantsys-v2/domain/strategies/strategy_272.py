"""
策略272：新能源动量策略 v1.0（规则版）

买入条件：
1. RSI < 50（不过热）
2. 价格突破MA5（>1%）
3. MACD > 0（趋势向上）
4. 成交量放大（>1.3倍）
"""
from typing import Optional, Dict, List
from datetime import datetime
from domain.strategies.base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)


class Strategy272(BaseStrategy):
    """策略272：基于规则的动量策略"""

    def __init__(self):
        super().__init__(
            strategy_id=272,
            name='策略272',
            description='新能源动量策略 v1.0 - 基于技术指标规则'
        )

    def check_signal(self, symbol: str, klines: List[Dict]) -> Optional[Dict]:
        """
        检查策略272信号

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

            # 2. 检查买入条件（严格）
            buy_signal = (
                rsi < 50 and                        # 不过热
                current_price > ma5 * 1.01 and      # 突破MA5
                macd > 0 and                        # 趋势向上
                vol_ratio > 1.3                     # 放量
            )

            if not buy_signal:
                return None

            # 3. 计算评分
            score = 70  # 基础分

            # RSI加分
            if rsi < 45:
                score += 5
            if rsi < 40:
                score += 5

            # 成交量加分
            if vol_ratio > 1.5:
                score += 5
            if vol_ratio > 2.0:
                score += 5

            # MACD加分
            if macd > 0.5:
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
            logger.error(f'策略272检查信号失败 {symbol}: {e}')
            return None
