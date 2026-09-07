"""
配对交易策略 (Pairs Correlation Strategy)

基于两个相关资产的价差均值回归策略。

买入信号: 价差偏离均值过大（负向），买入价差（买A卖B）
卖出信号: 价差偏离均值过大（正向），卖出价差（卖A买B）
"""
from typing import Dict, List, Any
import math

from domain.backtest.engine.strategy_base import StrategyBase


class PairsCorrelationStrategy(StrategyBase):
    """
    配对交易策略

    默认参数:
        lookback_period: 60  (回溯周期)
        entry_threshold: 2.0 (入场标准差倍数)
        exit_threshold: 0.5  (出场标准差倍数)

    注意: 需要传入两个symbol的K线数据
    """

    def _calculate_correlation(self, prices_a: List[float], prices_b: List[float]) -> float:
        """
        计算两个价格序列的相关系数

        Args:
            prices_a: 价格序列A
            prices_b: 价格序列B

        Returns:
            相关系数 (-1 到 1)
        """
        n = len(prices_a)
        if n != len(prices_b) or n < 2:
            return 0.0

        mean_a = sum(prices_a) / n
        mean_b = sum(prices_b) / n

        numerator = sum((prices_a[i] - mean_a) * (prices_b[i] - mean_b) for i in range(n))

        var_a = sum((prices_a[i] - mean_a) ** 2 for i in range(n))
        var_b = sum((prices_b[i] - mean_b) ** 2 for i in range(n))

        denominator = math.sqrt(var_a * var_b)

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def generate_signal(
        self,
        klines: List[Dict[str, Any]],
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据配对价差生成交易信号

        Args:
            klines: K线数据列表（需要包含两个symbol的数据）
            params: 策略参数，必须包含:
                - symbol_a: 第一个股票代码
                - symbol_b: 第二个股票代码
                - klines_b: 第二个股票的K线数据

        Returns:
            信号字典
        """
        if params is None:
            params = {}

        lookback_period = int(params.get('lookback_period', 60))
        entry_threshold = float(params.get('entry_threshold', 2.0))
        exit_threshold = float(params.get('exit_threshold', 0.5))

        # 获取第二个股票的K线数据
        klines_b = params.get('klines_b')
        if not klines_b:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': '配对交易需要提供第二个股票的K线数据 (klines_b)'
            }

        min_required = lookback_period + 1
        self._validate_klines(klines, min_length=min_required)

        if len(klines_b) < min_required:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'第二个股票K线数据不足: 需要至少 {min_required} 条'
            }

        # 提取价格数据
        closes_a = self._extract_closes(klines)
        closes_b = [float(k['close']) for k in klines_b]

        # 确保两个序列长度一致
        min_len = min(len(closes_a), len(closes_b))
        closes_a = closes_a[-min_len:]
        closes_b = closes_b[-min_len:]

        if min_len < lookback_period:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'配对数据不足: 需要至少 {lookback_period} 条'
            }

        # 计算价差序列 (spread = price_a - price_b)
        spreads = [closes_a[i] - closes_b[i] for i in range(len(closes_a))]

        # 计算价差的均值和标准差
        spread_mean = sum(spreads[-lookback_period:]) / lookback_period
        spread_variance = sum((s - spread_mean) ** 2 for s in spreads[-lookback_period:]) / lookback_period
        spread_std = math.sqrt(spread_variance)

        current_spread = spreads[-1]
        z_score = (current_spread - spread_mean) / spread_std if spread_std > 0 else 0

        # 计算相关系数
        correlation = self._calculate_correlation(
            closes_a[-lookback_period:],
            closes_b[-lookback_period:]
        )

        symbol_a = params.get('symbol_a', 'A')
        symbol_b = params.get('symbol_b', 'B')

        # 相关性太低，不适合配对交易
        if abs(correlation) < 0.5:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': (
                    f'{symbol_a}/{symbol_b} 相关性不足 ({correlation:.2f}), '
                    f'不适合配对交易'
                )
            }

        # 买入信号: 价差过低（买A卖B）
        if z_score < -entry_threshold:
            confidence = min(0.85, 0.6 + (abs(z_score) - entry_threshold) * 0.1)
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': (
                    f'价差过低 (Z-score={z_score:.2f}), '
                    f'买入{symbol_a}卖出{symbol_b}, 相关性 {correlation:.2f}'
                )
            }

        # 卖出信号: 价差过高（卖A买B）
        if z_score > entry_threshold:
            confidence = min(0.85, 0.6 + (abs(z_score) - entry_threshold) * 0.1)
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': (
                    f'价差过高 (Z-score={z_score:.2f}), '
                    f'卖出{symbol_a}买入{symbol_b}, 相关性 {correlation:.2f}'
                )
            }

        # 持有状态
        if abs(z_score) < exit_threshold:
            return {
                'action': 'hold',
                'confidence': 0.5,
                'reason': (
                    f'价差接近均值 (Z-score={z_score:.2f}), '
                    f'{symbol_a}/{symbol_b}, 相关性 {correlation:.2f}'
                )
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.6,
                'reason': (
                    f'价差偏离中等 (Z-score={z_score:.2f}), '
                    f'{symbol_a}/{symbol_b}, 等待更强信号'
                )
            }
