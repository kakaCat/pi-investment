"""
Unified configuration management using Pydantic Settings.

Replaces scattered os.environ reads with type-safe, validated configuration.
All configuration should be accessed via the singleton `get_config()` function.

Usage:
    from infrastructure.config.settings import get_config
    
    config = get_config()
    db_url = config.database.url
    feishu_webhook = config.external.feishu_webhook_url
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ThreadSettings(BaseSettings):
    """Thread and parallelism control settings."""
    
    model_config = SettingsConfigDict(env_prefix='')
    
    omp_num_threads: str = Field(default="1", description="OpenMP thread count")
    openblas_num_threads: str = Field(default="1", description="OpenBLAS thread count")
    mkl_num_threads: str = Field(default="1", description="MKL thread count")
    polars_max_threads: Optional[str] = Field(default=None, description="Polars max threads")


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""
    
    model_config = SettingsConfigDict(env_prefix='PG')
    
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(default="quant_investment", description="Database name")
    user: str = Field(default="postgres", description="Database user")
    password: str = Field(default="", description="Database password")
    db_schema: str = Field(default="quant", alias="PGSCHEMA", description="Schema name")
    
    @property
    def url(self) -> str:
        """Build PostgreSQL connection URL."""
        if self.password:
            return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"postgresql://{self.user}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_url(self) -> str:
        """Build async PostgreSQL connection URL."""
        if self.password:
            return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"postgresql+asyncpg://{self.user}@{self.host}:{self.port}/{self.database}"


class RedisSettings(BaseSettings):
    """Redis cache configuration."""
    
    model_config = SettingsConfigDict(env_prefix='REDIS_')
    
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    password: Optional[str] = Field(default=None, description="Redis password")
    db: int = Field(default=0, description="Redis database number")


class ExternalServiceSettings(BaseSettings):
    """External API and service credentials."""
    
    model_config = SettingsConfigDict(env_prefix='')
    
    feishu_webhook_url: Optional[str] = Field(default=None, description="Feishu notification webhook")
    feishu_bot_token: Optional[str] = Field(default=None, description="Feishu bot authentication token")
    tushare_token: Optional[str] = Field(default=None, description="Tushare API token")
    deepseek_api_key: Optional[str] = Field(default=None, description="DeepSeek LLM API key")
    quantsys_api_url: str = Field(default="http://127.0.0.1:5001", description="QuantSys API base URL")
    
    # Agent 通知服务配置
    agent_api_url: str = Field(default="http://127.0.0.1:3002", description="Agent API base URL")
    agent_api_token: Optional[str] = Field(default=None, description="Agent API authentication token")
    agent_timeout: int = Field(default=30, description="Agent API request timeout (seconds)")
    agent_notify_enabled: bool = Field(default=True, description="Enable agent notifications")
    agent_notify_log: str = Field(default="/tmp/agent_notify.log", description="Agent notification log file")


class ProxySettings(BaseSettings):
    """HTTP proxy configuration."""
    
    model_config = SettingsConfigDict(env_prefix='', case_sensitive=False)
    
    http_proxy: Optional[str] = Field(default=None, description="HTTP proxy URL")
    https_proxy: Optional[str] = Field(default=None, description="HTTPS proxy URL")
    
    def apply_to_env(self) -> None:
        """Apply proxy settings to os.environ for libraries that need it."""
        import os
        if self.http_proxy:
            os.environ['HTTP_PROXY'] = self.http_proxy
            os.environ['http_proxy'] = self.http_proxy
        if self.https_proxy:
            os.environ['HTTPS_PROXY'] = self.https_proxy
            os.environ['https_proxy'] = self.https_proxy


class LoggingSettings(BaseSettings):
    """Logging configuration."""
    
    model_config = SettingsConfigDict(env_prefix='LOG_')
    
    level: str = Field(default="INFO", description="Log level (DEBUG/INFO/WARNING/ERROR)")
    format: str = Field(default="json", description="Log format (json/text)")


class AppSettings(BaseSettings):
    """Application-level settings."""
    
    model_config = SettingsConfigDict(env_prefix='')
    
    use_agent_os_scheduler: bool = Field(default=True, description="Use Agent OS Scheduler vs local SchedulerService")
    initial_cash: float = Field(default=1000000.0, description="Initial cash for backtesting")
    market_monitor_log: Optional[str] = Field(default=None, description="Market monitor log file path")
    
    # API 服务器配置
    quantsys_api_host: str = Field(default="127.0.0.1", description="QuantSys API server host")
    quantsys_api_port: int = Field(default=5001, description="QuantSys API server port")
    quantsys_ws_port: int = Field(default=5003, description="QuantSys WebSocket server port")
    quantsys_api_url: str = Field(default="http://127.0.0.1:5001", description="QuantSys API base URL (for CLI clients)")
    
    # 数据库配置
    quant_db_path: Optional[str] = Field(default=None, description="Legacy SQLite database path")
    
    # 安全配置
    jwt_secret_key: Optional[str] = Field(default=None, description="JWT secret key for token signing")
    
    # 监控配置
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    environment: str = Field(default="development", description="Deployment environment (development/production)")
    
    # Quantlib 配置
    quant_market_adapter: str = Field(default="akshare", description="Market data adapter (akshare/tushare)")
    
    # Memory 配置
    memory_recall_cosine_floor: float = Field(default=0.30, description="Memory recall cosine similarity threshold")
    ollama_base_url: Optional[str] = Field(default=None, description="Ollama API base URL for embeddings")
    memory_embedding_model: Optional[str] = Field(default=None, description="Embedding model name")


class Config(BaseSettings):
    """Root configuration object aggregating all settings."""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',  # Ignore unknown env vars
    )
    
    # Nested settings groups
    threads: ThreadSettings = Field(default_factory=ThreadSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    external: ExternalServiceSettings = Field(default_factory=ExternalServiceSettings)
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    app: AppSettings = Field(default_factory=AppSettings)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Apply thread settings to environment on initialization
        self._apply_thread_settings()
    
    def _apply_thread_settings(self) -> None:
        """Apply thread settings to os.environ for NumPy/OpenBLAS/MKL."""
        import os
        os.environ['OMP_NUM_THREADS'] = self.threads.omp_num_threads
        os.environ['OPENBLAS_NUM_THREADS'] = self.threads.openblas_num_threads
        os.environ['MKL_NUM_THREADS'] = self.threads.mkl_num_threads
        if self.threads.polars_max_threads:
            os.environ['POLARS_MAX_THREADS'] = self.threads.polars_max_threads


# Singleton instance
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """Get the singleton configuration instance.
    
    Returns:
        Config: The global configuration object
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reload_config() -> Config:
    """Reload configuration from environment (useful for testing).
    
    Returns:
        Config: Fresh configuration instance
    """
    global _config_instance
    _config_instance = Config()
    return _config_instance
