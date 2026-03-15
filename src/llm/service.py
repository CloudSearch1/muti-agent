"""
LLM 服务

职责：提供统一的 LLM 调用接口，支持多提供商
"""

from __future__ import annotations

import asyncio
import random
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


# 重试配置
MAX_RETRIES = 3
BASE_DELAY = 1.0  # 基础延迟（秒）
MAX_DELAY = 30.0  # 最大延迟（秒）


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

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        判断错误是否可重试

        可重试的错误包括：
        - 网络超时
        - 服务暂时不可用 (5xx)
        - 速率限制 (429)
        """
        error_str = str(error).lower()
        retryable_indicators = [
            "timeout",
            "timed out",
            "connection",
            "network",
            "5xx",
            "500",
            "502",
            "503",
            "504",
            "429",
            "rate limit",
            "overloaded",
            "capacity",
        ]
        return any(indicator in error_str for indicator in retryable_indicators)

    async def _execute_with_retry(
        self,
        operation: str,
        func,
        *args,
        **kwargs,
    ):
        """
        使用指数退避重试执行操作

        Args:
            operation: 操作名称（用于日志）
            func: 要执行的异步函数
            *args, **kwargs: 传递给函数的参数

        Returns:
            函数执行结果

        Raises:
            LLMError: 重试耗尽后抛出最后一个错误
        """
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except LLMConfigError:
                # 配置错误不重试
                raise
            except LLMError as e:
                last_error = e
                if not self._is_retryable_error(e):
                    # 不可重试的错误直接抛出
                    raise
                if attempt < MAX_RETRIES - 1:
                    # 计算退避时间（指数退避 + 随机抖动）
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    jitter = random.uniform(0, delay * 0.1)
                    total_delay = delay + jitter

                    logger.warning(
                        f"LLM {operation} failed (attempt {attempt + 1}/{MAX_RETRIES}), "
                        f"retrying in {total_delay:.2f}s",
                        error=str(e),
                    )
                    await asyncio.sleep(total_delay)
            except Exception as e:
                last_error = e
                if not self._is_retryable_error(e):
                    raise LLMError(
                        f"LLM {operation} failed: {e}",
                        provider=self._provider.NAME if self._provider else None,
                        original_error=e,
                    ) from e
                if attempt < MAX_RETRIES - 1:
                    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                    jitter = random.uniform(0, delay * 0.1)
                    total_delay = delay + jitter

                    logger.warning(
                        f"LLM {operation} failed (attempt {attempt + 1}/{MAX_RETRIES}), "
                        f"retrying in {total_delay:.2f}s",
                        error=str(e),
                    )
                    await asyncio.sleep(total_delay)

        # 所有重试都失败
        raise LLMError(
            f"LLM {operation} failed after {MAX_RETRIES} attempts",
            provider=self._provider.NAME if self._provider else None,
            original_error=last_error,
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        生成响应（带重试机制）

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

        async def _do_generate():
            return await self._provider.generate(
                full_prompt,
                temperature=temperature,
                max_tokens=max_tokens or 2048,
                **kwargs,
            )

        try:
            content = await self._execute_with_retry("generate", _do_generate)

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
            ) from e

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
        对话（带重试机制）

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

        async def _do_chat():
            return await self._provider.generate(
                full_prompt,
                temperature=temperature,
                max_tokens=max_tokens or 2048,
                **kwargs,
            )

        try:
            content = await self._execute_with_retry("chat", _do_chat)

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
            ) from e


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
