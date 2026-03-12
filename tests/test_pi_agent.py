"""
PI-Python Agent 测试

测试 Agent 类和 AgentState
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_python.ai import (
    AssistantMessage,
    Context,
    Model,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
    AssistantMessageEvent,
    AssistantMessageEventStream,
    StreamOptions,
)
from pi_python.ai.types import ApiType
from pi_python.agent.agent import Agent, AgentState
from pi_python.agent.events import AgentEvent, AgentEventType
from pi_python.agent.tools import AgentTool, ToolResult


# ===========================================
# Fixtures
# ===========================================


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
def agent_state(mock_model):
    """创建 Agent 状态"""
    return AgentState(
        system_prompt="You are a helpful assistant.",
        model=mock_model,
    )


@pytest.fixture
def agent(agent_state):
    """创建 Agent 实例"""
    return Agent(initial_state=agent_state)


@pytest.fixture
def mock_tool():
    """创建 Mock 工具"""
    class MockTool(AgentTool):
        name = "test_tool"
        label = "Test Tool"
        description = "A test tool"
        parameters = {}
        required = []

        async def execute(self, tool_call_id, params, signal=None, on_update=None, context=None):
            return ToolResult.text(f"Executed with params: {params}")

    return MockTool()


# ===========================================
# AgentState Tests
# ===========================================


class TestAgentState:
    """AgentState 测试"""

    def test_init(self, mock_model):
        """测试初始化"""
        state = AgentState(
            system_prompt="Test prompt",
            model=mock_model,
        )

        assert state.system_prompt == "Test prompt"
        assert state.model == mock_model
        assert state.thinking_level == "off"
        assert state.tools == []
        assert state.messages == []
        assert state.is_streaming is False
        assert state.stream_message is None
        assert state.pending_tool_calls == set()
        assert state.error is None
        assert state.session is None

    def test_with_tools(self, mock_model, mock_tool):
        """测试带工具初始化"""
        state = AgentState(
            system_prompt="Test prompt",
            model=mock_model,
            tools=[mock_tool],
        )

        assert len(state.tools) == 1
        assert state.tools[0] == mock_tool

    def test_with_messages(self, mock_model):
        """测试带消息初始化"""
        messages = [UserMessage.from_text("Hello")]
        state = AgentState(
            system_prompt="Test prompt",
            model=mock_model,
            messages=messages,
        )

        assert len(state.messages) == 1


# ===========================================
# Agent Tests
# ===========================================


class TestAgent:
    """Agent 测试"""

    def test_init(self, agent, agent_state):
        """测试初始化"""
        assert agent.state == agent_state
        assert agent._steering_mode == "one-at-a-time"
        assert agent._follow_up_mode == "one-at-a-time"
        assert agent._subscribers == []

    def test_init_with_custom_converters(self, mock_model):
        """测试带自定义转换器初始化"""
        def custom_convert(messages):
            return messages

        async def custom_transform(context):
            return context

        state = AgentState(system_prompt="Test", model=mock_model)
        agent = Agent(
            initial_state=state,
            convert_to_llm=custom_convert,
            transform_context=custom_transform,
            steering_mode="all",
            follow_up_mode="all",
        )

        assert agent._convert_to_llm == custom_convert
        assert agent._transform_context == custom_transform
        assert agent._steering_mode == "all"
        assert agent._follow_up_mode == "all"

    def test_subscribe(self, agent):
        """测试订阅"""
        async def callback(event):
            pass

        agent.subscribe(callback)
        assert callback in agent._subscribers

    def test_unsubscribe(self, agent):
        """测试取消订阅"""
        async def callback(event):
            pass

        agent.subscribe(callback)
        agent.unsubscribe(callback)
        assert callback not in agent._subscribers

    @pytest.mark.asyncio
    async def test_emit(self, agent):
        """测试发射事件"""
        received = []

        async def callback(event):
            received.append(event)

        agent.subscribe(callback)

        event = AgentEvent(type=AgentEventType.MESSAGE_START)
        await agent._emit(event)

        assert len(received) == 1
        assert received[0] == event

    @pytest.mark.asyncio
    async def test_emit_multiple_subscribers(self, agent):
        """测试发射事件到多个订阅者"""
        received1 = []
        received2 = []

        async def callback1(event):
            received1.append(event)

        async def callback2(event):
            received2.append(event)

        agent.subscribe(callback1)
        agent.subscribe(callback2)

        event = AgentEvent(type=AgentEventType.MESSAGE_START)
        await agent._emit(event)

        assert len(received1) == 1
        assert len(received2) == 1

    @pytest.mark.asyncio
    async def test_emit_with_exception(self, agent):
        """测试订阅者抛出异常时继续执行"""
        received = []

        async def bad_callback(event):
            raise ValueError("Test error")

        async def good_callback(event):
            received.append(event)

        agent.subscribe(bad_callback)
        agent.subscribe(good_callback)

        event = AgentEvent(type=AgentEventType.MESSAGE_START)
        # 不应该抛出异常
        await agent._emit(event)

        assert len(received) == 1

    def test_default_convert_to_llm(self, agent):
        """测试默认消息转换"""
        messages = [
            UserMessage.from_text("Hello"),
            AssistantMessage(content=[TextContent(text="Hi")]),
            ToolResultMessage(tool_call_id="123", content=[TextContent(text="result")]),
        ]

        result = agent._default_convert_to_llm(messages)

        assert len(result) == 3

    def test_set_tools(self, agent, mock_tool):
        """测试设置工具"""
        agent.set_tools([mock_tool])

        assert len(agent.state.tools) == 1
        assert agent.state.tools[0] == mock_tool

    def test_add_tool(self, agent, mock_tool):
        """测试添加工具"""
        agent.add_tool(mock_tool)

        assert len(agent.state.tools) == 1
        assert agent.state.tools[0] == mock_tool

    def test_set_system_prompt(self, agent):
        """测试设置系统提示"""
        agent.set_system_prompt("New prompt")

        assert agent.state.system_prompt == "New prompt"

    def test_set_model(self, agent, mock_model):
        """测试设置模型"""
        new_model = Model(
            id="claude-sonnet-4-20250514",
            name="Claude Sonnet 4",
            api=ApiType.ANTHROPIC_MESSAGES,
            provider="anthropic",
        )

        agent.set_model(new_model)

        assert agent.state.model == new_model

    def test_clear_messages(self, agent):
        """测试清除消息"""
        agent.state.messages.append(UserMessage.from_text("Hello"))
        agent.clear_messages()

        assert len(agent.state.messages) == 0

    def test_get_messages(self, agent):
        """测试获取消息"""
        agent.state.messages.append(UserMessage.from_text("Hello"))

        messages = agent.get_messages()

        assert len(messages) == 1
        # 确保返回的是副本
        messages.append(UserMessage.from_text("World"))
        assert len(agent.state.messages) == 1

    def test_steer(self, agent):
        """测试发送 steering 消息"""
        msg = UserMessage.from_text("Steer")
        agent.steer(msg)

        assert not agent._steering_queue.empty()

    def test_follow_up(self, agent):
        """测试发送 follow-up 消息"""
        msg = UserMessage.from_text("Follow up")
        agent.follow_up(msg)

        assert not agent._follow_up_queue.empty()

    def test_abort(self, agent):
        """测试中止"""
        assert not agent._abort_controller.is_set()
        agent.abort()
        assert agent._abort_controller.is_set()

    @pytest.mark.asyncio
    async def test_complete_simple(self, agent, mock_model):
        """测试简单完成调用"""
        with patch("pi_python.agent.agent.complete") as mock_complete:
            mock_complete.return_value = AssistantMessage(
                content=[TextContent(text="Response")]
            )

            result = await agent.complete_simple("Hello")

            assert result == "Response"
            mock_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_context(self, agent):
        """测试构建上下文"""
        agent.state.messages.append(UserMessage.from_text("Hello"))

        context = await agent._build_context()

        assert context.system_prompt == "You are a helpful assistant."
        assert len(context.messages) == 1

    @pytest.mark.asyncio
    async def test_build_context_with_transform(self, mock_model):
        """测试带转换的上下文构建"""
        state = AgentState(system_prompt="Test", model=mock_model)

        async def transform(ctx):
            ctx.messages.append(UserMessage.from_text("Injected"))
            return ctx

        agent = Agent(initial_state=state, transform_context=transform)
        agent.state.messages.append(UserMessage.from_text("Hello"))

        context = await agent._build_context()

        assert len(context.messages) == 2

    @pytest.mark.asyncio
    async def test_process_stream(self, agent):
        """测试处理流式事件"""
        stream = AssistantMessageEventStream()
        stream._queue.put_nowait(AssistantMessageEvent(type="text_delta", delta="Hello "))
        stream._queue.put_nowait(AssistantMessageEvent(type="text_delta", delta="World"))
        stream._queue.put_nowait(AssistantMessageEvent(
            type="done",
            message=AssistantMessage(content=[TextContent(text="Hello World")])
        ))

        result = await agent._process_stream(stream)

        assert result is not None
        assert result.text == "Hello World"

    @pytest.mark.asyncio
    async def test_process_stream_with_thinking(self, agent):
        """测试处理带思考的流式事件"""
        from pi_python.ai import ThinkingContent

        stream = AssistantMessageEventStream()
        stream._queue.put_nowait(AssistantMessageEvent(type="thinking_delta", delta="Thinking..."))
        stream._queue.put_nowait(AssistantMessageEvent(type="text_delta", delta="Answer"))
        stream._queue.put_nowait(AssistantMessageEvent(type="done", message=None))

        result = await agent._process_stream(stream)

        assert result is not None
        # 检查有思考内容
        thinking_found = any(isinstance(c, ThinkingContent) for c in result.content)
        assert thinking_found

    @pytest.mark.asyncio
    async def test_process_stream_with_tool_call(self, agent):
        """测试处理带工具调用的流式事件"""
        tool_call = ToolCall(id="call-1", name="test_tool", input={"arg": "value"})

        stream = AssistantMessageEventStream()
        stream._queue.put_nowait(AssistantMessageEvent(type="tool_call", tool_call=tool_call))
        stream._queue.put_nowait(AssistantMessageEvent(type="done", message=None))

        result = await agent._process_stream(stream)

        assert result is not None
        assert len(result.content) == 1
        assert isinstance(result.content[0], ToolCall)
        assert result.content[0].name == "test_tool"

    @pytest.mark.asyncio
    async def test_process_stream_error(self, agent):
        """测试处理错误事件"""
        stream = AssistantMessageEventStream()
        stream._queue.put_nowait(AssistantMessageEvent(type="error", error="Test error"))

        with pytest.raises(RuntimeError, match="Test error"):
            await agent._process_stream(stream)

    @pytest.mark.asyncio
    async def test_prompt_basic(self, agent, mock_model):
        """测试基本 prompt 调用"""
        with patch("pi_python.agent.agent.stream") as mock_stream:
            mock_event_stream = AssistantMessageEventStream()
            mock_event_stream._queue.put_nowait(AssistantMessageEvent(
                type="done",
                message=AssistantMessage(content=[TextContent(text="Response")])
            ))
            mock_stream.return_value = mock_event_stream

            events = []

            async def collect_events(event):
                events.append(event)

            agent.subscribe(collect_events)
            await agent.prompt("Hello")

            # 验证事件发射
            event_types = [e.type for e in events]
            assert AgentEventType.AGENT_START in event_types
            assert AgentEventType.TURN_START in event_types
            assert AgentEventType.AGENT_END in event_types

    @pytest.mark.asyncio
    async def test_prompt_with_list_content(self, agent, mock_model):
        """测试使用内容列表的 prompt 调用"""
        with patch("pi_python.agent.agent.stream") as mock_stream:
            mock_event_stream = AssistantMessageEventStream()
            mock_event_stream._queue.put_nowait(AssistantMessageEvent(
                type="done",
                message=AssistantMessage(content=[TextContent(text="Response")])
            ))
            mock_stream.return_value = mock_event_stream

            await agent.prompt([TextContent(text="Hello")])

            # 用户消息 + 助手消息
            assert len(agent.state.messages) == 2
            assert isinstance(agent.state.messages[0], UserMessage)

    @pytest.mark.asyncio
    async def test_execute_tools(self, agent, mock_tool):
        """测试执行工具"""
        agent.state.tools.append(mock_tool)

        tool_call = ToolCall(id="call-1", name="test_tool", input={"arg": "value"})

        events = []

        async def collect_events(event):
            events.append(event)

        agent.subscribe(collect_events)

        result = await agent._execute_tools([tool_call])

        assert result is True

        # 验证事件发射
        event_types = [e.type for e in events]
        assert AgentEventType.TOOL_EXECUTION_START in event_types
        assert AgentEventType.TOOL_EXECUTION_END in event_types

        # 验证工具结果被添加
        assert len(agent.state.messages) == 1
        assert isinstance(agent.state.messages[0], ToolResultMessage)

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, agent):
        """测试执行未知工具"""
        tool_call = ToolCall(id="call-1", name="unknown_tool", input={})

        result = await agent._execute_tools([tool_call])

        assert result is True

        # 验证错误消息被添加
        assert len(agent.state.messages) == 1
        tool_result = agent.state.messages[0]
        assert "Unknown tool" in tool_result.content[0].text

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self, agent):
        """测试工具执行错误"""
        class ErrorTool(AgentTool):
            name = "error_tool"
            label = "Error Tool"
            description = "A tool that errors"
            parameters = {}
            required = []

            async def execute(self, tool_call_id, params, signal=None, on_update=None, context=None):
                raise ValueError("Tool error")

        agent.state.tools.append(ErrorTool())

        tool_call = ToolCall(id="call-1", name="error_tool", input={})

        events = []

        async def collect_events(event):
            events.append(event)

        agent.subscribe(collect_events)

        result = await agent._execute_tools([tool_call])

        assert result is True

        # 验证错误事件
        error_events = [e for e in events if e.type == AgentEventType.ERROR]
        assert len(error_events) == 1

    @pytest.mark.asyncio
    async def test_execute_tools_with_steering(self, agent, mock_tool):
        """测试 steering 中断工具执行"""
        agent.state.tools.append(mock_tool)

        # 添加 steering 消息
        agent.steer(UserMessage.from_text("Steer now!"))

        tool_call = ToolCall(id="call-1", name="test_tool", input={})

        result = await agent._execute_tools([tool_call])

        assert result is True

        # Steering 消息应该被添加到消息列表
        assert len(agent.state.messages) == 1
        assert isinstance(agent.state.messages[0], UserMessage)

    @pytest.mark.asyncio
    async def test_prompt_abort(self, agent, mock_model):
        """测试中止 prompt"""
        with patch("pi_python.agent.agent.stream") as mock_stream:
            # 创建一个在迭代时中止的流
            async def create_stream(*args, **kwargs):
                stream = AssistantMessageEventStream()
                # 中止
                agent.abort()
                stream._queue.put_nowait(AssistantMessageEvent(
                    type="done",
                    message=AssistantMessage(content=[TextContent(text="Response")])
                ))
                return stream

            mock_stream.side_effect = create_stream

            await agent.prompt("Hello")

            # 验证 agent 被中止
            assert agent._abort_controller.is_set()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])