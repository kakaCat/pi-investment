"""
API 装饰器 - 统一参数验证、错误处理、响应格式化
"""
import functools
import logging
from typing import Callable, Any, Dict, List, Optional

from flask import request, jsonify

from .validators import ValidationError
from .response_builder import success_response, error_response

logger = logging.getLogger(__name__)


def validate_params(schema: Dict[str, Dict[str, Any]]):
    """参数验证装饰器

    Args:
        schema: 参数验证规则
            {
                'param_name': {
                    'type': str|int|float|list|dict,
                    'required': bool,
                    'default': Any,
                    'validator': Callable,  # 自定义验证函数
                    'min': int|float,       # 数值最小值
                    'max': int|float,       # 数值最大值
                    'min_length': int,      # 字符串/列表最小长度
                    'max_length': int,      # 字符串/列表最大长度
                    'choices': List,        # 枚举值
                    'source': 'args'|'json'|'path'  # 参数来源，默认自动检测
                }
            }

    Example:
        @validate_params({
            'symbol': {'type': str, 'required': True, 'validator': validate_stock_symbol},
            'start_date': {'type': str, 'required': True, 'validator': validate_date},
            'limit': {'type': int, 'default': 100, 'min': 1, 'max': 1000}
        })
        def get_klines(symbol, start_date, limit):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                validated_params = {}

                for param_name, rules in schema.items():
                    # 确定参数来源
                    source = rules.get('source', 'auto')
                    if source == 'auto':
                        # 自动检测：path参数在kwargs中，query在args中，body在json中
                        if param_name in kwargs:
                            source = 'path'
                        elif request.method in ['POST', 'PUT', 'PATCH']:
                            source = 'json'
                        else:
                            source = 'args'

                    # 获取参数值
                    if source == 'path':
                        value = kwargs.get(param_name)
                    elif source == 'json':
                        data = request.get_json(silent=True) or {}
                        value = data.get(param_name)
                    else:  # args
                        value = request.args.get(param_name)

                    # 必需参数检查
                    if value is None:
                        if rules.get('required', False):
                            raise ValidationError(f"缺少必需参数: {param_name}")
                        if 'default' in rules:
                            value = rules['default']
                        else:
                            continue

                    # 类型转换
                    expected_type = rules.get('type')
                    if expected_type and value is not None:
                        try:
                            if expected_type == int:
                                value = int(value)
                            elif expected_type == float:
                                value = float(value)
                            elif expected_type == bool:
                                if isinstance(value, str):
                                    value = value.lower() in ('true', '1', 'yes')
                                else:
                                    value = bool(value)
                            elif expected_type == list:
                                if isinstance(value, str):
                                    value = [v.strip() for v in value.split(',') if v.strip()]
                                elif not isinstance(value, list):
                                    raise ValidationError(f"参数 {param_name} 必须是列表")
                            elif expected_type == dict:
                                if not isinstance(value, dict):
                                    raise ValidationError(f"参数 {param_name} 必须是对象")
                            elif expected_type == str:
                                value = str(value).strip()
                        except (ValueError, TypeError) as e:
                            raise ValidationError(f"参数 {param_name} 类型错误: {e}")

                    # 数值范围检查
                    if isinstance(value, (int, float)):
                        if 'min' in rules and value < rules['min']:
                            raise ValidationError(f"参数 {param_name} 不能小于 {rules['min']}")
                        if 'max' in rules and value > rules['max']:
                            raise ValidationError(f"参数 {param_name} 不能大于 {rules['max']}")

                    # 长度检查
                    if isinstance(value, (str, list)):
                        if 'min_length' in rules and len(value) < rules['min_length']:
                            raise ValidationError(f"参数 {param_name} 长度不能小于 {rules['min_length']}")
                        if 'max_length' in rules and len(value) > rules['max_length']:
                            raise ValidationError(f"参数 {param_name} 长度不能大于 {rules['max_length']}")

                    # 枚举值检查
                    if 'choices' in rules and value not in rules['choices']:
                        raise ValidationError(
                            f"参数 {param_name} 必须是以下值之一: {', '.join(map(str, rules['choices']))}"
                        )

                    # 自定义验证器
                    if 'validator' in rules:
                        validator = rules['validator']
                        try:
                            value = validator(value)
                        except ValidationError:
                            raise
                        except Exception as e:
                            raise ValidationError(f"参数 {param_name} 验证失败: {e}")

                    validated_params[param_name] = value

                # 将验证后的参数注入到函数调用中
                kwargs.update(validated_params)
                return func(*args, **kwargs)

            except ValidationError as e:
                return error_response(str(e), status_code=400)
            except Exception as e:
                logger.exception(f"参数验证异常: {e}")
                return error_response(f"参数验证失败: {e}", status_code=400)

        return wrapper
    return decorator


def handle_errors(func: Callable) -> Callable:
    """错误处理装饰器 - 统一捕获异常并返回标准错误响应"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            logger.warning(f"验证错误: {e}")
            return error_response(str(e), status_code=400)
        except ValueError as e:
            logger.warning(f"值错误: {e}")
            return error_response(str(e), status_code=400)
        except FileNotFoundError as e:
            logger.warning(f"资源未找到: {e}")
            return error_response(str(e), status_code=404)
        except PermissionError as e:
            logger.warning(f"权限错误: {e}")
            return error_response("权限不足", status_code=403)
        except Exception as e:
            logger.exception(f"服务器错误: {e}")
            return error_response(f"服务器内部错误: {e}", status_code=500)

    return wrapper


def format_response(func: Callable) -> Callable:
    """响应格式化装饰器 - 自动将返回值包装为标准响应格式

    如果函数返回:
    - dict: 包装为 success_response(data)
    - tuple(dict, int): 包装为 success_response(data, status_code)
    - Response对象: 直接返回
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)

        # 如果已经是Response对象，直接返回
        if hasattr(result, 'status_code'):
            return result

        # 如果是元组 (data, status_code)
        if isinstance(result, tuple) and len(result) == 2:
            data, status_code = result
            return success_response(data, status_code=status_code)

        # 如果是字典，包装为成功响应
        if isinstance(result, dict):
            return success_response(result)

        # 其他情况直接返回
        return result

    return wrapper


def require_auth(func: Callable) -> Callable:
    """认证检查装饰器（可选功能，当前为占位实现）"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # TODO: 实现认证逻辑
        # auth_header = request.headers.get('Authorization')
        # if not auth_header or not validate_token(auth_header):
        #     return error_response('未授权', status_code=401)
        return func(*args, **kwargs)

    return wrapper


def paginate(default_page_size: int = 20, max_page_size: int = 100):
    """分页装饰器 - 自动处理分页参数

    Args:
        default_page_size: 默认每页大小
        max_page_size: 最大每页大小

    注入参数:
        page: 页码（从1开始）
        page_size: 每页大小
        offset: 偏移量
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                page = max(1, request.args.get('page', 1, type=int))
                page_size = max(1, min(
                    request.args.get('pageSize', default_page_size, type=int),
                    max_page_size
                ))
                offset = (page - 1) * page_size

                kwargs.update({
                    'page': page,
                    'page_size': page_size,
                    'offset': offset
                })
            except Exception as e:
                logger.exception(f"分页参数处理失败: {e}")
                return error_response("分页参数错误", status_code=400)

            # Run the route outside the try/except so genuine handler errors
            # (DB failures, etc.) surface with their real message instead of
            # being relabelled as a pagination error.
            return func(*args, **kwargs)

        return wrapper
    return decorator


def log_request(func: Callable) -> Callable:
    """请求日志装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info(f"{request.method} {request.path} - {request.remote_addr}")
        result = func(*args, **kwargs)
        status = getattr(result, 'status_code', 200) if hasattr(result, 'status_code') else 200
        logger.info(f"{request.method} {request.path} - {status}")
        return result

    return wrapper
