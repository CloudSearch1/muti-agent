"""
集中配置管理模块

使用 Pydantic Settings 统一管理所有配置
"""

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
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
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    dashscope_api_key: Optional[str] = Field(default=None)
    
    # 缓存配置
    use_cache: bool = Field(default=True)
    cache_ttl: int = Field(default=3600)
    semantic_cache_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        extra="ignore",
    )


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
    )


# ============ Redis 配置 ============

class RedisSettings(BaseSettings):
    """Redis 配置"""
    enabled: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0, le=15)
    password: Optional[str] = Field(default=None)
    max_connections: int = Field(default=50, ge=10, le=200)
    
    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        extra="ignore",
    )


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
    architect_patterns: List[str] = Field(default=["MVC", "微服务"])
    
    # 执行配置
    timeout_seconds: int = Field(default=300, ge=60, le=600)
    max_retries: int = Field(default=3, ge=0, le=10)
    
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        extra="ignore",
    )


# ============ API 配置 ============

class APISettings(BaseSettings):
    """API 配置"""
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=16)
    debug: bool = Field(default=False)
    
    # CORS
    cors_origins: List[str] = Field(default=["*"])
    
    # 限流
    rate_limit: int = Field(default=60, ge=10, le=1000)
    
    # GZip
    gzip_min_size: int = Field(default=1000, ge=100, le=10000)
    
    model_config = SettingsConfigDict(
        env_prefix="API_",
        env_file=".env",
        extra="ignore",
    )


# ============ 日志配置 ============

class LoggingSettings(BaseSettings):
    """日志配置"""
    level: str = Field(default="INFO")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file: Optional[str] = Field(default=None)
    max_bytes: int = Field(default=10485760, ge=1048576, le=104857600)  # 10MB
    backup_count: int = Field(default=5, ge=1, le=20)
    
    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        extra="ignore",
    )


# ============ 安全配置 ============

class SecuritySettings(BaseSettings):
    """安全配置"""
    secret_key: str = Field(default="change-me-in-production")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    
    # 审计
    enable_audit: bool = Field(default=True)
    audit_log_file: Optional[str] = Field(default=None)
    
    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        env_file=".env",
        extra="ignore",
    )


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
    agent: AgentSettings = Field(default_factory=AgentSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    
    # 验证
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


# ============ 全局配置实例 ============

@lru_cache()
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
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except ImportError:
                raise ImportError("PyYAML not installed. Install with: pip install pyyaml")
        elif path.suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
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
