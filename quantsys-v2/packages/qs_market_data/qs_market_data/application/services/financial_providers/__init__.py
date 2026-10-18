"""
财务数据提供者模块

提供多个财务数据源的统一接口和 fallback 机制。

2026-10-01（REQ-261001145152-3982 t-59468b）：删除 5 个**同名重复实现**
（tencent / akshare / sina / eastmoney / tushare `_provider.py`，共 792 行）。
它们与 `adapters/outbound/datasources/providers/financial/` 下的实现同名，
而真正被装配和调用的是后者（`adapters/outbound/datasources/manager.py:104-106`
实例化的是 adapters 树里的 `SinaFinancialProvider` / `EastmoneyFinancialProvider`）。
本目录的这 5 份从未被实例化（全仓 class 名引用 0），属"改一处忘一处"的复发源。
保留：`base.py`、`eastmoney_direct_provider.py`、`sina_web_provider.py`
（后两者被 adapters 树懒加载引用，如 financial/eastmoney.py:33、financial/sina.py:33）。
"""
from .base import FinancialDataProvider, FinancialIndicators, ValuationData
# Backward compatibility aliases
FinancialData = FinancialIndicators
FinancialProvider = FinancialDataProvider
from .eastmoney_direct_provider import EastmoneyDirectProvider
from .sina_web_provider import SinaWebFinancialProvider

__all__ = [
    'FinancialDataProvider',
    'FinancialIndicators',
    'ValuationData',
    'FinancialData',
    'FinancialProvider',
    'EastmoneyDirectProvider',
    'SinaWebFinancialProvider',
]
