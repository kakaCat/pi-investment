"""
财务数据提供者模块

提供多个财务数据源的统一接口和 fallback 机制。
"""
from .base import FinancialDataProvider, FinancialIndicators, ValuationData
# Backward compatibility aliases
FinancialData = FinancialIndicators
FinancialProvider = FinancialDataProvider
from .tencent_provider import TencentFinancialProvider
from .akshare_provider import AkshareFinancialProvider
from .eastmoney_direct_provider import EastmoneyDirectProvider
from .sina_provider import SinaFinancialProvider
from .eastmoney_provider import EastmoneyFinancialProvider
from .tushare_provider import TushareFinancialProvider
from .sina_web_provider import SinaWebFinancialProvider

__all__ = [
    'FinancialDataProvider',
    'FinancialIndicators',
    'ValuationData',
    'FinancialData',
    'FinancialProvider',
    'TencentFinancialProvider',
    'AkshareFinancialProvider',
    'EastmoneyDirectProvider',
    'SinaFinancialProvider',
    'EastmoneyFinancialProvider',
    'TushareFinancialProvider',
    'SinaWebFinancialProvider',
]
