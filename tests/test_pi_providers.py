"""
PI-Python 提供商扩展测试

测试 ai/providers 模块的流式响应处理和错误处理
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from contextlib import asynccontextmanager

import httpx

from pi_python.ai.providers.anthropic import AnthropicProvider
from pi_python.ai.providers.bailian import BailianProvider
from pi_python.ai.providers.openai import OpenAIProvider
from pi_python.ai.providers.other import (
    AzureProvider,
    BedrockProvider,
    GoogleProvider,
    GroqProvider,
    MistralProvider,
    OllamaProvider,
    OpenRouterProvider,
    VLLMProvider,
)
from pi_python.ai.types import (
    ApiType,
    AssistantMessage,
    Context,
    Model,
    TextContent,
    ToolCall,
    UserMessage,
)
from pi_python.ai.stream import StreamOptions


def create_test_model(provider: str, model_id: str = "test-model") -> Model:
    """创建测试模型"""
    return Model(
        id=model_id,
        name=f"Test {provider}",
        api=ApiType.OPENAI_COMPLETIONS,
        provider=provider,
        base_url="",
    )


def create_test_context(text: str = "Hello") -> Context:
    """创建测试上下文"""
    ctx = Context()
    ctx.add_user_message(text)
    return ctx


class MockStreamResponse:
    """模拟流式响应"""

    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self._index = 0
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "Error",
                request=MagicMock(),
                response=MagicMock(status_code=self.status_code)
            )

    async def aiter_lines(self):
        for line in self._lines:
            yield line


@asynccontextmanager
async def mock_stream_context(lines: list[str], status_code: int = 200):
    """创建模拟流式上下文"""
    yield MockStreamResponse(lines, status_code)


# ============ Anthropic Provider Tests ============

class TestAnthropicProviderStreaming:
    """Anthropic 流式响应测试"""

    @pytest.mark.asyncio
    async def test_stream_text_response(self):
        """测试文本流式响应"""
        provider = AnthropicProvider(api_key="test-key")

        # 模拟 Anthropic SSE 响应
        lines = [
            'data: {"type":"message_start","message":{"usage":{"input_tokens":10}}}',
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"text"}}',
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}',
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" World"}}',
            'data: {"type":"content_block_stop","index":0}',
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
            'data: {"type":"message_stop"}',
        ]

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context(lines)

        provider._client = mock_client

        model = create_test_model("anthropic", "claude-sonnet-4-20250514")
        model.reasoning = True
        context = create_test_context()
        options = StreamOptions(api_key="test-key")

        stream = await provider.stream(model, context, options)

        # 等待后台任务完成
        events = []
        async for event in stream:
            events.append(event)

        # 验证事件
        assert any(e.type == "start" for e in events)
        assert any(e.type == "text_delta" and e.delta == "Hello" for e in events)
        assert any(e.type == "text_delta" and e.delta == " World" for e in events)
        assert any(e.type == "done" for e in events)

    @pytest.mark.asyncio
    async def test_stream_thinking_response(self):
        """测试思考内容流式响应"""
        provider = AnthropicProvider(api_key="test-key")

        lines = [
            'data: {"type":"message_start","message":{"usage":{"input_tokens":10}}}',
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"thinking"}}',
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"Let me think..."}}',
            'data: {"type":"content_block_stop","index":0}',
            'data: {"type":"content_block_start","index":1,"content_block":{"type":"text"}}',
            'data: {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"Answer"}}',
            'data: {"type":"content_block_stop","index":1}',
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
            'data: {"type":"message_stop"}',
        ]

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context(lines)
        provider._client = mock_client

        model = create_test_model("anthropic", "claude-sonnet-4-20250514")
        model.reasoning = True
        context = create_test_context()
        options = StreamOptions(api_key="test-key", reasoning="medium", thinking_budget=2048)

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        # 验证思考事件
        assert any(e.type == "thinking_delta" and e.delta == "Let me think..." for e in events)

    @pytest.mark.asyncio
    async def test_stream_tool_use_response(self):
        """测试工具调用流式响应"""
        provider = AnthropicProvider(api_key="test-key")

        lines = [
            'data: {"type":"message_start","message":{"usage":{"input_tokens":10}}}',
            'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"tool_123","name":"get_weather"}}',
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"city\\""}}',
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":": \\"Beijing\\"}"}}',
            'data: {"type":"content_block_stop","index":0}',
            'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}',
            'data: {"type":"message_stop"}',
        ]

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context(lines)
        provider._client = mock_client

        model = create_test_model("anthropic")
        context = create_test_context()
        options = StreamOptions(api_key="test-key")

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        # 验证工具调用事件
        tool_call_events = [e for e in events if e.type == "tool_call"]
        assert len(tool_call_events) == 1
        assert tool_call_events[0].tool_call.name == "get_weather"
        assert tool_call_events[0].tool_call.input == {"city": "Beijing"}

    @pytest.mark.asyncio
    async def test_stream_http_error(self):
        """测试 HTTP 错误处理"""
        provider = AnthropicProvider(api_key="test-key")

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context([], status_code=401)
        provider._client = mock_client

        model = create_test_model("anthropic")
        context = create_test_context()
        options = StreamOptions(api_key="test-key")

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        assert any(e.type == "error" for e in events)

    @pytest.mark.asyncio
    async def test_stream_timeout_error(self):
        """测试超时错误处理"""
        provider = AnthropicProvider(api_key="test-key")

        @asynccontextmanager
        async def mock_timeout_context(*args, **kwargs):
            raise httpx.TimeoutException("Timeout")
            yield  # Never reached

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_timeout_context()
        provider._client = mock_client

        model = create_test_model("anthropic")
        context = create_test_context()
        options = StreamOptions(api_key="test-key")

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        assert any(e.type == "error" and "超时" in (e.error or "") for e in events)


# ============ OpenAI Provider Tests ============

class TestOpenAIProviderStreaming:
    """OpenAI 流式响应测试"""

    @pytest.mark.asyncio
    async def test_stream_text_response(self):
        """测试文本流式响应"""
        provider = OpenAIProvider(api_key="test-key")

        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" World"}}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
            'data: [DONE]',
        ]

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context(lines)
        provider._client = mock_client

        model = create_test_model("openai", "gpt-4o")
        context = create_test_context()
        options = StreamOptions(api_key="test-key")

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        assert any(e.type == "text_delta" and e.delta == "Hello" for e in events)
        assert any(e.type == "text_delta" and e.delta == " World" for e in events)
        assert any(e.type == "done" for e in events)

    @pytest.mark.asyncio
    async def test_stream_tool_calls_response(self):
        """测试工具调用流式响应"""
        provider = OpenAIProvider(api_key="test-key")

        lines = [
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_123","function":{"name":"get_weather"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"city\\":"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":" \\"Beijing\\"}"}}]}}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
            'data: [DONE]',
        ]

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context(lines)
        provider._client = mock_client

        model = create_test_model("openai")
        context = create_test_context()
        options = StreamOptions(api_key="test-key")

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        # 验证完成事件（工具调用会包含在 done 事件的 message 中）
        done_events = [e for e in events if e.type == "done"]
        assert len(done_events) == 1
        # 验证消息包含工具调用
        message = done_events[0].message
        tool_calls = [c for c in message.content if hasattr(c, 'type') and c.type == 'tool_call']
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "get_weather"

    @pytest.mark.asyncio
    async def test_stream_with_usage(self):
        """测试带 usage 的响应"""
        provider = OpenAIProvider(api_key="test-key")

        lines = [
            'data: {"choices":[{"delta":{"content":"Hi"}}]}',
            'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":10,"completion_tokens":5}}',
            'data: [DONE]',
        ]

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context(lines)
        provider._client = mock_client

        model = create_test_model("openai")
        context = create_test_context()
        options = StreamOptions(api_key="test-key")

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        done_events = [e for e in events if e.type == "done"]
        assert len(done_events) == 1
        assert done_events[0].usage is not None


# ============ Bailian Provider Tests ============

class TestBailianProviderStreaming:
    """百炼流式响应测试"""

    @pytest.mark.asyncio
    async def test_stream_text_response(self):
        """测试文本流式响应"""
        provider = BailianProvider(api_key="test-key")

        lines = [
            'data: {"output":{"choices":[{"message":{"content":"你好"},"finish_reason":"stop"}]},"usage":{"input_tokens":10}}',
            'data: {"output":{"choices":[{"message":{"content":"你好世界"},"finish_reason":"stop"}]},"usage":{"input_tokens":10,"output_tokens":5}}',
        ]

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context(lines)
        provider._client = mock_client

        model = create_test_model("bailian", "qwen-max")
        context = create_test_context()
        options = StreamOptions(api_key="test-key")

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        assert any(e.type == "text_delta" for e in events)
        assert any(e.type == "done" for e in events)

    @pytest.mark.asyncio
    async def test_stream_error_response(self):
        """测试错误响应"""
        provider = BailianProvider(api_key="test-key")

        lines = [
            'data: {"code":"InvalidParameter","message":"参数错误"}',
        ]

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context(lines)
        provider._client = mock_client

        model = create_test_model("bailian")
        context = create_test_context()
        options = StreamOptions(api_key="test-key")

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        assert any(e.type == "error" for e in events)


# ============ Other Providers Tests ============

class TestGoogleProviderStreaming:
    """Google 流式响应测试"""

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """测试无 API Key"""
        provider = GoogleProvider()

        model = create_test_model("google", "gemini-pro")
        context = create_test_context()
        options = StreamOptions()

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)
            break

        assert events[0].type == "error"

    @pytest.mark.asyncio
    async def test_stream_response(self):
        """测试流式响应"""
        provider = GoogleProvider()

        lines = [
            'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}',
            'data: {"candidates":[{"content":{"parts":[{"text":" World"}]}}]}',
        ]

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context(lines)
        provider._client = mock_client

        model = create_test_model("google")
        context = create_test_context()
        options = StreamOptions(api_key="test-key")

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        assert any(e.type == "text_delta" for e in events)


class TestAzureProvider:
    """Azure 提供商测试"""

    def test_provider_name(self):
        """测试提供商名称"""
        provider = AzureProvider()
        assert provider.NAME == "azure"

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """测试无 API Key"""
        provider = AzureProvider()

        model = create_test_model("azure")
        context = create_test_context()
        options = StreamOptions()

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)
            break

        assert events[0].type == "error"


class TestBedrockProvider:
    """Bedrock 提供商测试"""

    def test_provider_name(self):
        """测试提供商名称"""
        provider = BedrockProvider()
        assert provider.NAME == "bedrock"

    @pytest.mark.asyncio
    async def test_stream_not_implemented(self):
        """测试未实现错误"""
        provider = BedrockProvider()

        model = create_test_model("bedrock")
        context = create_test_context()
        options = StreamOptions()

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)
            break

        assert events[0].type == "error"
        assert "尚未实现" in (events[0].error or "")


class TestMistralProvider:
    """Mistral 提供商测试"""

    def test_provider_name(self):
        """测试提供商名称"""
        provider = MistralProvider()
        assert provider.NAME == "mistral"

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """测试无 API Key"""
        provider = MistralProvider()

        model = create_test_model("mistral")
        context = create_test_context()
        options = StreamOptions()

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)
            break

        assert events[0].type == "error"


class TestGroqProvider:
    """Groq 提供商测试"""

    def test_provider_name(self):
        """测试提供商名称"""
        provider = GroqProvider()
        assert provider.NAME == "groq"

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """测试无 API Key"""
        provider = GroqProvider()

        model = create_test_model("groq")
        context = create_test_context()
        options = StreamOptions()

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)
            break

        assert events[0].type == "error"


class TestOpenRouterProvider:
    """OpenRouter 提供商测试"""

    def test_provider_name(self):
        """测试提供商名称"""
        provider = OpenRouterProvider()
        assert provider.NAME == "openrouter"

    @pytest.mark.asyncio
    async def test_stream_no_api_key(self):
        """测试无 API Key"""
        provider = OpenRouterProvider()

        model = create_test_model("openrouter")
        context = create_test_context()
        options = StreamOptions()

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)
            break

        assert events[0].type == "error"


class TestOllamaProviderStreaming:
    """Ollama 流式响应测试"""

    @pytest.mark.asyncio
    async def test_stream_response(self):
        """测试流式响应"""
        provider = OllamaProvider()

        # Ollama 使用 JSON 行格式，不是 SSE
        lines = [
            '{"message":{"content":"Hello"}}',
            '{"message":{"content":" World"},"done":true}',
        ]

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_context(lines)
        provider._client = mock_client

        model = create_test_model("ollama", "llama2")
        model.base_url = "http://localhost:11434"
        context = create_test_context()
        options = StreamOptions()

        stream = await provider.stream(model, context, options)

        events = []
        async for event in stream:
            events.append(event)

        assert any(e.type == "text_delta" for e in events)
        assert any(e.type == "done" for e in events)


class TestVLLMProvider:
    """vLLM 提供商测试"""

    def test_provider_name(self):
        """测试提供商名称"""
        provider = VLLMProvider()
        assert provider.NAME == "vllm"


# ============ Provider Base Tests ============

class TestBaseProviderMethods:
    """基础提供商方法测试"""

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success(self):
        """测试重试成功"""
        from pi_python.ai.providers.base import BaseProvider

        class TestProvider(BaseProvider):
            NAME = "test"
            async def stream(self, model, context, options):
                pass

        provider = TestProvider()

        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            return "success"

        result = await provider._retry_with_backoff(flaky_func, max_retries=3)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_backoff_max_retries(self):
        """测试超过最大重试次数"""
        from pi_python.ai.providers.base import BaseProvider

        class TestProvider(BaseProvider):
            NAME = "test"
            async def stream(self, model, context, options):
                pass

        provider = TestProvider()

        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Timeout")

        with pytest.raises(httpx.TimeoutException):
            await provider._retry_with_backoff(always_fail, max_retries=2)

        assert call_count == 3  # 初始调用 + 2 次重试

    def test_should_retry_429(self):
        """测试 429 错误应该重试"""
        from pi_python.ai.providers.base import BaseProvider

        class TestProvider(BaseProvider):
            NAME = "test"
            async def stream(self, model, context, options):
                pass

        provider = TestProvider()

        mock_response = MagicMock()
        mock_response.status_code = 429
        error = httpx.HTTPStatusError("Rate limit", request=MagicMock(), response=mock_response)

        assert provider._should_retry(error) is True

    def test_should_retry_5xx(self):
        """测试 5xx 错误应该重试"""
        from pi_python.ai.providers.base import BaseProvider

        class TestProvider(BaseProvider):
            NAME = "test"
            async def stream(self, model, context, options):
                pass

        provider = TestProvider()

        mock_response = MagicMock()
        mock_response.status_code = 503
        error = httpx.HTTPStatusError("Service unavailable", request=MagicMock(), response=mock_response)

        assert provider._should_retry(error) is True

    def test_should_not_retry_4xx(self):
        """测试 4xx 错误不应该重试"""
        from pi_python.ai.providers.base import BaseProvider

        class TestProvider(BaseProvider):
            NAME = "test"
            async def stream(self, model, context, options):
                pass

        provider = TestProvider()

        mock_response = MagicMock()
        mock_response.status_code = 400
        error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=mock_response)

        assert provider._should_retry(error) is False