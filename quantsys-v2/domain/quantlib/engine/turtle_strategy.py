"""
海龟交易策略 (Turtle Strategy)

经典的趋势跟踪策略，基于唐奇安通道突破。

买入信号: 价格突破20日最高价
卖出信号: 价格跌破10日最低价（止损）
"""
from typing import Dict, List, Any

from domain.quantlib.engine.strategy_base import StrategyBase


class TurtleStrategy(StrategyBase):
    """
    海龟交易策略

    默认参数:
        entry_period: 20  (入场突破周期)
        exit_period: 10   (出场突破周期)
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
            return 0.0

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
            return 0.0

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
        根据海龟交易法则生成交易信号

        Args:
            klines: K线数据列表
            params: 策略参数，支持 entry_period 和 exit_period

        Returns:
            信号字典
        """
        if params is None:
            params = {}

        entry_period = int(params.get('entry_period', 20))
        exit_period = int(params.get('exit_period', 10))
        min_required = max(entry_period, exit_period) + 1

        self._validate_klines(klines, min_length=min_required)

        # 提取价格数据
        highs = [float(k.get('high', k['close'])) for k in klines]
        lows = [float(k.get('low', k['close'])) for k in klines]
        closes = self._extract_closes(klines)

        # 计算唐奇安通道
        # 入场通道: 过去 entry_period 天的最高价/最低价
        entry_high = max(highs[-entry_period-1:-1])  # 不包括当天
        entry_low = min(lows[-entry_period-1:-1])

        # 出场通道: 过去 exit_period 天的最高价/最低价
        exit_high = max(highs[-exit_period-1:-1])
        exit_low = min(lows[-exit_period-1:-1])

        current_close = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]

        # 买入信号: 突破入场通道上轨
        if current_high > entry_high:
            breakout_strength = (current_high - entry_high) / entry_high
            confidence = min(0.85, 0.6 + breakout_strength * 10)

            # 计算 ATR
            atr = self._calculate_atr(klines, period=14)

            # 构建 ATR 止损
            stop_loss = self._build_stop_loss_atr(
                entry_price=current_close,
                atr=atr,
                multiplier=2.0,
                direction='long'
            )

            # 构建固定比例仓位（15%）
            position_sizing = self._build_position_sizing_percent(0.15)

            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'价格突破{entry_period}日高点 {entry_high:.2f}, '
                    f'当前价 {current_close:.2f}, 海龟入场信号'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'atr': round(atr, 2)
                }
            }

        # 卖出信号: 跌破出场通道下轨
        if current_low < exit_low:
            breakdown_strength = (exit_low - current_low) / exit_low
            confidence = min(0.85, 0.6 + breakdown_strength * 10)

            # 计算 ATR
            atr = self._calculate_atr(klines, period=14)

            # 构建 ATR 止损（做空）
            stop_loss = self._build_stop_loss_atr(
                entry_price=current_close,
                atr=atr,
                multiplier=2.0,
                direction='short'
            )

            # 构建固定比例仓位
            position_sizing = self._build_position_sizing_percent(0.15)

            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'价格跌破{exit_period}日低点 {exit_low:.2f}, '
                    f'当前价 {current_close:.2f}, 海龟止损信号'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'atr': round(atr, 2)
                }
            }

        # 持有状态判断
        if current_close > entry_low and current_close < entry_high:
            return {
                'action': 'hold',
                'confidence': 0.5,
                'reason': (
                    f'价格在通道内 [{entry_low:.2f}, {entry_high:.2f}], '
                    f'当前价 {current_close:.2f}, 等待突破'
                )
            }

        return {
            'action': 'hold',
            'confidence': 0.4,
            'reason': f'价格 {current_close:.2f}, 无明确信号'
        }
