"""
PI-Python 模型注册和管理

提供模型发现和注册功能
"""

from __future__ import annotations

from collections.abc import Callable

from .types import ApiType, Model, ModelCost


class ModelRegistry:
    """模型注册表"""

    _models: dict[str, Model] = {}
    _providers: dict[str, Callable] = {}

    @classmethod
    def register_model(cls, model: Model) -> None:
        """注册模型"""
        key = f"{model.provider}/{model.id}"
        cls._models[key] = model

    @classmethod
    def register_provider(cls, name: str, provider_fn: Callable) -> None:
        """注册提供商"""
        cls._providers[name] = provider_fn

    @classmethod
    def get_model(cls, provider: str, model_id: str) -> Model | None:
        """获取模型"""
        key = f"{provider}/{model_id}"
        return cls._models.get(key)

    @classmethod
    def get_provider(cls, name: str) -> Callable | None:
        """获取提供商函数"""
        return cls._providers.get(name)

    @classmethod
    def list_models(cls, provider: str | None = None) -> list[Model]:
        """列出模型"""
        models = list(cls._models.values())
        if provider:
            models = [m for m in models if m.provider == provider]
        return models

    @classmethod
    def list_providers(cls) -> list[str]:
        """列出提供商"""
        return list(cls._providers.keys())

    @classmethod
    def clear(cls) -> None:
        """清除注册表"""
        cls._models.clear()
        cls._providers.clear()


# 便捷函数
def register_model(model: Model) -> None:
    """注册模型"""
    ModelRegistry.register_model(model)


def register_provider(name: str, provider_fn: Callable) -> None:
    """注册提供商"""
    ModelRegistry.register_provider(name, provider_fn)


def get_model(provider: str, model_id: str) -> Model:
    """获取模型"""
    model = ModelRegistry.get_model(provider, model_id)
    if not model:
        raise ValueError(f"Unknown model: {provider}/{model_id}")
    return model


def get_provider(name: str) -> Callable | None:
    """获取提供商函数"""
    return ModelRegistry.get_provider(name)


def list_models(provider: str | None = None) -> list[Model]:
    """列出模型"""
    return ModelRegistry.list_models(provider)


# ============ 内置模型定义 ============

# OpenAI 模型
OPENAI_MODELS = [
    Model(
        id="gpt-4o",
        name="GPT-4o",
        api=ApiType.OPENAI_COMPLETIONS,
        provider="openai",
        base_url="https://api.openai.com/v1",
        context_window=128000,
        max_tokens=16384,
        cost=ModelCost(input=2.5, output=10.0)
    ),
    Model(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        api=ApiType.OPENAI_COMPLETIONS,
        provider="openai",
        base_url="https://api.openai.com/v1",
        context_window=128000,
        max_tokens=16384,
        cost=ModelCost(input=0.15, output=0.6)
    ),
    Model(
        id="gpt-4-turbo",
        name="GPT-4 Turbo",
        api=ApiType.OPENAI_COMPLETIONS,
        provider="openai",
        base_url="https://api.openai.com/v1",
        context_window=128000,
        max_tokens=4096,
        cost=ModelCost(input=10.0, output=30.0)
    ),
    Model(
        id="o1",
        name="o1",
        api=ApiType.OPENAI_COMPLETIONS,
        provider="openai",
        base_url="https://api.openai.com/v1",
        reasoning=True,
        context_window=200000,
        max_tokens=100000,
        cost=ModelCost(input=15.0, output=60.0)
    ),
    Model(
        id="o1-mini",
        name="o1 Mini",
        api=ApiType.OPENAI_COMPLETIONS,
        provider="openai",
        base_url="https://api.openai.com/v1",
        reasoning=True,
        context_window=128000,
        max_tokens=65536,
        cost=ModelCost(input=1.5, output=6.0)
    ),
]

# Anthropic 模型
ANTHROPIC_MODELS = [
    Model(
        id="claude-sonnet-4-20250514",
        name="Claude Sonnet 4",
        api=ApiType.ANTHROPIC_MESSAGES,
        provider="anthropic",
        base_url="https://api.anthropic.com",
        reasoning=True,
        context_window=200000,
        max_tokens=8192,
        cost=ModelCost(input=3.0, output=15.0)
    ),
    Model(
        id="claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        api=ApiType.ANTHROPIC_MESSAGES,
        provider="anthropic",
        base_url="https://api.anthropic.com",
        context_window=200000,
        max_tokens=8192,
        cost=ModelCost(input=3.0, output=15.0)
    ),
    Model(
        id="claude-3-5-haiku-20241022",
        name="Claude 3.5 Haiku",
        api=ApiType.ANTHROPIC_MESSAGES,
        provider="anthropic",
        base_url="https://api.anthropic.com",
        context_window=200000,
        max_tokens=8192,
        cost=ModelCost(input=0.8, output=4.0)
    ),
    Model(
        id="claude-3-opus-20240229",
        name="Claude 3 Opus",
        api=ApiType.ANTHROPIC_MESSAGES,
        provider="anthropic",
        base_url="https://api.anthropic.com",
        context_window=200000,
        max_tokens=4096,
        cost=ModelCost(input=15.0, output=75.0)
    ),
]

# Google 模型
GOOGLE_MODELS = [
    Model(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        api=ApiType.GOOGLE_GENERATIVE_AI,
        provider="google",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        context_window=1048576,
        max_tokens=8192,
        cost=ModelCost(input=0.1, output=0.4)
    ),
    Model(
        id="gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        api=ApiType.GOOGLE_GENERATIVE_AI,
        provider="google",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        context_window=2097152,
        max_tokens=8192,
        cost=ModelCost(input=1.25, output=5.0)
    ),
]

# 阿里百炼模型
BAILIAN_MODELS = [
    Model(
        id="qwen-max",
        name="Qwen Max",
        api=ApiType.BAILIAN,
        provider="bailian",
        base_url="https://dashscope.aliyuncs.com/api/v1",
        context_window=32768,
        max_tokens=8192,
        cost=ModelCost(input=0.04, output=0.12)
    ),
    Model(
        id="qwen-plus",
        name="Qwen Plus",
        api=ApiType.BAILIAN,
        provider="bailian",
        base_url="https://dashscope.aliyuncs.com/api/v1",
        context_window=131072,
        max_tokens=8192,
        cost=ModelCost(input=0.0008, output=0.002)
    ),
    Model(
        id="qwen-turbo",
        name="Qwen Turbo",
        api=ApiType.BAILIAN,
        provider="bailian",
        base_url="https://dashscope.aliyuncs.com/api/v1",
        context_window=131072,
        max_tokens=8192,
        cost=ModelCost(input=0.0003, output=0.0006)
    ),
]

# Ollama 模型（本地）
OLLAMA_MODELS = [
    Model(
        id="llama3.2",
        name="Llama 3.2",
        api=ApiType.OLLAMA,
        provider="ollama",
        base_url="http://localhost:11434",
        context_window=128000,
        max_tokens=4096,
        cost=ModelCost()  # 本地模型免费
    ),
    Model(
        id="qwen2.5-coder",
        name="Qwen 2.5 Coder",
        api=ApiType.OLLAMA,
        provider="ollama",
        base_url="http://localhost:11434",
        context_window=128000,
        max_tokens=8192,
        cost=ModelCost()
    ),
]


def register_builtin_models() -> None:
    """注册内置模型"""
    for model in OPENAI_MODELS:
        ModelRegistry.register_model(model)
    for model in ANTHROPIC_MODELS:
        ModelRegistry.register_model(model)
    for model in GOOGLE_MODELS:
        ModelRegistry.register_model(model)
    for model in BAILIAN_MODELS:
        ModelRegistry.register_model(model)
    for model in OLLAMA_MODELS:
        ModelRegistry.register_model(model)


# 自动注册内置模型
register_builtin_models()
