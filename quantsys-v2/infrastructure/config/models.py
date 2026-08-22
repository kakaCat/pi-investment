"""配置数据模型

P2-3: 定义服务配置的数据结构
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List


class ServiceLifecycle(str, Enum):
    """服务生命周期"""
    SINGLETON = 'singleton'
    TRANSIENT = 'transient'
    SCOPED = 'scoped'


@dataclass
class ServiceConfig:
    """单个服务配置

    支持三种注册方式：
    1. 类路径：class_path
    2. 接口-实现：interface + implementation
    3. 工厂函数：factory

    示例：
        # 方式1：直接类路径
        ServiceConfig(
            name='chan_service',
            class_path='application.services.chan_service.ChanService',
            lifecycle='singleton',
            dependencies={'kline_repo': 'kline_repository'}
        )

        # 方式2：接口-实现
        ServiceConfig(
            name='stock_repository',
            interface='domain.ports.IStockRepository',
            implementation='adapters.outbound.repositories.StockORMRepository',
            lifecycle='singleton'
        )

        # 方式3：工厂函数
        ServiceConfig(
            name='data_service',
            class_path='application.services.data_service.DataService',
            factory='infrastructure.factories.create_data_service',
            lifecycle='singleton'
        )
    """
    name: str
    class_path: Optional[str] = None
    interface: Optional[str] = None
    implementation: Optional[str] = None
    factory: Optional[str] = None
    lifecycle: str = 'singleton'
    dependencies: Dict[str, str] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    description: Optional[str] = None

    def __post_init__(self):
        """验证配置一致性"""
        # 至少需要 class_path 或 (interface + implementation) 或 factory
        has_class = self.class_path is not None
        has_interface = self.interface is not None and self.implementation is not None
        has_factory = self.factory is not None

        if not (has_class or has_interface or has_factory):
            raise ValueError(
                f"Service '{self.name}' must have either:\n"
                f"  - class_path, or\n"
                f"  - interface + implementation, or\n"
                f"  - factory"
            )

        # 验证生命周期
        try:
            ServiceLifecycle(self.lifecycle)
        except ValueError:
            valid_values = [lc.value for lc in ServiceLifecycle]
            raise ValueError(
                f"Invalid lifecycle '{self.lifecycle}' for service '{self.name}'. "
                f"Valid values: {valid_values}"
            )


@dataclass
class RepositoryConfig:
    """Repository 配置（语法糖）"""
    name: str
    interface: str
    implementation: str
    lifecycle: str = 'singleton'
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    description: Optional[str] = None

    def to_service_config(self) -> ServiceConfig:
        """转换为 ServiceConfig"""
        return ServiceConfig(
            name=self.name,
            interface=self.interface,
            implementation=self.implementation,
            lifecycle=self.lifecycle,
            config=self.config,
            enabled=self.enabled,
            description=self.description
        )


@dataclass
class EnvironmentConfig:
    """环境特定配置"""
    name: str  # dev, test, prod
    services: Dict[str, ServiceConfig] = field(default_factory=dict)
    repositories: Dict[str, RepositoryConfig] = field(default_factory=dict)


@dataclass
class ServicesConfig:
    """完整服务配置

    结构：
        version: 配置版本
        description: 配置描述
        services: 服务配置映射
        repositories: Repository 配置映射（会转换为 services）
        environments: 环境特定配置
        current_environment: 当前环境
        env_var_overrides: 环境变量覆盖（service_name -> {config_key: value}）
    """
    version: str = '1.0'
    description: str = ''
    services: Dict[str, ServiceConfig] = field(default_factory=dict)
    repositories: Dict[str, RepositoryConfig] = field(default_factory=dict)
    environments: Dict[str, EnvironmentConfig] = field(default_factory=dict)
    current_environment: str = 'dev'
    env_var_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def get_merged_services(self) -> Dict[str, ServiceConfig]:
        """获取合并后的服务配置

        合并顺序：
        1. 基础 services
        2. 基础 repositories（转为 services）
        3. 环境特定 services 覆盖
        4. 环境特定 repositories 覆盖

        Returns:
            完整的服务配置字典

        注意：环境变量覆盖已经在 loader 中应用到基础配置，会自动传递到合并结果
        """
        merged = {}

        # 1. 添加基础 services（深拷贝以避免修改原始配置）
        import copy
        for name, service in self.services.items():
            merged[name] = copy.deepcopy(service)

        # 2. 添加基础 repositories（转为 services，使用 repositories.name 作为 key）
        for repo_name, repo_config in self.repositories.items():
            service_name = f'repositories.{repo_name}'
            merged[service_name] = repo_config.to_service_config()

        # 3. 应用环境特定配置
        if self.current_environment in self.environments:
            env_config = self.environments[self.current_environment]

            # 环境 services 覆盖
            for service_name, service_config in env_config.services.items():
                if service_name in merged:
                    # 合并配置（环境配置优先）
                    base = merged[service_name]

                    # 如果环境配置是部分配置（占位符），只合并 config 和 enabled
                    if service_config.class_path == '_partial_config_placeholder':
                        merged[service_name] = ServiceConfig(
                            name=base.name,
                            class_path=base.class_path,
                            interface=base.interface,
                            implementation=base.implementation,
                            factory=base.factory,
                            lifecycle=base.lifecycle,
                            dependencies=base.dependencies,
                            config={**base.config, **service_config.config},
                            enabled=service_config.enabled,
                            description=base.description
                        )
                    else:
                        # 完整覆盖
                        merged[service_name] = ServiceConfig(
                            name=service_config.name or base.name,
                            class_path=service_config.class_path or base.class_path,
                            interface=service_config.interface or base.interface,
                            implementation=service_config.implementation or base.implementation,
                            factory=service_config.factory or base.factory,
                            lifecycle=service_config.lifecycle or base.lifecycle,
                            dependencies={**base.dependencies, **service_config.dependencies},
                            config={**base.config, **service_config.config},
                            enabled=service_config.enabled,
                            description=service_config.description or base.description
                        )
                else:
                    # 新服务（只有在不是占位符时才添加）
                    if service_config.class_path != '_partial_config_placeholder':
                        merged[service_name] = service_config

            # 环境 repositories 覆盖
            for repo_name, repo_config in env_config.repositories.items():
                service_name = f'repositories.{repo_name}'
                if service_name in merged:
                    # 合并配置
                    base = merged[service_name]
                    new_service = repo_config.to_service_config()

                    # 如果环境配置是部分配置（占位符），只覆盖提供的字段
                    interface = new_service.interface if new_service.interface != '_partial_placeholder' else base.interface
                    implementation = new_service.implementation if new_service.implementation != '_partial_placeholder' else base.implementation

                    merged[service_name] = ServiceConfig(
                        name=new_service.name or base.name,
                        interface=interface,
                        implementation=implementation,
                        lifecycle=new_service.lifecycle if new_service.lifecycle != 'singleton' else base.lifecycle,
                        config={**base.config, **new_service.config},
                        enabled=new_service.enabled,
                        description=new_service.description or base.description
                    )
                else:
                    # 新 repository（只有在不是占位符时才添加）
                    if repo_config.interface != '_partial_placeholder' and repo_config.implementation != '_partial_placeholder':
                        merged[service_name] = repo_config.to_service_config()

        # 过滤禁用的服务
        result = {k: v for k, v in merged.items() if v.enabled}

        # 4. 应用环境变量覆盖（最高优先级）
        for service_name, overrides in self.env_var_overrides.items():
            if service_name in result:
                # 更新 config 字典
                result[service_name].config.update(overrides)

        return result

    def get_service(self, name: str) -> Optional[ServiceConfig]:
        """获取服务配置（含环境合并）"""
        merged = self.get_merged_services()
        return merged.get(name)

    def list_services(self) -> List[str]:
        """列出所有服务名称"""
        return list(self.get_merged_services().keys())
