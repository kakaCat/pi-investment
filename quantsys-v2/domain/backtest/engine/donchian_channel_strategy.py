"""
唐奇安通道突破策略 (Donchian Channel Strategy)

基于唐奇安通道的趋势跟踪策略。

买入信号: 价格突破N日最高价
卖出信号: 价格跌破N日最低价
"""
from typing import Dict, List, Any

from domain.backtest.engine.strategy_base import StrategyBase


class DonchianChannelStrategy(StrategyBase):
    """
    唐奇安通道突破策略

    默认参数:
        period: 20  (通道周期)
    """

    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据唐奇安通道生成交易信号

        Args:
            klines: K线数据列表
            params: 策略参数，支持 period

        Returns:
            信号字典
        """
        if params is None:
            params = {}

        period = int(params.get('period', 20))
        min_required = period + 1

        self._validate_klines(klines, min_length=min_required)

        # 提取价格数据
        highs = [float(k.get('high', k['close'])) for k in klines]
        lows = [float(k.get('low', k['close'])) for k in klines]
        closes = self._extract_closes(klines)

        # 计算唐奇安通道（不包括当天）
        upper_band = max(highs[-period-1:-1])
        lower_band = min(lows[-period-1:-1])
        middle_band = (upper_band + lower_band) / 2

        current_close = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]
        prev_close = closes[-2]

        # 计算通道宽度（波动率指标）
        channel_width = (upper_band - lower_band) / middle_band

        # 买入信号: 突破上轨
        if current_high > upper_band and prev_close <= upper_band:
            # 通道越窄，突破越有效
            confidence = min(0.9, 0.65 + (0.1 - channel_width) * 2)
            confidence = max(0.5, confidence)

            # 构建固定百分比止损（-8%）
            stop_loss = self._build_stop_loss_percent(
                entry_price=current_close,
                percent=0.08,
                direction='long'
            )

            # 构建固定比例仓位（12%）
            position_sizing = self._build_position_sizing_percent(0.12)

            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'突破唐奇安通道上轨 {upper_band:.2f}, '
                    f'当前价 {current_close:.2f}, 通道宽度 {channel_width:.2%}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                }
            }

        # 卖出信号: 跌破下轨
        if current_low < lower_band and prev_close >= lower_band:
            confidence = min(0.9, 0.65 + (0.1 - channel_width) * 2)
            confidence = max(0.5, confidence)

            # 构建固定百分比止损（做空，+8%）
            stop_loss = self._build_stop_loss_percent(
                entry_price=current_close,
                percent=0.08,
                direction='short'
            )

            # 构建固定比例仓位
            position_sizing = self._build_position_sizing_percent(0.12)

            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'跌破唐奇安通道下轨 {lower_band:.2f}, '
                    f'当前价 {current_close:.2f}, 通道宽度 {channel_width:.2%}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                }
            }

        # 持有状态
        position_in_channel = (current_close - lower_band) / (upper_band - lower_band)

        if position_in_channel > 0.7:
            return {
                'action': 'hold',
                'confidence': 0.6,
                'reason': (
                    f'价格在通道上部 ({position_in_channel:.1%}), '
                    f'当前价 {current_close:.2f}, 接近上轨 {upper_band:.2f}'
                )
            }
        elif position_in_channel < 0.3:
            return {
                'action': 'hold',
                'confidence': 0.4,
                'reason': (
                    f'价格在通道下部 ({position_in_channel:.1%}), '
                    f'当前价 {current_close:.2f}, 接近下轨 {lower_band:.2f}'
                )
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.5,
                'reason': (
                    f'价格在通道中部 ({position_in_channel:.1%}), '
                    f'当前价 {current_close:.2f}, 区间 [{lower_band:.2f}, {upper_band:.2f}]'
                )
            }
