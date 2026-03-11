"""
PI-Python 流式 API 测试

测试 ai/stream.py 模块
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pi_python.ai.stream import (
    AssistantMessageEvent,
    AssistantMessageEventStream,
    StreamOptions,
    EventBuilder,
    stream,
    stream_simple,
    complete,
    register_provider,
    get_provider,
)
from pi_python.ai.types import (
    ApiType,
    AssistantMessage,
    Context,
    Model,
    ModelCost,
    StopReason,
    TextContent,
    ToolCall,
)


class TestAssistantMessageEvent:
    """流式事件测试"""

    def test_text_delta_event(self):
        """测试文本增量事件"""
        event = AssistantMessageEvent(
            type="text_delta",
            content_index=0,
            delta="Hello"
        )
        assert event.type == "text_delta"
        assert event.delta == "Hello"

    def test_tool_call_event(self):
        """测试工具调用事件"""
        tool_call = ToolCall(id="1", name="bash", input={"command": "ls"})
        event = AssistantMessageEvent(
            type="tool_call",
            tool_call=tool_call
        )
        assert event.type == "tool_call"
        assert event.tool_call.name == "bash"

    def test_done_event(self):
        """测试完成事件"""
        message = AssistantMessage(content=[TextContent(text="Done")])
        event = AssistantMessageEvent(
            type="done",
            reason=StopReason.STOP,
            message=message
        )
        assert event.type == "done"
        assert event.reason == StopReason.STOP

    def test_error_event(self):
        """测试错误事件"""
        event = AssistantMessageEvent(
            type="error",
            error="Something went wrong"
        )
        assert event.type == "error"
        assert event.error == "Something went wrong"


class TestAssistantMessageEventStream:
    """流式事件流测试"""

    @pytest.mark.asyncio
    async def test_emit_and_iterate(self):
        """测试发射和迭代事件"""
        stream = AssistantMessageEventStream()

        # 发射事件
        await stream.emit(EventBuilder.text_delta(0, "Hello"))
        await stream.emit(EventBuilder.text_delta(0, " World"))
        await stream.emit(EventBuilder.done(
            StopReason.STOP,
            AssistantMessage(content=[TextContent(text="Hello World")])
        ))

        # 迭代事件
        events = []
        async for event in stream:
            events.append(event)

        assert len(events) == 3
        assert events[0].type == "text_delta"
        assert events[1].type == "text_delta"
        assert events[2].type == "done"

    @pytest.mark.asyncio
    async def test_collect(self):
        """测试收集消息"""
        stream = AssistantMessageEventStream()

        await stream.emit(EventBuilder.text_delta(0, "Hello"))
        await stream.emit(EventBuilder.text_delta(0, " World"))
        await stream.emit(EventBuilder.done(
            StopReason.STOP,
            AssistantMessage(content=[TextContent(text="Hello World")])
        ))

        message = await stream.collect()
        assert message.text == "Hello World"

    def test_emit_sync(self):
        """测试同步发射事件"""
        stream = AssistantMessageEventStream()
        stream.emit_sync(EventBuilder.text_delta(0, "Hello"))

        # 验证事件已添加到队列
        assert not stream._queue.empty()


class TestStreamOptions:
    """流式调用选项测试"""

    def test_default_options(self):
        """测试默认选项"""
        options = StreamOptions()
        assert options.api_key is None
        assert options.timeout == 60
        assert options.temperature == 0.7
        assert options.max_tokens == 4096
        assert options.reasoning == "off"

    def test_custom_options(self):
        """测试自定义选项"""
        options = StreamOptions(
            api_key="test_key",
            temperature=0.5,
            max_tokens=8192
        )
        assert options.api_key == "test_key"
        assert options.temperature == 0.5
        assert options.max_tokens == 8192


class TestEventBuilder:
    """事件构建器测试"""

    def test_start(self):
        """测试开始事件"""
        event = EventBuilder.start()
        assert event.type == "start"

    def test_text_delta(self):
        """测试文本增量事件"""
        event = EventBuilder.text_delta(0, "Hello")
        assert event.type == "text_delta"
        assert event.content_index == 0
        assert event.delta == "Hello"

    def test_thinking_delta(self):
        """测试思考增量事件"""
        event = EventBuilder.thinking_delta(0, "Thinking...")
        assert event.type == "thinking_delta"
        assert event.delta == "Thinking..."

    def test_tool_call_end(self):
        """测试工具调用结束事件"""
        tool_call = ToolCall(id="1", name="bash", input={})
        event = EventBuilder.tool_call_end(tool_call)
        assert event.type == "tool_call"
        assert event.tool_call == tool_call

    def test_done(self):
        """测试完成事件"""
        message = AssistantMessage(content=[TextContent(text="Done")])
        event = EventBuilder.done(StopReason.STOP, message)
        assert event.type == "done"
        assert event.reason == StopReason.STOP
        assert event.message == message

    def test_error(self):
        """测试错误事件"""
        event = EventBuilder.error("Error occurred")
        assert event.type == "error"
        assert event.error == "Error occurred"
        assert event.reason == StopReason.ERROR


class TestProviderRegistry:
    """提供商注册测试"""

    def test_register_and_get_provider(self):
        """测试注册和获取提供商"""
        async def mock_provider(model, context, options):
            return AssistantMessageEventStream()

        register_provider("test_provider", mock_provider)
        provider = get_provider("test_provider")
        assert provider == mock_provider

    def test_get_unknown_provider(self):
        """测试获取未知提供商"""
        provider = get_provider("unknown_provider_xyz")
        assert provider is None


class TestStreamFunctions:
    """流式函数测试"""

    @pytest.mark.asyncio
    async def test_stream_with_unknown_provider(self):
        """测试未知提供商流式调用"""
        model = Model(
            id="test-model",
            name="Test Model",
            api=ApiType.CUSTOM,
            provider="unknown_provider_xyz",
            base_url=""
        )
        context = Context()

        with pytest.raises(ValueError, match="Unknown provider"):
            await stream(model, context)

    @pytest.mark.asyncio
    async def test_stream_simple(self):
        """测试简化流式调用"""
        model = Model(
            id="test-model",
            name="Test Model",
            api=ApiType.CUSTOM,
            provider="test_provider_simple",
            base_url="",
            reasoning=True
        )
        context = Context()

        # 注册模拟提供商
        async def mock_provider(model, context, options):
            stream = AssistantMessageEventStream()
            stream.emit_sync(EventBuilder.done(
                StopReason.STOP,
                AssistantMessage(content=[TextContent(text="Test")])
            ))
            return stream

        register_provider("test_provider_simple", mock_provider)

        result = await stream_simple(model, context, reasoning="medium")
        assert result is not None

    @pytest.mark.asyncio
    async def test_complete(self):
        """测试完成调用"""
        model = Model(
            id="test-model",
            name="Test Model",
            api=ApiType.CUSTOM,
            provider="test_provider_complete",
            base_url=""
        )
        context = Context()

        # 注册模拟提供商
        async def mock_provider(model, context, options):
            stream = AssistantMessageEventStream()
            stream.emit_sync(EventBuilder.text_delta(0, "Hello"))
            stream.emit_sync(EventBuilder.done(
                StopReason.STOP,
                AssistantMessage(content=[TextContent(text="Hello")])
            ))
            return stream

        register_provider("test_provider_complete", mock_provider)

        message = await complete(model, context)
        assert message.text == "Hello"