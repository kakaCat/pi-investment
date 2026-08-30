"""
依赖注入装饰器

提供便捷的依赖注入装饰器，简化路由中的服务获取。
"""
import functools
import inspect
from typing import Callable

from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory


def inject(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        sig = inspect.signature(func)

        for param_name in sig.parameters:
            if param_name in kwargs:
                continue

            if EnhancedServiceFactory.is_registered(param_name):
                kwargs[param_name] = EnhancedServiceFactory.resolve(param_name)

        return func(*args, **kwargs)

    return wrapper


def inject_service(service_name: str):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if EnhancedServiceFactory.is_registered(service_name):
                kwargs['service'] = EnhancedServiceFactory.resolve(service_name)
            else:
                raise AttributeError(f"Service '{service_name}' not found in factory")

            return func(*args, **kwargs)

        return wrapper
    return decorator
