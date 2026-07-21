"""MACD 计算器 - 使用 TA-Lib 计算真实 MACD"""
from typing import List
import pandas as pd
import numpy as np
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
from .types import KLine


class MACDCalculator:
    """
    MACD 计算器

    使用 TA-Lib 计算 MACD(12, 26, 9)
    """

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        初始化 MACD 计算器

        Args:
            fast_period: 快线周期（默认12）
            slow_period: 慢线周期（默认26）
            signal_period: 信号线周期（默认9）
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self, klines: List[KLine]) -> pd.DataFrame:
        """
        计算 MACD 指标

        Args:
            klines: K线列表

        Returns:
            DataFrame with columns: ['macd', 'signal', 'hist']
        """
        if not TALIB_AVAILABLE:
            # Fallback: 简化计算
            return self._calculate_simple(klines)

        # 提取收盘价
        closes = np.array([k.close for k in klines])

        # 使用 TA-Lib 计算 MACD
        macd, signal, hist = talib.MACD(
            closes,
            fastperiod=self.fast_period,
            slowperiod=self.slow_period,
            signalperiod=self.signal_period
        )

        return pd.DataFrame({
            'macd': macd,
            'signal': signal,
            'hist': hist
        })

    def calculate_area(self, klines: List[KLine], start_idx: int, end_idx: int) -> float:
        """
        计算线段对应的 MACD 柱面积

        Args:
            klines: K线列表
            start_idx: 起始索引
            end_idx: 结束索引

        Returns:
            MACD 柱面积（可能为负）
        """
        macd_df = self.calculate(klines)

        # 取指定区间的柱状图值
        hist_values = macd_df['hist'].iloc[start_idx:end_idx+1]

        # 计算面积（梯形积分）
        area = np.trapezoid(hist_values.fillna(0))

        return area

    def _calculate_simple(self, klines: List[KLine]) -> pd.DataFrame:
        """
        简化版 MACD 计算（TA-Lib 不可用时使用）

        使用 EMA 手动计算
        """
        closes = pd.Series([k.close for k in klines])

        # 计算快慢 EMA
        ema_fast = closes.ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = closes.ewm(span=self.slow_period, adjust=False).mean()

        # MACD = 快线 - 慢线
        macd = ema_fast - ema_slow

        # 信号线 = MACD 的 EMA
        signal = macd.ewm(span=self.signal_period, adjust=False).mean()

        # 柱状图 = MACD - 信号线
        hist = macd - signal

        return pd.DataFrame({
            'macd': macd,
            'signal': signal,
            'hist': hist
        })
