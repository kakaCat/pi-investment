"""
服务注册表 - 集中管理所有服务的依赖注入配置

P2-1 Phase 1: 将现有 ServiceFactory 的服务逐步迁移到 EnhancedServiceFactory
P2-3: 配置驱动注册（硬编码注册已弃用）

注册方式：
- 配置文件注册 - 从 config/services.yaml 加载（唯一支持方式）
"""
import logging
import os
from typing import Optional
from .enhanced_service_factory import EnhancedServiceFactory, ServiceLifecycle

logger = logging.getLogger(__name__)

# 全局标志：配置驱动默认启用
_CONFIG_DRIVEN_ENABLED = os.environ.get('QUANTSYS_CONFIG_DRIVEN', 'true').lower() in ('true', '1', 'yes')


def register_all_services(use_config: Optional[bool] = None, environment: Optional[str] = None):
    """注册所有服务到 EnhancedServiceFactory

    P2-3: 只支持配置驱动注册

    Args:
        use_config: 是否使用配置驱动注册
                   None（默认）- 使用环境变量 QUANTSYS_CONFIG_DRIVEN 决定
                   True - 强制使用配置文件
                   False - 已弃用，将忽略并使用配置驱动
        environment: 环境名称（dev/test/prod）

    注册方式：
    - 配置驱动：从 config/services.yaml 加载服务配置
    """
    # 确定使用哪种注册方式
    if use_config is None:
        use_config = _CONFIG_DRIVEN_ENABLED

    # P2-3: use_config=False 已弃用，发出警告
    if use_config is False:
        logger.warning(
            "⚠️  Hardcoded registration (use_config=False) is DEPRECATED and no longer supported. "
            "Falling back to config-driven registration. "
            "Update your code to use config-driven registration or remove use_config parameter."
        )
        use_config = True

    # P2-3: 配置驱动注册（唯一方式）
    try:
        from infrastructure.config.loader import load_config
        from infrastructure.config.validator import ConfigValidator

        logger.info(f"Loading services from configuration (environment: {environment or 'auto-detect'})")

        # 加载配置
        config = load_config(environment=environment)

        # 验证配置（非严格模式 - 允许某些类因缺少依赖而无法加载）
        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        if errors:
            logger.warning(f"Configuration validation found {len(errors)} issues (non-blocking):")
            for error in errors[:5]:  # 只显示前 5 个
                logger.warning(f"  - {error.service_name}: {error.error_type}")
            if len(errors) > 5:
                logger.warning(f"  ... and {len(errors) - 5} more")

        # 从配置注册服务
        EnhancedServiceFactory.register_from_config(config)

        registered_count = len(EnhancedServiceFactory.get_registered_services())
        logger.info(f"✅ Registered {registered_count} services from configuration")

    except Exception as e:
        logger.error(f"❌ Failed to load services from configuration: {e}")
        logger.error("Cannot fall back to hardcoded registration (deprecated). Please fix configuration errors.")
        raise RuntimeError(
            f"Service registration failed: {e}\n"
            "Hardcoded registration is no longer supported. "
            "Please check your config/services.yaml file for errors."
        ) from e


# ========== 已弃用的硬编码注册 ==========
# P2-3: 以下函数已弃用，保留仅供参考

def _register_services_hardcoded():
    """硬编码服务注册（已弃用）

    ⚠️  DEPRECATED: This function is no longer supported as of P2-3.

    使用配置驱动注册替代：
    1. 在 config/services.yaml 中定义服务
    2. 调用 register_all_services() 自动加载

    历史原因：
    - 硬编码注册违反依赖注入原则
    - 导致循环依赖和接口实例化问题
    - 维护成本高，扩展性差

    迁移指南：
    - 将服务定义迁移到 config/services.yaml
    - 更新服务构造函数支持依赖注入
    - 使用 EnhancedServiceFactory.resolve() 获取服务
    """
    raise RuntimeError(
        "Hardcoded service registration is DEPRECATED as of P2-3.\n"
        "Please use config-driven registration (config/services.yaml) instead.\n"
        "See docs/P2-3-production-validation-final-summary.md for migration guide."
    )

    # Stock Pool Repository
    from domain.ports.repository_ports_extended import IStockPoolRepository
    from adapters.outbound.repositories.stock_pool_repository import StockPoolORMRepository
    EnhancedServiceFactory.register(
        IStockPoolRepository,
        StockPoolORMRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # Strategy Repository
    from domain.ports import IStrategyRepository
    from adapters.outbound.repositories.strategy_repository import StrategyORMRepository
    EnhancedServiceFactory.register(
        IStrategyRepository,
        StrategyORMRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # Kline Repository
    from domain.ports import IKlineRepository
    from adapters.outbound.repositories.kline_repository import KlineORMRepository
    EnhancedServiceFactory.register(
        IKlineRepository,
        KlineORMRepository,
        lifecycle=ServiceLifecycle.SINGLETON
    )

    # Signal Repository
    from domain.ports import ISignalRepository
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
    # P0 Fix: 直接使用 DataProviderManager，删除冗余的 Adapter 层
    from domain.ports.datasource_ports import IDataProviderManager
    from adapters.outbound.datasources.manager import DataProviderManager

    # DataProviderManager 需要 DataService，使用工厂函数延迟初始化
    def create_data_provider_manager():
        from infrastructure.services.service_factory import ServiceFactory
        ds = ServiceFactory.get_data_service()
        return DataProviderManager(ds)

    EnhancedServiceFactory.register(
        IDataProviderManager,
        factory=create_data_provider_manager,
        lifecycle=ServiceLifecycle.SINGLETON
    )
    # IDataQualityMonitor 未被实际使用，已移除注册

    # ========== Application Services ==========

    # DataService - 核心服务，很多服务依赖它
    from application.services.data_service import DataService
    from application.services.financial_data_service_adapter import FinancialDataServiceAdapter

    EnhancedServiceFactory.register(
        FinancialDataServiceAdapter,
        factory=lambda: FinancialDataServiceAdapter(),
        lifecycle=ServiceLifecycle.SINGLETON
    )

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
            financial_service=EnhancedServiceFactory.resolve(FinancialDataServiceAdapter),
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
    from domain.backtest.engine.indicator_strategy_executor import IndicatorStrategyExecutor
    from domain.backtest.engine.script_strategy_executor import ScriptStrategyExecutor
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


# 导出
__all__ = [
    'register_all_services',
]
