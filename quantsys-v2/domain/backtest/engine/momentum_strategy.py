"""
动量策略 (Momentum Strategy)

基于ROC (Rate of Change) 的动量策略。

买入信号: ROC上穿零线，动量转正
卖出信号: ROC下穿零线，动量转负
"""
from typing import Dict, List, Any

from domain.backtest.engine.strategy_base import StrategyBase


class MomentumStrategy(StrategyBase):
    """
    ROC动量策略

    默认参数:
        roc_period: 12  (ROC周期)
        ma_period: 5    (ROC均线周期，用于平滑)
    """

    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据ROC动量生成交易信号

        Args:
            klines: K线数据列表
            params: 策略参数

        Returns:
            信号字典
        """
        if params is None:
            params = {}

        roc_period = int(params.get('roc_period', 12))
        ma_period = int(params.get('ma_period', 5))
        min_required = roc_period + ma_period + 1

        self._validate_klines(klines, min_length=min_required)
        closes = self._extract_closes(klines)

        # 计算ROC: ((当前价 - N日前价) / N日前价) * 100
        roc_values = []
        for i in range(roc_period, len(closes)):
            roc = ((closes[i] - closes[i - roc_period]) / closes[i - roc_period]) * 100
            roc_values.append(roc)

        if len(roc_values) < ma_period + 1:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'ROC数据不足 (需要至少 {min_required} 条K线)'
            }

        # 计算ROC的移动平均（平滑信号）
        roc_ma = self._calculate_ma(roc_values, ma_period)

        current_roc = roc_values[-1]
        prev_roc = roc_values[-2]
        current_roc_ma = roc_ma[-1]
        prev_roc_ma = roc_ma[-2]

        current_close = closes[-1]

        # 买入信号: ROC上穿零线（动量转正）
        if prev_roc_ma <= 0 and current_roc_ma > 0:
            confidence = min(0.85, 0.6 + abs(current_roc_ma) / 10)

            # 构建追踪止损（5%）
            stop_loss = self._build_stop_loss_trailing(
                entry_price=current_close,
                trailing_percent=0.05,
                direction='long'
            )

            # 构建 Kelly 仓位
            position_sizing = self._build_position_sizing_kelly(
                win_rate=0.52,
                profit_loss_ratio=1.8,
                kelly_fraction=0.25
            )

            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'ROC上穿零线 (ROC={current_roc:.2f}%, MA={current_roc_ma:.2f}%), '
                    f'动量转正, 当前价 {current_close:.2f}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'roc': round(current_roc, 2),
                    'roc_ma': round(current_roc_ma, 2)
                }
            }

        # 卖出信号: ROC下穿零线（动量转负）
        if prev_roc_ma >= 0 and current_roc_ma < 0:
            confidence = min(0.85, 0.6 + abs(current_roc_ma) / 10)

            # 构建追踪止损（做空，5%）
            stop_loss = self._build_stop_loss_trailing(
                entry_price=current_close,
                trailing_percent=0.05,
                direction='short'
            )

            # 构建 Kelly 仓位
            position_sizing = self._build_position_sizing_kelly(
                win_rate=0.52,
                profit_loss_ratio=1.8,
                kelly_fraction=0.25
            )

            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'ROC下穿零线 (ROC={current_roc:.2f}%, MA={current_roc_ma:.2f}%), '
                    f'动量转负, 当前价 {current_close:.2f}'
                ),
                'risk_management': {
                    'stop_loss': stop_loss,
                    'position_sizing': position_sizing
                },
                'indicators': {
                    'roc': round(current_roc, 2),
                    'roc_ma': round(current_roc_ma, 2)
                }
            }

        # 持有状态
        if current_roc_ma > 5:
            return {
                'action': 'hold',
                'confidence': 0.7,
                'reason': (
                    f'强势动量 (ROC MA={current_roc_ma:.2f}%), '
                    f'当前价 {current_close:.2f}, 趋势向上'
                )
            }
        elif current_roc_ma < -5:
            return {
                'action': 'hold',
                'confidence': 0.3,
                'reason': (
                    f'弱势动量 (ROC MA={current_roc_ma:.2f}%), '
                    f'当前价 {current_close:.2f}, 趋势向下'
                )
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.5,
                'reason': (
                    f'中性动量 (ROC MA={current_roc_ma:.2f}%), '
                    f'当前价 {current_close:.2f}, 无明确趋势'
                )
            }
