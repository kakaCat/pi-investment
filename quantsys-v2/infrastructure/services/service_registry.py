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
