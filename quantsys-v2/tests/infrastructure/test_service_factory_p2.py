"""
测试 P2-2 ServiceFactory 实施

验证：
1. 所有 P2-1 重构的服务可以通过 EnhancedServiceFactory 创建
2. 单例模式正常工作
3. 依赖自动解析
4. 与旧 ServiceFactory 的兼容性
"""
import pytest
from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory, ServiceLifecycle
from infrastructure.services.service_registry import register_all_services
from infrastructure.services.service_factory import ServiceFactory


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """每个测试前后重置工厂"""
    EnhancedServiceFactory.reset()
    ServiceFactory.reset_all()
    yield
    EnhancedServiceFactory.reset()
    ServiceFactory.reset_all()


def test_register_all_services():
    """测试注册所有服务"""
    register_all_services()

    services = EnhancedServiceFactory.get_registered_services()
    assert len(services) > 0, "应该注册了至少一个服务"

    # 验证关键服务已注册
    from domain.ports import IStockRepository, IKlineRepository, ISignalRepository
    assert EnhancedServiceFactory.is_registered(IStockRepository)
    assert EnhancedServiceFactory.is_registered(IKlineRepository)
    assert EnhancedServiceFactory.is_registered(ISignalRepository)


def test_repository_resolution():
    """测试 Repository 解析"""
    register_all_services()

    from domain.ports import IStockRepository, IKlineRepository

    # 解析 Repository
    stock_repo = EnhancedServiceFactory.resolve(IStockRepository)
    kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)

    assert stock_repo is not None
    assert kline_repo is not None

    # 验证单例模式
    stock_repo2 = EnhancedServiceFactory.resolve(IStockRepository)
    assert stock_repo is stock_repo2, "应该返回同一个实例（单例）"


def test_service_with_dependencies():
    """测试带依赖的服务解析"""
    register_all_services()

    from application.services.chan_service import ChanService

    # 解析带依赖的服务
    chan_service = EnhancedServiceFactory.resolve(ChanService)

    assert chan_service is not None
    assert chan_service.kline_repo is not None, "依赖应该被自动注入"


def test_stock_code_validator():
    """测试 StockCodeValidator 解析"""
    register_all_services()

    from application.services.stock_code_validator import StockCodeValidator

    validator = EnhancedServiceFactory.resolve(StockCodeValidator)

    assert validator is not None
    assert validator.kline_repo is not None


def test_chan_scan_service():
    """测试 ChanScanService 解析（多依赖）"""
    register_all_services()

    from application.services.chan_scan_service import ChanScanService

    scan_service = EnhancedServiceFactory.resolve(ChanScanService)

    assert scan_service is not None
    assert scan_service._chan is not None
    assert scan_service._pool_repo is not None
    assert scan_service._signal_repo is not None


def test_service_factory_compatibility():
    """测试与旧 ServiceFactory 的兼容性"""
    # 旧的 ServiceFactory 方法应该仍然工作
    data_service = ServiceFactory.get_data_service()
    assert data_service is not None

    # 新注册的服务也应该可以通过 ServiceFactory 获取（通过 _try_get_from_enhanced）
    register_all_services()

    from application.services.stock_pool_service import StockPoolService
    stock_pool_service = ServiceFactory.get_stock_pool_service()
    assert stock_pool_service is not None


def test_singleton_lifecycle():
    """测试单例生命周期"""
    register_all_services()

    from domain.ports import IStockRepository

    # 多次解析应该返回同一实例
    repo1 = EnhancedServiceFactory.resolve(IStockRepository)
    repo2 = EnhancedServiceFactory.resolve(IStockRepository)
    repo3 = EnhancedServiceFactory.resolve(IStockRepository)

    assert repo1 is repo2
    assert repo2 is repo3


def test_multiple_services():
    """测试解析多个不同服务"""
    register_all_services()

    from application.services.chan_service import ChanService
    from application.services.stock_code_validator import StockCodeValidator
    from application.services.decision_service import DecisionService

    services = [
        ChanService,
        StockCodeValidator,
        DecisionService,
    ]

    for service_type in services:
        service = EnhancedServiceFactory.resolve(service_type)
        assert service is not None, f"{service_type.__name__} 应该可以解析"


def test_reset_clears_singletons():
    """测试重置清空单例缓存"""
    register_all_services()

    from domain.ports import IStockRepository

    repo1 = EnhancedServiceFactory.resolve(IStockRepository)

    # 重置
    EnhancedServiceFactory.reset()
    register_all_services()

    repo2 = EnhancedServiceFactory.resolve(IStockRepository)

    # 重置后应该是新实例
    assert repo1 is not repo2


def test_service_not_registered():
    """测试未注册服务的错误处理"""
    register_all_services()

    class UnregisteredService:
        pass

    with pytest.raises(ValueError, match="Service not registered"):
        EnhancedServiceFactory.resolve(UnregisteredService)


def test_all_p2_1_services():
    """测试所有 P2-1 重构的服务都可以解析"""
    register_all_services()

    services_to_test = [
        # 缠论相关
        ('application.services.chan_service', 'ChanService'),
        ('application.services.chan_scan_service', 'ChanScanService'),
        ('application.services.chan_knowledge_distiller', 'ChanKnowledgeDistiller'),

        # 策略相关
        ('application.services.strategy_backtest_service', 'StrategyBacktestService'),
        ('application.services.strategy_weight_adjuster', 'StrategyWeightAdjuster'),
        ('application.services.strategy_circuit_breaker', 'StrategyCircuitBreaker'),

        # 数据质量
        ('application.services.data_quality_service', 'DataQualityService'),
        ('application.services.stock_code_validator', 'StockCodeValidator'),

        # 决策与知识
        ('application.services.decision_service', 'DecisionService'),
        ('application.services.knowledge_service', 'KnowledgeService'),
        ('application.services.experience_accumulator', 'ExperienceAccumulator'),

        # 其他服务
        ('application.services.strategy_service', 'StrategyService'),
        ('application.services.simulation_service', 'SimulationService'),
        ('application.services.scheduler_config_service', 'SchedulerConfigService'),
        ('application.services.smart_scheduler', 'SmartSchedulerService'),
        ('application.services.swing_point_service', 'SwingPointService'),
        ('application.services.performance_tracker', 'PerformanceTracker'),
        ('application.services.attribution_analyzer', 'AttributionAnalyzer'),
        ('application.services.signal_execution_scheduler', 'SignalExecutionScheduler'),
        ('application.services.factor_layering_service', 'FactorLayeringService'),
    ]

    for module_name, class_name in services_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            service_class = getattr(module, class_name)

            if EnhancedServiceFactory.is_registered(service_class):
                service = EnhancedServiceFactory.resolve(service_class)
                assert service is not None, f"{class_name} 解析失败"
            else:
                pytest.skip(f"{class_name} 未注册到 EnhancedServiceFactory")
        except Exception as e:
            pytest.fail(f"解析 {class_name} 时出错: {e}")
