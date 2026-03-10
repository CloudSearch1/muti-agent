"""
LLM 服务

职责：提供统一的 LLM 调用接口，支持多提供商
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import structlog
from pydantic import BaseModel, Field

from ..config.settings import AppSettings as Settings
from ..config.settings import get_settings
from .llm_provider import (
    AzureOpenAIProvider,
    BailianProvider,
    BaseProvider,
    ClaudeProvider,
    LLMConfigError,
    LLMError,
    OpenAIProvider,
)

logger = structlog.get_logger(__name__)


class LLMMessage(BaseModel):
    """LLM 消息"""

    role: str = Field(..., description="角色 (system/user/assistant)")
    content: str = Field(..., description="消息内容")


class LLMResponse(BaseModel):
    """LLM 响应"""

    content: str = Field(..., description="响应内容")
    model: str = Field(..., description="使用的模型")
    usage: dict[str, int] = Field(default_factory=dict, description="Token 使用量")
    finish_reason: str | None = Field(default=None, description="结束原因")


class LLMService:
    """
    LLM 服务

    统一管理 LLM 调用，支持多提供商切换
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._provider: BaseProvider | None = None
        self._initialize_provider()

        logger.info(
            "LLMService initialized",
            provider=self._provider.NAME if self._provider else "none",
        )

    def _initialize_provider(self) -> None:
        """初始化提供商"""
        # 优先使用 Azure
        if self.settings.azure_openai_api_key and self.settings.azure_openai_endpoint:
            self._provider = AzureOpenAIProvider(
                api_key=self.settings.azure_openai_api_key,
                endpoint=self.settings.azure_openai_endpoint,
                deployment=self.settings.azure_openai_deployment,
            )
        # 其次使用 Claude
        elif self.settings.anthropic_api_key:
            self._provider = ClaudeProvider(
                api_key=self.settings.anthropic_api_key,
            )
        # 再次使用 OpenAI
        elif self.settings.openai_api_key:
            self._provider = OpenAIProvider(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_api_base or "https://api.openai.com/v1",
                model=self.settings.openai_model,
            )
        # 最后使用百炼
        elif self.settings.dashscope_api_key:
            self._provider = BailianProvider(
                api_key=self.settings.dashscope_api_key,
            )
        else:
            logger.warning("No LLM API key configured")

    @property
    def provider(self) -> BaseProvider | None:
        """获取当前提供商"""
        return self._provider

    def is_configured(self) -> bool:
        """检查是否已配置"""
        return self._provider is not None

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        生成响应

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度
            max_tokens: 最大 token 数

        Returns:
            LLM 响应
        """
        if not self._provider:
            raise LLMConfigError("LLM provider not configured")

        # 构建完整提示
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        try:
            content = await self._provider.generate(
                full_prompt,
                temperature=temperature,
                max_tokens=max_tokens or 2048,
                **kwargs,
            )

            return LLMResponse(
                content=content,
                model=self._provider.NAME,
                usage={},
            )
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(
                f"LLM generate failed: {e}",
                provider=self._provider.NAME if self._provider else None,
                original_error=e,
            )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式生成"""
        if not self._provider:
            raise LLMConfigError("LLM provider not configured")

        # 构建完整提示
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        async for chunk in self._provider.generate_stream(
            full_prompt,
            temperature=temperature,
            max_tokens=max_tokens or 2048,
            **kwargs,
        ):
            yield chunk

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        对话

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]

        Returns:
            LLM 响应
        """
        if not self._provider:
            raise LLMConfigError("LLM provider not configured")

        # 构建提示
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"[System]: {content}")
            elif role == "user":
                prompt_parts.append(f"[User]: {content}")
            elif role == "assistant":
                prompt_parts.append(f"[Assistant]: {content}")

        full_prompt = "\n".join(prompt_parts)

        try:
            content = await self._provider.generate(
                full_prompt,
                temperature=temperature,
                max_tokens=max_tokens or 2048,
                **kwargs,
            )

            return LLMResponse(
                content=content,
                model=self._provider.NAME,
                usage={},
            )
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(
                f"LLM chat failed: {e}",
                provider=self._provider.NAME if self._provider else None,
                original_error=e,
            )


# 全局单例
_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """获取 LLM 服务单例"""
    global _service
    if _service is None:
        _service = LLMService()
    return _service


def reset_llm_service() -> LLMService:
    """重置 LLM 服务"""
    global _service
    _service = LLMService()
    return _service
