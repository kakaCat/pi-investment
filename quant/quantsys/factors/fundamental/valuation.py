"""
估值类基本面因子
"""
import pandas as pd
import numpy as np
from ..base import FundamentalFactor


class PE(FundamentalFactor):
    """市盈率 (Price-to-Earnings Ratio)"""

    def __init__(self):
        super().__init__(
            name="PE",
            description="市盈率 = 股价 / 每股收益"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算PE

        Args:
            data: 包含 'price' 和 'eps' 列的DataFrame
        """
        required_cols = ['price', 'eps']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        pe = data['price'] / data['eps']
        return pe.replace([np.inf, -np.inf], np.nan)


class PB(FundamentalFactor):
    """市净率 (Price-to-Book Ratio)"""

    def __init__(self):
        super().__init__(
            name="PB",
            description="市净率 = 股价 / 每股净资产"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算PB

        Args:
            data: 包含 'price' 和 'bvps' (每股净资产) 列的DataFrame
        """
        required_cols = ['price', 'bvps']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        pb = data['price'] / data['bvps']
        return pb.replace([np.inf, -np.inf], np.nan)


class PS(FundamentalFactor):
    """市销率 (Price-to-Sales Ratio)"""

    def __init__(self):
        super().__init__(
            name="PS",
            description="市销率 = 股价 / 每股销售额"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算PS

        Args:
            data: 包含 'price' 和 'sales_per_share' 列的DataFrame
        """
        required_cols = ['price', 'sales_per_share']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        ps = data['price'] / data['sales_per_share']
        return ps.replace([np.inf, -np.inf], np.nan)


class PCF(FundamentalFactor):
    """市现率 (Price-to-Cash Flow Ratio)"""

    def __init__(self):
        super().__init__(
            name="PCF",
            description="市现率 = 股价 / 每股现金流"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算PCF

        Args:
            data: 包含 'price' 和 'cfps' (每股现金流) 列的DataFrame
        """
        required_cols = ['price', 'cfps']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        pcf = data['price'] / data['cfps']
        return pcf.replace([np.inf, -np.inf], np.nan)


class DividendYield(FundamentalFactor):
    """股息率 (Dividend Yield)"""

    def __init__(self):
        super().__init__(
            name="DividendYield",
            description="股息率 = 每股股息 / 股价 * 100%"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算股息率

        Args:
            data: 包含 'price' 和 'dps' (每股股息) 列的DataFrame
        """
        required_cols = ['price', 'dps']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        dividend_yield = (data['dps'] / data['price']) * 100
        return dividend_yield.replace([np.inf, -np.inf], np.nan)


class EV_EBITDA(FundamentalFactor):
    """企业价值倍数 (EV/EBITDA)"""

    def __init__(self):
        super().__init__(
            name="EV_EBITDA",
            description="企业价值倍数 = 企业价值 / EBITDA"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算EV/EBITDA

        Args:
            data: 包含 'market_cap', 'total_debt', 'cash', 'ebitda' 列的DataFrame
        """
        required_cols = ['market_cap', 'total_debt', 'cash', 'ebitda']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        ev = data['market_cap'] + data['total_debt'] - data['cash']
        ev_ebitda = ev / data['ebitda']
        return ev_ebitda.replace([np.inf, -np.inf], np.nan)
