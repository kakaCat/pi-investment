"""
API 限流配置

使用 FastAPI + slowapi 实现速率限制，防止 DDoS 和滥用
"""
import logging
from typing import Optional
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    HAS_SLOWAPI = True
except ImportError:
    HAS_SLOWAPI = False
    logger.warning("slowapi not installed, rate limiting disabled")

_limiter: Optional["Limiter"] = None


def init_rate_limiter(app) -> Optional["Limiter"]:
    """初始化 API 限流器 (FastAPI 版本)

    Args:
        app: FastAPI 应用实例

    Returns:
        Limiter: 限流器实例
    """
    global _limiter

    if not HAS_SLOWAPI:
        logger.warning("Rate limiting disabled - slowapi not installed")
        return None

    from infrastructure.config import get_config
    config = get_config()
    redis_host = config.redis.host
    redis_port = config.redis.port
    redis_password = config.redis.password

    if redis_password:
        storage_uri = f"redis://:{redis_password}@{redis_host}:{redis_port}/1"
    else:
        storage_uri = f"redis://{redis_host}:{redis_port}/1"

    try:
        _limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=storage_uri,
            default_limits=["200 per day", "50 per hour"],
        )

        app.state.limiter = _limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

        logger.info(f"Rate limiter initialized with Redis: {redis_host}:{redis_port}")
        return _limiter

    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}")
        logger.warning("Rate limiting disabled - using in-memory fallback")

        _limiter = Limiter(
            key_func=get_remote_address,
            storage_uri="memory://",
            default_limits=["200 per day", "50 per hour"],
        )

        app.state.limiter = _limiter
        return _limiter


def get_rate_limiter() -> Optional["Limiter"]:
    """获取全局限流器实例"""
    return _limiter


class RateLimits:
    """预定义限流规则常量"""

    LOGIN = "5 per minute"
    REGISTER = "3 per hour"
    PASSWORD_RESET = "3 per hour"
    GENERAL_API = "100 per minute"
    SEARCH_API = "30 per minute"
    ML_PREDICT = "10 per minute"
    BACKTEST = "5 per minute"
    STRATEGY_EXECUTE = "10 per minute"
    STOCK_DATA = "60 per minute"
    REAL_TIME_QUOTE = "120 per minute"
    ADMIN_API = "30 per minute"


def limit_login(f):
    """登录限流装饰器"""
    if _limiter:
        return _limiter.limit(RateLimits.LOGIN)(f)
    return f


def limit_ml_predict(f):
    """ML 预测限流装饰器"""
    if _limiter:
        return _limiter.limit(RateLimits.ML_PREDICT)(f)
    return f


def limit_backtest(f):
    """回测限流装饰器"""
    if _limiter:
        return _limiter.limit(RateLimits.BACKTEST)(f)
    return f


def exempt_from_rate_limit(f):
    """豁免限流装饰器"""
    if _limiter:
        return _limiter.exempt(f)
    return f
