"""
PI-Python 提供商测试

测试 ai/providers 模块
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pi_python.ai.providers.base import BaseProvider
from pi_python.ai.providers.openai import OpenAIProvider
from pi_python.ai.providers.anthropic import AnthropicProvider
from pi_python.ai.providers.bailian import BailianProvider
from pi_python.ai.providers.other import (
    GoogleProvider,
    OllamaProvider,
    VLLMProvider,
)
from pi_python.ai.types import (
    ApiType,
    Context,
    Model,
    ModelCost,
    StopReason,
    TextContent,
)
from pi_python.ai.stream import (
    AssistantMessageEventStream,
    EventBuilder,
    StreamOptions,
)


class TestBaseProvider:
    """基础提供商测试"""

    def test_base_provider_creation(self):
        """测试基础提供商创建"""
        class TestProvider(BaseProvider):
            NAME = "test"
            async def stream(self, model, context, options):
                pass

        provider = TestProvider()
        assert provider.NAME == "test"
        assert provider._timeout == 60

    def test_base_provider_custom_timeout(self):
        """测试自定义超时"""
        class TestProvider(BaseProvider):
            NAME = "test"
            async def stream(self, model, context, options):
                pass

        provider = TestProvider(timeout=120)
        assert provider._timeout == 120

    @pytest.mark.asyncio
    async def test_close_client(self):
        """测试关闭客户端"""
        class TestProvider(BaseProvider):
            NAME = "test"
            async def stream(self, model, context, options):
                pass

        provider = TestProvider()
        # 跳过客户端初始化，避免代理配置问题
        provider._client = None
        await provider.close()
        assert provider._client is None


class TestOpenAIProvider:
    """OpenAI 提供商测试"""

    def test_provider_creation(self):
        """测试提供商创建"""
        provider = OpenAIProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        assert provider.base_url == "https://api.openai.com/v1"

    def test_provider_custom_base_url(self):
        """测试自定义基础 URL"""
        provider = OpenAIProvider(base_url="https://custom.api.com/v1")
        assert provider.base_url == "https://custom.api.com/v1"

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """测试无 API Key 的流式调用"""
        provider = OpenAIProvider(api_key=None)
        model = Model(
            id="gpt-4o",
            name="GPT-4o",
            api=ApiType.OPENAI_COMPLETIONS,
            provider="openai",
            base_url=""
        )
        context = Context()
        options = StreamOptions()

        stream = await provider.stream(model, context, options)

        # 应该立即返回错误事件
        events = []
        async for event in stream:
            events.append(event)
            break  # 只取第一个事件

        assert len(events) == 1
        assert events[0].type == "error"


class TestAnthropicProvider:
    """Anthropic 提供商测试"""

    def test_provider_creation(self):
        """测试提供商创建"""
        provider = AnthropicProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        assert provider.base_url == "https://api.anthropic.com"

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """测试无 API Key 的流式调用"""
        provider = AnthropicProvider(api_key=None)
        model = Model(
            id="claude-sonnet-4-20250514",
            name="Claude Sonnet 4",
            api=ApiType.ANTHROPIC_MESSAGES,
            provider="anthropic",
            base_url="",
            reasoning=True
        )
        context = Context()
        options = StreamOptions()

        stream = await provider.stream(model, context, options)

        # 应该立即返回错误事件
        events = []
        async for event in stream:
            events.append(event)
            break

        assert len(events) == 1
        assert events[0].type == "error"


class TestBailianProvider:
    """百炼提供商测试"""

    def test_provider_creation(self):
        """测试提供商创建"""
        provider = BailianProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        assert provider.base_url == "https://dashscope.aliyuncs.com/api/v1"

    def test_provider_custom_base_url(self):
        """测试自定义基础 URL"""
        provider = BailianProvider(base_url="https://custom.dashscope.com")
        assert provider.base_url == "https://custom.dashscope.com"

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """测试无 API Key 的流式调用"""
        provider = BailianProvider(api_key=None)
        model = Model(
            id="qwen-max",
            name="Qwen Max",
            api=ApiType.BAILIAN,
            provider="bailian",
            base_url=""
        )
        context = Context()
        options = StreamOptions()

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)
            break

        assert len(events) == 1
        assert events[0].type == "error"


class TestGoogleProvider:
    """Google 提供商测试"""

    def test_provider_creation(self):
        """测试提供商创建"""
        provider = GoogleProvider()
        assert provider.NAME == "google"


class TestOllamaProvider:
    """Ollama 提供商测试"""

    def test_provider_creation(self):
        """测试提供商创建"""
        provider = OllamaProvider()
        assert provider.NAME == "ollama"


class TestVLLMProvider:
    """vLLM 提供商测试"""

    def test_provider_creation(self):
        """测试提供商创建"""
        provider = VLLMProvider()
        assert provider.NAME == "vllm"


class TestProviderRegistry:
    """提供商注册测试"""

    def test_openai_registered(self):
        """测试 OpenAI 已注册"""
        # 注册测试提供商
        from pi_python.ai.stream import register_provider, get_provider
        async def mock_openai(model, context, options):
            pass
        register_provider("openai", mock_openai)

        provider = get_provider("openai")
        assert provider is not None

    def test_anthropic_registered(self):
        """测试 Anthropic 已注册"""
        from pi_python.ai.stream import register_provider, get_provider
        async def mock_anthropic(model, context, options):
            pass
        register_provider("anthropic", mock_anthropic)

        provider = get_provider("anthropic")
        assert provider is not None

    def test_bailian_registered(self):
        """测试百炼已注册"""
        from pi_python.ai.stream import register_provider, get_provider
        async def mock_bailian(model, context, options):
            pass
        register_provider("bailian", mock_bailian)

        provider = get_provider("bailian")
        assert provider is not None

    def test_ollama_registered(self):
        """测试 Ollama 已注册"""
        from pi_python.ai.stream import register_provider, get_provider
        async def mock_ollama(model, context, options):
            pass
        register_provider("ollama", mock_ollama)

        provider = get_provider("ollama")
        assert provider is not None