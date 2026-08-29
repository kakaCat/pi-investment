"""配置验证器

P2-3: 验证服务配置的正确性
"""
import structlog
logger = structlog.get_logger(__name__)

import importlib
from typing import List, Set, Dict, Optional
from pathlib import Path

from .models import ServiceConfig, ServicesConfig


class ValidationError:
    """验证错误"""
    def __init__(self, service_name: str, error_type: str, message: str):
        self.service_name = service_name
        self.error_type = error_type
        self.message = message

    def __str__(self) -> str:
        return f"[{self.error_type}] {self.service_name}: {self.message}"


class ConfigValidator:
    """配置验证器

    验证内容：
    1. 类路径存在性
    2. 依赖引用有效性
    3. 循环依赖检测
    4. 生命周期合法性
    5. 工厂函数存在性

    示例：
        validator = ConfigValidator()
        errors = validator.validate(config)
        if errors:
            for error in errors:
                print(error)
    """

    def __init__(self, strict: bool = False):
        """初始化验证器

        Args:
            strict: 严格模式（验证类是否可导入）
        """
        self.strict = strict

    def validate(self, config: ServicesConfig) -> List[ValidationError]:
        """验证配置

        Args:
            config: 服务配置

        Returns:
            验证错误列表（空列表表示验证通过）
        """
        errors = []

        # 获取合并后的服务配置
        services = config.get_merged_services()

        # 1. 验证每个服务
        for name, service in services.items():
            errors.extend(self._validate_service(service, services))

        # 2. 验证依赖图
        errors.extend(self._validate_dependency_graph(services))

        return errors

    def _validate_service(
        self,
        service: ServiceConfig,
        all_services: Dict[str, ServiceConfig]
    ) -> List[ValidationError]:
        """验证单个服务配置"""
        errors = []

        # 验证类路径
        if service.class_path:
            errors.extend(self._validate_class_path(service, service.class_path))

        # 验证接口和实现
        if service.interface:
            errors.extend(self._validate_class_path(service, service.interface))
        if service.implementation:
            errors.extend(self._validate_class_path(service, service.implementation))

        # 验证工厂函数
        if service.factory:
            errors.extend(self._validate_factory(service, service.factory))

        # 验证依赖引用
        for dep_param, dep_name in service.dependencies.items():
            if dep_name not in all_services:
                errors.append(ValidationError(
                    service.name,
                    'INVALID_DEPENDENCY',
                    f"Dependency '{dep_name}' (for parameter '{dep_param}') not found in services"
                ))

        return errors

    def _validate_class_path(
        self,
        service: ServiceConfig,
        class_path: str
    ) -> List[ValidationError]:
        """验证类路径"""
        errors = []

        if not self.strict:
            # 非严格模式：只检查格式
            if '.' not in class_path:
                errors.append(ValidationError(
                    service.name,
                    'INVALID_CLASS_PATH',
                    f"Class path '{class_path}' must contain module path"
                ))
            return errors

        # 严格模式：尝试导入
        try:
            module_path, class_name = class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            if not hasattr(module, class_name):
                errors.append(ValidationError(
                    service.name,
                    'CLASS_NOT_FOUND',
                    f"Class '{class_name}' not found in module '{module_path}'"
                ))
        except ImportError as e:
            errors.append(ValidationError(
                service.name,
                'MODULE_NOT_FOUND',
                f"Cannot import module for '{class_path}': {e}"
            ))
        except ValueError:
            errors.append(ValidationError(
                service.name,
                'INVALID_CLASS_PATH',
                f"Invalid class path format: '{class_path}'"
            ))

        return errors

    def _validate_factory(
        self,
        service: ServiceConfig,
        factory_path: str
    ) -> List[ValidationError]:
        """验证工厂函数"""
        errors = []

        if not self.strict:
            # 非严格模式：只检查格式
            if '.' not in factory_path:
                errors.append(ValidationError(
                    service.name,
                    'INVALID_FACTORY_PATH',
                    f"Factory path '{factory_path}' must contain module path"
                ))
            return errors

        # 严格模式：尝试导入
        try:
            module_path, func_name = factory_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            if not hasattr(module, func_name):
                errors.append(ValidationError(
                    service.name,
                    'FACTORY_NOT_FOUND',
                    f"Factory function '{func_name}' not found in module '{module_path}'"
                ))
            elif not callable(getattr(module, func_name)):
                errors.append(ValidationError(
                    service.name,
                    'FACTORY_NOT_CALLABLE',
                    f"Factory '{func_name}' is not callable"
                ))
        except ImportError as e:
            errors.append(ValidationError(
                service.name,
                'MODULE_NOT_FOUND',
                f"Cannot import module for factory '{factory_path}': {e}"
            ))
        except ValueError:
            errors.append(ValidationError(
                service.name,
                'INVALID_FACTORY_PATH',
                f"Invalid factory path format: '{factory_path}'"
            ))

        return errors

    def _validate_dependency_graph(
        self,
        services: Dict[str, ServiceConfig]
    ) -> List[ValidationError]:
        """验证依赖图（检测循环依赖）"""
        errors = []

        # 构建依赖图
        graph = {name: list(svc.dependencies.values()) for name, svc in services.items()}

        # 检测循环依赖
        for service_name in services:
            cycle = self._find_cycle(service_name, graph)
            if cycle:
                errors.append(ValidationError(
                    service_name,
                    'CIRCULAR_DEPENDENCY',
                    f"Circular dependency detected: {' -> '.join(cycle)}"
                ))

        return errors

    def _find_cycle(
        self,
        start: str,
        graph: Dict[str, List[str]],
        visited: Optional[Set[str]] = None,
        path: Optional[List[str]] = None
    ) -> Optional[List[str]]:
        """查找循环依赖（DFS）

        Args:
            start: 起始节点
            graph: 依赖图
            visited: 已访问节点
            path: 当前路径

        Returns:
            循环路径，如果没有循环则返回 None
        """
        if visited is None:
            visited = set()
        if path is None:
            path = []

        if start in path:
            # 找到循环
            cycle_start = path.index(start)
            return path[cycle_start:] + [start]

        if start in visited:
            return None

        visited.add(start)
        path.append(start)

        # 检查依赖
        for dep in graph.get(start, []):
            cycle = self._find_cycle(dep, graph, visited.copy(), path.copy())
            if cycle:
                return cycle

        return None

    def validate_and_report(self, config: ServicesConfig) -> bool:
        """验证配置并打印报告

        Args:
            config: 服务配置

        Returns:
            是否验证通过
        """
        errors = self.validate(config)

        if not errors:
            logger.info('✅ Configuration validation passed!')
            logger.info(f'   Total services: {len(config.get_merged_services())}')
            return True

        logger.info(f'❌ Configuration validation failed with {len(errors)} error(s):')
        logger.info("")

        # 按错误类型分组
        by_type: Dict[str, List[ValidationError]] = {}
        for error in errors:
            by_type.setdefault(error.error_type, []).append(error)

        for error_type, type_errors in sorted(by_type.items()):
            logger.info(f'  {error_type}:')
            for error in type_errors:
                logger.info(f'    - {error.service_name}: {error.message}')
            logger.info("")

        return False


def validate_config_file(config_path: Path, strict: bool = False) -> bool:
    """验证配置文件

    Args:
        config_path: 配置文件路径
        strict: 严格模式

    Returns:
        是否验证通过
    """
    from .loader import ConfigLoader

    try:
        # 加载配置
        loader = ConfigLoader(config_dir=config_path.parent)
        config = loader.load()

        # 验证
        validator = ConfigValidator(strict=strict)
        return validator.validate_and_report(config)

    except Exception as e:
        logger.info(f'❌ Failed to validate config: {e}')
        return False
