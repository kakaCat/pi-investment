"""
均线交叉策略 (MA Cross)

买入信号: 短期均线向上穿越长期均线（金叉）
卖出信号: 短期均线向下穿越长期均线（死叉）
"""
from typing import Dict, List, Any

from domain.quantlib.engine.strategy_base import StrategyBase


class MACrossStrategy(StrategyBase):
    """
    均线交叉策略

    默认参数:
        ma_short: 5  (短期均线周期)
        ma_long: 20  (长期均线周期)
    """

    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据均线交叉生成交易信号

        Args:
            klines: K线数据列表
            params: 策略参数，支持 ma_short 和 ma_long

        Returns:
            信号字典
        """
        if params is None:
            params = {}

        ma_short = int(params.get('ma_short', 5))
        ma_long = int(params.get('ma_long', 20))
        min_required = max(ma_short, ma_long) + 1

        self._validate_klines(klines, min_length=min_required)
        closes = self._extract_closes(klines)

        # 计算两条均线
        short_ma = self._calculate_ma(closes, ma_short)
        long_ma = self._calculate_ma(closes, ma_long)

        # 获取最新的有效值
        if short_ma[-1] is None or long_ma[-1] is None:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'均线尚未形成 (需要至少 {min_required} 条K线)'
            }

        # 获取前一日均线值
        prev_short = short_ma[-2]
        prev_long = long_ma[-2]
        curr_short = short_ma[-1]
        curr_long = long_ma[-1]

        # 判断交叉
        prev_diff = prev_short - prev_long
        curr_diff = curr_short - curr_long

        # 金叉: 短期从下方穿越长期
        if prev_diff <= 0 and curr_diff > 0:
            confidence = min(0.9, abs(curr_diff) / (abs(curr_long) + 1e-10) * 5)
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'MA{ma_short}({curr_short:.2f}) 上穿 '
                    f'MA{ma_long}({curr_long:.2f}), '
                    f'金叉信号'
                )
            }

        # 死叉: 短期从上方穿越长期
        if prev_diff >= 0 and curr_diff < 0:
            confidence = min(0.9, abs(curr_diff) / (abs(curr_long) + 1e-10) * 5)
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'MA{ma_short}({curr_short:.2f}) 下穿 '
                    f'MA{ma_long}({curr_long:.2f}), '
                    f'死叉信号'
                )
            }

        # 无交叉
        if curr_diff > 0:
            return {
                'action': 'hold',
                'confidence': 0.6,
                'reason': (
                    f'MA{ma_short}({curr_short:.2f}) 在 MA{ma_long}({curr_long:.2f}) 上方, '
                    f'多头排列，无交叉'
                )
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.4,
                'reason': (
                    f'MA{ma_short}({curr_short:.2f}) 在 MA{ma_long}({curr_long:.2f}) 下方, '
                    f'空头排列，无交叉'
                )
            }
