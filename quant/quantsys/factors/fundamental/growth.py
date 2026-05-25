"""
成长性类基本面因子
"""
import pandas as pd
import numpy as np
from ..base import FundamentalFactor


class RevenueGrowth(FundamentalFactor):
    """营收增长率 (Revenue Growth Rate)"""

    def __init__(self, period: str = 'yoy'):
        """
        Args:
            period: 'yoy' (同比) 或 'qoq' (环比)
        """
        super().__init__(
            name=f"RevenueGrowth_{period}",
            description=f"营收增长率 ({period})"
        )
        self.period = period

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算营收增长率

        Args:
            data: 包含 'revenue' 和 'revenue_prev' 列的DataFrame
                  revenue_prev 是上期营收（同比或环比）
        """
        required_cols = ['revenue', 'revenue_prev']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        growth = ((data['revenue'] - data['revenue_prev']) / data['revenue_prev']) * 100
        return growth.replace([np.inf, -np.inf], np.nan)


class ProfitGrowth(FundamentalFactor):
    """净利润增长率 (Net Profit Growth Rate)"""

    def __init__(self, period: str = 'yoy'):
        """
        Args:
            period: 'yoy' (同比) 或 'qoq' (环比)
        """
        super().__init__(
            name=f"ProfitGrowth_{period}",
            description=f"净利润增长率 ({period})"
        )
        self.period = period

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算净利润增长率

        Args:
            data: 包含 'net_profit' 和 'net_profit_prev' 列的DataFrame
        """
        required_cols = ['net_profit', 'net_profit_prev']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        growth = ((data['net_profit'] - data['net_profit_prev']) / data['net_profit_prev']) * 100
        return growth.replace([np.inf, -np.inf], np.nan)


class EPSGrowth(FundamentalFactor):
    """每股收益增长率 (EPS Growth Rate)"""

    def __init__(self, period: str = 'yoy'):
        """
        Args:
            period: 'yoy' (同比) 或 'qoq' (环比)
        """
        super().__init__(
            name=f"EPSGrowth_{period}",
            description=f"每股收益增长率 ({period})"
        )
        self.period = period

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算EPS增长率

        Args:
            data: 包含 'eps' 和 'eps_prev' 列的DataFrame
        """
        required_cols = ['eps', 'eps_prev']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        growth = ((data['eps'] - data['eps_prev']) / data['eps_prev']) * 100
        return growth.replace([np.inf, -np.inf], np.nan)


class PEG(FundamentalFactor):
    """市盈率相对盈利增长比率 (PEG Ratio)"""

    def __init__(self):
        super().__init__(
            name="PEG",
            description="PEG = PE / 净利润增长率"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算PEG

        Args:
            data: 包含 'pe' 和 'profit_growth' 列的DataFrame
        """
        required_cols = ['pe', 'profit_growth']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        peg = data['pe'] / data['profit_growth']
        return peg.replace([np.inf, -np.inf], np.nan)


class AssetGrowth(FundamentalFactor):
    """总资产增长率 (Total Assets Growth Rate)"""

    def __init__(self, period: str = 'yoy'):
        """
        Args:
            period: 'yoy' (同比) 或 'qoq' (环比)
        """
        super().__init__(
            name=f"AssetGrowth_{period}",
            description=f"总资产增长率 ({period})"
        )
        self.period = period

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算总资产增长率

        Args:
            data: 包含 'total_assets' 和 'total_assets_prev' 列的DataFrame
        """
        required_cols = ['total_assets', 'total_assets_prev']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        growth = ((data['total_assets'] - data['total_assets_prev']) / data['total_assets_prev']) * 100
        return growth.replace([np.inf, -np.inf], np.nan)
