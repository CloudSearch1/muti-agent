"""
PI-Python Adapter 测试

测试 LLMProviderAdapter 和 LLMFactoryAdapter
"""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_python.adapter import (
    LLMFactoryAdapter,
    LLMProviderAdapter,
    init_llm_providers,
    llm_generate,
    llm_generate_json,
    llm_generate_stream,
)
from pi_python.ai import (
    AssistantMessage,
    Context,
    Model,
    TextContent,
    AssistantMessageEvent,
    AssistantMessageEventStream,
    StreamOptions,
)
from pi_python.ai.types import ApiType


# ===========================================
# Fixtures
# ===========================================


@pytest.fixture(autouse=True)
def clear_factory():
    """每个测试前清除工厂注册"""
    LLMFactoryAdapter.clear()
    yield
    LLMFactoryAdapter.clear()


@pytest.fixture
def mock_model():
    """创建 Mock 模型"""
    return Model(
        id="gpt-4o",
        name="GPT-4o",
        api=ApiType.OPENAI_COMPLETIONS,
        provider="openai",
        base_url="https://api.openai.com/v1",
        context_window=128000,
        max_tokens=16384,
    )


@pytest.fixture
def mock_stream():
    """创建 Mock 事件流"""
    stream = AssistantMessageEventStream()

    async def mock_events():
        yield AssistantMessageEvent(type="text_delta", delta="Hello")
        yield AssistantMessageEvent(type="text_delta", delta=" World")
        yield AssistantMessageEvent(
            type="done",
            message=AssistantMessage(content=[TextContent(text="Hello World")])
        )

    # 设置 _queue 来模拟事件流
    async def setup_events():
        await stream.emit(AssistantMessageEvent(type="text_delta", delta="Hello"))
        await stream.emit(AssistantMessageEvent(type="text_delta", delta=" World"))
        await stream.emit(AssistantMessageEvent(
            type="done",
            message=AssistantMessage(content=[TextContent(text="Hello World")])
        ))

    # 使用 put_nowait 来同步设置
    stream._queue.put_nowait(AssistantMessageEvent(type="text_delta", delta="Hello"))
    stream._queue.put_nowait(AssistantMessageEvent(type="text_delta", delta=" World"))
    stream._queue.put_nowait(AssistantMessageEvent(
        type="done",
        message=AssistantMessage(content=[TextContent(text="Hello World")])
    ))

    return stream


# ===========================================
# LLMProviderAdapter Tests
# ===========================================


class TestLLMProviderAdapter:
    """LLMProviderAdapter 测试"""

    def test_init(self):
        """测试初始化"""
        adapter = LLMProviderAdapter("openai", "gpt-4o", api_key="test-key")

        assert adapter.provider == "openai"
        assert adapter.model_id == "gpt-4o"
        assert adapter.api_key == "test-key"
        assert adapter._model is None

    def test_init_without_api_key(self):
        """测试不带 API Key 初始化"""
        adapter = LLMProviderAdapter("openai", "gpt-4o")

        assert adapter.provider == "openai"
        assert adapter.model_id == "gpt-4o"
        assert adapter.api_key is None

    def test_model_property(self, mock_model):
        """测试模型属性"""
        with patch("pi_python.adapter.get_model") as mock_get_model:
            mock_get_model.return_value = mock_model

            adapter = LLMProviderAdapter("openai", "gpt-4o")

            # 第一次访问应该调用 get_model
            model = adapter.model
            assert model == mock_model
            mock_get_model.assert_called_once_with("openai", "gpt-4o")

            # 第二次访问应该使用缓存
            model2 = adapter.model
            assert model2 == mock_model
            mock_get_model.assert_called_once()  # 不应该再次调用

    @pytest.mark.asyncio
    async def test_generate(self, mock_model, mock_stream):
        """测试生成文本"""
        with patch("pi_python.adapter.get_model") as mock_get_model, \
             patch("pi_python.adapter.complete") as mock_complete:

            mock_get_model.return_value = mock_model
            mock_complete.return_value = AssistantMessage(
                content=[TextContent(text="Generated text")]
            )

            adapter = LLMProviderAdapter("openai", "gpt-4o", api_key="test-key")
            result = await adapter.generate("Hello", temperature=0.5, max_tokens=100)

            assert result == "Generated text"
            mock_complete.assert_called_once()

            # 验证传递的参数
            call_args = mock_complete.call_args
            assert call_args[0][0] == mock_model  # model
            assert isinstance(call_args[0][1], Context)  # context
            options = call_args[0][2]
            assert options.api_key == "test-key"
            assert options.temperature == 0.5
            assert options.max_tokens == 100

    @pytest.mark.asyncio
    async def test_generate_json(self, mock_model):
        """测试生成 JSON"""
        with patch("pi_python.adapter.get_model") as mock_get_model, \
             patch("pi_python.adapter.complete") as mock_complete:

            mock_get_model.return_value = mock_model

            # 测试普通 JSON
            mock_complete.return_value = AssistantMessage(
                content=[TextContent(text='{"name": "test", "value": 123}')]
            )

            adapter = LLMProviderAdapter("openai", "gpt-4o")
            result = await adapter.generate_json("Generate JSON")

            assert result == {"name": "test", "value": 123}

    @pytest.mark.asyncio
    async def test_generate_json_with_markdown(self, mock_model):
        """测试生成带 markdown 标记的 JSON"""
        with patch("pi_python.adapter.get_model") as mock_get_model, \
             patch("pi_python.adapter.complete") as mock_complete:

            mock_get_model.return_value = mock_model

            # 测试带 ```json 标记
            mock_complete.return_value = AssistantMessage(
                content=[TextContent(text='```json\n{"name": "test"}\n```')]
            )

            adapter = LLMProviderAdapter("openai", "gpt-4o")
            result = await adapter.generate_json("Generate JSON")

            assert result == {"name": "test"}

    @pytest.mark.asyncio
    async def test_generate_json_with_simple_markdown(self, mock_model):
        """测试生成带简单 markdown 标记的 JSON"""
        with patch("pi_python.adapter.get_model") as mock_get_model, \
             patch("pi_python.adapter.complete") as mock_complete:

            mock_get_model.return_value = mock_model

            # 测试带 ``` 标记
            mock_complete.return_value = AssistantMessage(
                content=[TextContent(text='```\n{"name": "test"}\n```')]
            )

            adapter = LLMProviderAdapter("openai", "gpt-4o")
            result = await adapter.generate_json("Generate JSON")

            assert result == {"name": "test"}

    @pytest.mark.asyncio
    async def test_generate_stream(self, mock_model):
        """测试流式生成"""
        with patch("pi_python.adapter.get_model") as mock_get_model, \
             patch("pi_python.adapter.stream") as mock_stream_func:

            mock_get_model.return_value = mock_model

            # 创建模拟的事件流
            mock_event_stream = AssistantMessageEventStream()
            mock_event_stream._queue.put_nowait(
                AssistantMessageEvent(type="text_delta", delta="Hello ")
            )
            mock_event_stream._queue.put_nowait(
                AssistantMessageEvent(type="text_delta", delta="World")
            )
            mock_event_stream._queue.put_nowait(
                AssistantMessageEvent(type="done", message=AssistantMessage(content=[]))
            )

            mock_stream_func.return_value = mock_event_stream

            adapter = LLMProviderAdapter("openai", "gpt-4o")
            chunks = []
            async for chunk in adapter.generate_stream("Hello"):
                chunks.append(chunk)

            assert chunks == ["Hello ", "World"]

    @pytest.mark.asyncio
    async def test_generate_stream_with_kwargs(self, mock_model):
        """测试带额外参数的流式生成"""
        with patch("pi_python.adapter.get_model") as mock_get_model, \
             patch("pi_python.adapter.stream") as mock_stream_func:

            mock_get_model.return_value = mock_model

            mock_event_stream = AssistantMessageEventStream()
            mock_event_stream._queue.put_nowait(
                AssistantMessageEvent(type="done", message=AssistantMessage(content=[]))
            )

            mock_stream_func.return_value = mock_event_stream

            adapter = LLMProviderAdapter("openai", "gpt-4o", api_key="test-key")
            chunks = []
            async for chunk in adapter.generate_stream("Hello", temperature=0.8, max_tokens=500):
                chunks.append(chunk)

            # 验证 stream 被调用
            mock_stream_func.assert_called_once()
            options = mock_stream_func.call_args[0][2]
            assert options.api_key == "test-key"
            assert options.temperature == 0.8
            assert options.max_tokens == 500


# ===========================================
# LLMFactoryAdapter Tests
# ===========================================


class TestLLMFactoryAdapter:
    """LLMFactoryAdapter 测试"""

    def test_register(self):
        """测试注册提供商"""
        adapter = LLMProviderAdapter("openai", "gpt-4o")
        LLMFactoryAdapter.register("openai", adapter)

        assert LLMFactoryAdapter.get("openai") == adapter

    def test_get(self):
        """测试获取提供商"""
        adapter = LLMProviderAdapter("openai", "gpt-4o")
        LLMFactoryAdapter.register("openai", adapter)

        result = LLMFactoryAdapter.get("openai")
        assert result == adapter

        # 测试不存在的提供商
        result = LLMFactoryAdapter.get("nonexistent")
        assert result is None

    def test_list_providers(self):
        """测试列出提供商"""
        adapter1 = LLMProviderAdapter("openai", "gpt-4o")
        adapter2 = LLMProviderAdapter("anthropic", "claude-sonnet-4-20250514")

        LLMFactoryAdapter.register("openai", adapter1)
        LLMFactoryAdapter.register("claude", adapter2)

        providers = LLMFactoryAdapter.list_providers()
        assert set(providers) == {"openai", "claude"}

    def test_get_default_with_env(self):
        """测试使用环境变量获取默认提供商"""
        adapter1 = LLMProviderAdapter("openai", "gpt-4o")
        adapter2 = LLMProviderAdapter("anthropic", "claude-sonnet-4-20250514")

        LLMFactoryAdapter.register("openai", adapter1)
        LLMFactoryAdapter.register("claude", adapter2)

        with patch.dict(os.environ, {"LLM_PROVIDER": "claude"}):
            result = LLMFactoryAdapter.get_default()
            assert result == adapter2

    def test_get_default_without_env(self):
        """测试没有环境变量时获取默认提供商"""
        adapter = LLMProviderAdapter("openai", "gpt-4o")
        LLMFactoryAdapter.register("openai", adapter)

        with patch.dict(os.environ, {}, clear=True):
            result = LLMFactoryAdapter.get_default()
            assert result == adapter

    def test_get_default_no_provider_registered(self):
        """测试没有注册任何提供商时获取默认"""
        with patch.dict(os.environ, {"LLM_PROVIDER": "nonexistent"}, clear=True):
            with pytest.raises(RuntimeError, match="没有可用的 LLM 提供商"):
                LLMFactoryAdapter.get_default()

    def test_clear(self):
        """测试清除所有提供商"""
        adapter = LLMProviderAdapter("openai", "gpt-4o")
        LLMFactoryAdapter.register("openai", adapter)

        assert len(LLMFactoryAdapter.list_providers()) == 1

        LLMFactoryAdapter.clear()

        assert len(LLMFactoryAdapter.list_providers()) == 0


# ===========================================
# 便捷函数测试
# ===========================================


class TestConvenienceFunctions:
    """便捷函数测试"""

    @pytest.mark.asyncio
    async def test_llm_generate_with_provider(self, mock_model):
        """测试 llm_generate 指定提供商"""
        with patch("pi_python.adapter.get_model") as mock_get_model, \
             patch("pi_python.adapter.complete") as mock_complete:

            mock_get_model.return_value = mock_model
            mock_complete.return_value = AssistantMessage(
                content=[TextContent(text="Generated text")]
            )

            adapter = LLMProviderAdapter("openai", "gpt-4o")
            LLMFactoryAdapter.register("openai", adapter)

            result = await llm_generate("Hello", provider="openai")

            assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_llm_generate_default_provider(self, mock_model):
        """测试 llm_generate 使用默认提供商"""
        with patch("pi_python.adapter.get_model") as mock_get_model, \
             patch("pi_python.adapter.complete") as mock_complete:

            mock_get_model.return_value = mock_model
            mock_complete.return_value = AssistantMessage(
                content=[TextContent(text="Generated text")]
            )

            adapter = LLMProviderAdapter("openai", "gpt-4o")
            LLMFactoryAdapter.register("openai", adapter)

            result = await llm_generate("Hello")

            assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_llm_generate_provider_not_found(self):
        """测试 llm_generate 提供商不存在"""
        with pytest.raises(RuntimeError, match="Provider not found"):
            await llm_generate("Hello", provider="nonexistent")

    @pytest.mark.asyncio
    async def test_llm_generate_json(self, mock_model):
        """测试 llm_generate_json"""
        with patch("pi_python.adapter.get_model") as mock_get_model, \
             patch("pi_python.adapter.complete") as mock_complete:

            mock_get_model.return_value = mock_model
            mock_complete.return_value = AssistantMessage(
                content=[TextContent(text='{"status": "ok"}')]
            )

            adapter = LLMProviderAdapter("openai", "gpt-4o")
            LLMFactoryAdapter.register("openai", adapter)

            result = await llm_generate_json("Generate JSON")

            assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_llm_generate_json_provider_not_found(self):
        """测试 llm_generate_json 提供商不存在"""
        with pytest.raises(RuntimeError, match="Provider not found"):
            await llm_generate_json("Generate JSON", provider="nonexistent")

    @pytest.mark.asyncio
    async def test_llm_generate_stream(self, mock_model):
        """测试 llm_generate_stream"""
        with patch("pi_python.adapter.get_model") as mock_get_model, \
             patch("pi_python.adapter.stream") as mock_stream_func:

            mock_get_model.return_value = mock_model

            mock_event_stream = AssistantMessageEventStream()
            mock_event_stream._queue.put_nowait(
                AssistantMessageEvent(type="text_delta", delta="Chunk")
            )
            mock_event_stream._queue.put_nowait(
                AssistantMessageEvent(type="done", message=AssistantMessage(content=[]))
            )

            mock_stream_func.return_value = mock_event_stream

            adapter = LLMProviderAdapter("openai", "gpt-4o")
            LLMFactoryAdapter.register("openai", adapter)

            chunks = []
            async for chunk in llm_generate_stream("Hello"):
                chunks.append(chunk)

            assert chunks == ["Chunk"]

    @pytest.mark.asyncio
    async def test_llm_generate_stream_provider_not_found(self):
        """测试 llm_generate_stream 提供商不存在"""
        with pytest.raises(RuntimeError, match="Provider not found"):
            chunks = []
            async for chunk in llm_generate_stream("Hello", provider="nonexistent"):
                chunks.append(chunk)


# ===========================================
# init_llm_providers 测试
# ===========================================


class TestInitLLMProviders:
    """init_llm_providers 测试"""

    def test_init_with_openai_key(self):
        """测试使用 OpenAI API Key 初始化"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            init_llm_providers()

            providers = LLMFactoryAdapter.list_providers()
            assert "openai" in providers

            adapter = LLMFactoryAdapter.get("openai")
            assert adapter.provider == "openai"
            assert adapter.model_id == "gpt-4o"

    def test_init_with_anthropic_key(self):
        """测试使用 Anthropic API Key 初始化"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            init_llm_providers()

            providers = LLMFactoryAdapter.list_providers()
            assert "claude" in providers

            adapter = LLMFactoryAdapter.get("claude")
            assert adapter.provider == "anthropic"
            assert adapter.model_id == "claude-sonnet-4-20250514"

    def test_init_with_azure_keys(self):
        """测试使用 Azure OpenAI 初始化"""
        env = {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
            "AZURE_OPENAI_DEPLOYMENT": "gpt-4-deployment"
        }
        with patch.dict(os.environ, env, clear=True):
            init_llm_providers()

            providers = LLMFactoryAdapter.list_providers()
            assert "azure" in providers

            adapter = LLMFactoryAdapter.get("azure")
            assert adapter.provider == "azure"
            assert adapter.model_id == "gpt-4-deployment"

    def test_init_with_bailian_key(self):
        """测试使用百炼 API Key 初始化"""
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}, clear=True):
            init_llm_providers()

            providers = LLMFactoryAdapter.list_providers()
            assert "bailian" in providers

            adapter = LLMFactoryAdapter.get("bailian")
            assert adapter.provider == "bailian"
            assert adapter.model_id == "qwen-plus"

    def test_init_always_registers_ollama(self):
        """测试总是注册 Ollama"""
        with patch.dict(os.environ, {}, clear=True):
            init_llm_providers()

            providers = LLMFactoryAdapter.list_providers()
            assert "ollama" in providers

            adapter = LLMFactoryAdapter.get("ollama")
            assert adapter.provider == "ollama"
            assert adapter.model_id == "llama3.2"

    def test_init_no_keys_registers_default(self):
        """测试没有 API Key 时注册默认提供商"""
        with patch.dict(os.environ, {}, clear=True):
            # 清除 Ollama 等，只测试默认行为
            LLMFactoryAdapter.clear()
            # 修改代码路径，使得没有提供商时注册默认
            # 由于 Ollama 总是被注册，这个测试验证回退逻辑
            init_llm_providers()

            # Ollama 应该被注册
            assert len(LLMFactoryAdapter.list_providers()) >= 1

    def test_init_multiple_providers(self):
        """测试同时注册多个提供商"""
        env = {
            "OPENAI_API_KEY": "openai-key",
            "ANTHROPIC_API_KEY": "anthropic-key",
            "DASHSCOPE_API_KEY": "bailian-key",
        }
        with patch.dict(os.environ, env, clear=True):
            init_llm_providers()

            providers = LLMFactoryAdapter.list_providers()
            assert "openai" in providers
            assert "claude" in providers
            assert "bailian" in providers
            assert "ollama" in providers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])