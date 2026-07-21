"""
RSI反转策略 (RSI Reversal)

买入信号: RSI 低于超卖线（默认 30），市场超卖，预期反弹
卖出信号: RSI 高于超买线（默认 70），市场超买，预期回调
"""
from typing import Dict, List, Any

from domain.quantlib.engine.strategy_base import StrategyBase


class RSIReversalStrategy(StrategyBase):
    """
    RSI反转策略

    默认参数:
        period: 14     (RSI 计算周期)
        oversold: 30   (超卖阈值)
        overbought: 70 (超买阈值)
    """

    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据RSI指标生成反转信号

        Args:
            klines: K线数据列表
            params: 策略参数，支持 period, oversold, overbought

        Returns:
            信号字典
        """
        if params is None:
            params = {}

        period = int(params.get('period', 14))
        oversold = float(params.get('oversold', 30))
        overbought = float(params.get('overbought', 70))
        min_required = period + 1

        self._validate_klines(klines, min_length=min_required)
        closes = self._extract_closes(klines)

        # 计算 RSI
        rsi = self._calculate_rsi(closes, period)

        # 超卖 - 买入信号
        if rsi <= oversold:
            confidence = min(0.9, (oversold - rsi) / oversold * 0.9 + 0.1)
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'RSI({period})={rsi:.2f} 低于超卖线 {oversold}, '
                    f'超卖反弹信号'
                )
            }

        # 超买 - 卖出信号
        if rsi >= overbought:
            confidence = min(0.9, (rsi - overbought) / (100 - overbought) * 0.9 + 0.1)
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'RSI({period})={rsi:.2f} 高于超买线 {overbought}, '
                    f'超买回调信号'
                )
            }

        # 中性区间
        return {
            'action': 'hold',
            'confidence': 0.5,
            'reason': f'RSI({period})={rsi:.2f} 在 [{oversold}, {overbought}] 正常区间'
        }
