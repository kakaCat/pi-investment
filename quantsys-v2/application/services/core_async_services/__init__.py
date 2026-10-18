"""核心通用异步服务集合（原 core_async_services.py 单文件拆分，2026-10-19）

一文件一服务；import 面保持 `from application.services.core_async_services import X`。
原文件中无消费者的 RiskCheckAsyncService / StrategyCodeAsyncService /
PortfolioAsyncService 已删除：三者内部还按 09-11 已证废的模式直接实例化
domain 端口 ABC（IRiskRepository(session) 等，raised "takes no arguments"），
调用即炸且全仓零调用点（方案卡 core_async_services 拆分行）。
"""
from application.services.core_async_services.data import DataAsyncService
from application.services.core_async_services.market_data import MarketDataAsyncService
from application.services.core_async_services.performance import PerformanceAnalysisAsyncService

__all__ = [
    'DataAsyncService',
    'MarketDataAsyncService',
    'PerformanceAnalysisAsyncService',
]
