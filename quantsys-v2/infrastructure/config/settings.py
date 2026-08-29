"""
统一配置管理

使用 Pydantic Settings 提供类型安全的配置管理，支持：
- 环境变量
- .env 文件
- 类型验证
- 默认值
"""

from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """数据库配置"""

    # PostgreSQL 连接
    pghost: str = Field(default="localhost", alias="PGHOST")
    pgport: int = Field(default=5432, alias="PGPORT")
    pguser: str = Field(default="postgres", alias="PGUSER")
    pgpassword: str = Field(default="", alias="PGPASSWORD")
    pgdatabase: str = Field(default="quant_investment", alias="PGDATABASE")

    # 连接池 (2026-08-28 扩容: pool_size 20->20 保持, max_overflow 20->30)
    pool_size: int = Field(default=20, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=30, alias="DB_MAX_OVERFLOW")
    pool_recycle: int = Field(default=3600, alias="DB_POOL_RECYCLE")
    pool_pre_ping: bool = Field(default=True, alias="DB_POOL_PRE_PING")

    @property
    def database_url(self) -> str:
        """构建数据库 URL"""
        if self.pgpassword:
            return f"postgresql://{self.pguser}:{self.pgpassword}@{self.pghost}:{self.pgport}/{self.pgdatabase}"
        return f"postgresql://{self.pguser}@{self.pghost}:{self.pgport}/{self.pgdatabase}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",  # 忽略未定义的环境变量
    )


class ThreadPoolSettings(BaseSettings):
    """线程池配置"""

    default_workers: int = Field(default=10, alias="DEFAULT_POOL_WORKERS")
    io_workers: int = Field(default=20, alias="IO_POOL_WORKERS")
    compute_workers: int = Field(default=4, alias="COMPUTE_POOL_WORKERS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",  # 忽略未定义的环境变量
    )


class SchedulerSettings(BaseSettings):
    """调度器配置"""

    tick_interval: int = Field(default=60, alias="SCHEDULER_TICK_INTERVAL")
    misfire_grace_time: int = Field(default=300, alias="SCHEDULER_MISFIRE_GRACE_TIME")

    # Agent OS 集成
    agent_os_enabled: bool = Field(default=True, alias="AGENT_OS_ENABLED")
    agent_os_url: str = Field(default="http://localhost:3002", alias="AGENT_OS_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",  # 忽略未定义的环境变量
    )


class ExternalServiceSettings(BaseSettings):
    """外部服务配置"""

    # 飞书
    feishu_webhook_url: Optional[str] = Field(default=None, alias="FEISHU_WEBHOOK_URL")
    feishu_weekly_report_webhook: Optional[str] = Field(default=None, alias="FEISHU_WEEKLY_REPORT_WEBHOOK")
    feishu_webhook_model_train: Optional[str] = Field(default=None, alias="FEISHU_WEBHOOK_MODEL_TRAIN")

    agent_api_url: str = Field(default="http://127.0.0.1:3002", alias="AGENT_API_URL")
    agent_timeout: int = Field(default=30, alias="AGENT_TIMEOUT")
    agent_notify_enabled: bool = Field(default=True, alias="AGENT_NOTIFY_ENABLED")
    agent_api_token: Optional[str] = Field(default=None, alias="AGENT_API_TOKEN")

    # Quantsys API (用于 agent-ts 调用)
    quantsys_api_url: str = Field(default="http://localhost:5001", alias="QUANTSYS_API_URL")

    @field_validator("agent_notify_enabled", mode="before")
    @classmethod
    def _parse_agent_notify_enabled(cls, v):
        """兼容 AGENT_NOTIFY_ENABLED=true/false 字符串配置。"""
        if isinstance(v, str):
            return v.strip().lower() == "true"
        return bool(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",  # 忽略未定义的环境变量
    )


class LoggingSettings(BaseSettings):
    """日志配置"""

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")  # json or console

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """验证日志格式"""
        valid_formats = {"json", "console"}
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f"Invalid log format: {v}. Must be one of {valid_formats}")
        return v_lower

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",  # 忽略未定义的环境变量
    )


class ProxySettings(BaseSettings):
    """代理配置（单一真相源）。

    akshare 等三方库从 os.environ 读取 HTTP_PROXY/HTTPS_PROXY，无法靠 DI 注入；
    代理的解析在此集中完成，infrastructure/config/proxy.py 在调用边界写/清环境变量。
    """

    http_proxy: Optional[str] = Field(default=None, alias="HTTP_PROXY")
    https_proxy: Optional[str] = Field(default=None, alias="HTTPS_PROXY")
    all_proxy: Optional[str] = Field(default=None, alias="ALL_PROXY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )


class AppSettings(BaseSettings):
    """应用配置（统一入口）"""

    # 环境
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # API 服务绑定地址（uvicorn 启动用）
    api_host: str = Field(default="127.0.0.1", alias="QUANTSYS_API_HOST")
    api_port: int = Field(default=5001, alias="QUANTSYS_API_PORT")

    # 子配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    thread_pool: ThreadPoolSettings = Field(default_factory=ThreadPoolSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    external: ExternalServiceSettings = Field(default_factory=ExternalServiceSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    proxy: ProxySettings = Field(default_factory=ProxySettings)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """验证环境"""
        valid_envs = {"development", "production", "test"}
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v_lower

    @property
    def is_production(self) -> bool:
        """是否生产环境"""
        return self.environment == "production"

    @property
    def is_test(self) -> bool:
        """是否测试环境"""
        return self.environment == "test"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",  # 忽略未定义的环境变量
    )


# ============================================================================
# 全局配置实例
# ============================================================================

# 延迟初始化，避免导入时就读取环境变量
_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """
    获取全局配置实例（单例模式）

    Returns:
        AppSettings 实例
    """
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


def reload_settings() -> AppSettings:
    """
    重新加载配置（用于测试或热加载）

    Returns:
        新的 AppSettings 实例
    """
    global _settings
    _settings = AppSettings()
    return _settings


# 便捷访问
settings = get_settings()
