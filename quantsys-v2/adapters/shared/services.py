"""共享服务访问层（框架无关）— 从 adapters/inbound/api/shared.py 解耦而来

提供统一的服务访问入口，供 Flask 与 FastAPI 两个 API 层共用。

重要：为避免循环依赖，此模块不再在顶层创建服务实例。
调用方应该直接使用 ServiceFactory 或使用下面的 getter 函数。
"""
from infrastructure.services.service_factory import ServiceFactory

# ── 向后兼容的 getter 函数（替代全局实例） ──
# 这些函数在首次调用时创建服务实例，避免模块导入时的循环依赖

def get_data_service():
    """获取 DataService 实例"""
    return ServiceFactory.get_data_service()

def get_strategy_service():
    """获取 StrategyCodeService 实例"""
    return ServiceFactory.get_strategy_code_service()

def get_stock_pool_service():
    """获取 StockPoolService 实例"""
    return ServiceFactory.get_stock_pool_service()

def get_scoring_service():
    """获取 ScoringService 实例"""
    return ServiceFactory.get_scoring_service()

def get_stock_scoring_service():
    """获取 StockScoringService 实例"""
    return ServiceFactory.get_stock_scoring_service()

def get_sector_rotation_service():
    """获取 SectorRotationService 实例"""
    return ServiceFactory.get_sector_rotation_service()

def get_pool_validation_service():
    """获取 PoolValidationService 实例"""
    return ServiceFactory.get_pool_validation_service()

def get_technical_analysis_service():
    """获取 TechnicalAnalysisService 实例"""
    return ServiceFactory.get_technical_analysis_service()

def get_risk_service():
    """获取 RiskService 实例"""
    return ServiceFactory.get_risk_service()

def get_data_quality_service():
    """获取 DataQualityService 实例"""
    return ServiceFactory.get_data_quality_service()

# ── Repository getter 函数 ──

def get_pool_repo():
    """获取 StockPoolORMRepository 实例"""
    from adapters.outbound.repositories import StockPoolORMRepository
    return StockPoolORMRepository()

def get_strategy_repository():
    """获取 StrategyORMRepository 实例"""
    from adapters.outbound.repositories import StrategyORMRepository
    return StrategyORMRepository()

def get_factor_adapter():
    """获取因子适配器实例"""
    from adapters.outbound.datasources.providers.quantlib import get_factor_adapter
    return get_factor_adapter()

# ── P1-5 新增服务 getter 函数 ──

def get_order_service():
    return ServiceFactory.get_order_service()

def get_account_trading_service():
    return ServiceFactory.get_account_trading_service()

def get_market_data_service():
    return ServiceFactory.get_market_data_service()

def get_hk_market_data_service():
    return ServiceFactory.get_hk_market_data_service()

def get_stock_data_service():
    return ServiceFactory.get_stock_data_service()

def get_lhb_service():
    return ServiceFactory.get_lhb_service()

def get_dividend_service():
    return ServiceFactory.get_dividend_service()

def get_diagnosis_service():
    return ServiceFactory.get_diagnosis_service()

def get_chan_service():
    return ServiceFactory.get_chan_service()

def get_backtest_engine():
    return ServiceFactory.get_backtest_engine()

def get_performance_analysis_service():
    return ServiceFactory.get_performance_analysis_service()

def get_data_async_service():
    return ServiceFactory.get_data_async_service()

def get_market_data_async_service():
    return ServiceFactory.get_market_data_async_service()

def get_decision_service():
    return ServiceFactory.get_decision_service()

def get_knowledge_service():
    return ServiceFactory.get_knowledge_service()

def get_session_service():
    return ServiceFactory.get_session_service()

def get_realtime_signal_service():
    return ServiceFactory.get_realtime_signal_service()

def get_simulation_service():
    return ServiceFactory.get_simulation_service()

def get_stock_pool_async_service():
    return ServiceFactory.get_stock_pool_async_service()

def get_signal_test_log():
    return ServiceFactory.get_signal_test_log()

def get_strategy_service_v2():
    return ServiceFactory.get_strategy_service()

def get_strategy_execution_service():
    return ServiceFactory.get_strategy_execution_service()

def get_strategy_validation_service():
    return ServiceFactory.get_strategy_validation_service()

def get_strategy_optimizer():
    return ServiceFactory.get_strategy_optimizer()

def get_game_alert_service():
    return ServiceFactory.get_game_alert_service()

# ── 向后兼容：保留旧的全局变量名作为属性（懒加载） ──
# 这样旧代码 `from adapters.shared.services import ds` 仍然能工作

class _LazyServiceModule:
    """延迟加载的服务模块，避免循环依赖"""

    @property
    def ServiceFactory(self):
        """导出 ServiceFactory 供外部使用"""
        from infrastructure.services.service_factory import ServiceFactory
        return ServiceFactory

    @property
    def ds(self):
        return get_data_service()

    @property
    def strategy_service(self):
        return get_strategy_service()

    @property
    def stock_pool_service(self):
        return get_stock_pool_service()

    @property
    def scoring_service(self):
        return get_scoring_service()

    @property
    def stock_scoring_service(self):
        return get_stock_scoring_service()

    @property
    def sector_rotation_service(self):
        return get_sector_rotation_service()

    @property
    def pool_validation_service(self):
        return get_pool_validation_service()

    @property
    def technical_analysis_service(self):
        return get_technical_analysis_service()

    @property
    def risk_service(self):
        return get_risk_service()

    @property
    def data_quality_service(self):
        return get_data_quality_service()

    @property
    def pool_repo(self):
        return get_pool_repo()

    @property
    def strategy_repository(self):
        return get_strategy_repository()

    @property
    def factor_adapter(self):
        return get_factor_adapter()

    # P1-5 新增
    @property
    def order_service(self):
        return get_order_service()

    @property
    def account_trading_service(self):
        return get_account_trading_service()

    @property
    def market_data_service(self):
        return get_market_data_service()

    @property
    def hk_market_data_service(self):
        return get_hk_market_data_service()

    @property
    def stock_data_service(self):
        return get_stock_data_service()

    @property
    def lhb_service(self):
        return get_lhb_service()

    @property
    def dividend_service(self):
        return get_dividend_service()

    @property
    def diagnosis_service(self):
        return get_diagnosis_service()

    @property
    def chan_service(self):
        return get_chan_service()

    @property
    def backtest_engine(self):
        return get_backtest_engine()

    @property
    def performance_analysis_service(self):
        return get_performance_analysis_service()

    @property
    def data_async_service(self):
        return get_data_async_service()

    @property
    def market_data_async_service(self):
        return get_market_data_async_service()

    @property
    def decision_service(self):
        return get_decision_service()

    @property
    def knowledge_service(self):
        return get_knowledge_service()

    @property
    def session_service(self):
        return get_session_service()

    @property
    def realtime_signal_service(self):
        return get_realtime_signal_service()

    @property
    def simulation_service(self):
        return get_simulation_service()

    @property
    def stock_pool_async_service(self):
        return get_stock_pool_async_service()

    @property
    def signal_test_log(self):
        return get_signal_test_log()

    @property
    def strategy_service_v2(self):
        return get_strategy_service_v2()

    @property
    def strategy_execution_service(self):
        return get_strategy_execution_service()

    @property
    def strategy_validation_service(self):
        return get_strategy_validation_service()

    @property
    def strategy_optimizer(self):
        return get_strategy_optimizer()

    @property
    def game_alert_service(self):
        return get_game_alert_service()

# 创建懒加载代理实例
import sys
sys.modules[__name__] = _LazyServiceModule()

# 注意：由于使用了模块替换技巧，__all__ 不再有效
# 所有属性通过 _LazyServiceModule 的 @property 动态提供
