"""共享服务访问层（框架无关）— 从 adapters/inbound/api/shared.py 解耦而来

提供统一的服务访问入口，供 Flask 与 FastAPI 两个 API 层共用。
所有 getter 函数都是普通函数，延迟加载由 adapters.shared.__init__.__getattr__ 处理。
"""


def get_service_factory():
    from infrastructure.services.service_factory import ServiceFactory
    return ServiceFactory


def get_data_service():
    return get_service_factory().get_data_service()

def get_strategy_service():
    return get_service_factory().get_strategy_code_service()

def get_stock_pool_service():
    return get_service_factory().get_stock_pool_service()

def get_scoring_service():
    return get_service_factory().get_scoring_service()

def get_stock_scoring_service():
    return get_service_factory().get_stock_scoring_service()

def get_sector_rotation_service():
    return get_service_factory().get_sector_rotation_service()

def get_pool_validation_service():
    return get_service_factory().get_pool_validation_service()

def get_technical_analysis_service():
    return get_service_factory().get_technical_analysis_service()

def get_risk_service():
    return get_service_factory().get_risk_service()

def get_data_quality_service():
    return get_service_factory().get_data_quality_service()

# ── Repository getter 函数 ──

def get_pool_repo():
    from adapters.outbound.repositories import StockPoolORMRepository
    return StockPoolORMRepository()

def get_strategy_repository():
    from adapters.outbound.repositories import StrategyORMRepository
    return StrategyORMRepository()

def get_signal_repo():
    return get_service_factory().get_signal_repository()

def get_stock_repo():
    return get_service_factory().get_stock_repository()

def get_kline_repo():
    return get_service_factory().get_kline_repository()

def get_portfolio_repo():
    return get_service_factory().get_portfolio_repository()

def get_factor_repo():
    return get_service_factory().get_factor_repository()

def get_risk_repo():
    return get_service_factory().get_risk_repository()

def get_execution_repo():
    from adapters.outbound.repositories.signal_execution_repository import SignalExecutionORMRepository
    return SignalExecutionORMRepository()

def get_backtest_repo():
    from adapters.outbound.repositories.backtest_repository import BacktestORMRepository
    return BacktestORMRepository()

def get_simulation_repo():
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    return SimulationORMRepository()

def get_factor_adapter():
    from adapters.outbound.datasources.providers.quantlib import get_factor_adapter as _get
    return _get()

# ── P1-5 新增服务 getter 函数 ──

def get_order_service():
    return get_service_factory().get_order_service()

def get_account_trading_service():
    return get_service_factory().get_account_trading_service()

def get_market_data_service():
    return get_service_factory().get_market_data_service()

def get_hk_market_data_service():
    return get_service_factory().get_hk_market_data_service()

def get_stock_data_service():
    return get_service_factory().get_stock_data_service()

def get_lhb_service():
    return get_service_factory().get_lhb_service()

def get_dividend_service():
    return get_service_factory().get_dividend_service()

def get_diagnosis_service():
    return get_service_factory().get_diagnosis_service()

def get_chan_service():
    return get_service_factory().get_chan_service()

def get_backtest_engine():
    return get_service_factory().get_backtest_engine()

def get_performance_analysis_service():
    return get_service_factory().get_performance_analysis_service()

def get_data_async_service():
    return get_service_factory().get_data_async_service()

def get_market_data_async_service():
    return get_service_factory().get_market_data_async_service()

def get_decision_service():
    return get_service_factory().get_decision_service()

def get_knowledge_service():
    return get_service_factory().get_knowledge_service()

def get_session_service():
    return get_service_factory().get_session_service()

def get_realtime_signal_service():
    return get_service_factory().get_realtime_signal_service()

def get_simulation_service():
    return get_service_factory().get_simulation_service()

def get_stock_pool_async_service():
    return get_service_factory().get_stock_pool_async_service()

def get_signal_test_log():
    return get_service_factory().get_signal_test_log()

def get_strategy_service_v2():
    return get_service_factory().get_strategy_service()

def get_strategy_execution_service():
    return get_service_factory().get_strategy_execution_service()

def get_strategy_validation_service():
    return get_service_factory().get_strategy_validation_service()

def get_strategy_optimizer():
    return get_service_factory().get_strategy_optimizer()

def get_game_alert_service():
    return get_service_factory().get_game_alert_service()


ds = get_data_service
strategy_service = get_strategy_service
stock_pool_service = get_stock_pool_service
scoring_service = get_scoring_service
stock_scoring_service = get_stock_scoring_service
sector_rotation_service = get_sector_rotation_service
pool_validation_service = get_pool_validation_service
pool_repo = get_pool_repo
strategy_repository = get_strategy_repository
factor_adapter = get_factor_adapter
decision_service = get_decision_service
simulation_service = get_simulation_service
stock_data_service = get_stock_data_service
signal_repo = get_signal_repo
stock_repo = get_stock_repo
kline_repo = get_kline_repo
portfolio_repo = get_portfolio_repo
factor_repo = get_factor_repo
risk_repo = get_risk_repo
execution_repo = get_execution_repo
backtest_repo = get_backtest_repo
simulation_repo = get_simulation_repo
