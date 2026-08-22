"""测试配置数据模型

P2-3: 测试配置数据结构和合并逻辑
"""

import pytest
from infrastructure.config.models import (
    ServiceConfig,
    RepositoryConfig,
    EnvironmentConfig,
    ServicesConfig,
    ServiceLifecycle
)


class TestServiceLifecycle:
    """测试服务生命周期枚举"""

    def test_lifecycle_values(self):
        """测试生命周期枚举值"""
        assert ServiceLifecycle.SINGLETON.value == 'singleton'
        assert ServiceLifecycle.TRANSIENT.value == 'transient'
        assert ServiceLifecycle.SCOPED.value == 'scoped'

    def test_lifecycle_from_string(self):
        """测试从字符串创建生命周期"""
        assert ServiceLifecycle('singleton') == ServiceLifecycle.SINGLETON
        assert ServiceLifecycle('transient') == ServiceLifecycle.TRANSIENT
        assert ServiceLifecycle('scoped') == ServiceLifecycle.SCOPED


class TestServiceConfig:
    """测试服务配置"""

    def test_service_config_with_class_path(self):
        """测试使用类路径的服务配置"""
        config = ServiceConfig(
            name='test_service',
            class_path='test.TestService',
            lifecycle='singleton'
        )

        assert config.name == 'test_service'
        assert config.class_path == 'test.TestService'
        assert config.lifecycle == 'singleton'

    def test_service_config_with_interface_implementation(self):
        """测试使用接口-实现的服务配置"""
        config = ServiceConfig(
            name='test_repo',
            interface='domain.ports.ITestRepository',
            implementation='adapters.TestORMRepository',
            lifecycle='singleton'
        )

        assert config.interface == 'domain.ports.ITestRepository'
        assert config.implementation == 'adapters.TestORMRepository'

    def test_service_config_with_factory(self):
        """测试使用工厂函数的服务配置"""
        config = ServiceConfig(
            name='test_service',
            class_path='test.TestService',
            factory='test.factories.create_test_service',
            lifecycle='singleton'
        )

        assert config.factory == 'test.factories.create_test_service'

    def test_service_config_with_dependencies(self):
        """测试带依赖的服务配置"""
        config = ServiceConfig(
            name='test_service',
            class_path='test.TestService',
            dependencies={'repo': 'test_repo', 'service': 'other_service'}
        )

        assert len(config.dependencies) == 2
        assert config.dependencies['repo'] == 'test_repo'

    def test_service_config_with_config_dict(self):
        """测试带配置字典的服务配置"""
        config = ServiceConfig(
            name='test_service',
            class_path='test.TestService',
            config={'cache_enabled': True, 'timeout': 30}
        )

        assert config.config['cache_enabled'] == True
        assert config.config['timeout'] == 30

    def test_service_config_validation_no_class_or_interface(self):
        """测试服务配置验证：缺少必需字段"""
        with pytest.raises(ValueError, match='must have either'):
            ServiceConfig(
                name='test_service',
                lifecycle='singleton'
                # 缺少 class_path、interface+implementation、factory
            )

    def test_service_config_validation_invalid_lifecycle(self):
        """测试服务配置验证：无效的生命周期"""
        with pytest.raises(ValueError, match='Invalid lifecycle'):
            ServiceConfig(
                name='test_service',
                class_path='test.TestService',
                lifecycle='invalid_lifecycle'
            )

    def test_service_config_enabled_flag(self):
        """测试服务启用/禁用标志"""
        config = ServiceConfig(
            name='test_service',
            class_path='test.TestService',
            enabled=False
        )

        assert config.enabled == False


class TestRepositoryConfig:
    """测试 Repository 配置"""

    def test_repository_config_basic(self):
        """测试基础 Repository 配置"""
        config = RepositoryConfig(
            name='stock',
            interface='domain.ports.IStockRepository',
            implementation='adapters.StockORMRepository'
        )

        assert config.name == 'stock'
        assert config.interface == 'domain.ports.IStockRepository'
        assert config.implementation == 'adapters.StockORMRepository'

    def test_repository_config_to_service_config(self):
        """测试 Repository 配置转换为 Service 配置"""
        repo_config = RepositoryConfig(
            name='stock',
            interface='domain.ports.IStockRepository',
            implementation='adapters.StockORMRepository',
            lifecycle='singleton',
            config={'pool_size': 10}
        )

        service_config = repo_config.to_service_config()

        assert isinstance(service_config, ServiceConfig)
        assert service_config.name == 'stock'
        assert service_config.interface == 'domain.ports.IStockRepository'
        assert service_config.implementation == 'adapters.StockORMRepository'
        assert service_config.lifecycle == 'singleton'
        assert service_config.config['pool_size'] == 10


class TestEnvironmentConfig:
    """测试环境配置"""

    def test_environment_config_basic(self):
        """测试基础环境配置"""
        env_config = EnvironmentConfig(
            name='test',
            services={
                'test_service': ServiceConfig(
                    name='test_service',
                    class_path='test.TestService'
                )
            }
        )

        assert env_config.name == 'test'
        assert 'test_service' in env_config.services


class TestServicesConfig:
    """测试完整服务配置"""

    def test_services_config_basic(self):
        """测试基础服务配置"""
        config = ServicesConfig(
            version='1.0',
            description='Test config',
            services={
                'service_a': ServiceConfig(name='service_a', class_path='test.ServiceA')
            },
            repositories={
                'repo_a': RepositoryConfig(
                    name='repo_a',
                    interface='test.IRepoA',
                    implementation='test.RepoA'
                )
            }
        )

        assert config.version == '1.0'
        assert config.description == 'Test config'
        assert len(config.services) == 1
        assert len(config.repositories) == 1

    def test_get_merged_services_basic(self):
        """测试获取合并后的服务（基础）"""
        config = ServicesConfig(
            services={
                'service_a': ServiceConfig(name='service_a', class_path='test.ServiceA')
            },
            repositories={
                'repo_a': RepositoryConfig(
                    name='repo_a',
                    interface='test.IRepoA',
                    implementation='test.RepoA'
                )
            }
        )

        merged = config.get_merged_services()

        # services 直接包含
        assert 'service_a' in merged

        # repositories 转为 repositories.name
        assert 'repositories.repo_a' in merged

    def test_get_merged_services_with_environment(self):
        """测试获取合并后的服务（含环境覆盖）"""
        config = ServicesConfig(
            services={
                'service_a': ServiceConfig(
                    name='service_a',
                    class_path='test.ServiceA',
                    config={'debug': False}
                )
            },
            environments={
                'dev': EnvironmentConfig(
                    name='dev',
                    services={
                        'service_a': ServiceConfig(
                            name='service_a',
                            class_path='test.ServiceA',
                            config={'debug': True}  # 覆盖
                        )
                    }
                )
            },
            current_environment='dev'
        )

        merged = config.get_merged_services()
        service_a = merged['service_a']

        # 环境配置应该覆盖基础配置
        assert service_a.config['debug'] == True

    def test_config_merging_deep(self):
        """测试配置字典深度合并"""
        config = ServicesConfig(
            services={
                'service_a': ServiceConfig(
                    name='service_a',
                    class_path='test.ServiceA',
                    config={'cache': True, 'timeout': 30}
                )
            },
            environments={
                'prod': EnvironmentConfig(
                    name='prod',
                    services={
                        'service_a': ServiceConfig(
                            name='service_a',
                            class_path='test.ServiceA',
                            config={'timeout': 60}  # 只覆盖 timeout
                        )
                    }
                )
            },
            current_environment='prod'
        )

        merged = config.get_merged_services()
        service_a = merged['service_a']

        # cache 保留，timeout 被覆盖
        assert service_a.config['cache'] == True
        assert service_a.config['timeout'] == 60

    def test_disabled_services_filtered(self):
        """测试禁用的服务被过滤"""
        config = ServicesConfig(
            services={
                'service_a': ServiceConfig(
                    name='service_a',
                    class_path='test.ServiceA',
                    enabled=True
                ),
                'service_b': ServiceConfig(
                    name='service_b',
                    class_path='test.ServiceB',
                    enabled=False
                )
            }
        )

        merged = config.get_merged_services()

        assert 'service_a' in merged
        assert 'service_b' not in merged

    def test_get_service_method(self):
        """测试获取单个服务配置"""
        config = ServicesConfig(
            services={
                'service_a': ServiceConfig(name='service_a', class_path='test.ServiceA')
            }
        )

        service = config.get_service('service_a')
        assert service is not None
        assert service.name == 'service_a'

        # 不存在的服务
        assert config.get_service('non_existent') is None

    def test_list_services_method(self):
        """测试列出所有服务名称"""
        config = ServicesConfig(
            services={
                'service_a': ServiceConfig(name='service_a', class_path='test.ServiceA')
            },
            repositories={
                'repo_a': RepositoryConfig(
                    name='repo_a',
                    interface='test.IRepoA',
                    implementation='test.RepoA'
                )
            }
        )

        service_names = config.list_services()

        assert 'service_a' in service_names
        assert 'repositories.repo_a' in service_names

    def test_environment_repository_override(self):
        """测试环境配置覆盖 Repository"""
        config = ServicesConfig(
            repositories={
                'stock': RepositoryConfig(
                    name='stock',
                    interface='domain.ports.IStockRepository',
                    implementation='adapters.StockORMRepository'
                )
            },
            environments={
                'test': EnvironmentConfig(
                    name='test',
                    repositories={
                        'stock': RepositoryConfig(
                            name='stock',
                            interface='domain.ports.IStockRepository',
                            implementation='tests.mocks.MockStockRepository'
                        )
                    }
                )
            },
            current_environment='test'
        )

        merged = config.get_merged_services()
        stock_repo = merged['repositories.stock']

        # 测试环境应该使用 Mock
        assert stock_repo.implementation == 'tests.mocks.MockStockRepository'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
