"""
服务注册表 - 集中管理所有服务的依赖注入配置

P2-1 Phase 1: 将现有 ServiceFactory 的服务逐步迁移到 EnhancedServiceFactory
"""
import logging
from .enhanced_service_factory import EnhancedServiceFactory, ServiceLifecycle

logger = logging.getLogger(__name__)


def register_all_services():
    """注册所有服务到 EnhancedServiceFactory

    迁移策略：
    1. 优先迁移 Repository 层（已有 Port 接口）
    2. 然后迁移 Application Services（从问题最多的开始）
    3. 保持与旧 ServiceFactory 的兼容性
    """

    # ========== Repository 层 (Domain Ports) ==========

    # Stock Repository
    from domain.ports.stock_repository_port import IStockRepository
    from adapters.outbound.repositories.stock_repository import StockORMRepository
    EnhancedServiceFactory.register(
        IStockRepository,
        StockORMRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # Stock Pool Repository
    from domain.ports.stock_pool_repository_port import IStockPoolRepository
    from adapters.outbound.repositories.stock_pool_repository import StockPoolORMRepository
    EnhancedServiceFactory.register(
        IStockPoolRepository,
        StockPoolORMRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # Strategy Repository
    from domain.ports.strategy_repository_port import IStrategyRepository
    from adapters.outbound.repositories.strategy_repository import StrategyORMRepository
    EnhancedServiceFactory.register(
        IStrategyRepository,
        StrategyORMRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # Kline Repository
    from domain.ports.kline_repository_port import IKlineRepository
    from adapters.outbound.repositories.kline_repository import KlineORMRepository
    EnhancedServiceFactory.register(
        IKlineRepository,
        KlineORMRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # Signal Repository
    from domain.ports.signal_repository_port import ISignalRepository
    from adapters.outbound.repositories.signal_repository import SignalORMRepository
    EnhancedServiceFactory.register(
        ISignalRepository,
        SignalORMRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # 扩展的 Repository（来自 repository_ports_extended）
    from domain.ports.repository_ports_extended import (
        ISimulationRepository,
        IPortfolioRepository,
        IFactorRepository,
        IBacktestRepository,
        IRiskRepository,
        ISignalExecutionRepository,
    )

    # 注意：这些 Repository 的实现类可能还在使用旧的直接导入方式
    # 这里先注册为简单的类实例化，后续可以优化
    EnhancedServiceFactory.register(
        ISimulationRepository,
        ISimulationRepository,  # 直接使用接口类（它可能同时是实现）
        lifecycle=ServiceLifecycle.SINGLETON
    )

    EnhancedServiceFactory.register(
        IPortfolioRepository,
        IPortfolioRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    EnhancedServiceFactory.register(
        IFactorRepository,
        IFactorRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    EnhancedServiceFactory.register(
        IBacktestRepository,
        IBacktestRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    EnhancedServiceFactory.register(
        IRiskRepository,
        IRiskRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    EnhancedServiceFactory.register(
        ISignalExecutionRepository,
        ISignalExecutionRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # ML Model Repository (P1-2 Phase 2)
    from domain.ports.ml_model_port import IMLModelRepository, IMLModelMetadataRepository
    from adapters.outbound.ml.ml_model_repository import MLModelFileRepository, MLModelMetadataDBRepository
    EnhancedServiceFactory.register(
        IMLModelRepository,
        MLModelFileRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )
    EnhancedServiceFactory.register(
        IMLModelMetadataRepository,
        MLModelMetadataDBRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # Data Provider Manager (P1-2 Phase 2)
    from domain.ports.data_provider_port import IDataProviderManager, IDataQualityMonitor
    from adapters.outbound.datasources.data_provider_adapter import DataProviderAdapter, SimpleDataQualityMonitor

    # DataProviderAdapter 需要 DataService，使用工厂函数延迟初始化
    def create_data_provider_adapter():
        from infrastructure.services.service_factory import ServiceFactory
        ds = ServiceFactory.get_data_service()
        return DataProviderAdapter(ds)

    EnhancedServiceFactory.register(
        IDataProviderManager,
        factory=create_data_provider_adapter,
        lifecycle=ServiceLifecycle.SINGLETON
    )
    EnhancedServiceFactory.register(
        IDataQualityMonitor,
        SimpleDataQualityMonitor,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # ========== Application Services ==========

    # DataService - 核心服务，很多服务依赖它
    from application.services.data_service import DataService
    from application.services.financial_data_service import FinancialDataService

    def create_data_service():
        """创建 DataService，使用依赖注入

        P2-1: 所有 Repository 依赖都通过 EnhancedServiceFactory 解析
        """
        # 从 EnhancedServiceFactory 解析所有 Repository 依赖
        from domain.ports.repository_ports_extended import (
            ISimulationRepository,
            IPortfolioRepository,
            IFactorRepository,
            IBacktestRepository,
            IRiskRepository,
            ISignalExecutionRepository,
        )

        return DataService(
            stock_repo=EnhancedServiceFactory.resolve(IStockRepository),
            kline_repo=EnhancedServiceFactory.resolve(IKlineRepository),
            signal_repo=EnhancedServiceFactory.resolve(ISignalRepository),
            simulation_repo=EnhancedServiceFactory.resolve(ISimulationRepository),
            portfolio_repo=EnhancedServiceFactory.resolve(IPortfolioRepository),
            factor_repo=EnhancedServiceFactory.resolve(IFactorRepository),
            backtest_repo=EnhancedServiceFactory.resolve(IBacktestRepository),
            risk_repo=EnhancedServiceFactory.resolve(IRiskRepository),
            strategy_repo=EnhancedServiceFactory.resolve(IStrategyRepository),
            execution_repo=EnhancedServiceFactory.resolve(ISignalExecutionRepository),
            financial_service=FinancialDataService(),
        )

    EnhancedServiceFactory.register(
        DataService,
        factory=create_data_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # OpportunityScoringService - 依赖 DataService 和 FactorAdapter
    from application.services.opportunity_scoring_service import OpportunityScoringService
    def create_scoring_service():
        from infrastructure.services.service_factory import ServiceFactory
        from adapters.outbound.datasources.providers.quantlib import get_factor_adapter
        ds = ServiceFactory.get_data_service()
        factor_adapter = get_factor_adapter()
        return OpportunityScoringService(ds.kline, ds.stock, factor_adapter)

    EnhancedServiceFactory.register(
        OpportunityScoringService,
        factory=create_scoring_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # StockPoolService - 依赖多个服务
    from application.services.stock_pool_service import StockPoolService
    def create_stock_pool_service():
        from infrastructure.services.service_factory import ServiceFactory
        ds = ServiceFactory.get_data_service()
        pool_repo = EnhancedServiceFactory.resolve(IStockPoolRepository)
        scoring_service = EnhancedServiceFactory.resolve(OpportunityScoringService)
        return StockPoolService(ds.stock, pool_repo=pool_repo, scoring_service=scoring_service)

    EnhancedServiceFactory.register(
        StockPoolService,
        factory=create_stock_pool_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # PoolValidationService - 依赖 Repository
    from application.services.pool_validation_service import PoolValidationService
    def create_pool_validation_service():
        pool_repo = EnhancedServiceFactory.resolve(IStockPoolRepository)
        strategy_repo = EnhancedServiceFactory.resolve(IStrategyRepository)
        return PoolValidationService(pool_repo=pool_repo, strategy_repo=strategy_repo)

    EnhancedServiceFactory.register(
        PoolValidationService,
        factory=create_pool_validation_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # StockScoringService - 依赖 DataService
    from application.services.stock_scoring_service import StockScoringService
    def create_stock_scoring_service():
        from infrastructure.services.service_factory import ServiceFactory
        ds = ServiceFactory.get_data_service()
        return StockScoringService(ds)

    EnhancedServiceFactory.register(
        StockScoringService,
        factory=create_stock_scoring_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # SectorRotationService - 依赖 DataService 的子服务
    from application.services.sector_rotation_service import SectorRotationService
    def create_sector_rotation_service():
        from infrastructure.services.service_factory import ServiceFactory
        ds = ServiceFactory.get_data_service()
        return SectorRotationService(ds.stock, ds.kline)

    EnhancedServiceFactory.register(
        SectorRotationService,
        factory=create_sector_rotation_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # ========== P2-1 重构的服务 ==========

    # RiskCheckService - 依赖 DataService
    from application.services.risk_check_service import RiskCheckService
    def create_risk_check_service():
        from infrastructure.services.service_factory import ServiceFactory
        ds = ServiceFactory.get_data_service()
        return RiskCheckService(ds)

    EnhancedServiceFactory.register(
        RiskCheckService,
        factory=create_risk_check_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # ChanService - 依赖 IKlineRepository
    from application.services.chan_service import ChanService
    def create_chan_service():
        kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
        return ChanService(kline_repo=kline_repo)

    EnhancedServiceFactory.register(
        ChanService,
        factory=create_chan_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # ChanScanService - 依赖 ChanService, IStockPoolRepository, ISignalRepository
    from application.services.chan_scan_service import ChanScanService
    def create_chan_scan_service():
        chan_service = EnhancedServiceFactory.resolve(ChanService)
        pool_repo = EnhancedServiceFactory.resolve(IStockPoolRepository)
        signal_repo = EnhancedServiceFactory.resolve(ISignalRepository)
        return ChanScanService(
            chan_service=chan_service,
            pool_repo=pool_repo,
            signal_repo=signal_repo
        )

    EnhancedServiceFactory.register(
        ChanScanService,
        factory=create_chan_scan_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # ChanKnowledgeDistiller - 依赖多个 Repository
    from application.services.chan_knowledge_distiller import ChanKnowledgeDistiller
    from domain.ports.repository_ports_extended import IAgentKnowledgeRepository
    def create_chan_knowledge_distiller():
        signal_repo = EnhancedServiceFactory.resolve(ISignalRepository)
        kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
        knowledge_repo = IAgentKnowledgeRepository()  # 暂时直接实例化
        return ChanKnowledgeDistiller(
            signal_repo=signal_repo,
            kline_repo=kline_repo,
            knowledge_repo=knowledge_repo
        )

    EnhancedServiceFactory.register(
        ChanKnowledgeDistiller,
        factory=create_chan_knowledge_distiller,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # FactorLayeringService - 依赖 IKlineRepository, IStockRepository, StockPoolService
    from application.services.factor_layering_service import FactorLayeringService
    def create_factor_layering_service():
        kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
        stock_repo = EnhancedServiceFactory.resolve(IStockRepository)
        stock_pool_service = EnhancedServiceFactory.resolve(StockPoolService)
        return FactorLayeringService(
            kline_repo=kline_repo,
            stock_repo=stock_repo,
            stock_pool_service=stock_pool_service
        )

    EnhancedServiceFactory.register(
        FactorLayeringService,
        factory=create_factor_layering_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # StrategyWeightAdjuster - 依赖 Repository
    from application.services.strategy_weight_adjuster import StrategyWeightAdjuster
    from domain.ports.repository_ports_extended import IStrategyWeightRepository, IStrategyPerformanceRepository
    def create_strategy_weight_adjuster():
        weight_repo = IStrategyWeightRepository()
        performance_repo = IStrategyPerformanceRepository()
        return StrategyWeightAdjuster(
            weight_repo=weight_repo,
            performance_repo=performance_repo
        )

    EnhancedServiceFactory.register(
        StrategyWeightAdjuster,
        factory=create_strategy_weight_adjuster,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # DecisionService - 依赖 Repository
    from application.services.decision_service import DecisionService
    from domain.ports.repository_ports_extended import IAgentIntelligenceRepository, IPoolChangeLogRepository
    def create_decision_service():
        decision_repo = IAgentIntelligenceRepository()
        change_log_repo = IPoolChangeLogRepository()
        return DecisionService(
            decision_repo=decision_repo,
            change_log_repo=change_log_repo
        )

    EnhancedServiceFactory.register(
        DecisionService,
        factory=create_decision_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # StrategyBacktestService - 依赖 IStrategyRepository
    from application.services.strategy_backtest_service import StrategyBacktestService
    from domain.quantlib.engine.indicator_strategy_executor import IndicatorStrategyExecutor
    from domain.quantlib.engine.script_strategy_executor import ScriptStrategyExecutor
    def create_strategy_backtest_service():
        strategy_repo = EnhancedServiceFactory.resolve(IStrategyRepository)
        return StrategyBacktestService(
            strategy_repo=strategy_repo,
            indicator_executor=IndicatorStrategyExecutor(),
            script_executor=ScriptStrategyExecutor()
        )

    EnhancedServiceFactory.register(
        StrategyBacktestService,
        factory=create_strategy_backtest_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # DataQualityService - 复杂依赖
    from application.services.data_quality_service import DataQualityService
    def create_data_quality_service():
        # DataQualityService 内部会创建其他服务，暂时保持原样
        return DataQualityService()

    EnhancedServiceFactory.register(
        DataQualityService,
        factory=create_data_quality_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # StrategyService (统一策略服务)
    from application.services.strategy_service import StrategyService
    def create_strategy_service():
        return StrategyService(repo=EnhancedServiceFactory.resolve(ISimulationRepository))

    EnhancedServiceFactory.register(
        StrategyService,
        factory=create_strategy_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # StockCodeValidator
    from application.services.stock_code_validator import StockCodeValidator
    def create_stock_code_validator():
        kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
        return StockCodeValidator(kline_repo=kline_repo)

    EnhancedServiceFactory.register(
        StockCodeValidator,
        factory=create_stock_code_validator,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # StrategyCircuitBreaker
    from application.services.strategy_circuit_breaker import StrategyCircuitBreaker
    from domain.ports.repository_ports_extended import IStrategyCircuitBreakerRepository
    def create_strategy_circuit_breaker():
        repo = IStrategyCircuitBreakerRepository()
        return StrategyCircuitBreaker(repo=repo)

    EnhancedServiceFactory.register(
        StrategyCircuitBreaker,
        factory=create_strategy_circuit_breaker,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # SchedulerConfigService
    from application.services.scheduler_config_service import SchedulerConfigService
    from domain.ports.repository_ports_extended import ISchedulerConfigRepository
    def create_scheduler_config_service():
        repo = ISchedulerConfigRepository()
        return SchedulerConfigService(repo=repo)

    EnhancedServiceFactory.register(
        SchedulerConfigService,
        factory=create_scheduler_config_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # SimulationService
    from application.services.simulation_service import SimulationService
    def create_simulation_service():
        repo = EnhancedServiceFactory.resolve(ISimulationRepository)
        return SimulationService(repo=repo)

    EnhancedServiceFactory.register(
        SimulationService,
        factory=create_simulation_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # ExperienceAccumulator
    from application.services.experience_accumulator import ExperienceAccumulator
    from application.services.signal_test_log import SignalTestLog
    def create_experience_accumulator():
        signal_log = SignalTestLog()
        perf_repo = IStrategyPerformanceRepository()
        return ExperienceAccumulator(
            signal_log=signal_log,
            perf_repo=perf_repo
        )

    EnhancedServiceFactory.register(
        ExperienceAccumulator,
        factory=create_experience_accumulator,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # KnowledgeService
    from application.services.knowledge_service import KnowledgeService
    def create_knowledge_service():
        repository = IAgentKnowledgeRepository()
        return KnowledgeService(repository=repository)

    EnhancedServiceFactory.register(
        KnowledgeService,
        factory=create_knowledge_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # SmartSchedulerService
    from application.services.smart_scheduler import SmartSchedulerService
    def create_smart_scheduler_service():
        config_repo = ISchedulerConfigRepository()
        return SmartSchedulerService(config_repo=config_repo)

    EnhancedServiceFactory.register(
        SmartSchedulerService,
        factory=create_smart_scheduler_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # SwingPointService
    from application.services.swing_point_service import SwingPointService
    def create_swing_point_service():
        kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
        validator = EnhancedServiceFactory.resolve(StockCodeValidator)
        return SwingPointService(
            kline_repo=kline_repo,
            validator=validator
        )

    EnhancedServiceFactory.register(
        SwingPointService,
        factory=create_swing_point_service,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # PerformanceTracker
    from application.services.performance_tracker import PerformanceTracker
    def create_performance_tracker():
        repo = EnhancedServiceFactory.resolve(ISimulationRepository)
        return PerformanceTracker(repo=repo)

    EnhancedServiceFactory.register(
        PerformanceTracker,
        factory=create_performance_tracker,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # AttributionAnalyzer
    from application.services.attribution_analyzer import AttributionAnalyzer
    def create_attribution_analyzer():
        pool_repo = EnhancedServiceFactory.resolve(IStockPoolRepository)
        return AttributionAnalyzer(pool_repo=pool_repo)

    EnhancedServiceFactory.register(
        AttributionAnalyzer,
        factory=create_attribution_analyzer,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # SignalExecutionScheduler
    from application.services.signal_execution_scheduler import SignalExecutionScheduler
    from application.services.strategy_code_service import StrategyCodeService
    from domain.ports.repository_ports_extended import ISignalExecutionLogRepository
    def create_signal_execution_scheduler():
        from infrastructure.services.service_factory import ServiceFactory
        data_service = ServiceFactory.get_data_service()
        strategy_service = StrategyCodeService()
        risk_service = EnhancedServiceFactory.resolve(RiskCheckService)
        signal_repo = EnhancedServiceFactory.resolve(ISignalRepository)
        log_repo = ISignalExecutionLogRepository()
        strategy_repo = EnhancedServiceFactory.resolve(IStrategyRepository)

        return SignalExecutionScheduler(
            data_service=data_service,
            strategy_service=strategy_service,
            risk_service=risk_service,
            signal_repo=signal_repo,
            log_repo=log_repo,
            strategy_repo=strategy_repo
        )

    EnhancedServiceFactory.register(
        SignalExecutionScheduler,
        factory=create_signal_execution_scheduler,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    logger.info(f"Registered {len(EnhancedServiceFactory.get_registered_services())} services to EnhancedServiceFactory")


# 提供兼容旧代码的桥接函数
def get_service_from_enhanced_factory(service_type):
    """从 EnhancedServiceFactory 获取服务，如果未注册则返回 None"""
    if EnhancedServiceFactory.is_registered(service_type):
        return EnhancedServiceFactory.resolve(service_type)
    return None


__all__ = [
    'register_all_services',
    'get_service_from_enhanced_factory',
]
