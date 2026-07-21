"""
API 限流配置

使用 Flask-Limiter 实现速率限制，防止 DDoS 和滥用
"""
import os
import logging
from typing import Optional
from flask import Flask, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)

# 全局限流器实例
_limiter: Optional[Limiter] = None


def init_rate_limiter(app: Flask) -> Limiter:
    """初始化 API 限流器

    Args:
        app: Flask 应用实例

    Returns:
        Limiter: 限流器实例

    Usage:
        from flask import Flask
        from infrastructure.auth import init_rate_limiter

        app = Flask(__name__)
        limiter = init_rate_limiter(app)

        @app.route('/api/endpoint')
        @limiter.limit("10/minute")
        def endpoint():
            return {'message': 'Limited endpoint'}
    """
    global _limiter

    # 从环境变量读取 Redis 配置
    redis_host = os.environ.get("REDIS_HOST", "127.0.0.1")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))
    redis_password = os.environ.get("REDIS_PASSWORD", "")

    # 构建 Redis URI
    if redis_password:
        storage_uri = f"redis://:{redis_password}@{redis_host}:{redis_port}/1"
    else:
        storage_uri = f"redis://{redis_host}:{redis_port}/1"

    try:
        _limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            storage_uri=storage_uri,
            default_limits=["200 per day", "50 per hour"],  # 全局默认限制
            storage_options={"socket_connect_timeout": 30},
            strategy="fixed-window",  # 固定窗口策略
            # 自定义错误消息
            headers_enabled=True,
            swallow_errors=True,  # 限流器错误不影响应用
        )

        logger.info(
            f"✅ Rate limiter initialized with Redis storage: {redis_host}:{redis_port}"
        )

        # 注册错误处理器
        @app.errorhandler(429)
        def ratelimit_handler(e):
            return {
                "success": False,
                "error": "Rate limit exceeded",
                "message": str(e.description),
                "retry_after": e.description if hasattr(e, 'description') else None
            }, 429

        return _limiter

    except Exception as e:
        logger.error(f"❌ Failed to initialize rate limiter: {e}")
        logger.warning("⚠️ Rate limiting disabled - using in-memory fallback")

        # 降级到内存存储
        _limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            storage_uri="memory://",
            default_limits=["200 per day", "50 per hour"],
        )

        return _limiter


def get_rate_limiter() -> Optional[Limiter]:
    """获取全局限流器实例"""
    return _limiter


# ── 预定义限流规则 ──

class RateLimits:
    """预定义限流规则常量"""

    # 认证相关
    LOGIN = "5 per minute"           # 登录：每分钟 5 次
    REGISTER = "3 per hour"          # 注册：每小时 3 次
    PASSWORD_RESET = "3 per hour"    # 密码重置：每小时 3 次

    # API 调用
    GENERAL_API = "100 per minute"   # 一般 API：每分钟 100 次
    SEARCH_API = "30 per minute"     # 搜索 API：每分钟 30 次

    # 资源密集型操作
    ML_PREDICT = "10 per minute"     # ML 预测：每分钟 10 次
    BACKTEST = "5 per minute"        # 回测：每分钟 5 次
    STRATEGY_EXECUTE = "10 per minute"  # 策略执行：每分钟 10 次

    # 数据获取
    STOCK_DATA = "60 per minute"     # 股票数据：每分钟 60 次
    REAL_TIME_QUOTE = "120 per minute"  # 实时行情：每分钟 120 次

    # 管理操作
    ADMIN_API = "30 per minute"      # 管理 API：每分钟 30 次


# ── 便捷装饰器 ──

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


# ── 限流豁免 ──

def exempt_from_rate_limit(f):
    """豁免限流装饰器（用于健康检查等）"""
    if _limiter:
        return _limiter.exempt(f)
    return f
