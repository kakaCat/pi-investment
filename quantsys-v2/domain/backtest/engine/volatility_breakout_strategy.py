"""
波动率突破策略 (Volatility Breakout Strategy)

基于ATR (Average True Range) 的波动率突破策略。

买入信号: 价格突破 (昨收 + ATR * 系数)
卖出信号: 价格跌破 (昨收 - ATR * 系数)
"""
from typing import Dict, List, Any

from domain.backtest.engine.strategy_base import StrategyBase


class VolatilityBreakoutStrategy(StrategyBase):
    """
    ATR波动率突破策略

    默认参数:
        atr_period: 14      (ATR周期)
        atr_multiplier: 2.0 (ATR倍数)
    """

    def _calculate_atr(self, klines: List[Dict[str, Any]], period: int = 14) -> float:
        """
        计算ATR (Average True Range)

        Args:
            klines: K线数据列表
            period: ATR周期

        Returns:
            最新ATR值
        """
        if len(klines) < period + 1:
            raise ValueError(f"K线数据不足: 需要至少 {period + 1} 条")

        true_ranges = []
        for i in range(1, len(klines)):
            high = float(klines[i].get('high', klines[i]['close']))
            low = float(klines[i].get('low', klines[i]['close']))
            prev_close = float(klines[i-1]['close'])

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            raise ValueError(f"TR数据不足: 需要至少 {period} 条")

        # Wilder's smoothing
        atr = sum(true_ranges[:period]) / period
        for i in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[i]) / period

        return atr

    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据ATR波动率突破生成交易信号

        Args:
            klines: K线数据列表
            params: 策略参数

        Returns:
            信号字典
        """
        if params is None:
            params = {}

        atr_period = int(params.get('atr_period', 14))
        atr_multiplier = float(params.get('atr_multiplier', 2.0))
        min_required = atr_period + 2

        self._validate_klines(klines, min_length=min_required)

        # 计算ATR
        atr = self._calculate_atr(klines, atr_period)

        # 获取价格数据
        closes = self._extract_closes(klines)
        highs = [float(k.get('high', k['close'])) for k in klines]
        lows = [float(k.get('low', k['close'])) for k in klines]

        prev_close = closes[-2]
        current_close = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]

        # 计算突破阈值
        upper_threshold = prev_close + atr * atr_multiplier
        lower_threshold = prev_close - atr * atr_multiplier

        # 买入信号: 突破上阈值
        if current_high > upper_threshold:
            breakout_strength = (current_high - upper_threshold) / atr
            confidence = min(0.85, 0.65 + breakout_strength * 0.2)

            # 构建 ATR 止损（做多，止损价 = 当前价 - 2*ATR）
            stop_loss = self._build_stop_loss_atr(
                entry_price=current_close,
                atr=atr,
                multiplier=2.0,
                direction='long'
            )

            # 构建 Kelly 仓位（基于历史回测数据）
            position_sizing = self._build_position_sizing_kelly(
                win_rate=0.55,
                profit_loss_ratio=2.0,
                kelly_fraction=0.25
            )

            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'突破波动率上阈值 {upper_threshold:.2f} '
                    f'(昨收 {prev_close:.2f} + {atr_multiplier}*ATR {atr:.2f}), '
                    f'当前价 {current_close:.2f}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'atr': round(atr, 2)
                }
            }

        # 卖出信号: 跌破下阈值
        if current_low < lower_threshold:
            breakdown_strength = (lower_threshold - current_low) / atr
            confidence = min(0.85, 0.65 + breakdown_strength * 0.2)

            # 构建 ATR 止损（做空，止损价 = 当前价 + 2*ATR）
            stop_loss = self._build_stop_loss_atr(
                entry_price=current_close,
                atr=atr,
                multiplier=2.0,
                direction='short'
            )

            # 构建 Kelly 仓位
            position_sizing = self._build_position_sizing_kelly(
                win_rate=0.55,
                profit_loss_ratio=2.0,
                kelly_fraction=0.25
            )

            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'跌破波动率下阈值 {lower_threshold:.2f} '
                    f'(昨收 {prev_close:.2f} - {atr_multiplier}*ATR {atr:.2f}), '
                    f'当前价 {current_close:.2f}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'atr': round(atr, 2)
                }
            }

        # 持有状态
        position_in_range = (current_close - lower_threshold) / (upper_threshold - lower_threshold)

        if position_in_range > 0.7:
            return {
                'action': 'hold',
                'confidence': 0.6,
                'reason': (
                    f'价格接近上阈值 ({position_in_range:.1%}), '
                    f'当前价 {current_close:.2f}, ATR {atr:.2f}'
                )
            }
        elif position_in_range < 0.3:
            return {
                'action': 'hold',
                'confidence': 0.4,
                'reason': (
                    f'价格接近下阈值 ({position_in_range:.1%}), '
                    f'当前价 {current_close:.2f}, ATR {atr:.2f}'
                )
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.5,
                'reason': (
                    f'价格在波动区间内 ({position_in_range:.1%}), '
                    f'当前价 {current_close:.2f}, 区间 [{lower_threshold:.2f}, {upper_threshold:.2f}]'
                )
            }
