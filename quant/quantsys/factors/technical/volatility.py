"""
波动类技术因子
"""
import pandas as pd
import numpy as np
from ..base import TechnicalFactor


class ATR(TechnicalFactor):
    """平均真实波幅 (Average True Range)"""

    def __init__(self, period: int = 14):
        super().__init__(
            name=f"ATR{period}",
            description=f"{period}日平均真实波幅",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算ATR"""
        required_cols = ['high', 'low', 'close']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        high = data['high']
        low = data['low']
        close = data['close']

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.period, min_periods=1).mean()

        return atr


class BollingerBands(TechnicalFactor):
    """布林带 (Bollinger Bands)"""

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__(
            name="BB",
            description=f"布林带 (period={period}, std={std_dev})"
        )
        self.period = period
        self.std_dev = std_dev

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算布林带

        Returns:
            DataFrame with columns: bb_upper, bb_middle, bb_lower, bb_width, bb_percent
        """
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")

        close = data['close']
        middle = close.rolling(window=self.period, min_periods=1).mean()
        std = close.rolling(window=self.period, min_periods=1).std()

        upper = middle + (std * self.std_dev)
        lower = middle - (std * self.std_dev)

        width = upper - lower
        percent = (close - lower) / width

        result = pd.DataFrame({
            'bb_upper': upper,
            'bb_middle': middle,
            'bb_lower': lower,
            'bb_width': width,
            'bb_percent': percent
        }, index=data.index)

        return result

    def validate(self, result: pd.DataFrame) -> bool:
        """验证布林带结果"""
        if result is None or len(result) == 0:
            return False

        required_cols = ['bb_upper', 'bb_middle', 'bb_lower', 'bb_width', 'bb_percent']
        if not all(col in result.columns for col in required_cols):
            return False

        if result.isna().all().all():
            return False

        return True


class KeltnerChannel(TechnicalFactor):
    """肯特纳通道 (Keltner Channel)"""

    def __init__(self, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0):
        super().__init__(
            name="KC",
            description=f"肯特纳通道 (EMA={ema_period}, ATR={atr_period}, mult={multiplier})"
        )
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.multiplier = multiplier

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算肯特纳通道

        Returns:
            DataFrame with columns: kc_upper, kc_middle, kc_lower
        """
        required_cols = ['high', 'low', 'close']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        middle = data['close'].ewm(span=self.ema_period, adjust=False).mean()

        high = data['high']
        low = data['low']
        close = data['close']

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period, min_periods=1).mean()

        upper = middle + (atr * self.multiplier)
        lower = middle - (atr * self.multiplier)

        result = pd.DataFrame({
            'kc_upper': upper,
            'kc_middle': middle,
            'kc_lower': lower
        }, index=data.index)

        return result

    def validate(self, result: pd.DataFrame) -> bool:
        """验证肯特纳通道结果"""
        if result is None or len(result) == 0:
            return False

        required_cols = ['kc_upper', 'kc_middle', 'kc_lower']
        if not all(col in result.columns for col in required_cols):
            return False

        if result.isna().all().all():
            return False

        return True


class StandardDeviation(TechnicalFactor):
    """标准差 (Standard Deviation)"""

    def __init__(self, period: int = 20):
        super().__init__(
            name=f"STD{period}",
            description=f"{period}日标准差",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算标准差"""
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")

        return data['close'].rolling(window=self.period, min_periods=1).std()


class HistoricalVolatility(TechnicalFactor):
    """历史波动率 (Historical Volatility)"""

    def __init__(self, period: int = 20):
        super().__init__(
            name=f"HV{period}",
            description=f"{period}日历史波动率（年化）",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算历史波动率"""
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")

        log_returns = np.log(data['close'] / data['close'].shift(1))
        volatility = log_returns.rolling(window=self.period, min_periods=1).std()

        # 年化波动率（假设252个交易日）
        annualized_volatility = volatility * np.sqrt(252) * 100

        return annualized_volatility


class DonchianChannel(TechnicalFactor):
    """唐奇安通道 (Donchian Channel)"""

    def __init__(self, period: int = 20):
        super().__init__(
            name=f"DC{period}",
            description=f"{period}日唐奇安通道",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算唐奇安通道

        Returns:
            DataFrame with columns: dc_upper, dc_middle, dc_lower
        """
        required_cols = ['high', 'low']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        upper = data['high'].rolling(window=self.period, min_periods=1).max()
        lower = data['low'].rolling(window=self.period, min_periods=1).min()
        middle = (upper + lower) / 2

        result = pd.DataFrame({
            'dc_upper': upper,
            'dc_middle': middle,
            'dc_lower': lower
        }, index=data.index)

        return result

    def validate(self, result: pd.DataFrame) -> bool:
        """验证唐奇安通道结果"""
        if result is None or len(result) == 0:
            return False

        required_cols = ['dc_upper', 'dc_middle', 'dc_lower']
        if not all(col in result.columns for col in required_cols):
            return False

        if result.isna().all().all():
            return False

        return True
