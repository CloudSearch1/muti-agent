"""
配置管理

职责：统一管理应用配置，支持环境变量和配置文件
"""

from typing import Any

import structlog
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    """
    应用配置
    
    从环境变量和 .env 文件加载配置
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===========================================
    # 应用配置
    # ===========================================

    app_name: str = Field(default="IntelliTeam", description="应用名称")
    app_env: str = Field(default="development", description="环境")
    debug: bool = Field(default=True, description="调试模式")
    log_level: str = Field(default="INFO", description="日志级别")

    # ===========================================
    # LLM 配置
    # ===========================================

    openai_api_key: str | None = Field(default=None, description="OpenAI API Key")
    openai_api_base: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API 基础 URL",
    )
    openai_model: str = Field(default="gpt-4", description="OpenAI 模型")

    azure_openai_api_key: str | None = Field(default=None)
    azure_openai_endpoint: str | None = Field(default=None)
    azure_openai_deployment: str | None = Field(default=None)

    # ===========================================
    # 数据库配置
    # ===========================================

    database_url: str = Field(
        default="postgresql+asyncpg://localhost:5432/intelliteam",
        description="PostgreSQL 连接 URL",
    )

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis 连接 URL",
    )

    # ===========================================
    # 向量数据库配置
    # ===========================================

    milvus_host: str = Field(default="localhost", description="Milvus 主机")
    milvus_port: int = Field(default=19530, description="Milvus 端口")
    milvus_user: str | None = Field(default=None)
    milvus_password: str | None = Field(default=None)

    # ===========================================
    # 嵌入模型配置
    # ===========================================

    embedding_model: str = Field(
        default="BAAI/bge-m3",
        description="嵌入模型",
    )
    embedding_device: str = Field(default="cpu", description="嵌入设备")
    embedding_dimension: int = Field(default=1024, description="嵌入维度")

    # ===========================================
    # Agent 配置
    # ===========================================

    agent_max_iterations: int = Field(default=10, description="Agent 最大迭代次数")
    agent_timeout_seconds: int = Field(default=300, description="Agent 超时时间")
    agent_temperature: float = Field(default=0.3, description="Agent 温度参数")

    # ===========================================
    # API 配置
    # ===========================================

    api_host: str = Field(default="0.0.0.0", description="API 监听地址")
    api_port: int = Field(default=8000, description="API 端口")
    api_workers: int = Field(default=4, description="API 工作进程数")

    # ===========================================
    # 验证方法
    # ===========================================

    def validate_llm_config(self) -> bool:
        """验证 LLM 配置"""
        if not self.openai_api_key and not self.azure_openai_api_key:
            logger.warning("No LLM API key configured")
            return False
        return True

    def validate_database_config(self) -> bool:
        """验证数据库配置"""
        if not self.database_url:
            logger.error("Database URL not configured")
            return False
        return True

    def is_production(self) -> bool:
        """检查是否为生产环境"""
        return self.app_env == "production"

    def is_development(self) -> bool:
        """检查是否为开发环境"""
        return self.app_env == "development"

    def get_model_config(self) -> dict[str, Any]:
        """获取模型配置"""
        if self.azure_openai_api_key:
            return {
                "provider": "azure",
                "api_key": self.azure_openai_api_key,
                "endpoint": self.azure_openai_endpoint,
                "deployment": self.azure_openai_deployment,
            }
        else:
            return {
                "provider": "openai",
                "api_key": self.openai_api_key,
                "base_url": self.openai_api_base,
                "model": self.openai_model,
            }


# 全局单例
_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局配置单例"""
    global _settings
    if _settings is None:
        _settings = Settings()
        logger.info(
            "Settings loaded",
            app_name=_settings.app_name,
            app_env=_settings.app_env,
        )
    return _settings


def reload_settings() -> Settings:
    """重新加载配置"""
    global _settings
    _settings = Settings()
    return _settings
