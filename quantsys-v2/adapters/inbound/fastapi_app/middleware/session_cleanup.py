"""
FastAPI 中间件：自动清理 ORM Session

功能：
1. 确保每个请求结束后 Session 被正确关闭
2. 异常时自动回滚事务
3. 记录 Session 泄漏

用法：
    from adapters.inbound.fastapi_app.middleware.session_cleanup import SessionCleanupMiddleware
    app.add_middleware(SessionCleanupMiddleware)
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import structlog

logger = structlog.get_logger(__name__)


class SessionCleanupMiddleware(BaseHTTPMiddleware):
    """确保每个请求结束后 Session 被正确关闭"""

    async def dispatch(self, request: Request, call_next):
        try:
            # 处理请求
            response = await call_next(request)
            return response
        finally:
            # 无论成功还是失败，都清理 Session
            try:
                from infrastructure.persistence.orm import close_session
                close_session()
            except Exception as e:
                logger.warning(
                    "session_cleanup_failed",
                    path=request.url.path,
                    error=str(e)
                )
