"""
突破策略 (Breakout Strategy)

价格突破 + 成交量确认的突破策略。

买入信号: 价格突破阻力位 + 成交量放大
卖出信号: 价格跌破支撑位 + 成交量放大
"""
from typing import Dict, List, Any

from domain.backtest.engine.strategy_base import StrategyBase


class BreakoutStrategy(StrategyBase):
    """
    突破策略（价格 + 成交量确认）

    默认参数:
        lookback_period: 20  (回溯周期，用于确定阻力/支撑位)
        volume_ma_period: 10 (成交量均线周期)
        volume_threshold: 1.5 (成交量放大倍数)
    """

    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据价格突破和成交量生成交易信号

        Args:
            klines: K线数据列表
            params: 策略参数

        Returns:
            信号字典
        """
        if params is None:
            params = {}

        lookback_period = int(params.get('lookback_period', 20))
        volume_ma_period = int(params.get('volume_ma_period', 10))
        volume_threshold = float(params.get('volume_threshold', 1.5))
        min_required = max(lookback_period, volume_ma_period) + 1

        self._validate_klines(klines, min_length=min_required)

        # 提取价格和成交量数据
        highs = [float(k.get('high', k['close'])) for k in klines]
        lows = [float(k.get('low', k['close'])) for k in klines]
        closes = self._extract_closes(klines)
        volumes = [float(k.get('volume', 0)) for k in klines]

        # 计算阻力位和支撑位（过去N日的最高/最低价，不包括当天）
        resistance = max(highs[-lookback_period-1:-1])
        support = min(lows[-lookback_period-1:-1])

        # 计算成交量均线
        volume_ma = sum(volumes[-volume_ma_period-1:-1]) / volume_ma_period

        current_close = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]
        current_volume = volumes[-1]
        prev_close = closes[-2]

        # 成交量是否放大
        volume_surge = current_volume / volume_ma if volume_ma > 0 else 1.0

        # 买入信号: 突破阻力位 + 成交量放大
        if current_high > resistance and prev_close <= resistance:
            if volume_surge >= volume_threshold:
                confidence = min(0.9, 0.7 + (volume_surge - volume_threshold) * 0.1)
                return {
                    'action': 'buy',
                    'confidence': round(confidence, 4),
                    'reason': (
                        f'突破阻力位 {resistance:.2f}, 成交量放大 {volume_surge:.1f}x, '
                        f'当前价 {current_close:.2f}'
                    )
                }
            else:
                return {
                    'action': 'hold',
                    'confidence': 0.5,
                    'reason': (
                        f'突破阻力位 {resistance:.2f} 但成交量不足 ({volume_surge:.1f}x), '
                        f'当前价 {current_close:.2f}, 等待确认'
                    )
                }

        # 卖出信号: 跌破支撑位 + 成交量放大
        if current_low < support and prev_close >= support:
            if volume_surge >= volume_threshold:
                confidence = min(0.9, 0.7 + (volume_surge - volume_threshold) * 0.1)
                return {
                    'action': 'sell',
                    'confidence': round(confidence, 4),
                    'reason': (
                        f'跌破支撑位 {support:.2f}, 成交量放大 {volume_surge:.1f}x, '
                        f'当前价 {current_close:.2f}'
                    )
                }
            else:
                return {
                    'action': 'hold',
                    'confidence': 0.5,
                    'reason': (
                        f'跌破支撑位 {support:.2f} 但成交量不足 ({volume_surge:.1f}x), '
                        f'当前价 {current_close:.2f}, 等待确认'
                    )
                }

        # 持有状态
        range_position = (current_close - support) / (resistance - support) if resistance > support else 0.5

        if range_position > 0.8:
            return {
                'action': 'hold',
                'confidence': 0.6,
                'reason': (
                    f'价格接近阻力位 {resistance:.2f} ({range_position:.1%}), '
                    f'当前价 {current_close:.2f}, 等待突破'
                )
            }
        elif range_position < 0.2:
            return {
                'action': 'hold',
                'confidence': 0.4,
                'reason': (
                    f'价格接近支撑位 {support:.2f} ({range_position:.1%}), '
                    f'当前价 {current_close:.2f}, 等待突破'
                )
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.5,
                'reason': (
                    f'价格在区间内 [{support:.2f}, {resistance:.2f}] ({range_position:.1%}), '
                    f'当前价 {current_close:.2f}'
                )
            }
