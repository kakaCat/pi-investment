"""
基本面因子模块
"""
from .valuation import PE, PB, PS, PCF, DividendYield, EV_EBITDA
from .profitability import ROE, ROA, GrossMargin, NetMargin, ROIC, OperatingMargin
from .growth import RevenueGrowth, ProfitGrowth, EPSGrowth, PEG, AssetGrowth
from .quality import DebtToAsset, CurrentRatio, QuickRatio, CashRatio, DebtToEquity, InterestCoverage, AssetTurnover, InventoryTurnover

__all__ = [
    # Valuation
    'PE', 'PB', 'PS', 'PCF', 'DividendYield', 'EV_EBITDA',
    # Profitability
    'ROE', 'ROA', 'GrossMargin', 'NetMargin', 'ROIC', 'OperatingMargin',
    # Growth
    'RevenueGrowth', 'ProfitGrowth', 'EPSGrowth', 'PEG', 'AssetGrowth',
    # Quality
    'DebtToAsset', 'CurrentRatio', 'QuickRatio', 'CashRatio', 'DebtToEquity', 'InterestCoverage', 'AssetTurnover', 'InventoryTurnover'
]
