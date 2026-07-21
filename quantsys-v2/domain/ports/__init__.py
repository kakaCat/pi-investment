"""
Domain Ports (Interfaces)

定义 Domain 层需要的外部依赖接口（端口）
遵循依赖倒置原则：Domain 定义接口，Adapters 实现接口

架构原则：
- Domain 层只依赖这些抽象接口，不依赖具体实现
- Adapters 层实现这些接口
- 依赖方向：Adapters → Domain (依赖倒置)
"""

from .repository_ports import (
    IKlineRepository,
    ISignalRepository,
    IPortfolioRepository,
    IRiskRepository,
    IFactorRepository,
    IStrategyRepository,
)

from .repository_ports_extended import (
    IStockRepository,
    IBacktestRepository,
    IFinancialRepository,
    IStockPoolRepository,
    IPositionRepository,
    IRiskConfigRepository,
    IStrategyPerformanceRepository,
    IFundFlowRepository,
    IMarketStyleRepository,
    IDataQualityRepository,
    IMlModelRepository,
    IStrategyCircuitBreakerRepository,
    IStrategyWeightRepository,
    ITraceabilityRepository,
    IAgentIntelligenceRepository,
    ISignalExecutionLogRepository,
    ISignalExecutionRepository,
    ISimulationRepository,
    IAsyncKlineRepository,
    IAsyncFactorRepository,
)

__all__ = [
    # 核心接口
    'IKlineRepository',
    'ISignalRepository',
    'IPortfolioRepository',
    'IRiskRepository',
    'IFactorRepository',
    'IStrategyRepository',
    # 扩展接口
    'IStockRepository',
    'IBacktestRepository',
    'IFinancialRepository',
    'IStockPoolRepository',
    'IPositionRepository',
    'IRiskConfigRepository',
    'IStrategyPerformanceRepository',
    'IFundFlowRepository',
    'IMarketStyleRepository',
    'IDataQualityRepository',
    'IMlModelRepository',
    'IStrategyCircuitBreakerRepository',
    'IStrategyWeightRepository',
    'ITraceabilityRepository',
    'IAgentIntelligenceRepository',
    'ISignalExecutionLogRepository',
    'ISignalExecutionRepository',
    'ISimulationRepository',
    'IAsyncKlineRepository',
    'IAsyncFactorRepository',
]
