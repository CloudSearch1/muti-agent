"""
LLM 数据模型定义
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    """服务商类型"""
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai-compatible"
    ANTHROPIC = "anthropic"


class LLMProvider(BaseModel):
    """LLM 服务商配置"""
    name: str = Field(..., description="服务商标识")
    display_name: str = Field(..., description="显示名称")
    type: ProviderType = Field(default=ProviderType.OPENAI_COMPATIBLE, description="服务商类型")
    base_url: str = Field(..., description="API 基础 URL")
    models: list[str] = Field(default_factory=list, description="支持的模型列表")
    default_model: str = Field(..., description="默认模型")
    env_key: str | None = Field(default=None, description="API Key 环境变量名")
    api_key: str | None = Field(default=None, description="API Key (运行时设置)")
    enabled: bool = Field(default=True, description="是否启用")

    model_config = {"extra": "ignore"}


class LLMConfig(BaseModel):
    """LLM 完整配置"""
    providers: list[LLMProvider] = Field(default_factory=list, description="服务商列表")
    default: str = Field(default="openai/gpt-4o", description="默认模型 (provider/model)")
    fallback: str | None = Field(default=None, description="备用模型")
    settings: dict[str, Any] = Field(
        default_factory=lambda: {
            "timeout": 60,
            "max_retries": 3,
            "temperature": 0.7,
            "max_tokens": 4096,
        },
        description="全局设置",
    )

    model_config = {"extra": "ignore"}

    def get_provider(self, name: str) -> LLMProvider | None:
        """获取服务商配置"""
        for p in self.providers:
            if p.name == name:
                return p
        return None

    def get_default_provider(self) -> LLMProvider | None:
        """获取默认服务商"""
        if "/" in self.default:
            provider_name = self.default.split("/")[0]
            return self.get_provider(provider_name)
        return self.providers[0] if self.providers else None


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")

    model_config = {"extra": "ignore"}


class ChatRequest(BaseModel):
    """聊天请求"""
    messages: list[ChatMessage] = Field(..., description="消息列表")
    model: str | None = Field(default=None, description="模型 (provider/model 格式)")
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)
    stream: bool = Field(default=False, description="是否流式输出")
    extra: dict[str, Any] = Field(default_factory=dict, description="额外参数")

    model_config = {"extra": "ignore"}


class ChatResponse(BaseModel):
    """聊天响应"""
    id: str = Field(..., description="响应 ID")
    model: str = Field(..., description="使用的模型")
    provider: str = Field(..., description="服务商")
    content: str = Field(..., description="回复内容")
    role: str = Field(default="assistant", description="角色")
    usage: dict[str, int] = Field(default_factory=dict, description="Token 使用量")
    created: datetime = Field(default_factory=datetime.now, description="创建时间")
    latency_ms: float = Field(default=0, description="响应延迟(ms)")

    model_config = {"extra": "ignore"}


class ProviderInfo(BaseModel):
    """服务商信息 (用于 API 响应)"""
    name: str
    display_name: str
    type: str
    models: list[str]
    default_model: str
    enabled: bool
    configured: bool = Field(default=False, description="是否已配置 API Key")


class TestConnectionResult(BaseModel):
    """连接测试结果"""
    provider: str
    model: str
    success: bool
    latency_ms: float = Field(default=0)
    error: str | None = None
    response_preview: str | None = None


class ModelConfigRequest(BaseModel):
    """模型配置请求"""
    provider: str = Field(..., description="服务商名称")
    api_key: str | None = Field(default=None, description="API Key")
    base_url: str | None = Field(default=None, description="自定义 Base URL")
    enabled: bool | None = Field(default=None, description="是否启用")
    default_model: str | None = Field(default=None, description="默认模型")