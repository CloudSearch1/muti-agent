"""
PI-Python 与现有系统的集成适配器

提供与 src/llm/ 的向后兼容接口
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .ai import (
    Context,
    Model,
    complete,
    get_model,
    stream,
)
from .ai.stream import StreamOptions

__all__ = [
    "LLMProviderAdapter",
    "LLMFactoryAdapter",
    "llm_generate",
    "llm_generate_json",
    "llm_generate_stream",
    "init_llm_providers",
]


class LLMProviderAdapter:
    """
    LLM 提供商适配器

    将 pi_python.ai 适配到现有 src/llm/ 接口
    """

    def __init__(
        self,
        provider: str,
        model_id: str,
        api_key: str | None = None,
    ):
        """
        初始化适配器

        Args:
            provider: 提供商名称
            model_id: 模型 ID
            api_key: API Key（可选，默认从环境变量读取）
        """
        self.provider: str = provider
        self.model_id: str = model_id
        self.api_key: str | None = api_key
        self._model: Model | None = None

    @property
    def model(self) -> Model:
        """获取模型"""
        if self._model is None:
            self._model = get_model(self.provider, self.model_id)
        return self._model

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """生成文本"""
        context = Context()
        context.add_user_message(prompt)

        options = StreamOptions(
            api_key=self.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        message = await complete(self.model, context, options)
        return message.text

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成 JSON"""
        import json

        json_prompt = f"{prompt}\n\n请以严格的 JSON 格式回复，不要包含其他文字。"
        content = await self.generate(json_prompt, temperature, max_tokens, **kwargs)

        # 清理 markdown 标记
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        return json.loads(cleaned)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式生成"""
        context = Context()
        context.add_user_message(prompt)

        options = StreamOptions(
            api_key=self.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        event_stream = await stream(self.model, context, options)

        async for event in event_stream:
            if event.type == "text_delta" and event.delta:
                yield event.delta


class LLMFactoryAdapter:
    """
    LLM 工厂适配器。

    兼容现有 src/llm/llm_provider.LLMFactory 接口。

    Note:
        此类是向后兼容层，用于适配现有的 LLM 接口。
        底层使用 pi_python.ai.model.ModelRegistry 管理模型。
        区别：
        - LLMFactoryAdapter: 管理 LLMProviderAdapter 实例（高级 API）
        - ModelRegistry: 管理 Model 实例和提供商函数（低级 API）
    """

    _providers: dict[str, LLMProviderAdapter] = {}

    @classmethod
    def register(cls, name: str, provider: LLMProviderAdapter) -> None:
        """注册提供商"""
        cls._providers[name] = provider

    @classmethod
    def get(cls, name: str) -> LLMProviderAdapter | None:
        """获取提供商"""
        return cls._providers.get(name)

    @classmethod
    def get_default(cls) -> LLMProviderAdapter:
        """获取默认提供商"""
        import os
        provider_name = os.getenv("LLM_PROVIDER", "openai")
        provider = cls.get(provider_name)
        if not provider:
            if cls._providers:
                provider = list(cls._providers.values())[0]
            else:
                raise RuntimeError("没有可用的 LLM 提供商")
        return provider

    @classmethod
    def list_providers(cls) -> list[str]:
        """列出所有已注册的提供商"""
        return list(cls._providers.keys())

    @classmethod
    def clear(cls) -> None:
        """清除所有已注册的提供商"""
        cls._providers.clear()


# 便捷函数（兼容现有接口）

async def llm_generate(prompt: str, provider: str | None = None, **kwargs: Any) -> str:
    """便捷函数：生成文本"""
    if provider:
        p = LLMFactoryAdapter.get(provider)
    else:
        p = LLMFactoryAdapter.get_default()

    if not p:
        raise RuntimeError(f"Provider not found: {provider}")

    return await p.generate(prompt, **kwargs)


async def llm_generate_json(prompt: str, provider: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """便捷函数：生成 JSON"""
    if provider:
        p = LLMFactoryAdapter.get(provider)
    else:
        p = LLMFactoryAdapter.get_default()

    if not p:
        raise RuntimeError(f"Provider not found: {provider}")

    return await p.generate_json(prompt, **kwargs)


async def llm_generate_stream(
    prompt: str,
    provider: str | None = None,
    **kwargs: Any
) -> AsyncIterator[str]:
    """便捷函数：流式生成"""
    if provider:
        p = LLMFactoryAdapter.get(provider)
    else:
        p = LLMFactoryAdapter.get_default()

    if not p:
        raise RuntimeError(f"Provider not found: {provider}")

    async for chunk in p.generate_stream(prompt, **kwargs):
        yield chunk


def init_llm_providers() -> None:
    """
    初始化 LLM 提供商

    根据环境变量自动注册可用的提供商
    """
    import os

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        LLMFactoryAdapter.register(
            "openai",
            LLMProviderAdapter("openai", "gpt-4o")
        )

    # Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        LLMFactoryAdapter.register(
            "claude",
            LLMProviderAdapter("anthropic", "claude-sonnet-4-20250514")
        )

    # Azure OpenAI
    if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
        LLMFactoryAdapter.register(
            "azure",
            LLMProviderAdapter("azure", os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4"))
        )

    # 百炼
    if os.getenv("DASHSCOPE_API_KEY"):
        LLMFactoryAdapter.register(
            "bailian",
            LLMProviderAdapter("bailian", "qwen-plus")
        )

    # Ollama
    LLMFactoryAdapter.register(
        "ollama",
        LLMProviderAdapter("ollama", "llama3.2")
    )

    # 如果没有自动注册，注册一个默认的
    if not LLMFactoryAdapter._providers:
        LLMFactoryAdapter.register(
            "openai",
            LLMProviderAdapter("openai", "gpt-4o")
        )
