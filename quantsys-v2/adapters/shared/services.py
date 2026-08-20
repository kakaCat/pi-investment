"""共享服务实例（框架无关）— 从 adapters/inbound/api/shared.py 解耦而来

服务单例与 repository 实例，供 Flask 与 FastAPI 两个 API 层共用。
"""
from infrastructure.services.service_factory import ServiceFactory

# ── 服务实例（使用工厂模式） ──
ds = ServiceFactory.get_data_service()
strategy_service = ServiceFactory.get_strategy_code_service()
stock_pool_service = ServiceFactory.get_stock_pool_service()
scoring_service = ServiceFactory.get_scoring_service()
stock_scoring_service = ServiceFactory.get_stock_scoring_service()
sector_rotation_service = ServiceFactory.get_sector_rotation_service()
pool_validation_service = ServiceFactory.get_pool_validation_service()
technical_analysis_service = ServiceFactory.get_technical_analysis_service()
risk_service = ServiceFactory.get_risk_service()
data_quality_service = ServiceFactory.get_data_quality_service()
# strategy_rotation_service = ServiceFactory.get_strategy_rotation_service()  # 临时注释：模块不存在

# Repository 实例
from adapters.outbound.repositories import StockPoolORMRepository, StrategyORMRepository
pool_repo = StockPoolORMRepository()
strategy_repository = StrategyORMRepository()

# 因子适配器（已迁移到 adapters/outbound/datasources/providers/quantlib，见架构审计 P0-2）
from adapters.outbound.datasources.providers.quantlib import get_factor_adapter
factor_adapter = get_factor_adapter()

# ── P1-5 新增：路由层直接导入的服务统一纳入共享导出 ──
order_service = ServiceFactory.get_order_service()
account_trading_service = ServiceFactory.get_account_trading_service()
market_data_service = ServiceFactory.get_market_data_service()
hk_market_data_service = ServiceFactory.get_hk_market_data_service()
stock_data_service = ServiceFactory.get_stock_data_service()
lhb_service = ServiceFactory.get_lhb_service()
dividend_service = ServiceFactory.get_dividend_service()
diagnosis_service = ServiceFactory.get_diagnosis_service()
chan_service = ServiceFactory.get_chan_service()
backtest_engine = ServiceFactory.get_backtest_engine()
performance_analysis_service = ServiceFactory.get_performance_analysis_service()
data_async_service = ServiceFactory.get_data_async_service()
market_data_async_service = ServiceFactory.get_market_data_async_service()
decision_service = ServiceFactory.get_decision_service()
knowledge_service = ServiceFactory.get_knowledge_service()
session_service = ServiceFactory.get_session_service()
realtime_signal_service = ServiceFactory.get_realtime_signal_service()
simulation_service = ServiceFactory.get_simulation_service()
stock_pool_async_service = ServiceFactory.get_stock_pool_async_service()
signal_test_log = ServiceFactory.get_signal_test_log()
strategy_service_v2 = ServiceFactory.get_strategy_service()
strategy_execution_service = ServiceFactory.get_strategy_execution_service()
strategy_validation_service = ServiceFactory.get_strategy_validation_service()
strategy_optimizer = ServiceFactory.get_strategy_optimizer()
game_alert_service = ServiceFactory.get_game_alert_service()
enhanced_financial_service = ServiceFactory.get_enhanced_financial_service()

__all__ = [
    'ds', 'strategy_service', 'stock_pool_service', 'pool_repo',
    'pool_validation_service', 'factor_adapter', 'scoring_service',
    'stock_scoring_service', 'sector_rotation_service', 'strategy_repository',
    'ServiceFactory', 'technical_analysis_service', 'risk_service',
    'data_quality_service',
    # P1-5 新增
    'order_service', 'account_trading_service', 'market_data_service',
    'hk_market_data_service', 'stock_data_service', 'lhb_service',
    'dividend_service', 'diagnosis_service', 'chan_service',
    'backtest_engine', 'performance_analysis_service',
    'data_async_service', 'market_data_async_service',
    'decision_service', 'knowledge_service', 'session_service',
    'realtime_signal_service', 'simulation_service',
    'stock_pool_async_service', 'signal_test_log',
    'strategy_service_v2', 'strategy_execution_service',
    'strategy_validation_service', 'strategy_optimizer',
    'game_alert_service', 'enhanced_financial_service',
]
