"""
API 错误处理器 - 统一错误处理和日志记录
"""
import logging
import traceback
from typing import Optional

from flask import Flask, request
from werkzeug.exceptions import HTTPException

from .response_builder import error_response

logger = logging.getLogger(__name__)


def register_error_handlers(app: Flask):
    """注册全局错误处理器

    Args:
        app: Flask应用实例
    """

    @app.errorhandler(400)
    def bad_request(e):
        """处理400错误"""
        logger.warning(f"Bad Request: {request.path} - {e}")
        return error_response(str(e.description) if hasattr(e, 'description') else '请求参数错误', status_code=400)

    @app.errorhandler(404)
    def not_found(e):
        """处理404错误"""
        logger.warning(f"Not Found: {request.path}")
        return error_response(f"资源未找到: {request.path}", status_code=404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        """处理405错误"""
        logger.warning(f"Method Not Allowed: {request.method} {request.path}")
        return error_response(f"不支持的请求方法: {request.method}", status_code=405)

    @app.errorhandler(500)
    def internal_error(e):
        """处理500错误"""
        logger.error(f"Internal Error: {request.path}")
        logger.error(traceback.format_exc())
        return error_response("服务器内部错误", status_code=500)

    @app.errorhandler(Exception)
    def handle_exception(e):
        """处理所有未捕获的异常"""
        # 如果是HTTP异常，使用原始处理器
        if isinstance(e, HTTPException):
            return e

        # 记录详细错误信息
        logger.error(f"Unhandled Exception: {request.method} {request.path}")
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())

        # 返回通用错误响应
        return error_response(
            "服务器内部错误，请稍后重试",
            status_code=500,
            error_code='INTERNAL_ERROR'
        )


class APIError(Exception):
    """API错误基类"""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: Optional[str] = None,
        details: Optional[dict] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details

    def to_response(self):
        """转换为Flask响应"""
        return error_response(
            self.message,
            status_code=self.status_code,
            error_code=self.error_code,
            details=self.details
        )


class ValidationError(APIError):
    """验证错误"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message,
            status_code=400,
            error_code='VALIDATION_ERROR',
            details=details
        )


class NotFoundError(APIError):
    """资源未找到错误"""

    def __init__(self, resource: str, resource_id: Optional[str] = None):
        message = f"{resource}未找到"
        if resource_id:
            message += f": {resource_id}"
        super().__init__(
            message,
            status_code=404,
            error_code='NOT_FOUND'
        )


class UnauthorizedError(APIError):
    """未授权错误"""

    def __init__(self, message: str = "未授权"):
        super().__init__(
            message,
            status_code=401,
            error_code='UNAUTHORIZED'
        )


class ForbiddenError(APIError):
    """权限不足错误"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(
            message,
            status_code=403,
            error_code='FORBIDDEN'
        )


class ConflictError(APIError):
    """资源冲突错误"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message,
            status_code=409,
            error_code='CONFLICT',
            details=details
        )


class ServerError(APIError):
    """服务器错误"""

    def __init__(self, message: str = "服务器内部错误"):
        super().__init__(
            message,
            status_code=500,
            error_code='INTERNAL_ERROR'
        )


def log_error(error: Exception, context: Optional[dict] = None):
    """记录错误日志

    Args:
        error: 异常对象
        context: 上下文信息
    """
    logger.error(f"Error: {error}")

    if context:
        logger.error(f"Context: {context}")

    logger.error(traceback.format_exc())


def handle_database_error(error: Exception) -> tuple:
    """处理数据库错误

    Args:
        error: 数据库异常

    Returns:
        tuple: (error_message, status_code)
    """
    error_str = str(error).lower()

    # 连接错误
    if 'connection' in error_str or 'connect' in error_str:
        logger.error(f"Database connection error: {error}")
        return "数据库连接失败", 503

    # 超时错误
    if 'timeout' in error_str:
        logger.error(f"Database timeout: {error}")
        return "数据库查询超时", 504

    # 约束违反
    if 'unique' in error_str or 'constraint' in error_str:
        logger.warning(f"Database constraint violation: {error}")
        return "数据约束冲突", 409

    # 其他数据库错误
    logger.error(f"Database error: {error}")
    logger.error(traceback.format_exc())
    return "数据库操作失败", 500


def handle_external_api_error(error: Exception, service_name: str = "外部服务") -> tuple:
    """处理外部API错误

    Args:
        error: 异常对象
        service_name: 服务名称

    Returns:
        tuple: (error_message, status_code)
    """
    error_str = str(error).lower()

    # 超时错误
    if 'timeout' in error_str:
        logger.error(f"{service_name} timeout: {error}")
        return f"{service_name}请求超时", 504

    # 连接错误
    if 'connection' in error_str:
        logger.error(f"{service_name} connection error: {error}")
        return f"{service_name}连接失败", 503

    # 其他错误
    logger.error(f"{service_name} error: {error}")
    logger.error(traceback.format_exc())
    return f"{service_name}请求失败", 502
