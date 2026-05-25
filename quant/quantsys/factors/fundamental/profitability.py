"""
盈利能力类基本面因子
"""
import pandas as pd
import numpy as np
from ..base import FundamentalFactor


class ROE(FundamentalFactor):
    """净资产收益率 (Return on Equity)"""

    def __init__(self):
        super().__init__(
            name="ROE",
            description="净资产收益率 = 净利润 / 股东权益 * 100%"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算ROE

        Args:
            data: 包含 'net_profit' 和 'equity' 列的DataFrame
        """
        required_cols = ['net_profit', 'equity']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        roe = (data['net_profit'] / data['equity']) * 100
        return roe.replace([np.inf, -np.inf], np.nan)


class ROA(FundamentalFactor):
    """总资产收益率 (Return on Assets)"""

    def __init__(self):
        super().__init__(
            name="ROA",
            description="总资产收益率 = 净利润 / 总资产 * 100%"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算ROA

        Args:
            data: 包含 'net_profit' 和 'total_assets' 列的DataFrame
        """
        required_cols = ['net_profit', 'total_assets']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        roa = (data['net_profit'] / data['total_assets']) * 100
        return roa.replace([np.inf, -np.inf], np.nan)


class GrossMargin(FundamentalFactor):
    """毛利率 (Gross Profit Margin)"""

    def __init__(self):
        super().__init__(
            name="GrossMargin",
            description="毛利率 = (营业收入 - 营业成本) / 营业收入 * 100%"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算毛利率

        Args:
            data: 包含 'revenue' 和 'cost' 列的DataFrame
        """
        required_cols = ['revenue', 'cost']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        gross_margin = ((data['revenue'] - data['cost']) / data['revenue']) * 100
        return gross_margin.replace([np.inf, -np.inf], np.nan)


class NetMargin(FundamentalFactor):
    """净利率 (Net Profit Margin)"""

    def __init__(self):
        super().__init__(
            name="NetMargin",
            description="净利率 = 净利润 / 营业收入 * 100%"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算净利率

        Args:
            data: 包含 'net_profit' 和 'revenue' 列的DataFrame
        """
        required_cols = ['net_profit', 'revenue']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        net_margin = (data['net_profit'] / data['revenue']) * 100
        return net_margin.replace([np.inf, -np.inf], np.nan)


class ROIC(FundamentalFactor):
    """投入资本回报率 (Return on Invested Capital)"""

    def __init__(self):
        super().__init__(
            name="ROIC",
            description="投入资本回报率 = NOPAT / 投入资本 * 100%"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算ROIC

        Args:
            data: 包含 'nopat' (税后净营业利润) 和 'invested_capital' 列的DataFrame
        """
        required_cols = ['nopat', 'invested_capital']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        roic = (data['nopat'] / data['invested_capital']) * 100
        return roic.replace([np.inf, -np.inf], np.nan)


class OperatingMargin(FundamentalFactor):
    """营业利润率 (Operating Profit Margin)"""

    def __init__(self):
        super().__init__(
            name="OperatingMargin",
            description="营业利润率 = 营业利润 / 营业收入 * 100%"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算营业利润率

        Args:
            data: 包含 'operating_profit' 和 'revenue' 列的DataFrame
        """
        required_cols = ['operating_profit', 'revenue']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        operating_margin = (data['operating_profit'] / data['revenue']) * 100
        return operating_margin.replace([np.inf, -np.inf], np.nan)
