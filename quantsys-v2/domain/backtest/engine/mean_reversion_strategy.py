"""
均值回归策略 (Mean Reversion Strategy)

基于布林带的均值回归策略。

买入信号: 价格触及下轨，预期反弹
卖出信号: 价格触及上轨，预期回落
"""
import structlog
logger = structlog.get_logger(__name__)
from typing import Dict, List, Any

from domain.backtest.engine.strategy_base import StrategyBase


class MeanReversionStrategy(StrategyBase):
    """
    均值回归策略

    默认参数:
        period: 20      (布林带周期)
        num_std: 2.0    (标准差倍数)
        threshold: 0.02 (触及阈值，2%以内算触及)
    """

    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据布林带均值回归生成交易信号

        Args:
            klines: K线数据列表
            params: 策略参数

        Returns:
            信号字典
        """
        if params is None:
            params = {}

        period = int(params.get('period', 20))
        num_std = float(params.get('num_std', 2.0))
        threshold = float(params.get('threshold', 0.02))
        min_required = period + 1

        self._validate_klines(klines, min_length=min_required)
        closes = self._extract_closes(klines)

        # 计算布林带
        bands = self._calculate_bollinger_bands(closes, period, num_std)
        upper = bands['upper'][-1]
        lower = bands['lower'][-1]
        middle = bands['middle'][-1]

        current_close = closes[-1]
        prev_close = closes[-2]

        # 计算价格相对位置
        band_width = upper - lower
        position = (current_close - lower) / band_width if band_width > 0 else 0.5

        # 计算距离上下轨的距离
        dist_to_lower = abs(current_close - lower) / lower
        dist_to_upper = abs(current_close - upper) / upper

        # 买入信号: 触及下轨（超卖）
        if dist_to_lower <= threshold and current_close < middle:
            # RSI确认（如果数据足够）
            rsi_confirm = 1.0
            if len(closes) >= 15:
                try:
                    rsi = self._calculate_rsi(closes, 14)
                    if rsi < 30:
                        rsi_confirm = 1.2  # RSI超卖，增强信号
                except Exception:
                    logger.debug("unexpected exception in module", exc_info=True)
                    pass

            confidence = min(0.85, 0.6 + (threshold - dist_to_lower) * 10) * rsi_confirm
            confidence = min(0.9, confidence)
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'价格触及布林带下轨 {lower:.2f}, '
                    f'当前价 {current_close:.2f}, 预期均值回归'
                )
            }

        # 卖出信号: 触及上轨（超买）
        if dist_to_upper <= threshold and current_close > middle:
            rsi_confirm = 1.0
            if len(closes) >= 15:
                try:
                    rsi = self._calculate_rsi(closes, 14)
                    if rsi > 70:
                        rsi_confirm = 1.2  # RSI超买，增强信号
                except Exception:
                    logger.debug("unexpected exception in module", exc_info=True)
                    pass

            confidence = min(0.85, 0.6 + (threshold - dist_to_upper) * 10) * rsi_confirm
            confidence = min(0.9, confidence)
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'价格触及布林带上轨 {upper:.2f}, '
                    f'当前价 {current_close:.2f}, 预期均值回归'
                )
            }

        # 持有状态
        if position > 0.8:
            return {
                'action': 'hold',
                'confidence': 0.6,
                'reason': (
                    f'价格在上轨附近 ({position:.1%}), '
                    f'当前价 {current_close:.2f}, 等待回归信号'
                )
            }
        elif position < 0.2:
            return {
                'action': 'hold',
                'confidence': 0.4,
                'reason': (
                    f'价格在下轨附近 ({position:.1%}), '
                    f'当前价 {current_close:.2f}, 等待回归信号'
                )
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.5,
                'reason': (
                    f'价格在中轨附近 ({position:.1%}), '
                    f'当前价 {current_close:.2f}, 中轨 {middle:.2f}'
                )
            }
