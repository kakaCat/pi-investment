"""
回测领域 (Backtest Domain)

职责：
- 策略回测引擎
- 回测阶段管理（数据准备、信号生成、执行、评估）
- 回测流水线
- 回测结果评估

核心概念：
- BacktestEngine: 回测引擎核心，协调整个回测流程
- Stage: 回测阶段，每个阶段负责一个独立的职责
- Pipeline: 数据处理流水线
- BacktestResult: 回测结果和性能指标

与其他领域的关系：
- 使用 domain.strategies 中的策略定义
- 使用 domain.risk 进行风险评估
- 使用 domain.factors 计算因子
- 调用 infrastructure.quantlib 进行技术计算

示例：
    from domain.backtest import BacktestEngine
    from domain.backtest.stages import DataStage, SignalStage
    
    engine = BacktestEngine(strategy=my_strategy)
    result = engine.run(start_date='2023-01-01', end_date='2023-12-31')
"""

# 暂时不导出具体类，等待更新完导入路径后再添加
__all__ = []
