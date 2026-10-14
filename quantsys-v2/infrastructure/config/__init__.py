"""配置驱动集成模块

P2-3: 配置驱动集成
- 配置数据模型
- 配置加载器
- 配置验证器
"""

from .models import ServiceConfig, ServicesConfig, ServiceLifecycle
from .loader import ConfigLoader
from .validator import ConfigValidator


class _CompatDatabase:
    """`config.database` 兼容视图（2026-10-01 · REQ-261001145152-3982 t-649eb9）

    调用方写的是 `config.database.url` / `.async_url` / `.database`，而真实 settings 里
    只有 `DatabaseSettings.database_url` 属性与 `pgdatabase` 字段——口径不一致，
    过去 get_config() 返回 `{}` 导致这些访问抛 AttributeError 并被 `except` 吞掉
    （典型后果：DSN 静默退回环境变量、异步库拿不到 DSN）。
    本视图把调用方期望的三个名字映射到真实数据，其余属性透传。
    """

    def __init__(self, db):
        self._db = db

    @property
    def url(self) -> str:
        return self._db.database_url

    @property
    def async_url(self) -> str:
        """异步驱动 DSN（asyncpg）。"""
        return self._db.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def database(self) -> str:
        return self._db.pgdatabase

    def __getattr__(self, name):
        return getattr(self._db, name)


class _CompatExternal:
    """`config.external` 兼容视图：补上调用方在用、但 settings 未定义的 deepseek_api_key。"""

    def __init__(self, external):
        self._ext = external

    @property
    def deepseek_api_key(self):
        import os

        return os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")

    def __getattr__(self, name):
        return getattr(self._ext, name)


class _CompatRedis:
    """`config.redis` 兼容视图（rate_limiter 在读 config.redis.host/port/password）。

    settings 里**没有 redis 段**，但本模块已有 `get_redis_config()` 提供真实值
    （环境变量 + 本机 6379 默认），故直接复用，不另造一份默认值。
    """

    def __getattr__(self, name):
        cfg = get_redis_config()
        if name in cfg:
            return cfg[name]
        raise AttributeError(f"redis.{name}")


class _CompatLogging:
    """`config.logging` 兼容视图：调用方读 `.level` / `.format`，
    而真实 settings 提供的是 `.log_level` / `.log_format`——名字不同，过去必抛
    AttributeError，于是 websocket_server 那段日志配置整段失效。"""

    def __init__(self, logging_settings):
        self._log = logging_settings

    @property
    def level(self):
        return self._log.log_level

    @property
    def format(self):
        return self._log.log_format

    def __getattr__(self, name):
        return getattr(self._log, name)


class _CompatApp:
    """`config.app` 兼容视图（settings 里没有 app 段，但多个调用方在读它）。

    两类名字：
    - **有真实来源的**：`quantsys_api_url` 取自 `settings.external`；
    - **纯环境变量驱动的**（全仓无定义、调用方自带兜底）：jwt_secret_key / sentry_dsn /
      quantsys_api_host / quantsys_ws_port / quant_db_path / memory_recall_cosine_floor。

    未设置时**抛 AttributeError**，这不是偷懒，而是**保持调用方的兜底语义**：
    例如 memory/service.py 写的是
        try: return config.app.memory_recall_cosine_floor
        except AttributeError: return 0.30
    若这里返回 None，该函数就会返回 None 而不是 0.30。
    "取不到"与"取到空值"必须区分，否则修一个坑会挖出另一个。
    """

    _ENV_BACKED = {
        "jwt_secret_key": "JWT_SECRET_KEY",
        "sentry_dsn": "SENTRY_DSN",
        "quantsys_api_host": "QUANTSYS_API_HOST",
        "quantsys_ws_port": "QUANTSYS_WS_PORT",
        "quant_db_path": "QUANT_DB_PATH",
        "memory_recall_cosine_floor": "MEMORY_RECALL_COSINE_FLOOR",
    }

    def __init__(self, settings):
        self._settings = settings

    @property
    def quantsys_api_url(self):
        return self._settings.external.quantsys_api_url

    def __getattr__(self, name):
        import os

        env = self._ENV_BACKED.get(name)
        if env:
            raw = os.getenv(env)
            if raw is None or raw == "":
                raise AttributeError(f"app.{name}（未配置 {env}）")
            if name == "memory_recall_cosine_floor":
                try:
                    return float(raw)
                except ValueError as exc:
                    raise AttributeError(f"app.{name} 非数值: {raw!r}") from exc
            return raw
        raise AttributeError(f"app.{name}")


class _CompatConfig:
    """`get_config()` 返回的兼容配置对象：真实 settings + 名字映射 + 其余透传。"""

    def __init__(self, settings):
        self._settings = settings
        self.database = _CompatDatabase(settings.database)
        self.external = _CompatExternal(settings.external)
        self.logging = _CompatLogging(settings.logging)
        self.redis = _CompatRedis()
        self.app = _CompatApp(settings)

    def __getattr__(self, name):
        return getattr(self._settings, name)


def _flatten_settings(settings, prefix: str = "") -> dict:
    """把嵌套 settings 摊平成 {大写下划线键: 值}，供旧代码按键取值。

    同时登记 alias（Field(alias="PGHOST")）——旧代码用的正是这种环境变量风格的名字。
    """
    out = {}
    for name, field in type(settings).model_fields.items():
        value = getattr(settings, name, None)
        if hasattr(type(value), "model_fields"):  # 嵌套 settings 段
            out.update(_flatten_settings(value, prefix=f"{prefix}{name}_"))
            continue
        aliases = {name.upper(), f"{prefix}{name}".upper()}
        alias = getattr(field, "alias", None)
        if alias:
            aliases.add(str(alias).upper())
        for key in aliases:
            out[key] = value
    return out


# 向后兼容：提供旧的 get_config 函数
def get_config(key: str = None, default=None):
    """向后兼容配置入口（2026-10-01 · t-649eb9 修复，原实现是**空壳**）

    原实现：`if key is None: return {}` / `return default` —— 也就是说
    无参调用拿到空字典、带键调用永远拿到 default。而它在生产上有 17 处调用
    （engine.py 取 DSN、jwt_manager、llm_service、sentry_config、rate_limiter、
    websocket_server、cli、memory embedding 等），于是这些路径**全部静默走默认值**：
    典型后果是 ORM 拿不到 DSN、密钥为空——属于"配置看起来配了、实际没生效"。

    现在的语义：
    - 无参：返回**兼容配置对象**（真实 settings + 名字映射，见 _CompatConfig）
    - 带键：依次查 环境变量 → settings 摊平表（含 alias），都没有才返回 default

    新代码请直接用 `get_settings()`（本函数只为存量调用方保留）。
    """
    from .settings import get_settings

    settings = get_settings()

    if key is None:
        return _CompatConfig(settings)

    import os

    if key in os.environ:
        return os.environ[key]

    flat = _flatten_settings(settings)
    if key in flat and flat[key] is not None:
        return flat[key]
    if key.upper() in flat and flat[key.upper()] is not None:
        return flat[key.upper()]
    return default


def get_redis_config():
    """获取 Redis 连接配置（向后兼容旧接口）

    cache_factory 依赖此函数构造 Redis 客户端。从环境变量读取，
    缺省指向本机 6379（同 async_cache_service 默认值）。

    Returns:
        dict: Redis 连接配置（redis.Redis kwargs）
    """
    import os

    return {
        'host': os.getenv('REDIS_HOST', 'localhost'),
        'port': int(os.getenv('REDIS_PORT', 6379)),
        'db': int(os.getenv('REDIS_DB', 0)),
        'password': os.getenv('REDIS_PASSWORD'),
    }


# 向后兼容：re-export 缓存工厂（scripts/tools/benchmark_cache.py 等仍从本模块导入）
from .cache_factory import create_cache_service, create_redis_client  # noqa: E402

__all__ = [
    'ServiceConfig',
    'ServicesConfig',
    'ServiceLifecycle',
    'ConfigLoader',
    'ConfigValidator',
    'get_config',  # 向后兼容
    'get_redis_config',  # 向后兼容
    'create_cache_service',
    'create_redis_client',
]
