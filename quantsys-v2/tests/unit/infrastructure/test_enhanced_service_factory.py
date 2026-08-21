"""
测试 EnhancedServiceFactory 的依赖注入功能

P2-1 Phase 1: 验证自动依赖解析、生命周期管理、循环依赖检测
"""
import pytest
from infrastructure.services.enhanced_service_factory import (
    EnhancedServiceFactory,
    ServiceLifecycle,
    inject,
    register_service,
)


# 测试用的接口和实现（避免 Test 前缀以免 pytest 警告）
class ITestRepository:
    def get_data(self):
        raise NotImplementedError


class MockRepository(ITestRepository):
    def __init__(self):
        self.data = "test_data"

    def get_data(self):
        return self.data


class ITestService:
    def process(self):
        raise NotImplementedError


class MockService(ITestService):
    def __init__(self, repo: ITestRepository):
        self.repo = repo

    def process(self):
        return f"processed_{self.repo.get_data()}"


class MockServiceWithMultipleDeps:
    def __init__(self, repo: ITestRepository, service: ITestService):
        self.repo = repo
        self.service = service

    def execute(self):
        return f"{self.service.process()}_and_{self.repo.get_data()}"


@pytest.fixture(autouse=True)
def reset_factory():
    """每个测试前重置工厂"""
    EnhancedServiceFactory.reset()
    yield
    EnhancedServiceFactory.reset()


class TestServiceRegistration:
    """测试服务注册"""

    def test_register_interface_to_implementation(self):
        """测试接口到实现的映射注册"""
        EnhancedServiceFactory.register(
            ITestRepository,
            MockRepository,
            lifecycle=ServiceLifecycle.SINGLETON
        )

        assert EnhancedServiceFactory.is_registered(ITestRepository)
        assert "ITestRepository" in EnhancedServiceFactory.get_registered_services()

    def test_register_with_factory_function(self):
        """测试使用工厂函数注册"""
        EnhancedServiceFactory.register(
            ITestRepository,
            factory=lambda: MockRepository(),
            lifecycle=ServiceLifecycle.SINGLETON
        )

        repo = EnhancedServiceFactory.resolve(ITestRepository)
        assert isinstance(repo, MockRepository)
        assert repo.get_data() == "test_data"

    def test_register_decorator(self):
        """测试装饰器形式的注册"""
        @register_service(ITestRepository)
        class DecoratedRepository(ITestRepository):
            def get_data(self):
                return "decorated"

        assert EnhancedServiceFactory.is_registered(ITestRepository)
        repo = EnhancedServiceFactory.resolve(ITestRepository)
        assert repo.get_data() == "decorated"


class TestDependencyResolution:
    """测试依赖解析"""

    def test_resolve_simple_service(self):
        """测试解析简单服务（无依赖）"""
        EnhancedServiceFactory.register(ITestRepository, MockRepository)

        repo = EnhancedServiceFactory.resolve(ITestRepository)
        assert isinstance(repo, MockRepository)
        assert repo.get_data() == "test_data"

    def test_resolve_service_with_dependency(self):
        """测试解析有依赖的服务"""
        # 注册依赖
        EnhancedServiceFactory.register(ITestRepository, MockRepository)
        # 注册服务（依赖会自动从构造函数推断）
        EnhancedServiceFactory.register(ITestService, MockService)

        service = EnhancedServiceFactory.resolve(ITestService)
        assert isinstance(service, MockService)
        assert service.process() == "processed_test_data"

    def test_resolve_service_with_multiple_dependencies(self):
        """测试解析有多个依赖的服务"""
        EnhancedServiceFactory.register(ITestRepository, MockRepository)
        EnhancedServiceFactory.register(ITestService, MockService)
        EnhancedServiceFactory.register(
            MockServiceWithMultipleDeps,
            MockServiceWithMultipleDeps
        )

        service = EnhancedServiceFactory.resolve(MockServiceWithMultipleDeps)
        assert service.execute() == "processed_test_data_and_test_data"

    def test_resolve_unregistered_service_raises_error(self):
        """测试解析未注册的服务抛出异常"""
        with pytest.raises(ValueError, match="Service not registered"):
            EnhancedServiceFactory.resolve(ITestRepository)


class TestLifecycleManagement:
    """测试生命周期管理"""

    def test_singleton_returns_same_instance(self):
        """测试 Singleton 返回相同实例"""
        EnhancedServiceFactory.register(
            ITestRepository,
            MockRepository,
            lifecycle=ServiceLifecycle.SINGLETON
        )

        repo1 = EnhancedServiceFactory.resolve(ITestRepository)
        repo2 = EnhancedServiceFactory.resolve(ITestRepository)

        assert repo1 is repo2

    def test_transient_returns_different_instances(self):
        """测试 Transient 返回不同实例"""
        EnhancedServiceFactory.register(
            ITestRepository,
            MockRepository,
            lifecycle=ServiceLifecycle.TRANSIENT
        )

        repo1 = EnhancedServiceFactory.resolve(ITestRepository)
        repo2 = EnhancedServiceFactory.resolve(ITestRepository)

        assert repo1 is not repo2
        assert isinstance(repo1, MockRepository)
        assert isinstance(repo2, MockRepository)


class TestCircularDependencyDetection:
    """测试循环依赖检测"""

    def test_circular_dependency_raises_error(self):
        """测试循环依赖抛出异常"""
        # 创建循环依赖：A -> B -> A
        # 注意：使用显式依赖声明而不是字符串注解
        class ServiceA:
            pass

        class ServiceB:
            pass

        # 显式声明循环依赖
        EnhancedServiceFactory.register(
            ServiceA,
            ServiceA,
            dependencies=[ServiceB]
        )
        EnhancedServiceFactory.register(
            ServiceB,
            ServiceB,
            dependencies=[ServiceA]
        )

        with pytest.raises(ValueError, match="Circular dependency detected"):
            EnhancedServiceFactory.resolve(ServiceA)


class TestInjectDecorator:
    """测试 @inject 装饰器"""

    def test_inject_decorator_auto_resolves_dependencies(self):
        """测试 @inject 装饰器自动解析依赖"""
        EnhancedServiceFactory.register(ITestRepository, MockRepository)

        @inject(ITestRepository)
        class AutoInjectedService:
            def __init__(self, repo: ITestRepository):
                self.repo = repo

        # 不传参数，自动注入
        service = AutoInjectedService()
        assert isinstance(service.repo, MockRepository)
        assert service.repo.get_data() == "test_data"

    def test_inject_decorator_allows_manual_injection(self):
        """测试 @inject 装饰器允许手动注入"""
        @inject(ITestRepository)
        class ManualInjectedService:
            def __init__(self, repo: ITestRepository):
                self.repo = repo

        # 手动传参数
        manual_repo = MockRepository()
        manual_repo.data = "manual_data"
        service = ManualInjectedService(manual_repo)

        assert service.repo.data == "manual_data"


class TestReset:
    """测试重置功能"""

    def test_reset_clears_registrations(self):
        """测试重置清除所有注册"""
        EnhancedServiceFactory.register(ITestRepository, MockRepository)
        assert EnhancedServiceFactory.is_registered(ITestRepository)

        EnhancedServiceFactory.reset()
        assert not EnhancedServiceFactory.is_registered(ITestRepository)

    def test_reset_clears_singleton_instances(self):
        """测试重置清除单例实例"""
        EnhancedServiceFactory.register(
            ITestRepository,
            MockRepository,
            lifecycle=ServiceLifecycle.SINGLETON
        )

        repo1 = EnhancedServiceFactory.resolve(ITestRepository)
        EnhancedServiceFactory.reset()

        # 重新注册后解析，应该是新实例
        EnhancedServiceFactory.register(
            ITestRepository,
            MockRepository,
            lifecycle=ServiceLifecycle.SINGLETON
        )
        repo2 = EnhancedServiceFactory.resolve(ITestRepository)

        assert repo1 is not repo2
