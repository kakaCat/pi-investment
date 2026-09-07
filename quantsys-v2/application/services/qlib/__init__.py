"""
Qlib Services Package

整合微软 Qlib 量化框架到 quantsys-v2

模块:
- qlib_data_adapter: 数据适配器（连接 PostgreSQL）
- alpha158_service: Alpha158 因子服务
- qlib_model_service: 模型训练服务
- qlib_backtest_service: 回测服务
"""

__all__ = [
    'QuantsysV2DataProvider',
    'QlibAlpha158Service',
    'QlibModelService',
    'QlibBacktestService'
]
