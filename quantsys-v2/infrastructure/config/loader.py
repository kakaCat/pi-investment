"""配置加载器

P2-3: 从 YAML 文件加载服务配置
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

from .models import (
    ServiceConfig,
    RepositoryConfig,
    EnvironmentConfig,
    ServicesConfig,
    ServiceLifecycle
)


class ConfigLoader:
    """配置加载器

    加载优先级：
    1. 基础配置文件（config/services.yaml）
    2. 环境特定配置（config/services.{env}.yaml）
    3. 环境变量覆盖

    示例：
        loader = ConfigLoader()
        config = loader.load()  # 自动检测环境

        # 或指定环境
        config = loader.load(environment='test')
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """初始化加载器

        Args:
            config_dir: 配置目录，默认为 quantsys-v2/config
        """
        if config_dir is None:
            # 自动检测配置目录
            current_file = Path(__file__)
            quantsys_root = current_file.parent.parent.parent
            config_dir = quantsys_root / 'config'

        self.config_dir = Path(config_dir)
        self.base_config_file = self.config_dir / 'services.yaml'

    def load(self, environment: Optional[str] = None) -> ServicesConfig:
        """加载服务配置

        Args:
            environment: 环境名称（dev/test/prod），默认从环境变量读取

        Returns:
            完整的服务配置

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置格式错误
        """
        # 1. 检测环境
        if environment is None:
            environment = self._detect_environment()

        # 2. 加载基础配置
        if not self.base_config_file.exists():
            raise FileNotFoundError(
                f"Base config file not found: {self.base_config_file}\n"
                f"Please create it or check the config directory."
            )

        base_config = self._load_yaml(self.base_config_file)

        # 3. 加载环境特定配置
        env_config_file = self.config_dir / f'services.{environment}.yaml'
        env_config = {}
        if env_config_file.exists():
            env_config = self._load_yaml(env_config_file)

        # 4. 解析配置
        services_config = self._parse_config(base_config, env_config, environment)

        # 5. 收集环境变量覆盖（传递配置以便查找已知服务名）
        env_var_overrides = self._collect_env_overrides(services_config)
        services_config.env_var_overrides = env_var_overrides

        return services_config

    def _detect_environment(self) -> str:
        """检测当前环境

        优先级：
        1. QUANTSYS_ENV 环境变量
        2. PYTHON_ENV 环境变量
        3. 默认 'dev'
        """
        return os.environ.get('QUANTSYS_ENV') or \
               os.environ.get('PYTHON_ENV') or \
               'dev'

    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """加载 YAML 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}")
        except Exception as e:
            raise IOError(f"Failed to load {file_path}: {e}")

    def _parse_config(
        self,
        base_config: Dict[str, Any],
        env_config: Dict[str, Any],
        environment: str
    ) -> ServicesConfig:
        """解析配置字典为配置对象

        Args:
            base_config: 基础配置字典
            env_config: 环境特定配置字典
            environment: 当前环境

        Returns:
            ServicesConfig 对象
        """
        # 解析基础配置
        version = base_config.get('version', '1.0')
        description = base_config.get('description', '')

        # 解析 services
        services = {}
        for name, cfg in base_config.get('services', {}).items():
            services[name] = self._parse_service_config(name, cfg)

        # 解析 repositories
        repositories = {}
        for name, cfg in base_config.get('repositories', {}).items():
            repositories[name] = self._parse_repository_config(name, cfg)

        # 解析环境配置
        environments = {}

        # 从 base_config.environments 解析
        for env_name, env_cfg in base_config.get('environments', {}).items():
            environments[env_name] = self._parse_environment_config(env_name, env_cfg)

        # 合并当前环境的配置文件
        if env_config:
            current_env_config = self._parse_environment_config(environment, env_config)
            if environment in environments:
                # 合并
                existing = environments[environment]
                existing.services.update(current_env_config.services)
                existing.repositories.update(current_env_config.repositories)
            else:
                environments[environment] = current_env_config

        return ServicesConfig(
            version=version,
            description=description,
            services=services,
            repositories=repositories,
            environments=environments,
            current_environment=environment
        )

    def _parse_service_config(self, name: str, cfg: Dict[str, Any], partial: bool = False) -> ServiceConfig:
        """解析单个服务配置

        Args:
            name: 服务名称
            cfg: 配置字典
            partial: 是否允许部分配置（用于环境覆盖）
        """
        # 如果是部分配置且没有提供必需字段，创建一个最小的配置对象
        # 注意：这个对象会在后续合并时被完整配置覆盖
        if partial and not any(k in cfg for k in ['class', 'interface', 'implementation', 'factory']):
            # 环境配置只有 config/enabled 等字段，提供一个虚拟的 class_path
            # 这个对象不会单独使用，只用于合并
            return ServiceConfig(
                name=name,
                class_path='_partial_config_placeholder',  # 占位符
                lifecycle=cfg.get('lifecycle', 'singleton'),
                dependencies=cfg.get('dependencies', {}),
                config=cfg.get('config', {}),
                enabled=cfg.get('enabled', True),
                description=cfg.get('description')
            )

        return ServiceConfig(
            name=name,
            class_path=cfg.get('class'),
            interface=cfg.get('interface'),
            implementation=cfg.get('implementation'),
            factory=cfg.get('factory'),
            lifecycle=cfg.get('lifecycle', 'singleton'),
            dependencies=cfg.get('dependencies', {}),
            config=cfg.get('config', {}),
            enabled=cfg.get('enabled', True),
            description=cfg.get('description')
        )

    def _parse_repository_config(self, name: str, cfg: Dict[str, Any], partial: bool = False) -> RepositoryConfig:
        """解析单个 Repository 配置

        Args:
            name: Repository 名称
            cfg: 配置字典
            partial: 是否允许部分配置（用于环境覆盖）
        """
        # 如果是部分配置且缺少必需字段，创建一个占位符
        if partial and ('interface' not in cfg or 'implementation' not in cfg):
            return RepositoryConfig(
                name=name,
                interface=cfg.get('interface', '_partial_placeholder'),
                implementation=cfg.get('implementation', '_partial_placeholder'),
                lifecycle=cfg.get('lifecycle', 'singleton'),
                config=cfg.get('config', {}),
                enabled=cfg.get('enabled', True),
                description=cfg.get('description')
            )

        # 检查是否有必需字段
        if 'interface' not in cfg or 'implementation' not in cfg:
            raise ValueError(
                f"Repository '{name}' must have both 'interface' and 'implementation' fields"
            )

        return RepositoryConfig(
            name=name,
            interface=cfg['interface'],
            implementation=cfg['implementation'],
            lifecycle=cfg.get('lifecycle', 'singleton'),
            config=cfg.get('config', {}),
            enabled=cfg.get('enabled', True),
            description=cfg.get('description')
        )

    def _parse_environment_config(self, env_name: str, cfg: Dict[str, Any]) -> EnvironmentConfig:
        """解析环境配置"""
        services = {}
        for name, service_cfg in cfg.get('services', {}).items():
            services[name] = self._parse_service_config(name, service_cfg, partial=True)

        repositories = {}
        for name, repo_cfg in cfg.get('repositories', {}).items():
            repositories[name] = self._parse_repository_config(name, repo_cfg, partial=True)

        return EnvironmentConfig(
            name=env_name,
            services=services,
            repositories=repositories
        )

    def _collect_env_overrides(self, config: ServicesConfig) -> Dict[str, Dict[str, Any]]:
        """收集环境变量覆盖

        返回格式：{service_name: {config_key: value}}

        环境变量格式：QUANTSYS_SERVICE_<service_name>_<config_key>=value

        注意：由于服务名称和配置键都可能包含下划线，我们需要智能解析。
        策略：尝试匹配已知的服务名（从 services 和 repositories）。

        Args:
            config: 已解析的配置对象，用于获取已知服务名
        """
        prefix = 'QUANTSYS_SERVICE_'
        overrides = {}

        # 获取所有已知的服务名（services + repositories）
        known_service_names = set(config.services.keys())
        known_service_names.update(config.repositories.keys())

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            # 移除前缀并转小写
            rest = key[len(prefix):].lower()
            parts = rest.split('_')

            # 尝试不同长度的服务名前缀，优先匹配已知服务名
            found = False
            for i in range(len(parts) - 1, 0, -1):
                potential_service_name = '_'.join(parts[:i])
                potential_config_key = '_'.join(parts[i:])

                # 检查是否是已知的服务名
                if potential_service_name in known_service_names:
                    if potential_service_name not in overrides:
                        overrides[potential_service_name] = {}
                    overrides[potential_service_name][potential_config_key] = self._parse_env_value(value)
                    found = True
                    break

            # 如果没有匹配到已知服务名，使用最短的服务名（最后一个下划线分隔）
            # 例如：data_service_cache_enabled -> data_service + cache_enabled
            if not found and len(parts) >= 2:
                service_name = '_'.join(parts[:-1])
                config_key = parts[-1]
                if service_name not in overrides:
                    overrides[service_name] = {}
                overrides[service_name][config_key] = self._parse_env_value(value)

        return overrides

    def _apply_env_overrides(self, config: ServicesConfig):
        """应用环境变量覆盖

        环境变量格式：
        QUANTSYS_SERVICE_<service_name>_<config_key>=value

        示例：
        QUANTSYS_SERVICE_data_service_cache_enabled=false

        注意：环境变量覆盖直接修改 config 对象中的服务配置

        DEPRECATED: 此方法已弃用，使用 env_var_overrides 字段代替
        """
        prefix = 'QUANTSYS_SERVICE_'

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            # 解析环境变量
            parts = key[len(prefix):].lower().split('_', 1)
            if len(parts) != 2:
                continue

            service_name, config_key = parts

            # 查找服务（在基础 services 中）
            if service_name in config.services:
                # 直接修改基础配置
                config.services[service_name].config[config_key] = self._parse_env_value(value)
            # 也检查 repositories
            elif service_name in config.repositories:
                config.repositories[service_name].config[config_key] = self._parse_env_value(value)

    def _parse_env_value(self, value: str) -> Any:
        """解析环境变量值

        支持类型：
        - bool: true/false
        - int: 数字
        - float: 小数
        - str: 其他
        """
        # bool
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False

        # int
        try:
            return int(value)
        except ValueError:
            pass

        # float
        try:
            return float(value)
        except ValueError:
            pass

        # str
        return value

    def validate_config_file(self, config_file: Optional[Path] = None) -> tuple[bool, list[str]]:
        """验证配置文件格式

        Args:
            config_file: 配置文件路径，默认为基础配置文件

        Returns:
            (是否有效, 错误信息列表)
        """
        if config_file is None:
            config_file = self.base_config_file

        errors = []

        # 检查文件存在
        if not config_file.exists():
            errors.append(f"Config file not found: {config_file}")
            return False, errors

        # 尝试加载
        try:
            config_data = self._load_yaml(config_file)
        except Exception as e:
            errors.append(f"Failed to load YAML: {e}")
            return False, errors

        # 验证必需字段
        if 'services' not in config_data and 'repositories' not in config_data:
            errors.append("Config must have 'services' or 'repositories' section")

        # 验证 services
        for name, cfg in config_data.get('services', {}).items():
            try:
                self._parse_service_config(name, cfg)
            except Exception as e:
                errors.append(f"Invalid service '{name}': {e}")

        # 验证 repositories
        for name, cfg in config_data.get('repositories', {}).items():
            if 'interface' not in cfg:
                errors.append(f"Repository '{name}' missing 'interface'")
            if 'implementation' not in cfg:
                errors.append(f"Repository '{name}' missing 'implementation'")

        return len(errors) == 0, errors


# 全局加载器实例
_default_loader: Optional[ConfigLoader] = None


def get_default_loader() -> ConfigLoader:
    """获取默认配置加载器（单例）"""
    global _default_loader
    if _default_loader is None:
        _default_loader = ConfigLoader()
    return _default_loader


def load_config(environment: Optional[str] = None) -> ServicesConfig:
    """快捷函数：加载配置"""
    return get_default_loader().load(environment)
