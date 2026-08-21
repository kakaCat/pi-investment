"""
服务工厂 - 替代shared.py的全局单例模式

提供服务实例的统一获取接口，支持延迟初始化和单例模式
"""
import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class ServiceFactory:
    """服务工厂类

    使用单例模式管理服务实例，替代shared.py的全局变量
    """

    _instances = {}

    @classmethod
    @lru_cache(maxsize=1)
    def get_data_service(cls):
        """获取DataService实例"""
        if 'data_service' not in cls._instances:
            from application.services.data_service import DataService
            cls._instances['data_service'] = DataService()
            logger.info("DataService initialized")
        return cls._instances['data_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_strategy_code_service(cls):
        """获取StrategyCodeService实例"""
        if 'strategy_code_service' not in cls._instances:
            from application.services.strategy_code_service import StrategyCodeService
            cls._instances['strategy_code_service'] = StrategyCodeService()
            logger.info("StrategyCodeService initialized")
        return cls._instances['strategy_code_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_stock_pool_service(cls):
        """获取StockPoolService实例"""
        if 'stock_pool_service' not in cls._instances:
            from application.services.stock_pool_service import StockPoolService
            from adapters.outbound.repositories import StockPoolORMRepository
            from application.services.opportunity_scoring_service import OpportunityScoringService
            from adapters.outbound.datasources.providers.quantlib import get_factor_adapter

            ds = cls.get_data_service()
            pool_repo = StockPoolORMRepository()
            factor_adapter = get_factor_adapter()
            scoring_service = OpportunityScoringService(ds.kline, ds.stock, factor_adapter)

            cls._instances['stock_pool_service'] = StockPoolService(
                ds.stock,
                pool_repo=pool_repo,
                scoring_service=scoring_service
            )
            logger.info("StockPoolService initialized")
        return cls._instances['stock_pool_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_scoring_service(cls):
        """获取OpportunityScoringService实例"""
        if 'scoring_service' not in cls._instances:
            from application.services.opportunity_scoring_service import OpportunityScoringService
            from adapters.outbound.datasources.providers.quantlib import get_factor_adapter

            ds = cls.get_data_service()
            factor_adapter = get_factor_adapter()
            cls._instances['scoring_service'] = OpportunityScoringService(
                ds.kline, ds.stock, factor_adapter
            )
            logger.info("OpportunityScoringService initialized")
        return cls._instances['scoring_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_stock_scoring_service(cls):
        """获取StockScoringService实例"""
        if 'stock_scoring_service' not in cls._instances:
            from application.services.stock_scoring_service import StockScoringService
            ds = cls.get_data_service()
            cls._instances['stock_scoring_service'] = StockScoringService(ds)
            logger.info("StockScoringService initialized")
        return cls._instances['stock_scoring_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_sector_rotation_service(cls):
        """获取SectorRotationService实例"""
        if 'sector_rotation_service' not in cls._instances:
            from application.services.sector_rotation_service import SectorRotationService
            ds = cls.get_data_service()
            cls._instances['sector_rotation_service'] = SectorRotationService(
                ds.stock, ds.kline
            )
            logger.info("SectorRotationService initialized")
        return cls._instances['sector_rotation_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_pool_validation_service(cls):
        """获取PoolValidationService实例"""
        if 'pool_validation_service' not in cls._instances:
            from application.services.pool_validation_service import PoolValidationService
            from adapters.outbound.repositories import StockPoolORMRepository, StrategyORMRepository

            pool_repo = StockPoolORMRepository()
            strategy_repo = StrategyORMRepository()
            cls._instances['pool_validation_service'] = PoolValidationService(
                pool_repo=pool_repo,
                strategy_repo=strategy_repo
            )
            logger.info("PoolValidationService initialized")
        return cls._instances['pool_validation_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_scheduler_config_service(cls):
        """获取SchedulerConfigService实例"""
        if 'scheduler_config_service' not in cls._instances:
            from application.services.scheduler_config_service import SchedulerConfigService
            cls._instances['scheduler_config_service'] = SchedulerConfigService()
            logger.info("SchedulerConfigService initialized")
        return cls._instances['scheduler_config_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_condition_monitor_service(cls):
        """获取ConditionMonitorService实例"""
        if 'condition_monitor_service' not in cls._instances:
            from application.services.condition_monitor import ConditionMonitorService
            cls._instances['condition_monitor_service'] = ConditionMonitorService()
            logger.info("ConditionMonitorService initialized")
        return cls._instances['condition_monitor_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_technical_analysis_service(cls):
        """获取TechnicalAnalysisService实例"""
        if 'technical_analysis_service' not in cls._instances:
            from application.services.technical_analysis_service import TechnicalAnalysisService
            cls._instances['technical_analysis_service'] = TechnicalAnalysisService()
            logger.info("TechnicalAnalysisService initialized")
        return cls._instances['technical_analysis_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_risk_service(cls):
        """获取RiskService实例"""
        if 'risk_service' not in cls._instances:
            from application.services.risk_service import RiskService
            cls._instances['risk_service'] = RiskService()
            logger.info("RiskService initialized")
        return cls._instances['risk_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_data_quality_service(cls):
        """获取DataQualityService实例"""
        if 'data_quality_service' not in cls._instances:
            from application.services.data_quality_service import DataQualityService
            cls._instances['data_quality_service'] = DataQualityService()
            logger.info("DataQualityService initialized")
        return cls._instances['data_quality_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_strategy_rotation_service(cls):
        """获取StrategyRotationService实例"""
        if 'strategy_rotation_service' not in cls._instances:
            from application.services.strategy_rotation_service import StrategyRotationService
            cls._instances['strategy_rotation_service'] = StrategyRotationService()
            logger.info("StrategyRotationService initialized")
        return cls._instances['strategy_rotation_service']

    # ── 以下为 P1-5 新增：路由层直接导入的服务统一纳入工厂 ──

    @classmethod
    @lru_cache(maxsize=1)
    def get_order_service(cls):
        """获取OrderService实例（模块级单例 order_service）"""
        if 'order_service' not in cls._instances:
            from application.services import order_service
            cls._instances['order_service'] = order_service
            logger.info("OrderService initialized")
        return cls._instances['order_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_account_trading_service(cls):
        """获取AccountTradingService实例"""
        if 'account_trading_service' not in cls._instances:
            from application.services.account_trading_service import account_trading_service
            cls._instances['account_trading_service'] = account_trading_service
            logger.info("AccountTradingService initialized")
        return cls._instances['account_trading_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_market_data_service(cls):
        """获取MarketDataService实例（模块级单例 market_data_service）"""
        if 'market_data_service' not in cls._instances:
            from application.services.market_data_service import market_data_service
            cls._instances['market_data_service'] = market_data_service
            logger.info("MarketDataService initialized")
        return cls._instances['market_data_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_hk_market_data_service(cls):
        """获取HKMarketDataService实例（模块级单例 hk_market_data_service）"""
        if 'hk_market_data_service' not in cls._instances:
            from application.services.hk_market_data_service import hk_market_data_service
            cls._instances['hk_market_data_service'] = hk_market_data_service
            logger.info("HKMarketDataService initialized")
        return cls._instances['hk_market_data_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_stock_data_service(cls):
        """获取StockDataService实例（模块级单例 stock_data_service）"""
        if 'stock_data_service' not in cls._instances:
            from application.services.stock_data_service import stock_data_service
            cls._instances['stock_data_service'] = stock_data_service
            logger.info("StockDataService initialized")
        return cls._instances['stock_data_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_lhb_service(cls):
        """获取LhbService实例"""
        if 'lhb_service' not in cls._instances:
            from application.services.lhb_service import LhbService
            cls._instances['lhb_service'] = LhbService()
            logger.info("LhbService initialized")
        return cls._instances['lhb_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_dividend_service(cls):
        """获取DividendService实例"""
        if 'dividend_service' not in cls._instances:
            from application.services.dividend_service import DividendService
            cls._instances['dividend_service'] = DividendService()
            logger.info("DividendService initialized")
        return cls._instances['dividend_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_diagnosis_service(cls):
        """获取DiagnosisService实例"""
        if 'diagnosis_service' not in cls._instances:
            from application.services.diagnosis_service import DiagnosisService
            cls._instances['diagnosis_service'] = DiagnosisService()
            logger.info("DiagnosisService initialized")
        return cls._instances['diagnosis_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_chan_service(cls):
        """获取ChanService实例"""
        if 'chan_service' not in cls._instances:
            from application.services.chan_service import ChanService
            cls._instances['chan_service'] = ChanService()
            logger.info("ChanService initialized")
        return cls._instances['chan_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_backtest_engine(cls):
        """获取BacktestAsyncEngine实例"""
        if 'backtest_engine' not in cls._instances:
            from application.services.backtest_async_engine import BacktestAsyncEngine
            cls._instances['backtest_engine'] = BacktestAsyncEngine()
            logger.info("BacktestAsyncEngine initialized")
        return cls._instances['backtest_engine']

    @classmethod
    @lru_cache(maxsize=1)
    def get_performance_analysis_service(cls):
        """获取PerformanceAnalysisAsyncService实例"""
        if 'performance_analysis_service' not in cls._instances:
            from application.services.core_async_services import PerformanceAnalysisAsyncService
            cls._instances['performance_analysis_service'] = PerformanceAnalysisAsyncService()
            logger.info("PerformanceAnalysisAsyncService initialized")
        return cls._instances['performance_analysis_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_data_async_service(cls):
        """获取DataAsyncService实例"""
        if 'data_async_service' not in cls._instances:
            from application.services.core_async_services import DataAsyncService
            cls._instances['data_async_service'] = DataAsyncService()
            logger.info("DataAsyncService initialized")
        return cls._instances['data_async_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_market_data_async_service(cls):
        """获取MarketDataAsyncService实例"""
        if 'market_data_async_service' not in cls._instances:
            from application.services.core_async_services import MarketDataAsyncService
            cls._instances['market_data_async_service'] = MarketDataAsyncService()
            logger.info("MarketDataAsyncService initialized")
        return cls._instances['market_data_async_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_decision_service(cls):
        """获取DecisionService实例"""
        if 'decision_service' not in cls._instances:
            from application.services.decision_service import DecisionService
            cls._instances['decision_service'] = DecisionService()
            logger.info("DecisionService initialized")
        return cls._instances['decision_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_knowledge_service(cls):
        """获取KnowledgeService实例"""
        if 'knowledge_service' not in cls._instances:
            from application.services.knowledge_service import KnowledgeService
            cls._instances['knowledge_service'] = KnowledgeService()
            logger.info("KnowledgeService initialized")
        return cls._instances['knowledge_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_session_service(cls):
        """获取SessionService实例"""
        if 'session_service' not in cls._instances:
            from application.services.session_service import SessionService
            cls._instances['session_service'] = SessionService()
            logger.info("SessionService initialized")
        return cls._instances['session_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_realtime_signal_service(cls):
        """获取RealtimeSignalService实例"""
        if 'realtime_signal_service' not in cls._instances:
            from application.services.realtime_signal_service import RealtimeSignalService
            cls._instances['realtime_signal_service'] = RealtimeSignalService()
            logger.info("RealtimeSignalService initialized")
        return cls._instances['realtime_signal_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_simulation_service(cls):
        """获取SimulationService实例"""
        if 'simulation_service' not in cls._instances:
            from application.services.simulation_service import SimulationService
            cls._instances['simulation_service'] = SimulationService()
            logger.info("SimulationService initialized")
        return cls._instances['simulation_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_stock_pool_async_service(cls):
        """获取StockPoolAsyncService实例"""
        if 'stock_pool_async_service' not in cls._instances:
            from application.services.stock_pool_async_service import StockPoolAsyncService
            cls._instances['stock_pool_async_service'] = StockPoolAsyncService()
            logger.info("StockPoolAsyncService initialized")
        return cls._instances['stock_pool_async_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_signal_test_log(cls):
        """获取SignalTestLog实例"""
        if 'signal_test_log' not in cls._instances:
            from application.services.signal_test_log import SignalTestLog
            cls._instances['signal_test_log'] = SignalTestLog()
            logger.info("SignalTestLog initialized")
        return cls._instances['signal_test_log']

    @classmethod
    @lru_cache(maxsize=1)
    def get_strategy_service(cls):
        """获取StrategyService实例"""
        if 'strategy_service' not in cls._instances:
            from application.services.strategy_service import StrategyService
            cls._instances['strategy_service'] = StrategyService()
            logger.info("StrategyService initialized")
        return cls._instances['strategy_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_strategy_execution_service(cls):
        """获取StrategyExecutionService实例"""
        if 'strategy_execution_service' not in cls._instances:
            from application.services.strategy_execution_service import StrategyExecutionService
            cls._instances['strategy_execution_service'] = StrategyExecutionService()
            logger.info("StrategyExecutionService initialized")
        return cls._instances['strategy_execution_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_strategy_validation_service(cls):
        """获取StrategyValidationService实例"""
        if 'strategy_validation_service' not in cls._instances:
            from application.services.strategy_validation_service import StrategyValidationService
            cls._instances['strategy_validation_service'] = StrategyValidationService()
            logger.info("StrategyValidationService initialized")
        return cls._instances['strategy_validation_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_strategy_optimizer(cls):
        """获取StrategyOptimizer实例"""
        if 'strategy_optimizer' not in cls._instances:
            from application.services.strategy_optimizer import StrategyOptimizer
            cls._instances['strategy_optimizer'] = StrategyOptimizer()
            logger.info("StrategyOptimizer initialized")
        return cls._instances['strategy_optimizer']

    @classmethod
    @lru_cache(maxsize=1)
    def get_game_alert_service(cls):
        """获取GameAlertService实例"""
        if 'game_alert_service' not in cls._instances:
            from application.services.game_alert_service import GameAlertService
            cls._instances['game_alert_service'] = GameAlertService()
            logger.info("GameAlertService initialized")
        return cls._instances['game_alert_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_enhanced_financial_service(cls):
        """获取EnhancedFinancialDataService实例"""
        if 'enhanced_financial_service' not in cls._instances:
            from application.services.enhanced_financial_data_service import get_enhanced_financial_service
            cls._instances['enhanced_financial_service'] = get_enhanced_financial_service()
            logger.info("EnhancedFinancialDataService initialized")
        return cls._instances['enhanced_financial_service']

    # ── P1-2 Phase 2: 数据源接口抽象 (2026-08-21) ──

    @classmethod
    @lru_cache(maxsize=1)
    def get_ml_model_repository(cls):
        """获取ML模型仓库实例

        Returns:
            IMLModelRepository: ML模型仓库接口实现
        """
        if 'ml_model_repository' not in cls._instances:
            from adapters.outbound.ml.ml_model_repository import MLModelFileRepository
            cls._instances['ml_model_repository'] = MLModelFileRepository()
            logger.info("MLModelFileRepository initialized")
        return cls._instances['ml_model_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_ml_model_metadata_repository(cls):
        """获取ML模型元数据仓库实例

        Returns:
            IMLModelMetadataRepository: ML模型元数据仓库接口实现
        """
        if 'ml_model_metadata_repository' not in cls._instances:
            from adapters.outbound.ml.ml_model_repository import MLModelMetadataDBRepository
            cls._instances['ml_model_metadata_repository'] = MLModelMetadataDBRepository()
            logger.info("MLModelMetadataDBRepository initialized")
        return cls._instances['ml_model_metadata_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_data_provider_manager(cls):
        """获取数据提供者管理器实例

        Returns:
            IDataProviderManager: 数据提供者管理器接口实现
        """
        if 'data_provider_manager' not in cls._instances:
            from adapters.outbound.datasources.data_provider_adapter import DataProviderAdapter
            # 传入 DataService 以支持 DatabaseKlineProvider
            ds = cls.get_data_service()
            cls._instances['data_provider_manager'] = DataProviderAdapter(ds)
            logger.info("DataProviderAdapter initialized")
        return cls._instances['data_provider_manager']

    @classmethod
    @lru_cache(maxsize=1)
    def get_data_quality_monitor(cls):
        """获取数据质量监控器实例

        Returns:
            IDataQualityMonitor: 数据质量监控接口实现
        """
        if 'data_quality_monitor' not in cls._instances:
            from adapters.outbound.datasources.data_provider_adapter import SimpleDataQualityMonitor
            cls._instances['data_quality_monitor'] = SimpleDataQualityMonitor()
            logger.info("SimpleDataQualityMonitor initialized")
        return cls._instances['data_quality_monitor']

    @classmethod
    def reset_all(cls):
        """重置所有服务实例（用于测试）"""
        cls._instances.clear()
        cls.get_data_service.cache_clear()
        cls.get_strategy_code_service.cache_clear()
        cls.get_stock_pool_service.cache_clear()
        cls.get_scoring_service.cache_clear()
        cls.get_stock_scoring_service.cache_clear()
        cls.get_sector_rotation_service.cache_clear()
        cls.get_pool_validation_service.cache_clear()
        cls.get_scheduler_config_service.cache_clear()
        cls.get_condition_monitor_service.cache_clear()
        cls.get_technical_analysis_service.cache_clear()
        cls.get_risk_service.cache_clear()
        cls.get_data_quality_service.cache_clear()
        cls.get_strategy_rotation_service.cache_clear()
        # P1-5 新增
        cls.get_order_service.cache_clear()
        cls.get_account_trading_service.cache_clear()
        cls.get_market_data_service.cache_clear()
        cls.get_hk_market_data_service.cache_clear()
        cls.get_stock_data_service.cache_clear()
        cls.get_lhb_service.cache_clear()
        cls.get_dividend_service.cache_clear()
        cls.get_diagnosis_service.cache_clear()
        cls.get_chan_service.cache_clear()
        cls.get_backtest_engine.cache_clear()
        cls.get_performance_analysis_service.cache_clear()
        cls.get_data_async_service.cache_clear()
        cls.get_market_data_async_service.cache_clear()
        cls.get_decision_service.cache_clear()
        cls.get_knowledge_service.cache_clear()
        cls.get_session_service.cache_clear()
        cls.get_realtime_signal_service.cache_clear()
        cls.get_simulation_service.cache_clear()
        cls.get_stock_pool_async_service.cache_clear()
        cls.get_signal_test_log.cache_clear()
        cls.get_strategy_service.cache_clear()
        cls.get_strategy_execution_service.cache_clear()
        cls.get_strategy_validation_service.cache_clear()
        cls.get_strategy_optimizer.cache_clear()
        cls.get_game_alert_service.cache_clear()
        cls.get_enhanced_financial_service.cache_clear()
        # P1-2 Phase 2
        cls.get_ml_model_repository.cache_clear()
        cls.get_ml_model_metadata_repository.cache_clear()
        cls.get_data_provider_manager.cache_clear()
        cls.get_data_quality_monitor.cache_clear()
        logger.info("All services reset")


# 提供兼容旧代码的全局访问方式
def get_data_service():
    """获取DataService实例（兼容接口）"""
    return ServiceFactory.get_data_service()


def get_strategy_service():
    """获取StrategyCodeService实例（兼容接口）"""
    return ServiceFactory.get_strategy_code_service()


def get_stock_pool_service():
    """获取StockPoolService实例（兼容接口）"""
    return ServiceFactory.get_stock_pool_service()


# 导出所有服务获取函数
__all__ = [
    'ServiceFactory',
    'get_data_service',
    'get_strategy_service',
    'get_stock_pool_service',
]
