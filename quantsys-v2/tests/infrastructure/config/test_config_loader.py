"""测试配置加载器

P2-3: 测试 YAML 配置加载和环境变量覆盖
"""

import pytest
import os
from pathlib import Path
import tempfile
import yaml

from infrastructure.config.loader import ConfigLoader, load_config
from infrastructure.config.models import ServicesConfig


class TestConfigLoader:
    """测试配置加载器核心功能"""

    def test_default_config_dir_detection(self):
        """测试自动检测配置目录"""
        loader = ConfigLoader()
        assert loader.config_dir.exists()
        assert (loader.config_dir / 'services.yaml').exists()

    def test_environment_detection(self):
        """测试环境检测"""
        loader = ConfigLoader()

        # 默认环境
        env = loader._detect_environment()
        assert env in ['dev', 'test', 'prod']

    def test_environment_variable_override(self):
        """测试环境变量设置环境"""
        loader = ConfigLoader()

        # 设置环境变量
        os.environ['QUANTSYS_ENV'] = 'test'
        try:
            env = loader._detect_environment()
            assert env == 'test'
        finally:
            del os.environ['QUANTSYS_ENV']

    def test_load_base_config(self):
        """测试加载基础配置文件"""
        loader = ConfigLoader()
        config = loader.load(environment='dev')

        assert isinstance(config, ServicesConfig)
        assert config.version is not None
        assert len(config.services) > 0 or len(config.repositories) > 0

    def test_load_with_environment(self):
        """测试加载特定环境配置"""
        loader = ConfigLoader()

        # 加载测试环境
        test_config = loader.load(environment='test')
        assert test_config.current_environment == 'test'

        # 加载生产环境
        prod_config = loader.load(environment='prod')
        assert prod_config.current_environment == 'prod'

    def test_environment_config_merging(self):
        """测试环境配置合并"""
        loader = ConfigLoader()
        config = loader.load(environment='test')

        # 测试环境应该覆盖基础配置
        services = config.get_merged_services()

        # 检查测试环境的 Mock 仓库
        if 'repositories.stock' in services:
            stock_repo = services['repositories.stock']
            # 测试环境使用 Mock
            assert 'Mock' in stock_repo.implementation or stock_repo.implementation == 'tests.mocks.MockStockRepository'

    def test_missing_config_file_error(self):
        """测试配置文件不存在时抛出异常"""
        # 创建一个不存在的配置目录
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(config_dir=Path(tmpdir))

            with pytest.raises(FileNotFoundError):
                loader.load()

    def test_validate_config_file(self):
        """测试配置文件格式验证"""
        loader = ConfigLoader()

        is_valid, errors = loader.validate_config_file()
        assert is_valid
        assert len(errors) == 0


class TestEnvironmentVariableOverride:
    """测试环境变量覆盖配置"""

    def test_apply_env_overrides(self):
        """测试应用环境变量覆盖"""
        # 设置环境变量
        os.environ['QUANTSYS_SERVICE_data_service_cache_enabled'] = 'false'
        os.environ['QUANTSYS_SERVICE_watch_engine_check_interval'] = '120'

        try:
            loader = ConfigLoader()
            config = loader.load(environment='dev')

            services = config.get_merged_services()
            data_service = services.get('data_service')

            # 环境变量应该覆盖配置
            if data_service:
                assert data_service.config.get('cache_enabled') == False
        finally:
            # 清理环境变量
            if 'QUANTSYS_SERVICE_data_service_cache_enabled' in os.environ:
                del os.environ['QUANTSYS_SERVICE_data_service_cache_enabled']
            if 'QUANTSYS_SERVICE_watch_engine_check_interval' in os.environ:
                del os.environ['QUANTSYS_SERVICE_watch_engine_check_interval']

    def test_parse_env_value_types(self):
        """测试环境变量值类型解析"""
        loader = ConfigLoader()

        # bool
        assert loader._parse_env_value('true') == True
        assert loader._parse_env_value('false') == False
        assert loader._parse_env_value('yes') == True
        assert loader._parse_env_value('no') == False

        # int
        assert loader._parse_env_value('123') == 123
        assert loader._parse_env_value('-456') == -456

        # float
        assert loader._parse_env_value('3.14') == 3.14
        assert loader._parse_env_value('-2.5') == -2.5

        # str
        assert loader._parse_env_value('hello') == 'hello'


class TestGlobalLoader:
    """测试全局加载器函数"""

    def test_get_default_loader_singleton(self):
        """测试默认加载器是单例"""
        from infrastructure.config.loader import get_default_loader

        loader1 = get_default_loader()
        loader2 = get_default_loader()

        assert loader1 is loader2

    def test_load_config_shortcut(self):
        """测试快捷加载函数"""
        config = load_config(environment='dev')

        assert isinstance(config, ServicesConfig)
        assert config.current_environment == 'dev'


class TestInvalidConfigHandling:
    """测试无效配置处理"""

    def test_invalid_yaml_syntax(self):
        """测试 YAML 语法错误处理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / 'services.yaml'

            # 写入无效的 YAML
            with open(config_file, 'w') as f:
                f.write("invalid: yaml: syntax:\n  - unclosed")

            loader = ConfigLoader(config_dir=config_dir)

            with pytest.raises(ValueError, match='Invalid YAML'):
                loader.load()

    def test_missing_required_fields(self):
        """测试缺少必需字段"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / 'services.yaml'

            # 写入缺少必需字段的配置
            config_data = {
                'version': '1.0',
                # 缺少 services 或 repositories
            }

            with open(config_file, 'w') as f:
                yaml.dump(config_data, f)

            loader = ConfigLoader(config_dir=config_dir)

            is_valid, errors = loader.validate_config_file()
            assert not is_valid
            assert any('services' in err.lower() or 'repositories' in err.lower() for err in errors)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
