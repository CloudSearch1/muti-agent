"""
IntelliTeam 配置管理模块

提供统一的配置加载和验证
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用配置
    app_name: str = Field(default="IntelliTeam", description="应用名称")
    app_env: str = Field(default="development", description="环境")
    debug: bool = Field(default=True, description="调试模式")
    
    # 服务器配置
    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8080, description="监听端口")
    
    # LLM 配置
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API Key")
    openai_api_base: str = Field(default="https://api.openai.com/v1", description="API Base URL")
    openai_model: str = Field(default="gpt-4", description="模型名称")
    
    # 数据库配置
    database_url: Optional[str] = Field(default=None, description="数据库 URL")
    redis_url: Optional[str] = Field(default=None, description="Redis URL")
    
    # Agent 配置
    agent_max_iterations: int = Field(default=10, description="最大迭代次数")
    agent_timeout_seconds: int = Field(default=300, description="超时时间")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    def is_production(self) -> bool:
        """是否生产环境"""
        return self.app_env == "production"
    
    def is_development(self) -> bool:
        """是否开发环境"""
        return self.app_env == "development"


# 全局配置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置单例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """重新加载配置"""
    global _settings
    _settings = Settings()
    return _settings
