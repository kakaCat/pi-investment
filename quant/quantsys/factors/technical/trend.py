"""
趋势类技术因子
"""
import pandas as pd
import numpy as np
from ..base import TechnicalFactor


class MA(TechnicalFactor):
    """简单移动平均线 (Simple Moving Average)"""

    def __init__(self, period: int = 20):
        super().__init__(
            name=f"MA{period}",
            description=f"{period}日简单移动平均线",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算MA"""
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")

        return data['close'].rolling(window=self.period, min_periods=1).mean()


class EMA(TechnicalFactor):
    """指数移动平均线 (Exponential Moving Average)"""

    def __init__(self, period: int = 12):
        super().__init__(
            name=f"EMA{period}",
            description=f"{period}日指数移动平均线",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算EMA"""
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")

        return data['close'].ewm(span=self.period, adjust=False).mean()


class MACD(TechnicalFactor):
    """MACD指标 (Moving Average Convergence Divergence)"""

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        super().__init__(
            name="MACD",
            description="MACD指标（DIF, DEA, Histogram）"
        )
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算MACD

        Returns:
            DataFrame with columns: macd_dif, macd_dea, macd_histogram
        """
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")

        # 计算快线和慢线EMA
        ema_fast = data['close'].ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = data['close'].ewm(span=self.slow_period, adjust=False).mean()

        # DIF = 快线 - 慢线
        macd_dif = ema_fast - ema_slow

        # DEA = DIF的EMA
        macd_dea = macd_dif.ewm(span=self.signal_period, adjust=False).mean()

        # Histogram = DIF - DEA
        macd_histogram = macd_dif - macd_dea

        result = pd.DataFrame({
            'macd_dif': macd_dif,
            'macd_dea': macd_dea,
            'macd_histogram': macd_histogram
        }, index=data.index)

        return result

    def validate(self, result: pd.DataFrame) -> bool:
        """验证MACD结果"""
        if result is None or len(result) == 0:
            return False

        required_cols = ['macd_dif', 'macd_dea', 'macd_histogram']
        if not all(col in result.columns for col in required_cols):
            return False

        # 检查是否全为NaN
        if result.isna().all().all():
            return False

        return True


class ADX(TechnicalFactor):
    """平均趋向指标 (Average Directional Index)"""

    def __init__(self, period: int = 14):
        super().__init__(
            name=f"ADX{period}",
            description=f"{period}日平均趋向指标，衡量趋势强度",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算ADX"""
        required_cols = ['high', 'low', 'close']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        high = data['high']
        low = data['low']
        close = data['close']

        # 计算True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 计算方向移动
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        plus_dm = pd.Series(plus_dm, index=data.index)
        minus_dm = pd.Series(minus_dm, index=data.index)

        # 平滑TR和DM
        atr = tr.rolling(window=self.period).mean()
        plus_di = 100 * (plus_dm.rolling(window=self.period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=self.period).mean() / atr)

        # 计算DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

        # ADX是DX的移动平均
        adx = dx.rolling(window=self.period).mean()

        return adx


class SMA(TechnicalFactor):
    """简单移动平均线的别名"""

    def __init__(self, period: int = 20):
        super().__init__(
            name=f"SMA{period}",
            description=f"{period}日简单移动平均线",
            period=period
        )
        self._ma = MA(period)

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        return self._ma.calculate(data)


class WMA(TechnicalFactor):
    """加权移动平均线 (Weighted Moving Average)"""

    def __init__(self, period: int = 20):
        super().__init__(
            name=f"WMA{period}",
            description=f"{period}日加权移动平均线",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算WMA"""
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")

        weights = np.arange(1, self.period + 1)

        def weighted_mean(x):
            if len(x) < self.period:
                return np.nan
            return np.sum(weights * x[-self.period:]) / np.sum(weights)

        return data['close'].rolling(window=self.period).apply(weighted_mean, raw=True)
