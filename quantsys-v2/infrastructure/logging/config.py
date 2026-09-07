"""
结构化日志配置 - structlog

提供 JSON 格式日志、trace ID 追踪、敏感信息过滤
"""
import logging
import os
import sys
from typing import Any, Dict, Optional
import uuid


def configure_structured_logging(
    level: str = "INFO",
    json_format: bool = True,
    enable_trace_id: bool = True,
) -> logging.Logger:
    """配置结构化日志

    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR）
        json_format: 是否输出 JSON 格式（生产环境建议 True）
        enable_trace_id: 是否启用 trace ID 追踪

    Returns:
        logging.Logger: 配置好的 logger

    Usage:
        # 在应用启动时调用一次
        from infrastructure.logging import configure_structured_logging
        configure_structured_logging(level="INFO", json_format=True)

        # 在代码中使用
        import structlog
        logger = structlog.get_logger()
        logger.info("ml_predict_called", symbol="600000", model_version="v2.3")

        # 输出:
        # {"event": "ml_predict_called", "symbol": "600000", "model_version": "v2.3",
        #  "timestamp": "2026-06-24T14:30:00Z", "level": "info"}
    """
    try:
        import structlog
        from structlog.processors import JSONRenderer
        from structlog.stdlib import add_log_level, add_logger_name
        from structlog.dev import ConsoleRenderer
    except ImportError:
        print("⚠️ structlog not installed. Run: pip install structlog")
        print("⚠️ Falling back to standard logging")
        return _configure_standard_logging(level)

    # 配置标准库 logging（structlog 的底层）
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # 选择渲染器
    if json_format:
        # 生产环境：JSON 格式（可搜索、可解析）
        renderer = JSONRenderer()
    else:
        # 开发环境：彩色控制台输出（易读）
        renderer = ConsoleRenderer(colors=True)

    # 配置处理器链
    processors = [
        # 1. 添加 logger 名称
        add_logger_name,
        # 2. 添加日志级别
        add_log_level,
        # 3. 添加时间戳（ISO 8601 格式）
        structlog.processors.TimeStamper(fmt="iso"),
        # 4. 添加堆栈信息（异常时）
        structlog.processors.StackInfoRenderer(),
        # 5. 格式化异常
        structlog.processors.format_exc_info,
        # 6. 过滤敏感信息
        _filter_sensitive_processor,
        # 7. Unicode 解码
        structlog.processors.UnicodeDecoder(),
        # 8. 最终渲染
        renderer,
    ]

    # 如果启用 trace ID，添加到处理器链
    if enable_trace_id:
        processors.insert(0, _add_trace_id_processor)

    # 配置 structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger()
    logger.info(
        "structured_logging_configured",
        level=level,
        json_format=json_format,
        enable_trace_id=enable_trace_id,
    )

    return logger


def _configure_standard_logging(level: str) -> logging.Logger:
    """降级到标准 logging（structlog 不可用时）"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    logger.warning("Using standard logging (structlog not available)")
    return logger


def _add_trace_id_processor(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """添加 trace ID 到日志

    trace ID 用于追踪分布式系统中的请求链路
    """
    # 尝试从上下文获取 trace ID
    trace_id = _get_current_trace_id()

    if not trace_id:
        # 如果没有，生成新的 trace ID
        trace_id = str(uuid.uuid4())[:8]
        _set_current_trace_id(trace_id)

    event_dict["trace_id"] = trace_id
    return event_dict


def _filter_sensitive_processor(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """过滤敏感信息（密码、Token、API Key）"""
    sensitive_keys = [
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "authorization",
        "auth",
    ]

    for key in list(event_dict.keys()):
        # 检查键名是否包含敏感关键词
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            event_dict[key] = "***REDACTED***"

        # 检查值是否是字符串且看起来像密码/Token
        elif isinstance(event_dict[key], str):
            value = event_dict[key]
            # JWT Token 格式
            if value.count(".") == 2 and len(value) > 50:
                event_dict[key] = "***JWT_REDACTED***"
            # API Key 格式（长字符串）
            elif len(value) > 32 and value.isalnum():
                event_dict[key] = "***KEY_REDACTED***"

    return event_dict


# ── Trace ID 上下文管理 ──

import contextvars

_trace_id_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trace_id", default=None
)


def _get_current_trace_id() -> Optional[str]:
    """获取当前上下文的 trace ID"""
    return _trace_id_context.get()


def _set_current_trace_id(trace_id: str) -> None:
    """设置当前上下文的 trace ID"""
    _trace_id_context.set(trace_id)


def get_trace_id() -> str:
    """获取当前 trace ID（公共 API）

    Returns:
        str: 当前请求的 trace ID

    Usage:
        from infrastructure.logging import get_trace_id

        trace_id = get_trace_id()
        logger.info("processing_request", trace_id=trace_id)
    """
    trace_id = _get_current_trace_id()
    if not trace_id:
        trace_id = str(uuid.uuid4())[:8]
        _set_current_trace_id(trace_id)
    return trace_id


def set_trace_id(trace_id: str) -> None:
    """设置 trace ID（用于跨服务传递）

    Args:
        trace_id: 从上游服务接收的 trace ID

    Usage:
        from infrastructure.logging import set_trace_id

        # 在 FastAPI 中间件中
        async def middleware(request: Request, call_next):
            trace_id = request.headers.get('X-Trace-ID')
            if trace_id:
                set_trace_id(trace_id)
            return await call_next(request)
    """
    _set_current_trace_id(trace_id)


# ── 日志装饰器 ──

def log_execution(operation: str):
    """装饰器：记录函数执行日志

    Args:
        operation: 操作名称

    Usage:
        from infrastructure.logging import log_execution

        @log_execution("ml_predict")
        def predict_model(symbol: str):
            # 自动记录开始/结束/耗时/异常
            pass
    """
    import functools
    import time
    import structlog

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = structlog.get_logger()
            start_time = time.time()

            logger.info(
                f"{operation}_started",
                operation=operation,
                function=func.__name__,
            )

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                logger.info(
                    f"{operation}_completed",
                    operation=operation,
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                logger.error(
                    f"{operation}_failed",
                    operation=operation,
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    error=str(e),
                    error_type=type(e).__name__,
                )

                # 重新抛出异常
                raise

        return wrapper
    return decorator
