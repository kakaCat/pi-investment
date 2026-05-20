"""
动量类技术因子
"""
import pandas as pd
import numpy as np
from ..base import TechnicalFactor


class RSI(TechnicalFactor):
    """相对强弱指标 (Relative Strength Index)"""

    def __init__(self, period: int = 14):
        super().__init__(
            name=f"RSI{period}",
            description=f"{period}日相对强弱指标",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算RSI"""
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")

        close = data['close']
        delta = close.diff()

        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=self.period, min_periods=1).mean()
        avg_loss = loss.rolling(window=self.period, min_periods=1).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi


class KDJ(TechnicalFactor):
    """KDJ随机指标"""

    def __init__(self, n: int = 9, m1: int = 3, m2: int = 3):
        super().__init__(
            name="KDJ",
            description=f"KDJ随机指标 (n={n}, m1={m1}, m2={m2})"
        )
        self.n = n
        self.m1 = m1
        self.m2 = m2

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算KDJ

        Returns:
            DataFrame with columns: k, d, j
        """
        required_cols = ['high', 'low', 'close']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        low_min = data['low'].rolling(window=self.n, min_periods=1).min()
        high_max = data['high'].rolling(window=self.n, min_periods=1).max()

        rsv = 100 * (data['close'] - low_min) / (high_max - low_min)
        rsv = rsv.fillna(50)

        k = rsv.ewm(alpha=1/self.m1, adjust=False).mean()
        d = k.ewm(alpha=1/self.m2, adjust=False).mean()
        j = 3 * k - 2 * d

        result = pd.DataFrame({
            'k': k,
            'd': d,
            'j': j
        }, index=data.index)

        return result

    def validate(self, result: pd.DataFrame) -> bool:
        """验证KDJ结果"""
        if result is None or len(result) == 0:
            return False

        required_cols = ['k', 'd', 'j']
        if not all(col in result.columns for col in required_cols):
            return False

        if result.isna().all().all():
            return False

        return True


class CCI(TechnicalFactor):
    """商品通道指标 (Commodity Channel Index)"""

    def __init__(self, period: int = 20):
        super().__init__(
            name=f"CCI{period}",
            description=f"{period}日商品通道指标",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算CCI"""
        required_cols = ['high', 'low', 'close']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        tp = (data['high'] + data['low'] + data['close']) / 3
        ma = tp.rolling(window=self.period, min_periods=1).mean()
        md = tp.rolling(window=self.period, min_periods=1).apply(
            lambda x: np.abs(x - x.mean()).mean(), raw=True
        )

        cci = (tp - ma) / (0.015 * md)

        return cci


class ROC(TechnicalFactor):
    """变动率指标 (Rate of Change)"""

    def __init__(self, period: int = 12):
        super().__init__(
            name=f"ROC{period}",
            description=f"{period}日变动率指标",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算ROC"""
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")

        close = data['close']
        roc = 100 * (close - close.shift(self.period)) / close.shift(self.period)

        return roc


class WilliamsR(TechnicalFactor):
    """威廉指标 (Williams %R)"""

    def __init__(self, period: int = 14):
        super().__init__(
            name=f"WR{period}",
            description=f"{period}日威廉指标",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算Williams %R"""
        required_cols = ['high', 'low', 'close']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        highest_high = data['high'].rolling(window=self.period, min_periods=1).max()
        lowest_low = data['low'].rolling(window=self.period, min_periods=1).min()

        wr = -100 * (highest_high - data['close']) / (highest_high - lowest_low)
        wr = wr.replace([np.inf, -np.inf], np.nan)

        return wr


class MOM(TechnicalFactor):
    """动量指标 (Momentum)"""

    def __init__(self, period: int = 10):
        super().__init__(
            name=f"MOM{period}",
            description=f"{period}日动量指标",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算动量"""
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")

        mom = data['close'] - data['close'].shift(self.period)

        return mom


class STOCH(TechnicalFactor):
    """随机指标 (Stochastic Oscillator)"""

    def __init__(self, k_period: int = 14, d_period: int = 3):
        super().__init__(
            name="STOCH",
            description=f"随机指标 (K={k_period}, D={d_period})"
        )
        self.k_period = k_period
        self.d_period = d_period

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算随机指标

        Returns:
            DataFrame with columns: stoch_k, stoch_d
        """
        required_cols = ['high', 'low', 'close']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        lowest_low = data['low'].rolling(window=self.k_period, min_periods=1).min()
        highest_high = data['high'].rolling(window=self.k_period, min_periods=1).max()

        stoch_k = 100 * (data['close'] - lowest_low) / (highest_high - lowest_low)
        stoch_k = stoch_k.replace([np.inf, -np.inf], np.nan).fillna(50)
        stoch_d = stoch_k.rolling(window=self.d_period, min_periods=1).mean()

        result = pd.DataFrame({
            'stoch_k': stoch_k,
            'stoch_d': stoch_d
        }, index=data.index)

        return result

    def validate(self, result: pd.DataFrame) -> bool:
        """验证STOCH结果"""
        if result is None or len(result) == 0:
            return False

        required_cols = ['stoch_k', 'stoch_d']
        if not all(col in result.columns for col in required_cols):
            return False

        if result.isna().all().all():
            return False

        return True
