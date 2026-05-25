"""
成交量类技术因子
"""
import pandas as pd
import numpy as np
from ..base import TechnicalFactor


class OBV(TechnicalFactor):
    """能量潮指标 (On-Balance Volume)"""

    def __init__(self):
        super().__init__(
            name="OBV",
            description="能量潮指标，累积成交量"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算OBV"""
        required_cols = ['close', 'volume']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        close = data['close']
        volume = data['volume']

        obv = pd.Series(0, index=data.index, dtype=float)
        obv.iloc[0] = volume.iloc[0]

        for i in range(1, len(data)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]

        return obv


class MFI(TechnicalFactor):
    """资金流量指标 (Money Flow Index)"""

    def __init__(self, period: int = 14):
        super().__init__(
            name=f"MFI{period}",
            description=f"{period}日资金流量指标",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算MFI"""
        required_cols = ['high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        typical_price = (data['high'] + data['low'] + data['close']) / 3
        money_flow = typical_price * data['volume']

        price_diff = typical_price.diff()

        positive_flow = money_flow.where(price_diff > 0, 0)
        negative_flow = money_flow.where(price_diff < 0, 0)

        positive_mf = positive_flow.rolling(window=self.period, min_periods=1).sum()
        negative_mf = negative_flow.rolling(window=self.period, min_periods=1).sum()

        mfi = 100 - (100 / (1 + positive_mf / negative_mf))

        return mfi


class VWAP(TechnicalFactor):
    """成交量加权平均价 (Volume Weighted Average Price)"""

    def __init__(self, period: int = 20):
        super().__init__(
            name=f"VWAP{period}",
            description=f"{period}日成交量加权平均价",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算VWAP"""
        required_cols = ['high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        typical_price = (data['high'] + data['low'] + data['close']) / 3
        vwap = (typical_price * data['volume']).rolling(window=self.period, min_periods=1).sum() / \
               data['volume'].rolling(window=self.period, min_periods=1).sum()

        return vwap


class VolumeRatio(TechnicalFactor):
    """量比 (Volume Ratio)"""

    def __init__(self, period: int = 5):
        super().__init__(
            name=f"VR{period}",
            description=f"{period}日量比",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算量比"""
        if 'volume' not in data.columns:
            raise ValueError("Data must contain 'volume' column")

        avg_volume = data['volume'].rolling(window=self.period, min_periods=1).mean()
        volume_ratio = data['volume'] / avg_volume

        return volume_ratio


class AD(TechnicalFactor):
    """累积/派发线 (Accumulation/Distribution Line)"""

    def __init__(self):
        super().__init__(
            name="AD",
            description="累积/派发线"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算A/D线"""
        required_cols = ['high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        clv = ((data['close'] - data['low']) - (data['high'] - data['close'])) / \
              (data['high'] - data['low'])
        clv = clv.fillna(0)

        ad = (clv * data['volume']).cumsum()

        return ad


class CMF(TechnicalFactor):
    """蔡金资金流量 (Chaikin Money Flow)"""

    def __init__(self, period: int = 20):
        super().__init__(
            name=f"CMF{period}",
            description=f"{period}日蔡金资金流量",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算CMF"""
        required_cols = ['high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        clv = ((data['close'] - data['low']) - (data['high'] - data['close'])) / \
              (data['high'] - data['low'])
        clv = clv.fillna(0)

        money_flow_volume = clv * data['volume']

        cmf = money_flow_volume.rolling(window=self.period, min_periods=1).sum() / \
              data['volume'].rolling(window=self.period, min_periods=1).sum()

        return cmf


class EMV(TechnicalFactor):
    """简易波动指标 (Ease of Movement)"""

    def __init__(self, period: int = 14):
        super().__init__(
            name=f"EMV{period}",
            description=f"{period}日简易波动指标",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算EMV"""
        required_cols = ['high', 'low', 'volume']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        mid_point = (data['high'] + data['low']) / 2
        mid_point_move = mid_point - mid_point.shift(1)

        box_ratio = (data['volume'] / 1000000) / (data['high'] - data['low'])

        emv_raw = mid_point_move / box_ratio
        emv = emv_raw.rolling(window=self.period, min_periods=1).mean()

        return emv


class ForceIndex(TechnicalFactor):
    """力度指标 (Force Index)"""

    def __init__(self, period: int = 13):
        super().__init__(
            name=f"FI{period}",
            description=f"{period}日力度指标",
            period=period
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """计算力度指标"""
        required_cols = ['close', 'volume']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        force = data['close'].diff() * data['volume']
        force_index = force.ewm(span=self.period, adjust=False).mean()

        return force_index
