"""
因子库 - 技术因子和基本面因子计算框架
"""
from quantsys.factors.base import BaseFactor, TechnicalFactor, FundamentalFactor
from quantsys.factors.calculator import FactorCalculator
from quantsys.factors.cache import FactorCache

# 导入技术因子
from quantsys.factors.technical.trend import MA, EMA, MACD, ADX, SMA, WMA
from quantsys.factors.technical.momentum import RSI, KDJ, CCI, ROC, WilliamsR, MOM, STOCH
from quantsys.factors.technical.volatility import ATR, BollingerBands, KeltnerChannel, StandardDeviation, HistoricalVolatility, DonchianChannel
from quantsys.factors.technical.volume import OBV, MFI, VWAP, VolumeRatio, AD, CMF, EMV, ForceIndex

# 导入基本面因子
from quantsys.factors.fundamental.valuation import PE, PB, PS, PCF, DividendYield, EV_EBITDA
from quantsys.factors.fundamental.profitability import ROE, ROA, GrossMargin, NetMargin, ROIC, OperatingMargin
from quantsys.factors.fundamental.growth import RevenueGrowth, ProfitGrowth, EPSGrowth, PEG, AssetGrowth
from quantsys.factors.fundamental.quality import DebtToAsset, CurrentRatio, QuickRatio, CashRatio, DebtToEquity, InterestCoverage, AssetTurnover, InventoryTurnover

__version__ = '0.1.0'

__all__ = [
    # 基础类
    'BaseFactor',
    'TechnicalFactor',
    'FundamentalFactor',
    'FactorCalculator',
    'FactorCache',

    # 技术因子 - 趋势
    'MA', 'EMA', 'MACD', 'ADX', 'SMA', 'WMA',

    # 技术因子 - 动量
    'RSI', 'KDJ', 'CCI', 'ROC', 'WilliamsR', 'MOM', 'STOCH',

    # 技术因子 - 波动
    'ATR', 'BollingerBands', 'KeltnerChannel', 'StandardDeviation', 'HistoricalVolatility', 'DonchianChannel',

    # 技术因子 - 成交量
    'OBV', 'MFI', 'VWAP', 'VolumeRatio', 'AD', 'CMF', 'EMV', 'ForceIndex',

    # 基本面因子 - 估值
    'PE', 'PB', 'PS', 'PCF', 'DividendYield', 'EV_EBITDA',

    # 基本面因子 - 盈利
    'ROE', 'ROA', 'GrossMargin', 'NetMargin', 'ROIC', 'OperatingMargin',

    # 基本面因子 - 成长
    'RevenueGrowth', 'ProfitGrowth', 'EPSGrowth', 'PEG', 'AssetGrowth',

    # 基本面因子 - 质量
    'DebtToAsset', 'CurrentRatio', 'QuickRatio', 'CashRatio', 'DebtToEquity', 'InterestCoverage', 'AssetTurnover', 'InventoryTurnover',
]
