"""
质量类基本面因子
"""
import pandas as pd
import numpy as np
from ..base import FundamentalFactor


class DebtToAsset(FundamentalFactor):
    """资产负债率 (Debt-to-Asset Ratio)"""

    def __init__(self):
        super().__init__(
            name="DebtToAsset",
            description="资产负债率 = 总负债 / 总资产 * 100%"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算资产负债率

        Args:
            data: 包含 'total_liabilities' 和 'total_assets' 列的DataFrame
        """
        required_cols = ['total_liabilities', 'total_assets']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        debt_to_asset = (data['total_liabilities'] / data['total_assets']) * 100
        return debt_to_asset.replace([np.inf, -np.inf], np.nan)


class CurrentRatio(FundamentalFactor):
    """流动比率 (Current Ratio)"""

    def __init__(self):
        super().__init__(
            name="CurrentRatio",
            description="流动比率 = 流动资产 / 流动负债"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算流动比率

        Args:
            data: 包含 'current_assets' 和 'current_liabilities' 列的DataFrame
        """
        required_cols = ['current_assets', 'current_liabilities']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        current_ratio = data['current_assets'] / data['current_liabilities']
        return current_ratio.replace([np.inf, -np.inf], np.nan)


class QuickRatio(FundamentalFactor):
    """速动比率 (Quick Ratio)"""

    def __init__(self):
        super().__init__(
            name="QuickRatio",
            description="速动比率 = (流动资产 - 存货) / 流动负债"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算速动比率

        Args:
            data: 包含 'current_assets', 'inventory', 'current_liabilities' 列的DataFrame
        """
        required_cols = ['current_assets', 'inventory', 'current_liabilities']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        quick_ratio = (data['current_assets'] - data['inventory']) / data['current_liabilities']
        return quick_ratio.replace([np.inf, -np.inf], np.nan)


class CashRatio(FundamentalFactor):
    """现金比率 (Cash Ratio)"""

    def __init__(self):
        super().__init__(
            name="CashRatio",
            description="现金比率 = (货币资金 + 交易性金融资产) / 流动负债"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算现金比率

        Args:
            data: 包含 'cash', 'marketable_securities', 'current_liabilities' 列的DataFrame
        """
        required_cols = ['cash', 'marketable_securities', 'current_liabilities']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        cash_ratio = (data['cash'] + data['marketable_securities']) / data['current_liabilities']
        return cash_ratio.replace([np.inf, -np.inf], np.nan)


class DebtToEquity(FundamentalFactor):
    """产权比率 (Debt-to-Equity Ratio)"""

    def __init__(self):
        super().__init__(
            name="DebtToEquity",
            description="产权比率 = 总负债 / 股东权益"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算产权比率

        Args:
            data: 包含 'total_liabilities' 和 'equity' 列的DataFrame
        """
        required_cols = ['total_liabilities', 'equity']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        debt_to_equity = data['total_liabilities'] / data['equity']
        return debt_to_equity.replace([np.inf, -np.inf], np.nan)


class InterestCoverage(FundamentalFactor):
    """利息保障倍数 (Interest Coverage Ratio)"""

    def __init__(self):
        super().__init__(
            name="InterestCoverage",
            description="利息保障倍数 = EBIT / 利息费用"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算利息保障倍数

        Args:
            data: 包含 'ebit' 和 'interest_expense' 列的DataFrame
        """
        required_cols = ['ebit', 'interest_expense']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        interest_coverage = data['ebit'] / data['interest_expense']
        return interest_coverage.replace([np.inf, -np.inf], np.nan)


class AssetTurnover(FundamentalFactor):
    """总资产周转率 (Asset Turnover Ratio)"""

    def __init__(self):
        super().__init__(
            name="AssetTurnover",
            description="总资产周转率 = 营业收入 / 平均总资产"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算总资产周转率

        Args:
            data: 包含 'revenue' 和 'avg_total_assets' 列的DataFrame
        """
        required_cols = ['revenue', 'avg_total_assets']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        asset_turnover = data['revenue'] / data['avg_total_assets']
        return asset_turnover.replace([np.inf, -np.inf], np.nan)


class InventoryTurnover(FundamentalFactor):
    """存货周转率 (Inventory Turnover Ratio)"""

    def __init__(self):
        super().__init__(
            name="InventoryTurnover",
            description="存货周转率 = 营业成本 / 平均存货"
        )

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算存货周转率

        Args:
            data: 包含 'cost' 和 'avg_inventory' 列的DataFrame
        """
        required_cols = ['cost', 'avg_inventory']
        if not all(col in data.columns for col in required_cols):
            raise ValueError(f"Data must contain columns: {required_cols}")

        inventory_turnover = data['cost'] / data['avg_inventory']
        return inventory_turnover.replace([np.inf, -np.inf], np.nan)
