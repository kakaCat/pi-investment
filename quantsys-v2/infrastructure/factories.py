"""服务工厂函数

P2-3: 为复杂服务提供工厂函数
这些工厂函数处理需要复杂初始化逻辑的服务
"""

from typing import Any


def create_data_service():
    """创建 DataService 实例

    DataService 有11个依赖，使用工厂函数简化创建
    """
    from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
    from application.services.data_service import DataService
    from domain.ports import (
        IStockRepository,
        IKlineRepository,
        ISignalRepository,
        ISimulationRepository,
        IPortfolioRepository,
        IFactorRepository,
        IBacktestRepository,
        IRiskRepository,
        IStrategyRepository,
        ISignalExecutionRepository,
    )
    from application.services.financial_data_service_adapter import FinancialDataServiceAdapter

    # 解析所有依赖
    stock_repo = EnhancedServiceFactory.resolve(IStockRepository)
    kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
    signal_repo = EnhancedServiceFactory.resolve(ISignalRepository)
    simulation_repo = EnhancedServiceFactory.resolve(ISimulationRepository)
    portfolio_repo = EnhancedServiceFactory.resolve(IPortfolioRepository)
    factor_repo = EnhancedServiceFactory.resolve(IFactorRepository)
    backtest_repo = EnhancedServiceFactory.resolve(IBacktestRepository)
    risk_repo = EnhancedServiceFactory.resolve(IRiskRepository)
    strategy_repo = EnhancedServiceFactory.resolve(IStrategyRepository)
    execution_repo = EnhancedServiceFactory.resolve(ISignalExecutionRepository)
    financial_service = EnhancedServiceFactory.resolve(FinancialDataServiceAdapter)

    return DataService(
        stock_repo=stock_repo,
        kline_repo=kline_repo,
        signal_repo=signal_repo,
        simulation_repo=simulation_repo,
        portfolio_repo=portfolio_repo,
        factor_repo=factor_repo,
        backtest_repo=backtest_repo,
        risk_repo=risk_repo,
        strategy_repo=strategy_repo,
        execution_repo=execution_repo,
        financial_service=financial_service,
    )


def create_watch_engine():
    """创建 WatchEngine 实例

    WatchEngine 需要复杂的初始化
    """
    from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
    from application.services.watch_engine import WatchEngine
    from domain.ports import IKlineRepository
    from application.services.data_service import DataService

    kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
    data_service = EnhancedServiceFactory.resolve(DataService)

    return WatchEngine(
        kline_repo=kline_repo,
        data_service=data_service
    )


def create_signal_execution_scheduler():
    """创建 SignalExecutionScheduler 实例

    SignalExecutionScheduler 有多个依赖
    """
    from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
    from application.services.signal_execution_scheduler import SignalExecutionScheduler
    from application.services.data_service import DataService
    from application.services.strategy_code_service import StrategyCodeService
    from application.services.risk_check_service import RiskCheckService
    from domain.ports import (
        ISignalRepository,
        ISignalExecutionLogRepository,
        IStrategyRepository,
    )
    from application.services.paper_trading_engine import PaperTradingEngine

    data_service = EnhancedServiceFactory.resolve(DataService)
    strategy_service = EnhancedServiceFactory.resolve(StrategyCodeService)
    risk_service = EnhancedServiceFactory.resolve(RiskCheckService)
    signal_repo = EnhancedServiceFactory.resolve(ISignalRepository)
    log_repo = EnhancedServiceFactory.resolve(ISignalExecutionLogRepository)
    strategy_repo = EnhancedServiceFactory.resolve(IStrategyRepository)
    paper_engine = EnhancedServiceFactory.resolve(PaperTradingEngine)

    return SignalExecutionScheduler(
        data_service=data_service,
        strategy_service=strategy_service,
        risk_service=risk_service,
        signal_repo=signal_repo,
        log_repo=log_repo,
        strategy_repo=strategy_repo,
        paper_engine=paper_engine,
    )


__all__ = [
    'create_data_service',
    'create_watch_engine',
    'create_signal_execution_scheduler',
]
