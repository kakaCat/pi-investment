"""测试配置驱动集成

P2-3: 测试从配置文件加载和注册服务
"""

import pytest
from pathlib import Path
import tempfile
import yaml

from infrastructure.config import ConfigLoader, ServicesConfig, ServiceConfig
from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory, ServiceLifecycle


class TestConfigLoader:
    """测试配置加载器"""

    def test_load_basic_config(self):
        """测试加载基础配置"""
        # 使用实际的配置文件
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        assert config is not None
        assert config.version == '1.0'
        assert config.current_environment == 'dev'

        # 检查合并后的服务
        services = config.get_merged_services()
        assert len(services) > 0

        # 验证 repositories 被转换为服务
        assert 'repositories.stock' in services
        assert 'repositories.kline' in services

        # 验证 services
        assert 'chan_service' in services

    def test_environment_override(self):
        """测试环境特定配置覆盖"""
        loader = ConfigLoader()

        # 加载测试环境配置
        config = loader.load(environment='test')
        services = config.get_merged_services()

        # 检查测试环境覆盖
        stock_repo = services.get('repositories.stock')
        assert stock_repo is not None
        # 测试环境应该使用 Mock 仓库
        assert 'Mock' in stock_repo.implementation

    def test_service_config_parsing(self):
        """测试服务配置解析"""
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        # 获取 chan_service 配置
        chan_service = config.get_service('chan_service')
        assert chan_service is not None
        assert chan_service.class_path == 'application.services.chan_service.ChanService'
        assert chan_service.lifecycle == 'singleton'
        assert 'kline_repo' in chan_service.dependencies

    def test_list_services(self):
        """测试列出所有服务"""
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        service_names = config.list_services()
        assert len(service_names) > 0
        assert 'chan_service' in service_names
        assert 'repositories.stock' in service_names


class TestConfigValidator:
    """测试配置验证器"""

    def test_validate_valid_config(self):
        """测试验证有效配置"""
        from infrastructure.config import ConfigValidator

        loader = ConfigLoader()
        config = loader.load(environment='dev')

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        # 非严格模式不应该有错误（只检查格式）
        assert len(errors) == 0

    def test_validate_missing_dependency(self):
        """测试验证缺失的依赖"""
        from infrastructure.config import ConfigValidator, ServicesConfig

        # 创建一个有错误的配置
        config = ServicesConfig(
            services={
                'test_service': ServiceConfig(
                    name='test_service',
                    class_path='test.TestService',
                    dependencies={'repo': 'non_existent_repo'}
                )
            }
        )

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        # 应该检测到依赖缺失
        assert len(errors) > 0
        assert any('INVALID_DEPENDENCY' in str(e) for e in errors)


class TestEnhancedServiceFactoryConfigIntegration:
    """测试 EnhancedServiceFactory 配置集成"""

    def setup_method(self):
        """每个测试前重置工厂"""
        EnhancedServiceFactory.reset()

    def test_register_from_config(self):
        """测试从配置注册服务"""
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        # 从配置注册服务
        EnhancedServiceFactory.register_from_config(config)

        # 验证服务已注册
        from domain.ports import IStockRepository, IKlineRepository
        assert EnhancedServiceFactory.is_registered(IStockRepository)
        assert EnhancedServiceFactory.is_registered(IKlineRepository)

    def test_resolve_service_from_config(self):
        """测试解析配置注册的服务"""
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        EnhancedServiceFactory.register_from_config(config)

        # 解析服务
        from domain.ports import IKlineRepository
        kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)

        assert kline_repo is not None
        assert hasattr(kline_repo, 'get_klines')  # 验证接口方法

    def test_service_with_dependencies_from_config(self):
        """测试带依赖的服务（从配置）"""
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        EnhancedServiceFactory.register_from_config(config)

        # 解析带依赖的服务
        from application.services.chan_service import ChanService
        chan_service = EnhancedServiceFactory.resolve(ChanService)

        assert chan_service is not None
        assert chan_service.kline_repo is not None

    def test_singleton_lifecycle_from_config(self):
        """测试配置中的单例生命周期"""
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        EnhancedServiceFactory.register_from_config(config)

        # 解析两次，应该返回同一个实例
        from domain.ports import IKlineRepository
        instance1 = EnhancedServiceFactory.resolve(IKlineRepository)
        instance2 = EnhancedServiceFactory.resolve(IKlineRepository)

        assert instance1 is instance2

    def test_factory_function_from_config(self):
        """测试配置中的工厂函数"""
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        EnhancedServiceFactory.register_from_config(config)

        # data_service 使用工厂函数
        from application.services.data_service import DataService
        data_service = EnhancedServiceFactory.resolve(DataService)

        assert data_service is not None
        assert data_service.stock is not None
        assert data_service.kline is not None


class TestConfigMerging:
    """测试配置合并逻辑"""

    def test_base_config_loaded(self):
        """测试基础配置加载"""
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        # 基础配置的服务应该存在
        assert config.get_service('chan_service') is not None

    def test_environment_config_override(self):
        """测试环境配置覆盖基础配置"""
        loader = ConfigLoader()
        config = loader.load(environment='test')

        # 测试环境覆盖的配置
        stock_repo = config.get_service('repositories.stock')
        assert 'Mock' in stock_repo.implementation

    def test_config_field_merging(self):
        """测试配置字段合并"""
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        data_service = config.get_service('data_service')
        assert data_service.config.get('cache_enabled') == True
        assert data_service.config.get('debug') == True


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def setup_method(self):
        """每个测试前重置工厂"""
        EnhancedServiceFactory.reset()

    def test_hardcoded_registration_still_works(self):
        """测试硬编码注册仍然工作"""
        # 手动注册一个服务
        from domain.ports import IStockRepository
        from adapters.outbound.repositories import StockORMRepository

        EnhancedServiceFactory.register(
            IStockRepository,
            StockORMRepository,
            lifecycle=ServiceLifecycle.SINGLETON
        )

        # 解析服务
        stock_repo = EnhancedServiceFactory.resolve(IStockRepository)
        assert stock_repo is not None

    def test_config_and_hardcoded_coexist(self):
        """测试配置和硬编码注册可以共存"""
        # 1. 先从配置加载
        loader = ConfigLoader()
        config = loader.load(environment='dev')
        EnhancedServiceFactory.register_from_config(config)

        # 2. 手动注册额外的服务
        from application.services.chan_service import ChanService
        from domain.ports import IKlineRepository

        def custom_chan_service():
            kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
            return ChanService(kline_repo=kline_repo)

        EnhancedServiceFactory.register(
            ChanService,
            factory=custom_chan_service,
            lifecycle=ServiceLifecycle.SINGLETON
        )

        # 3. 解析服务
        chan_service = EnhancedServiceFactory.resolve(ChanService)
        assert chan_service is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
