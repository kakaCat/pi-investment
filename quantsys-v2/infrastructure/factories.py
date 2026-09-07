"""服务工厂函数

P2-3: 为复杂服务提供工厂函数
这些工厂函数处理需要复杂初始化逻辑的服务
"""

from typing import Any


def create_signal_execution_scheduler():
    """创建 SignalExecutionScheduler 实例

    SignalExecutionScheduler 有多个依赖
    """
    from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
    from application.services.signal_execution_scheduler import SignalExecutionScheduler
    from application.services.strategy_code_service import StrategyCodeService
    from application.services.risk_check_service import RiskCheckService
    from domain.ports import (
        ISignalRepository,
        ISignalExecutionLogRepository,
        IStrategyRepository,
    )
    from application.services.paper_trading_engine import PaperTradingEngine

    strategy_service = EnhancedServiceFactory.resolve(StrategyCodeService)
    risk_service = EnhancedServiceFactory.resolve(RiskCheckService)
    signal_repo = EnhancedServiceFactory.resolve(ISignalRepository)
    log_repo = EnhancedServiceFactory.resolve(ISignalExecutionLogRepository)
    strategy_repo = EnhancedServiceFactory.resolve(IStrategyRepository)
    paper_engine = EnhancedServiceFactory.resolve(PaperTradingEngine)

    return SignalExecutionScheduler(
        strategy_service=strategy_service,
        risk_service=risk_service,
        signal_repo=signal_repo,
        log_repo=log_repo,
        strategy_repo=strategy_repo,
        paper_engine=paper_engine,
    )


__all__ = [
    'create_signal_execution_scheduler',
]
