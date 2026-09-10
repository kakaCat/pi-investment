"""
Shim: multi_source_data_fetcher 已迁移到 adapters/outbound/datasources/
此文件保留以兼容 live_trading 内部模块导入。
"""
from adapters.outbound.datasources.multi_source_data_fetcher import MultiSourceDataFetcher

__all__ = ['MultiSourceDataFetcher']
