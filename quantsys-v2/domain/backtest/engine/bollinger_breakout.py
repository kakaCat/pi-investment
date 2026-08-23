"""
布林带突破策略 (Bollinger Breakout)

买入信号: 价格向上突破上轨
卖出信号: 价格向下突破下轨
"""
from typing import Dict, List, Any

from domain.backtest.engine.strategy_base import StrategyBase


class BollingerBreakoutStrategy(StrategyBase):
    """
    布林带突破策略

    默认参数:
        period: 20    (均线周期)
        num_std: 2.0  (标准差倍数)
    """

    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据布林带突破生成交易信号

        Args:
            klines: K线数据列表
            params: 策略参数，支持 period 和 num_std

        Returns:
            信号字典
        """
        if params is None:
            params = {}

        period = int(params.get('period', 20))
        num_std = float(params.get('num_std', 2.0))
        min_required = period + 1

        self._validate_klines(klines, min_length=min_required)
        closes = self._extract_closes(klines)

        # 计算布林带
        bands = self._calculate_bollinger_bands(closes, period, num_std)

        upper = bands['upper'][-1]
        lower = bands['lower'][-1]
        middle = bands['middle'][-1]
        prev_upper = bands['upper'][-2]
        prev_lower = bands['lower'][-2]
        prev_close = closes[-2]
        curr_close = closes[-1]

        if upper is None or lower is None or middle is None:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'布林带尚未形成 (需要至少 {min_required} 条K线)'
            }

        band_width = upper - lower

        # 向上突破上轨
        if prev_close <= prev_upper and curr_close > upper:
            breakout_pct = (curr_close - upper) / (band_width + 1e-10)
            confidence = min(0.9, 0.5 + breakout_pct * 5)
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'价格({curr_close:.2f})向上突破布林上轨({upper:.2f}), '
                    f'中轨({middle:.2f}), 下轨({lower:.2f})'
                )
            }

        # 向下突破下轨
        if prev_close >= prev_lower and curr_close < lower:
            breakout_pct = (lower - curr_close) / (band_width + 1e-10)
            confidence = min(0.9, 0.5 + breakout_pct * 5)
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'价格({curr_close:.2f})向下突破布林下轨({lower:.2f}), '
                    f'中轨({middle:.2f}), 上轨({upper:.2f})'
                )
            }

        # 无突破
        if curr_close > middle:
            return {
                'action': 'hold',
                'confidence': 0.6,
                'reason': (
                    f'价格({curr_close:.2f})在中轨({middle:.2f})上方, '
                    f'上轨({upper:.2f}), 下轨({lower:.2f}), 无突破'
                )
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.4,
                'reason': (
                    f'价格({curr_close:.2f})在中轨({middle:.2f})下方, '
                    f'上轨({upper:.2f}), 下轨({lower:.2f}), 无突破'
                )
            }
