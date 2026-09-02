"""
测试服务注册表与配置系统集成

P2-3: 验证 service_registry.py 是否正确集成配置驱动注册
"""

import pytest
import os
from infrastructure.services.service_registry import register_all_services
from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory


class TestServiceRegistryConfigIntegration:
    """测试服务注册表配置集成"""

    def setup_method(self):
        """每个测试前清空服务注册"""
        EnhancedServiceFactory._descriptors.clear()
        EnhancedServiceFactory._singletons.clear()

    def test_register_with_config_driven_enabled(self):
        """测试配置驱动注册（默认开启）"""
        # 设置环境变量启用配置驱动
        os.environ['QUANTSYS_CONFIG_DRIVEN'] = 'true'

        # 注册服务
        register_all_services()

        # 验证服务已注册
        registered = EnhancedServiceFactory.get_registered_services()
        assert len(registered) > 0, "Should register services from config"

        # 验证关键 Repository 已注册
        from domain.ports import IStockRepository, IKlineRepository
        assert EnhancedServiceFactory.is_registered(IStockRepository)
        assert EnhancedServiceFactory.is_registered(IKlineRepository)

    def test_register_with_config_driven_disabled(self):
        """测试硬编码注册（禁用配置驱动）"""
        # 显式禁用配置驱动
        register_all_services(use_config=False)

        # 验证服务已注册
        registered = EnhancedServiceFactory.get_registered_services()
        assert len(registered) > 0, "Should register services via hardcoded logic"

        # 验证关键 Repository 已注册
        from domain.ports import IStockRepository, IKlineRepository
        assert EnhancedServiceFactory.is_registered(IStockRepository)
        assert EnhancedServiceFactory.is_registered(IKlineRepository)

    def test_register_with_specific_environment(self):
        """测试指定环境的配置注册"""
        # 使用 test 环境
        register_all_services(use_config=True, environment='test')

        # 验证服务已注册
        registered = EnhancedServiceFactory.get_registered_services()
        assert len(registered) > 0

    def test_config_driven_fallback_on_error(self):
        """测试配置加载失败时降级到硬编码"""
        # 使用不存在的环境，触发降级
        register_all_services(use_config=True, environment='nonexistent_env_xyz')

        # 即使配置加载失败，硬编码注册仍应工作
        registered = EnhancedServiceFactory.get_registered_services()
        assert len(registered) > 0, "Should fallback to hardcoded registration"


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def setup_method(self):
        """每个测试前清空服务注册"""
        EnhancedServiceFactory._descriptors.clear()
        EnhancedServiceFactory._singletons.clear()

    def test_old_api_still_works(self):
        """测试旧的 API 仍然可用"""
        # 旧代码调用方式（无参数）
        register_all_services()

        # 应该能够解析服务
        from domain.ports import IStockRepository
        stock_repo = EnhancedServiceFactory.resolve(IStockRepository)
        assert stock_repo is not None

    def test_explicit_hardcoded_registration(self):
        """测试显式使用硬编码注册"""
        # 明确指定不使用配置
        register_all_services(use_config=False)

        from domain.ports import IKlineRepository
        kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
        assert kline_repo is not None


class TestEnvironmentVariableControl:
    """测试环境变量控制"""

    def setup_method(self):
        """每个测试前清空服务注册"""
        EnhancedServiceFactory._descriptors.clear()
        EnhancedServiceFactory._singletons.clear()
        # 保存原始环境变量
        self.original_config_driven = os.environ.get('QUANTSYS_CONFIG_DRIVEN')

    def teardown_method(self):
        """恢复原始环境变量"""
        if self.original_config_driven is not None:
            os.environ['QUANTSYS_CONFIG_DRIVEN'] = self.original_config_driven
        elif 'QUANTSYS_CONFIG_DRIVEN' in os.environ:
            del os.environ['QUANTSYS_CONFIG_DRIVEN']

    def test_env_var_enables_config_driven(self):
        """测试环境变量启用配置驱动"""
        os.environ['QUANTSYS_CONFIG_DRIVEN'] = 'true'
        register_all_services()

        # 应该使用配置驱动
        registered = EnhancedServiceFactory.get_registered_services()
        assert len(registered) > 0

    def test_env_var_disables_config_driven(self):
        """测试环境变量禁用配置驱动"""
        os.environ['QUANTSYS_CONFIG_DRIVEN'] = 'false'
        register_all_services()

        # 应该使用硬编码注册
        registered = EnhancedServiceFactory.get_registered_services()
        assert len(registered) > 0

    def test_env_var_variations(self):
        """测试环境变量不同值"""
        for value in ['1', 'yes', 'True', 'TRUE']:
            EnhancedServiceFactory._descriptors.clear()
            EnhancedServiceFactory._singletons.clear()
            os.environ['QUANTSYS_CONFIG_DRIVEN'] = value
            register_all_services()
            assert len(EnhancedServiceFactory.get_registered_services()) > 0

        for value in ['0', 'no', 'False', 'FALSE']:
            EnhancedServiceFactory._descriptors.clear()
            EnhancedServiceFactory._singletons.clear()
            os.environ['QUANTSYS_CONFIG_DRIVEN'] = value
            register_all_services()
            assert len(EnhancedServiceFactory.get_registered_services()) > 0


class TestConfigDrivenVsHardcoded:
    """对比配置驱动和硬编码注册"""

    def setup_method(self):
        """每个测试前清空服务注册"""
        EnhancedServiceFactory._descriptors.clear()
        EnhancedServiceFactory._singletons.clear()

    def test_both_methods_register_core_repositories(self):
        """测试两种方式都能注册核心 Repository"""
        from domain.ports import IStockRepository, IKlineRepository, ISignalRepository

        # 方式 1: 配置驱动
        EnhancedServiceFactory._descriptors.clear()
        EnhancedServiceFactory._singletons.clear()
        register_all_services(use_config=True)
        config_driven_count = len(EnhancedServiceFactory.get_registered_services())
        assert EnhancedServiceFactory.is_registered(IStockRepository)
        assert EnhancedServiceFactory.is_registered(IKlineRepository)
        assert EnhancedServiceFactory.is_registered(ISignalRepository)

        # 方式 2: 硬编码
        EnhancedServiceFactory._descriptors.clear()
        EnhancedServiceFactory._singletons.clear()
        register_all_services(use_config=False)
        hardcoded_count = len(EnhancedServiceFactory.get_registered_services())
        assert EnhancedServiceFactory.is_registered(IStockRepository)
        assert EnhancedServiceFactory.is_registered(IKlineRepository)
        assert EnhancedServiceFactory.is_registered(ISignalRepository)

        # 配置驱动应该注册更多服务（因为配置文件更完整）
        # 但至少核心服务应该一致
        assert config_driven_count > 0
        assert hardcoded_count > 0
