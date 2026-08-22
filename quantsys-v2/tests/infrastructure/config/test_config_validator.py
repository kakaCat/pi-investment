"""测试配置验证器

P2-3: 测试配置验证逻辑
"""

import pytest
from infrastructure.config.validator import ConfigValidator, ValidationError
from infrastructure.config.models import ServiceConfig, ServicesConfig, RepositoryConfig


class TestValidationError:
    """测试验证错误类"""

    def test_validation_error_str(self):
        """测试验证错误字符串表示"""
        error = ValidationError(
            service_name='test_service',
            error_type='INVALID_DEPENDENCY',
            message='Dependency not found'
        )

        error_str = str(error)
        assert 'test_service' in error_str
        assert 'INVALID_DEPENDENCY' in error_str
        assert 'Dependency not found' in error_str


class TestConfigValidator:
    """测试配置验证器"""

    def test_validate_empty_config(self):
        """测试验证空配置"""
        config = ServicesConfig()
        validator = ConfigValidator(strict=False)

        errors = validator.validate(config)
        assert len(errors) == 0  # 空配置也是有效的

    def test_validate_simple_service(self):
        """测试验证简单服务"""
        config = ServicesConfig(
            services={
                'test_service': ServiceConfig(
                    name='test_service',
                    class_path='application.services.test.TestService',
                    lifecycle='singleton'
                )
            }
        )

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        # 非严格模式不检查类是否真实存在
        assert len(errors) == 0

    def test_validate_invalid_class_path_format(self):
        """测试验证无效的类路径格式"""
        config = ServicesConfig(
            services={
                'test_service': ServiceConfig(
                    name='test_service',
                    class_path='InvalidClassName',  # 没有模块路径
                    lifecycle='singleton'
                )
            }
        )

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        assert len(errors) > 0
        assert any('INVALID_CLASS_PATH' in e.error_type for e in errors)

    def test_validate_missing_dependency(self):
        """测试验证缺失的依赖"""
        config = ServicesConfig(
            services={
                'service_a': ServiceConfig(
                    name='service_a',
                    class_path='test.ServiceA',
                    dependencies={'dep': 'non_existent_service'}
                )
            }
        )

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        assert len(errors) > 0
        assert any('INVALID_DEPENDENCY' in e.error_type for e in errors)

    def test_validate_circular_dependency(self):
        """测试检测循环依赖"""
        config = ServicesConfig(
            services={
                'service_a': ServiceConfig(
                    name='service_a',
                    class_path='test.ServiceA',
                    dependencies={'b': 'service_b'}
                ),
                'service_b': ServiceConfig(
                    name='service_b',
                    class_path='test.ServiceB',
                    dependencies={'a': 'service_a'}
                )
            }
        )

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        assert len(errors) > 0
        assert any('CIRCULAR_DEPENDENCY' in e.error_type for e in errors)

    def test_validate_valid_dependencies(self):
        """测试验证有效的依赖"""
        config = ServicesConfig(
            services={
                'service_a': ServiceConfig(
                    name='service_a',
                    class_path='test.ServiceA',
                    dependencies={}
                ),
                'service_b': ServiceConfig(
                    name='service_b',
                    class_path='test.ServiceB',
                    dependencies={'a': 'service_a'}
                )
            }
        )

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        # 没有循环依赖，service_a 存在
        dependency_errors = [e for e in errors if 'DEPENDENCY' in e.error_type]
        assert len(dependency_errors) == 0

    def test_validate_repository_config(self):
        """测试验证 Repository 配置"""
        config = ServicesConfig(
            repositories={
                'stock': RepositoryConfig(
                    name='stock',
                    interface='domain.ports.IStockRepository',
                    implementation='adapters.repositories.StockORMRepository'
                )
            }
        )

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        assert len(errors) == 0


class TestStrictValidation:
    """测试严格模式验证"""

    def test_strict_mode_checks_imports(self):
        """测试严格模式检查类是否可导入"""
        config = ServicesConfig(
            services={
                'test_service': ServiceConfig(
                    name='test_service',
                    class_path='non.existent.module.TestService',
                    lifecycle='singleton'
                )
            }
        )

        validator = ConfigValidator(strict=True)
        errors = validator.validate(config)

        assert len(errors) > 0
        assert any('MODULE_NOT_FOUND' in e.error_type or 'CLASS_NOT_FOUND' in e.error_type for e in errors)

    def test_strict_mode_validates_real_classes(self):
        """测试严格模式验证真实的类

        注意：使用内置的 dict 类作为测试对象，避免依赖链问题
        """
        config = ServicesConfig(
            services={
                'dict_service': ServiceConfig(
                    name='dict_service',
                    class_path='builtins.dict',
                    lifecycle='singleton'
                )
            }
        )

        validator = ConfigValidator(strict=True)
        errors = validator.validate(config)

        # dict 是内置类，应该能够成功验证
        class_errors = [e for e in errors if 'MODULE_NOT_FOUND' in e.error_type or 'CLASS_NOT_FOUND' in e.error_type]
        assert len(class_errors) == 0


class TestFactoryValidation:
    """测试工厂函数验证"""

    def test_validate_factory_path_format(self):
        """测试验证工厂函数路径格式"""
        config = ServicesConfig(
            services={
                'test_service': ServiceConfig(
                    name='test_service',
                    class_path='test.TestService',
                    factory='InvalidFactory',  # 没有模块路径
                    lifecycle='singleton'
                )
            }
        )

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        assert len(errors) > 0
        assert any('INVALID_FACTORY_PATH' in e.error_type for e in errors)

    def test_validate_factory_exists_strict(self):
        """测试严格模式验证工厂函数存在"""
        config = ServicesConfig(
            services={
                'test_service': ServiceConfig(
                    name='test_service',
                    class_path='test.TestService',
                    factory='non.existent.create_test',
                    lifecycle='singleton'
                )
            }
        )

        validator = ConfigValidator(strict=True)
        errors = validator.validate(config)

        assert len(errors) > 0
        assert any('MODULE_NOT_FOUND' in e.error_type or 'FACTORY_NOT_FOUND' in e.error_type for e in errors)


class TestValidationReport:
    """测试验证报告"""

    def test_validate_and_report_success(self, capsys):
        """测试成功验证的报告"""
        config = ServicesConfig(
            services={
                'test_service': ServiceConfig(
                    name='test_service',
                    class_path='test.TestService',
                    lifecycle='singleton'
                )
            }
        )

        validator = ConfigValidator(strict=False)
        result = validator.validate_and_report(config)

        assert result == True

        captured = capsys.readouterr()
        assert '✅' in captured.out
        assert 'passed' in captured.out.lower()

    def test_validate_and_report_failure(self, capsys):
        """测试失败验证的报告"""
        config = ServicesConfig(
            services={
                'test_service': ServiceConfig(
                    name='test_service',
                    class_path='InvalidClassName',
                    lifecycle='singleton'
                )
            }
        )

        validator = ConfigValidator(strict=False)
        result = validator.validate_and_report(config)

        assert result == False

        captured = capsys.readouterr()
        assert '❌' in captured.out
        assert 'failed' in captured.out.lower()


class TestComplexDependencyGraph:
    """测试复杂依赖图"""

    def test_deep_dependency_chain(self):
        """测试深层依赖链"""
        config = ServicesConfig(
            services={
                'service_a': ServiceConfig(
                    name='service_a',
                    class_path='test.ServiceA',
                    dependencies={}
                ),
                'service_b': ServiceConfig(
                    name='service_b',
                    class_path='test.ServiceB',
                    dependencies={'a': 'service_a'}
                ),
                'service_c': ServiceConfig(
                    name='service_c',
                    class_path='test.ServiceC',
                    dependencies={'b': 'service_b'}
                ),
                'service_d': ServiceConfig(
                    name='service_d',
                    class_path='test.ServiceD',
                    dependencies={'c': 'service_c'}
                )
            }
        )

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        # 深层依赖链是有效的
        dependency_errors = [e for e in errors if 'CIRCULAR' in e.error_type]
        assert len(dependency_errors) == 0

    def test_multiple_dependencies(self):
        """测试多个依赖"""
        config = ServicesConfig(
            services={
                'repo_a': ServiceConfig(name='repo_a', class_path='test.RepoA'),
                'repo_b': ServiceConfig(name='repo_b', class_path='test.RepoB'),
                'service': ServiceConfig(
                    name='service',
                    class_path='test.Service',
                    dependencies={'a': 'repo_a', 'b': 'repo_b'}
                )
            }
        )

        validator = ConfigValidator(strict=False)
        errors = validator.validate(config)

        dependency_errors = [e for e in errors if 'DEPENDENCY' in e.error_type]
        assert len(dependency_errors) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
