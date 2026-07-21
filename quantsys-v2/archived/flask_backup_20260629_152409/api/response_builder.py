"""
API 响应构建器 - 统一响应格式
"""
import math
from typing import Any, Dict, Optional
from datetime import datetime, date

from flask import jsonify, Response


def sanitize_for_json(obj: Any) -> Any:
    """递归清理 NaN/Infinity/日期 以便 JSON 序列化

    Args:
        obj: 待清理的对象

    Returns:
        清理后的对象
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif hasattr(obj, '__dict__'):
        # 处理自定义对象
        return sanitize_for_json(obj.__dict__)
    return obj


def success_response(
    data: Any = None,
    message: str = None,
    status_code: int = 200,
    **extra_fields
) -> Response:
    """构建成功响应

    Args:
        data: 响应数据
        message: 成功消息（可选）
        status_code: HTTP状态码
        **extra_fields: 额外的响应字段

    Returns:
        Flask Response对象

    Example:
        success_response({'stocks': [...]}, message='查询成功')
        # => {success: true, data: {...}, message: '查询成功'}

        success_response(stocks=[...], count=10)
        # => {success: true, stocks: [...], count: 10}
    """
    response = {'success': True}

    if data is not None:
        response['data'] = sanitize_for_json(data)

    if message:
        response['message'] = message

    # 添加额外字段
    for key, value in extra_fields.items():
        response[key] = sanitize_for_json(value)

    return jsonify(response), status_code


def error_response(
    error: str,
    status_code: int = 400,
    error_code: str = None,
    details: Dict = None
) -> Response:
    """构建错误响应

    Args:
        error: 错误消息
        status_code: HTTP状态码
        error_code: 错误代码（可选）
        details: 错误详情（可选）

    Returns:
        Flask Response对象

    Example:
        error_response('股票代码不能为空', status_code=400)
        # => {success: false, error: '股票代码不能为空'}

        error_response('验证失败', error_code='VALIDATION_ERROR', details={...})
        # => {success: false, error: '验证失败', error_code: 'VALIDATION_ERROR', details: {...}}
    """
    response = {
        'success': False,
        'error': str(error)
    }

    if error_code:
        response['error_code'] = error_code

    if details:
        response['details'] = sanitize_for_json(details)

    return jsonify(response), status_code


def paginated_response(
    items: list,
    total: int,
    page: int,
    page_size: int,
    **extra_fields
) -> Response:
    """构建分页响应

    Args:
        items: 当前页数据
        total: 总记录数
        page: 当前页码
        page_size: 每页大小
        **extra_fields: 额外的响应字段

    Returns:
        Flask Response对象

    Example:
        paginated_response(stocks, total=100, page=1, page_size=20)
        # => {
        #   success: true,
        #   data: [...],
        #   pagination: {
        #     total: 100,
        #     page: 1,
        #     page_size: 20,
        #     total_pages: 5
        #   }
        # }
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    response = {
        'success': True,
        'data': sanitize_for_json(items),
        'pagination': {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages
        }
    }

    # 添加额外字段
    for key, value in extra_fields.items():
        response[key] = sanitize_for_json(value)

    return jsonify(response)


def list_response(
    items: list,
    count: int = None,
    item_name: str = 'items',
    **extra_fields
) -> Response:
    """构建列表响应

    Args:
        items: 列表数据
        count: 记录数（如果不提供则自动计算）
        item_name: 列表字段名称
        **extra_fields: 额外的响应字段

    Returns:
        Flask Response对象

    Example:
        list_response(stocks, item_name='stocks')
        # => {success: true, stocks: [...], count: 10}
    """
    if count is None:
        count = len(items)

    response = {
        'success': True,
        item_name: sanitize_for_json(items),
        'count': count
    }

    # 添加额外字段
    for key, value in extra_fields.items():
        response[key] = sanitize_for_json(value)

    return jsonify(response)


def created_response(
    data: Any = None,
    message: str = '创建成功',
    resource_id: Any = None,
    **extra_fields
) -> Response:
    """构建创建成功响应 (201)

    Args:
        data: 创建的资源数据
        message: 成功消息
        resource_id: 资源ID
        **extra_fields: 额外的响应字段

    Returns:
        Flask Response对象

    Example:
        created_response(resource_id=123, message='策略创建成功')
        # => {success: true, message: '策略创建成功', id: 123}
    """
    response = {
        'success': True,
        'message': message
    }

    if resource_id is not None:
        response['id'] = resource_id

    if data is not None:
        response['data'] = sanitize_for_json(data)

    # 添加额外字段
    for key, value in extra_fields.items():
        response[key] = sanitize_for_json(value)

    return jsonify(response), 201


def no_content_response() -> Response:
    """构建无内容响应 (204)

    Returns:
        Flask Response对象
    """
    return '', 204


def not_found_response(
    resource: str = '资源',
    resource_id: Any = None
) -> Response:
    """构建未找到响应 (404)

    Args:
        resource: 资源名称
        resource_id: 资源ID

    Returns:
        Flask Response对象

    Example:
        not_found_response('股票', '000001.SZ')
        # => {success: false, error: '股票未找到: 000001.SZ'}
    """
    if resource_id:
        error = f"{resource}未找到: {resource_id}"
    else:
        error = f"{resource}未找到"

    return error_response(error, status_code=404)


def validation_error_response(
    errors: Dict[str, str]
) -> Response:
    """构建验证错误响应 (400)

    Args:
        errors: 字段错误映射 {field: error_message}

    Returns:
        Flask Response对象

    Example:
        validation_error_response({'symbol': '股票代码格式不正确', 'date': '日期不能为空'})
        # => {success: false, error: '参数验证失败', details: {...}}
    """
    return error_response(
        '参数验证失败',
        status_code=400,
        error_code='VALIDATION_ERROR',
        details=errors
    )


def unauthorized_response(message: str = '未授权') -> Response:
    """构建未授权响应 (401)

    Args:
        message: 错误消息

    Returns:
        Flask Response对象
    """
    return error_response(message, status_code=401, error_code='UNAUTHORIZED')


def forbidden_response(message: str = '权限不足') -> Response:
    """构建禁止访问响应 (403)

    Args:
        message: 错误消息

    Returns:
        Flask Response对象
    """
    return error_response(message, status_code=403, error_code='FORBIDDEN')


def conflict_response(message: str, details: Dict = None) -> Response:
    """构建冲突响应 (409)

    Args:
        message: 错误消息
        details: 冲突详情

    Returns:
        Flask Response对象

    Example:
        conflict_response('策略名称已存在', details={'name': 'ma_cross'})
    """
    return error_response(message, status_code=409, error_code='CONFLICT', details=details)


def server_error_response(message: str = '服务器内部错误') -> Response:
    """构建服务器错误响应 (500)

    Args:
        message: 错误消息

    Returns:
        Flask Response对象
    """
    return error_response(message, status_code=500, error_code='INTERNAL_ERROR')
