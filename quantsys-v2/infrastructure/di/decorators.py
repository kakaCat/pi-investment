"""
Flask 依赖注入装饰器

提供便捷的依赖注入装饰器，简化路由中的服务获取。

使用方法:
    from infrastructure.di.decorators import inject

    @bp.route('/api/pools')
    @inject
    def list_pools(stock_pool_service):
        # stock_pool_service 自动注入
        pools = stock_pool_service.list_pools()
        return {'data': pools}
"""
import functools
import inspect
from typing import Callable

from flask import current_app


def inject(func: Callable) -> Callable:
    """
    依赖注入装饰器

    自动从容器中注入函数参数：
    - 参数名与容器中的服务名匹配时，自动注入该服务
    - 不匹配的参数保持原样（如 path 参数、query 参数）

    Example:
        @bp.route('/api/pools/<int:pool_id>')
        @inject
        def get_pool(pool_id, stock_pool_service):
            # pool_id 从路由参数获取
            # stock_pool_service 从容器自动注入
            pool = stock_pool_service.get_pool(pool_id)
            return {'data': pool}
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 获取容器
        container = current_app.container

        # 获取函数签名
        sig = inspect.signature(func)

        # 遍历参数，尝试从容器注入
        for param_name in sig.parameters:
            # 如果参数已经在 kwargs 中（来自路由或请求），跳过
            if param_name in kwargs:
                continue

            # 尝试从容器获取服务
            if hasattr(container, param_name):
                service_provider = getattr(container, param_name)
                kwargs[param_name] = service_provider()

        return func(*args, **kwargs)

    return wrapper


def inject_service(service_name: str):
    """
    注入指定服务的装饰器（显式指定）

    Args:
        service_name: 容器中的服务名称

    Example:
        @bp.route('/api/pools')
        @inject_service('stock_pool_service')
        def list_pools(service):
            pools = service.list_pools()
            return {'data': pools}
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            container = current_app.container

            if hasattr(container, service_name):
                service_provider = getattr(container, service_name)
                kwargs['service'] = service_provider()
            else:
                raise AttributeError(f"Service '{service_name}' not found in container")

            return func(*args, **kwargs)

        return wrapper
    return decorator
