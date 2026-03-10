"""
集中配置管理模块

使用 Pydantic Settings 统一管理所有配置
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ============ LLM 配置 ============

class LLMSettings(BaseSettings):
    """LLM 配置"""
    provider: str = Field(default="openai", description="LLM 提供商")
    model: str = Field(default="gpt-3.5-turbo", description="默认模型")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=8192)
    timeout: int = Field(default=60, ge=10, le=300)

    # API Keys
    openai_api_key: str | None = Field(default=None)
    anthropic_api_key: str | None = Field(default=None)
    dashscope_api_key: str | None = Field(default=None)

    # 本地 LLM 配置
    local_provider: str = Field(
        default="ollama",
        description="本地 LLM 提供商 (ollama/vllm/lmstudio)"
    )
    local_base_url: str | None = Field(
        default=None,
        description="本地 LLM 服务地址"
    )
    local_model: str | None = Field(
        default=None,
        description="本地 LLM 模型名称"
    )
    local_timeout: int = Field(
        default=120,
        ge=30,
        le=600,
        description="本地 LLM 超时时间（秒）"
    )

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    # 敏感字段列表
    _SENSITIVE_FIELDS: set[str] = {
        "openai_api_key", "anthropic_api_key", "dashscope_api_key"
    }

    def get_safe_summary(self) -> dict[str, Any]:
        """获取安全的配置摘要（排除敏感字段）"""
        data = self.model_dump()
        for field in self._SENSITIVE_FIELDS:
            if field in data and data[field]:
                data[field] = "***REDACTED***"
        return data

    def get_local_config(self) -> dict[str, Any]:
        """获取本地 LLM 配置"""
        return {
            "provider": self.local_provider,
            "base_url": self.local_base_url,
            "model": self.local_model,
            "timeout": self.local_timeout,
        }


# ============ 数据库配置 ============

class DatabaseSettings(BaseSettings):
    """数据库配置"""
    url: str = Field(default="sqlite+aiosqlite:///./intelliteam.db")
    pool_size: int = Field(default=50, ge=5, le=200)
    max_overflow: int = Field(default=20, ge=0, le=100)
    pool_recycle: int = Field(default=1800, ge=300, le=7200)
    pool_timeout: int = Field(default=10, ge=5, le=60)
    echo: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )


# ============ Redis 配置 ============

class RedisSettings(BaseSettings):
    """Redis 配置"""
    enabled: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0, le=15)
    password: str | None = Field(default=None)
    max_connections: int = Field(default=50, ge=10, le=200)

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    _SENSITIVE_FIELDS: set[str] = {"password"}

    def get_safe_summary(self) -> dict[str, Any]:
        """获取安全的配置摘要"""
        data = self.model_dump()
        for field in self._SENSITIVE_FIELDS:
            if field in data and data[field]:
                data[field] = "***REDACTED***"
        return data


# ============ Celery 配置 ============

class CelerySettings(BaseSettings):
    """Celery 配置"""
    broker_url: str = Field(default="redis://localhost:6379/1", description="消息代理 URL")
    result_backend: str = Field(default="redis://localhost:6379/1", description="结果后端 URL")
    timezone: str = Field(default="Asia/Shanghai", description="时区")
    task_serializer: str = Field(default="json")
    result_serializer: str = Field(default="json")
    accept_content: list[str] = Field(default=["json"])
    task_acks_late: bool = Field(default=True)
    task_reject_on_worker_lost: bool = Field(default=True)
    result_expires: int = Field(default=3600, description="结果过期时间（秒）")
    worker_concurrency: int = Field(default=4, ge=1, le=32)
    worker_prefetch_multiplier: int = Field(default=1)

    model_config = SettingsConfigDict(
        env_prefix="CELERY_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    _SENSITIVE_FIELDS: set[str] = {"broker_url", "result_backend"}

    def get_safe_summary(self) -> dict[str, Any]:
        """获取安全的配置摘要"""
        data = self.model_dump()
        for field in self._SENSITIVE_FIELDS:
            if field in data and data[field]:
                data[field] = "***REDACTED***"
        return data


# ============ Agent 配置 ============

class AgentSettings(BaseSettings):
    """Agent 配置"""
    # Coder Agent
    coder_model: str = Field(default="gpt-4")
    coder_language: str = Field(default="python")
    coder_style: str = Field(default="pep8")

    # Tester Agent
    tester_framework: str = Field(default="pytest")
    tester_coverage_target: int = Field(default=80, ge=50, le=100)

    # DocWriter Agent
    doc_format: str = Field(default="markdown")

    # Architect Agent
    architect_patterns: list[str] = Field(default=["MVC", "微服务"])

    # 执行配置
    timeout_seconds: int = Field(default=300, ge=60, le=600)
    max_retries: int = Field(default=3, ge=0, le=10)

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )


# ============ API 配置 ============

class APISettings(BaseSettings):
    """API 配置"""
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=16)
    debug: bool = Field(default=False)

    # CORS
    cors_origins: list[str] = Field(default=["*"])

    # 限流
    rate_limit: int = Field(default=60, ge=10, le=1000)

    # GZip
    gzip_min_size: int = Field(default=1000, ge=100, le=10000)

    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )


# ============ 日志配置 ============

class LoggingSettings(BaseSettings):
    """日志配置"""
    level: str = Field(default="INFO")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file: str | None = Field(default=None)
    max_bytes: int = Field(default=10485760, ge=1048576, le=104857600)  # 10MB
    backup_count: int = Field(default=5, ge=1, le=20)

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )


# ============ 安全配置 ============

class SecuritySettings(BaseSettings):
    """安全配置"""
    secret_key: str = Field(default="change-me-in-production")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)

    # 审计
    enable_audit: bool = Field(default=True)
    audit_log_file: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    _SENSITIVE_FIELDS: set[str] = {"secret_key"}

    def get_safe_summary(self) -> dict[str, Any]:
        """获取安全的配置摘要"""
        data = self.model_dump()
        for field in self._SENSITIVE_FIELDS:
            if field in data and data[field]:
                data[field] = "***REDACTED***"
        return data


# ============ 应用总配置 ============

class AppSettings(BaseSettings):
    """应用总配置"""
    # 应用信息
    name: str = Field(default="IntelliTeam")
    version: str = Field(default="2.0.0")
    description: str = Field(default="智能研发协作平台")
    environment: str = Field(default="development")

    # 子配置
    llm: LLMSettings = Field(default_factory=LLMSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    @model_validator(mode="after")
    def validate_production_security(self) -> AppSettings:
        """生产环境安全检查"""
        if self.environment == "production":
            if self.security.secret_key == "change-me-in-production":
                raise ValueError(
                    "生产环境必须修改 SECURITY_SECRET_KEY 默认值！"
                    "请在环境变量中设置安全的密钥。"
                )
        return self

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        if v not in ["development", "staging", "production"]:
            raise ValueError(
                "Environment must be 'development', 'staging', or 'production'"
            )
        return v

    def is_development(self) -> bool:
        """是否开发环境"""
        return self.environment == "development"

    def is_production(self) -> bool:
        """是否生产环境"""
        return self.environment == "production"

    def get_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "name": self.name,
            "version": self.version,
            "environment": self.environment,
            "llm_provider": self.llm.provider,
            "database": "configured" if self.database.url else "not configured",
            "redis_enabled": self.redis.enabled,
            "api_port": self.api.port,
            "debug": self.api.debug,
        }

    # ============ 向后兼容属性（旧版 flat settings API） ============

    @property
    def app_name(self) -> str:
        """兼容旧版 app_name"""
        return self.name

    @property
    def app_env(self) -> str:
        """兼容旧版 app_env"""
        return self.environment

    @property
    def debug(self) -> bool:
        """兼容旧版 debug"""
        return self.api.debug

    @property
    def api_host(self) -> str:
        """兼容旧版 api_host"""
        return self.api.host

    @property
    def api_port(self) -> int:
        """兼容旧版 api_port"""
        return self.api.port

    @property
    def database_url(self) -> str:
        """兼容旧版 database_url"""
        return self.database.url

    @property
    def redis_url(self) -> str:
        """兼容旧版 redis_url"""
        if self.redis.password:
            return f"redis://:{self.redis.password}@{self.redis.host}:{self.redis.port}/{self.redis.db}"
        return f"redis://{self.redis.host}:{self.redis.port}/{self.redis.db}"

    @property
    def agent_timeout_seconds(self) -> int:
        """兼容旧版 agent_timeout_seconds"""
        return self.agent.timeout_seconds

    @property
    def agent_temperature(self) -> float:
        """兼容旧版 agent_temperature"""
        return self.llm.temperature

    # LLM 兼容属性
    @property
    def openai_api_key(self) -> str | None:
        """兼容旧版 openai_api_key"""
        return self.llm.openai_api_key

    @property
    def openai_model(self) -> str:
        """兼容旧版 openai_model"""
        return self.llm.model

    @property
    def openai_api_base(self) -> str | None:
        """兼容旧版 openai_api_base"""
        return None

    @property
    def anthropic_api_key(self) -> str | None:
        """兼容旧版 anthropic_api_key"""
        return self.llm.anthropic_api_key

    @property
    def dashscope_api_key(self) -> str | None:
        """兼容旧版 dashscope_api_key"""
        return self.llm.dashscope_api_key

    @property
    def azure_openai_api_key(self) -> str | None:
        """兼容旧版 azure_openai_api_key"""
        return None

    @property
    def azure_openai_endpoint(self) -> str | None:
        """兼容旧版 azure_openai_endpoint"""
        return None

    @property
    def azure_openai_deployment(self) -> str | None:
        """兼容旧版 azure_openai_deployment"""
        return None


# ============ 全局配置实例 ============

@lru_cache
def get_settings() -> AppSettings:
    """
    获取应用配置（单例，带缓存）

    Returns:
        AppSettings: 应用配置实例
    """
    return AppSettings()


def reload_settings() -> AppSettings:
    """
    重新加载配置（清除缓存）

    Returns:
        AppSettings: 新的应用配置实例
    """
    get_settings.cache_clear()
    return get_settings()


# ============ 配置加载器 ============

class ConfigLoader:
    """配置加载器"""

    @staticmethod
    def load_from_file(file_path: str) -> Dict[str, Any]:
        """
        从文件加载配置

        Args:
            file_path: 配置文件路径（YAML/JSON）

        Returns:
            配置字典
        """
        import json
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")

        if path.suffix in [".yaml", ".yml"]:
            try:
                import yaml
                with open(path, encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except ImportError:
                raise ImportError("PyYAML not installed. Install with: pip install pyyaml")
        elif path.suffix == ".json":
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        else:
            raise ValueError(f"Unsupported config file format: {path.suffix}")

    @staticmethod
    def save_to_file(config: Dict[str, Any], file_path: str, format: str = "yaml"):
        """
        保存配置到文件

        Args:
            config: 配置字典
            file_path: 文件路径
            format: 文件格式（yaml/json）
        """
        import json
        from pathlib import Path

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if format in ["yaml", "yml"]:
            try:
                import yaml
                with open(path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
            except ImportError:
                raise ImportError("PyYAML not installed")
        elif format == "json":
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported format: {format}")


# ============ 便捷函数 ============

def get_llm_settings() -> LLMSettings:
    """获取 LLM 配置"""
    return get_settings().llm


def get_database_settings() -> DatabaseSettings:
    """获取数据库配置"""
    return get_settings().database


def get_agent_settings() -> AgentSettings:
    """获取 Agent 配置"""
    return get_settings().agent


def get_api_settings() -> APISettings:
    """获取 API 配置"""
    return get_settings().api


def get_redis_settings() -> RedisSettings:
    """获取 Redis 配置"""
    return get_settings().redis


def get_celery_settings() -> CelerySettings:
    """获取 Celery 配置"""
    return get_settings().celery


def get_logging_settings() -> LoggingSettings:
    """获取日志配置"""
    return get_settings().logging


def get_security_settings() -> SecuritySettings:
    """获取安全配置"""
    return get_settings().security
