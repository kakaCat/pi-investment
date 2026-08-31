"""
服务工厂 - 替代shared.py的全局单例模式

提供服务实例的统一获取接口，支持延迟初始化和单例模式

P2-1: 渐进式迁移到 EnhancedServiceFactory
- 优先从 EnhancedServiceFactory 获取服务
- 如果未注册则回退到旧的实现
- 保持向后兼容
"""
import logging
from typing import Optional, Type, TypeVar
from functools import lru_cache

logger = logging.getLogger(__name__)

T = TypeVar('T')

# 延迟导入以避免循环依赖
_enhanced_factory_initialized = False


def _ensure_enhanced_factory():
    """确保 EnhancedServiceFactory 已初始化"""
    global _enhanced_factory_initialized
    if not _enhanced_factory_initialized:
        try:
            from .service_registry import register_all_services
            register_all_services()
            _enhanced_factory_initialized = True
            logger.info("EnhancedServiceFactory initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize EnhancedServiceFactory: {e}")


def _try_get_from_enhanced(service_type: Type[T]) -> Optional[T]:
    """尝试从 EnhancedServiceFactory 获取服务"""
    try:
        _ensure_enhanced_factory()
        from .enhanced_service_factory import EnhancedServiceFactory
        if EnhancedServiceFactory.is_registered(service_type):
            return EnhancedServiceFactory.resolve(service_type)
    except Exception as e:
        logger.debug(f"Failed to get {service_type.__name__} from EnhancedServiceFactory: {e}")
    return None


class ServiceFactory:
    """服务工厂类

    使用单例模式管理服务实例，替代shared.py的全局变量
    """

    _instances = {}

    @classmethod
    @lru_cache(maxsize=1)
    def get_strategy_code_service(cls):
        """获取StrategyCodeService实例

        P2-3: 优先使用 EnhancedServiceFactory（配置驱动 + 依赖注入）
        """
        if 'strategy_code_service' not in cls._instances:
            try:
                from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
                from application.services.strategy_code_service import StrategyCodeService

                # 确保 EnhancedServiceFactory 已完成注册（同 get_data_service 的时序修复）
                _ensure_enhanced_factory()

                # 尝试解析已注册的实例
                if EnhancedServiceFactory.is_registered(StrategyCodeService):
                    cls._instances['strategy_code_service'] = EnhancedServiceFactory.resolve(StrategyCodeService)
                    logger.info("StrategyCodeService resolved from EnhancedServiceFactory")
                else:
                    # 2026-08-25 修复（回测 'NoneType' has no attribute 'get_by_id'）：
                    # 回退模式传入 None 导致所有依赖 strategy_repo/kline_repo 的调用全挂
                    # （回测三端点全灭）。改为直接构造具体 ORM 实现——
                    # 实例化的是实现类而非接口，不违反"不实例化接口"原则。
                    from adapters.outbound.repositories.strategy_repository import StrategyORMRepository
                    from adapters.outbound.repositories.kline_repository import KlineORMRepository
                    cls._instances['strategy_code_service'] = StrategyCodeService(
                        strategy_repo=StrategyORMRepository(),
                        kline_repo=KlineORMRepository()
                    )
                    logger.warning("StrategyCodeService initialized with concrete ORM repositories (fallback mode)")
            except Exception as e:
                logger.error(f"Failed to initialize StrategyCodeService: {e}")
                raise
        return cls._instances['strategy_code_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_stock_pool_service(cls):
        """获取StockPoolService实例"""
        # P2-1: 优先从 EnhancedServiceFactory 获取
        from application.services.stock_pool_service import StockPoolService
        enhanced = _try_get_from_enhanced(StockPoolService)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'stock_pool_service' not in cls._instances:
            from adapters.outbound.repositories import StockPoolORMRepository
            from application.services.opportunity_scoring_service import OpportunityScoringService
            from adapters.outbound.datasources.providers.quantlib import get_factor_adapter

            kline_repo = cls.get_kline_repository()
            stock_repo = cls.get_stock_repository()
            pool_repo = StockPoolORMRepository()
            factor_adapter = get_factor_adapter()
            scoring_service = OpportunityScoringService(kline_repo, stock_repo, factor_adapter)

            cls._instances['stock_pool_service'] = StockPoolService(
                stock_repo,
                pool_repo=pool_repo,
                scoring_service=scoring_service
            )
            logger.info("StockPoolService initialized (legacy)")
        return cls._instances['stock_pool_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_scoring_service(cls):
        """获取OpportunityScoringService实例"""
        # P2-1: 优先从 EnhancedServiceFactory 获取
        from application.services.opportunity_scoring_service import OpportunityScoringService
        enhanced = _try_get_from_enhanced(OpportunityScoringService)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'scoring_service' not in cls._instances:
            from adapters.outbound.datasources.providers.quantlib import get_factor_adapter
            from adapters.outbound.repositories.financial_repository import FinancialORMRepository
            from adapters.outbound.repositories.fund_flow_repository import FundFlowORMRepository

            kline_repo = cls.get_kline_repository()
            stock_repo = cls.get_stock_repository()
            factor_adapter = get_factor_adapter()
            financial_repo = FinancialORMRepository()
            fund_flow_repo = FundFlowORMRepository()
            cls._instances['scoring_service'] = OpportunityScoringService(
                kline_repo, stock_repo, factor_adapter,
                financial_repo=financial_repo,
                fund_flow_repo=fund_flow_repo,
            )
            logger.info("OpportunityScoringService initialized (legacy, with financial_repo + fund_flow_repo)")
        return cls._instances['scoring_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_stock_scoring_service(cls):
        """获取StockScoringService实例"""
        # P2-1: 优先从 EnhancedServiceFactory 获取
        from application.services.stock_scoring_service import StockScoringService
        enhanced = _try_get_from_enhanced(StockScoringService)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'stock_scoring_service' not in cls._instances:
            cls._instances['stock_scoring_service'] = StockScoringService()
            logger.info("StockScoringService initialized (legacy)")
        return cls._instances['stock_scoring_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_sector_rotation_service(cls):
        """获取SectorRotationService实例"""
        # P2-1: 优先从 EnhancedServiceFactory 获取
        from application.services.sector_rotation_service import SectorRotationService
        enhanced = _try_get_from_enhanced(SectorRotationService)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'sector_rotation_service' not in cls._instances:
            stock_repo = cls.get_stock_repository()
            kline_repo = cls.get_kline_repository()
            cls._instances['sector_rotation_service'] = SectorRotationService(
                stock_repo, kline_repo
            )
            logger.info("SectorRotationService initialized (legacy)")
        return cls._instances['sector_rotation_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_pool_validation_service(cls):
        """获取PoolValidationService实例"""
        # P2-1: 优先从 EnhancedServiceFactory 获取
        from application.services.pool_validation_service import PoolValidationService
        enhanced = _try_get_from_enhanced(PoolValidationService)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'pool_validation_service' not in cls._instances:
            from adapters.outbound.repositories import StockPoolORMRepository, StrategyORMRepository

            pool_repo = StockPoolORMRepository()
            strategy_repo = StrategyORMRepository()
            cls._instances['pool_validation_service'] = PoolValidationService(
                pool_repo=pool_repo,
                strategy_repo=strategy_repo
            )
            logger.info("PoolValidationService initialized (legacy)")
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
        """获取OrderService实例（模块级单例 new_order_service）"""
        if 'order_service' not in cls._instances:
            from application.services import new_order_service
            cls._instances['order_service'] = new_order_service
            logger.info("OrderService initialized (via new_order_service)")
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
            from adapters.outbound.repositories.agent_intelligence_repository import \
                AgentIntelligenceORMRepository
            cls._instances['decision_service'] = DecisionService(
                decision_repo=AgentIntelligenceORMRepository())
            logger.info("DecisionService initialized")
        return cls._instances['decision_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_knowledge_service(cls):
        """获取KnowledgeService实例"""
        if 'knowledge_service' not in cls._instances:
            from application.services.knowledge_service import KnowledgeService
            from adapters.outbound.repositories.agent_knowledge_repository import AgentKnowledgeORMRepository
            repository = AgentKnowledgeORMRepository()
            cls._instances['knowledge_service'] = KnowledgeService(repository=repository)
            logger.info("KnowledgeService initialized with AgentKnowledgeORMRepository")
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
            from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
            repo = SimulationORMRepository()
            cls._instances['simulation_service'] = SimulationService(repo=repo)
            logger.info("SimulationService initialized with SimulationORMRepository")
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
            from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
            repo = SimulationORMRepository()
            cls._instances['strategy_service'] = StrategyService(repo=repo)
            logger.info("StrategyService initialized with SimulationORMRepository")
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
            strategy_service = cls.get_strategy_code_service()
            cls._instances['strategy_optimizer'] = StrategyOptimizer(strategy_service)
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

    # ── P1-2 Phase 2: 数据源接口抽象 (2026-08-21) ──

    @classmethod
    @lru_cache(maxsize=1)
    def get_ml_model_repository(cls):
        """获取ML模型仓库实例

        Returns:
            IMLModelRepository: ML模型仓库接口实现
        """
        # P2-1: 优先从 EnhancedServiceFactory 获取
        from domain.ports.ml_model_port import IMLModelRepository
        enhanced = _try_get_from_enhanced(IMLModelRepository)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'ml_model_repository' not in cls._instances:
            from adapters.outbound.ml.ml_model_repository import MLModelFileRepository
            cls._instances['ml_model_repository'] = MLModelFileRepository()
            logger.info("MLModelFileRepository initialized (legacy)")
        return cls._instances['ml_model_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_ml_model_metadata_repository(cls):
        """获取ML模型元数据仓库实例

        Returns:
            IMLModelMetadataRepository: ML模型元数据仓库接口实现
        """
        # P2-1: 优先从 EnhancedServiceFactory 获取
        from domain.ports.ml_model_port import IMLModelMetadataRepository
        enhanced = _try_get_from_enhanced(IMLModelMetadataRepository)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'ml_model_metadata_repository' not in cls._instances:
            from adapters.outbound.ml.ml_model_repository import MLModelMetadataDBRepository
            cls._instances['ml_model_metadata_repository'] = MLModelMetadataDBRepository()
            logger.info("MLModelMetadataDBRepository initialized (legacy)")
        return cls._instances['ml_model_metadata_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_data_provider_manager(cls):
        """获取数据提供者管理器实例

        Returns:
            IDataProviderManager: 数据提供者管理器接口实现
        """
        # P2-1: 优先从 EnhancedServiceFactory 获取
        from domain.ports.datasource_ports import IDataProviderManager
        enhanced = _try_get_from_enhanced(IDataProviderManager)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'data_provider_manager' not in cls._instances:
            from adapters.outbound.datasources.manager import DataProviderManager
            cls._instances['data_provider_manager'] = DataProviderManager()
            logger.info("DataProviderManager initialized (legacy)")
        return cls._instances['data_provider_manager']

    @classmethod
    @lru_cache(maxsize=1)
    def get_data_quality_monitor(cls):
        """获取数据质量监控器实例 (已废弃)

        P0 Fix: IDataQualityMonitor 未被实际使用，此方法保留仅为向后兼容

        Returns:
            None: 该功能已移除
        """
        logger.warning("get_data_quality_monitor() is deprecated and returns None")
        return None

    # ── P2-1: Repository 工厂方法 (2026-08-21) ──

    @classmethod
    @lru_cache(maxsize=1)
    def get_stock_repository(cls):
        """获取Stock Repository实例

        Returns:
            IStockRepository: Stock仓库接口实现
        """
        from domain.ports.repository_ports_extended import IStockRepository
        enhanced = _try_get_from_enhanced(IStockRepository)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'stock_repository' not in cls._instances:
            from adapters.outbound.repositories.stock_repository import StockORMRepository
            cls._instances['stock_repository'] = StockORMRepository()
            logger.info("StockORMRepository initialized (legacy)")
        return cls._instances['stock_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_stock_pool_repository(cls):
        """获取StockPool Repository实例

        Returns:
            IStockPoolRepository: StockPool仓库接口实现
        """
        from domain.ports.repository_ports_extended import IStockPoolRepository
        enhanced = _try_get_from_enhanced(IStockPoolRepository)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'stock_pool_repository' not in cls._instances:
            from adapters.outbound.repositories.stock_pool_repository import StockPoolORMRepository
            cls._instances['stock_pool_repository'] = StockPoolORMRepository()
            logger.info("StockPoolORMRepository initialized (legacy)")
        return cls._instances['stock_pool_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_strategy_repository(cls):
        """获取Strategy Repository实例

        Returns:
            IStrategyRepository: Strategy仓库接口实现
        """
        from domain.ports.repository_ports_extended import IStrategyRepository
        enhanced = _try_get_from_enhanced(IStrategyRepository)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'strategy_repository' not in cls._instances:
            from adapters.outbound.repositories.strategy_repository import StrategyORMRepository
            cls._instances['strategy_repository'] = StrategyORMRepository()
            logger.info("StrategyORMRepository initialized (legacy)")
        return cls._instances['strategy_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_kline_repository(cls):
        """获取Kline Repository实例

        Returns:
            IKlineRepository: Kline仓库接口实现
        """
        from domain.ports.repository_ports_extended import IKlineRepository
        enhanced = _try_get_from_enhanced(IKlineRepository)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'kline_repository' not in cls._instances:
            from adapters.outbound.repositories.kline_repository import KlineORMRepository
            cls._instances['kline_repository'] = KlineORMRepository()
            logger.info("KlineORMRepository initialized (legacy)")
        return cls._instances['kline_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_signal_repository(cls):
        """获取Signal Repository实例

        Returns:
            ISignalRepository: Signal仓库接口实现
        """
        from domain.ports.repository_ports_extended import ISignalRepository
        enhanced = _try_get_from_enhanced(ISignalRepository)
        if enhanced:
            return enhanced

        # 回退到旧实现
        if 'signal_repository' not in cls._instances:
            from adapters.outbound.repositories.signal_repository import SignalORMRepository
            cls._instances['signal_repository'] = SignalORMRepository()
            logger.info("SignalORMRepository initialized (legacy)")
        return cls._instances['signal_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_portfolio_repository(cls):
        from domain.ports.repository_ports import IPortfolioRepository
        enhanced = _try_get_from_enhanced(IPortfolioRepository)
        if enhanced:
            return enhanced
        if 'portfolio_repository' not in cls._instances:
            from adapters.outbound.repositories.portfolio_repository import PortfolioORMRepository
            cls._instances['portfolio_repository'] = PortfolioORMRepository()
            logger.info("PortfolioORMRepository initialized (legacy)")
        return cls._instances['portfolio_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_risk_repository(cls):
        from domain.ports.repository_ports import IRiskRepository
        enhanced = _try_get_from_enhanced(IRiskRepository)
        if enhanced:
            return enhanced
        if 'risk_repository' not in cls._instances:
            from adapters.outbound.repositories.risk_repository import RiskORMRepository
            cls._instances['risk_repository'] = RiskORMRepository()
            logger.info("RiskORMRepository initialized (legacy)")
        return cls._instances['risk_repository']

    @classmethod
    @lru_cache(maxsize=1)
    def get_factor_repository(cls):
        from domain.ports.repository_ports import IFactorRepository
        enhanced = _try_get_from_enhanced(IFactorRepository)
        if enhanced:
            return enhanced
        if 'factor_repository' not in cls._instances:
            from adapters.outbound.repositories.factor_repository import FactorORMRepository
            cls._instances['factor_repository'] = FactorORMRepository()
            logger.info("FactorORMRepository initialized (legacy)")
        return cls._instances['factor_repository']

    @classmethod
    def reset_all(cls):
        """重置所有服务实例（用于测试）"""
        cls._instances.clear()
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
        # P1-2 Phase 2
        cls.get_ml_model_repository.cache_clear()
        cls.get_ml_model_metadata_repository.cache_clear()
        cls.get_data_provider_manager.cache_clear()
        cls.get_data_quality_monitor.cache_clear()
        # P2-1 Repository
        cls.get_stock_repository.cache_clear()
        cls.get_stock_pool_repository.cache_clear()
        cls.get_strategy_repository.cache_clear()
        cls.get_kline_repository.cache_clear()
        cls.get_signal_repository.cache_clear()

        # P2-1: 重置 EnhancedServiceFactory
        try:
            from .enhanced_service_factory import EnhancedServiceFactory
            EnhancedServiceFactory.reset()
        except Exception as e:
            logger.warning(f"Failed to reset EnhancedServiceFactory: {e}")

        # 重置初始化标志
        global _enhanced_factory_initialized
        _enhanced_factory_initialized = False

        logger.info("All services reset")


# 提供兼容旧代码的全局访问方式
def get_strategy_service():
    """获取StrategyCodeService实例（兼容接口）"""
    return ServiceFactory.get_strategy_code_service()


def get_stock_pool_service():
    """获取StockPoolService实例（兼容接口）"""
    return ServiceFactory.get_stock_pool_service()


# 导出所有服务获取函数
__all__ = [
    'ServiceFactory',
    'get_strategy_service',
    'get_stock_pool_service',
]
