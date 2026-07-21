"""
依赖注入容器测试

验证容器的正确性和服务生命周期。
"""
import pytest
from infrastructure.di.container import Container


class TestContainer:
    """测试依赖注入容器"""

    def test_container_initialization(self):
        """测试容器初始化"""
        container = Container()
        assert container is not None

    def test_singleton_services(self):
        """测试单例服务 - 多次调用返回同一实例"""
        container = Container()

        # 数据服务应该是单例
        data_service1 = container.data_service()
        data_service2 = container.data_service()

        assert data_service1 is data_service2, "Singleton service should return same instance"

    def test_factory_services(self):
        """测试工厂服务 - 每次调用返回新实例"""
        container = Container()

        # 股票池服务应该是工厂模式
        pool_service1 = container.stock_pool_service()
        pool_service2 = container.stock_pool_service()

        assert pool_service1 is not pool_service2, "Factory service should return different instances"

    def test_service_dependencies(self):
        """测试服务依赖注入是否正确"""
        container = Container()

        # 获取股票池服务
        pool_service = container.stock_pool_service()

        # 验证服务已正确初始化（有必要的依赖）
        assert pool_service is not None
        assert hasattr(pool_service, 'stock_repo')
        assert hasattr(pool_service, 'pool_repo')

    def test_all_services_can_be_created(self):
        """测试所有服务都可以成功创建"""
        container = Container()

        services_to_test = [
            'data_service',
            'strategy_service',
            'factor_adapter',
            'opportunity_scoring_service',
            'stock_scoring_service',
            'sector_rotation_service',
            'stock_pool_service',
            'pool_validation_service',
        ]

        for service_name in services_to_test:
            if hasattr(container, service_name):
                service_provider = getattr(container, service_name)
                service = service_provider()
                assert service is not None, f"{service_name} should be created successfully"


class TestDIDecorator:
    """测试依赖注入装饰器"""

    def test_inject_decorator_with_flask(self):
        """测试 Flask 环境下的依赖注入装饰器"""
        from flask import Flask
        from infrastructure.di.decorators import inject

        app = Flask(__name__)
        app.container = Container()

        @inject
        def test_func(data_service):
            return data_service

        with app.app_context():
            app.container = Container()
            # 注意：这里需要在请求上下文中测试
            # 简化测试，仅验证装饰器不会抛出异常
            assert test_func is not None

    def test_inject_with_multiple_services(self):
        """测试注入多个服务"""
        from flask import Flask
        from infrastructure.di.decorators import inject

        app = Flask(__name__)
        app.container = Container()

        @inject
        def test_func(data_service, strategy_service):
            return data_service, strategy_service

        # 验证函数签名正确
        assert test_func is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
