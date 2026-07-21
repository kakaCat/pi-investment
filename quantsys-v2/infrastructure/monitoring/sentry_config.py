"""
Sentry 错误监控配置

自动捕获未处理异常、性能追踪、错误告警
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Sentry 是否已初始化
_sentry_initialized = False


def init_sentry(
    dsn: Optional[str] = None,
    environment: Optional[str] = None,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
) -> bool:
    """初始化 Sentry 错误追踪

    Args:
        dsn: Sentry DSN，默认从环境变量 SENTRY_DSN 读取
        environment: 环境名称（development/staging/production）
        traces_sample_rate: 性能追踪采样率（0.0-1.0），默认 10%
        profiles_sample_rate: 性能分析采样率（0.0-1.0），默认 10%

    Returns:
        bool: 是否成功初始化

    Usage:
        # 在应用启动时调用
        init_sentry()

        # 手动捕获异常
        from infrastructure.monitoring import capture_exception
        try:
            risky_operation()
        except Exception as e:
            capture_exception(e, extra_context={'user_id': 123})
    """
    global _sentry_initialized

    if _sentry_initialized:
        logger.info("Sentry already initialized")
        return True

    # 从环境变量读取 DSN
    dsn = dsn or os.environ.get("SENTRY_DSN")

    if not dsn:
        logger.warning(
            "Sentry DSN not configured. Set SENTRY_DSN environment variable to enable error tracking."
        )
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        # 环境检测
        if environment is None:
            environment = os.environ.get("ENVIRONMENT", "development")

        # 日志集成：WARNING 及以上自动发送到 Sentry
        logging_integration = LoggingIntegration(
            level=logging.INFO,        # 捕获 INFO 及以上
            event_level=logging.ERROR  # ERROR 及以上作为事件
        )

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            integrations=[
                SqlalchemyIntegration(),
                RedisIntegration(),
                logging_integration,
            ],
            before_send=_filter_sensitive_data,
            # 设置版本（从 git commit 读取）
            release=_get_release_version(),
        )

        _sentry_initialized = True
        logger.info(
            f"✅ Sentry initialized: environment={environment}, "
            f"traces_sample_rate={traces_sample_rate}"
        )
        return True

    except ImportError:
        logger.error(
            "❌ Sentry SDK not installed. Run: pip install sentry-sdk"
        )
        return False
    except Exception as e:
        logger.error(f"❌ Failed to initialize Sentry: {e}")
        return False


def _filter_sensitive_data(event, hint):
    """过滤敏感信息（密码、Token）

    在发送到 Sentry 前移除敏感数据
    """
    # 过滤环境变量中的敏感信息
    if "contexts" in event and "runtime" in event["contexts"]:
        env = event["contexts"]["runtime"].get("env", {})
        sensitive_keys = ["PGPASSWORD", "REDIS_PASSWORD", "SECRET_KEY", "API_KEY", "TOKEN"]
        for key in sensitive_keys:
            if key in env:
                env[key] = "***REDACTED***"

    # 过滤请求头中的敏感信息
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        if "Authorization" in headers:
            headers["Authorization"] = "***REDACTED***"
        if "Cookie" in headers:
            headers["Cookie"] = "***REDACTED***"

    return event


def _get_release_version() -> str:
    """获取版本号（从 git commit）"""
    try:
        import subprocess
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return f"quantsys-v2@{commit}"
    except:
        return "quantsys-v2@unknown"


def capture_exception(
    exception: Exception,
    extra_context: Optional[dict] = None,
    tags: Optional[dict] = None,
) -> Optional[str]:
    """手动捕获异常到 Sentry

    Args:
        exception: 异常对象
        extra_context: 额外上下文信息
        tags: 标签（用于分组和过滤）

    Returns:
        str: Sentry event ID（用于跟踪）

    Example:
        try:
            ml_predict(symbol='600000', model_id='v2.3')
        except Exception as e:
            event_id = capture_exception(e,
                extra_context={
                    'symbol': '600000',
                    'model_id': 'v2.3',
                },
                tags={'component': 'ml_predict'}
            )
            logger.error(f"ML prediction failed, Sentry event: {event_id}")
    """
    if not _sentry_initialized:
        logger.warning("Sentry not initialized, exception not captured")
        return None

    try:
        import sentry_sdk

        # 设置上下文
        if extra_context:
            with sentry_sdk.configure_scope() as scope:
                for key, value in extra_context.items():
                    scope.set_context(key, value)

        # 设置标签
        if tags:
            with sentry_sdk.configure_scope() as scope:
                for key, value in tags.items():
                    scope.set_tag(key, value)

        # 捕获异常
        event_id = sentry_sdk.capture_exception(exception)
        return event_id

    except Exception as e:
        logger.error(f"Failed to capture exception to Sentry: {e}")
        return None


def capture_message(
    message: str,
    level: str = "info",
    extra_context: Optional[dict] = None,
) -> Optional[str]:
    """发送消息到 Sentry（非异常）

    Args:
        message: 消息内容
        level: 级别（debug/info/warning/error/fatal）
        extra_context: 额外上下文

    Returns:
        str: Sentry event ID

    Example:
        # 记录重要业务事件
        capture_message(
            "Large trade detected",
            level="warning",
            extra_context={'amount': 1000000, 'symbol': '600000'}
        )
    """
    if not _sentry_initialized:
        return None

    try:
        import sentry_sdk

        if extra_context:
            with sentry_sdk.configure_scope() as scope:
                for key, value in extra_context.items():
                    scope.set_context(key, value)

        event_id = sentry_sdk.capture_message(message, level=level)
        return event_id

    except Exception as e:
        logger.error(f"Failed to capture message to Sentry: {e}")
        return None
