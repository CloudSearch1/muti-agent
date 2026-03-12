"""
PI-Python 核心类型测试

测试 ai/types.py 模块
"""

import pytest
from pi_python.ai.types import (
    ApiType,
    StopReason,
    TextContent,
    ImageContent,
    ThinkingContent,
    ToolCall,
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    Model,
    ModelCost,
    Tool,
    ToolParameter,
    Context,
    parse_message,
)


class TestApiType:
    """API 类型测试"""

    def test_api_type_values(self):
        """测试 API 类型值"""
        assert ApiType.OPENAI_COMPLETIONS == "openai-completions"
        assert ApiType.ANTHROPIC_MESSAGES == "anthropic-messages"
        assert ApiType.GOOGLE_GENERATIVE_AI == "google-generative-ai"
        assert ApiType.BAILIAN == "bailian"
        assert ApiType.OLLAMA == "ollama"

    def test_api_type_enum(self):
        """测试 API 类型枚举"""
        assert ApiType("openai-completions") == ApiType.OPENAI_COMPLETIONS


class TestStopReason:
    """停止原因测试"""

    def test_stop_reason_values(self):
        """测试停止原因值"""
        assert StopReason.STOP == "stop"
        assert StopReason.TOOL_USE == "tool_use"
        assert StopReason.MAX_TOKENS == "max_tokens"
        assert StopReason.ABORTED == "aborted"
        assert StopReason.ERROR == "error"


class TestContentTypes:
    """内容类型测试"""

    def test_text_content(self):
        """测试文本内容"""
        content = TextContent(text="Hello")
        assert content.type == "text"
        assert content.text == "Hello"

    def test_image_content(self):
        """测试图片内容"""
        content = ImageContent(source={
            "type": "url",
            "media_type": "image/png",
            "data": "https://example.com/image.png"
        })
        assert content.type == "image"
        assert content.source["type"] == "url"

    def test_thinking_content(self):
        """测试思考内容"""
        content = ThinkingContent(thinking="Let me think...")
        assert content.type == "thinking"
        assert content.thinking == "Let me think..."

    def test_tool_call(self):
        """测试工具调用"""
        tool_call = ToolCall(
            id="call_123",
            name="bash",
            input={"command": "ls"}
        )
        assert tool_call.type == "tool_call"
        assert tool_call.id == "call_123"
        assert tool_call.name == "bash"
        assert tool_call.input == {"command": "ls"}


class TestMessages:
    """消息类型测试"""

    def test_user_message_from_text(self):
        """测试从文本创建用户消息"""
        msg = UserMessage.from_text("Hello")
        assert msg.role == "user"
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextContent)
        assert msg.content[0].text == "Hello"

    def test_user_message_with_content_list(self):
        """测试带内容列表的用户消息"""
        content = [TextContent(text="Hello"), ImageContent(source={"type": "url"})]
        msg = UserMessage(content=content)
        assert msg.role == "user"
        assert len(msg.content) == 2

    def test_assistant_message(self):
        """测试助手消息"""
        msg = AssistantMessage(content=[TextContent(text="Hi there!")])
        assert msg.role == "assistant"
        assert msg.text == "Hi there!"

    def test_assistant_message_text_property(self):
        """测试助手消息文本属性"""
        msg = AssistantMessage(content=[
            TextContent(text="Hello "),
            TextContent(text="World"),
            ToolCall(id="1", name="test", input={})
        ])
        assert msg.text == "Hello World"

    def test_tool_result_message(self):
        """测试工具结果消息"""
        msg = ToolResultMessage(
            tool_call_id="call_123",
            content=[TextContent(text="Result")]
        )
        assert msg.role == "tool_result"
        assert msg.tool_call_id == "call_123"

    def test_parse_message_user(self):
        """测试解析用户消息"""
        data = {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
        msg = parse_message(data)
        assert isinstance(msg, UserMessage)

    def test_parse_message_assistant(self):
        """测试解析助手消息"""
        data = {"role": "assistant", "content": [{"type": "text", "text": "Hi"}]}
        msg = parse_message(data)
        assert isinstance(msg, AssistantMessage)

    def test_parse_message_tool_result(self):
        """测试解析工具结果消息"""
        data = {
            "role": "tool_result",
            "tool_call_id": "call_123",
            "content": [{"type": "text", "text": "Result"}]
        }
        msg = parse_message(data)
        assert isinstance(msg, ToolResultMessage)

    def test_parse_message_invalid(self):
        """测试解析无效消息"""
        with pytest.raises(ValueError):
            parse_message({"role": "invalid"})


class TestModel:
    """模型定义测试"""

    def test_model_creation(self):
        """测试模型创建"""
        model = Model(
            id="gpt-4o",
            name="GPT-4o",
            api=ApiType.OPENAI_COMPLETIONS,
            provider="openai",
            base_url="https://api.openai.com/v1",
            context_window=128000,
            max_tokens=16384
        )
        assert model.id == "gpt-4o"
        assert model.provider == "openai"
        assert model.reasoning is False

    def test_model_with_cost(self):
        """测试带成本的模型"""
        model = Model(
            id="gpt-4o",
            name="GPT-4o",
            api=ApiType.OPENAI_COMPLETIONS,
            provider="openai",
            base_url="",
            cost=ModelCost(input=2.5, output=10.0)
        )
        assert model.cost.input == 2.5
        assert model.cost.output == 10.0

    def test_model_repr(self):
        """测试模型字符串表示"""
        model = Model(
            id="gpt-4o",
            name="GPT-4o",
            api=ApiType.OPENAI_COMPLETIONS,
            provider="openai",
            base_url=""
        )
        assert repr(model) == "Model(openai/gpt-4o)"


class TestTool:
    """工具定义测试"""

    def test_tool_creation(self):
        """测试工具创建"""
        tool = Tool(
            name="bash",
            description="Execute bash command",
            parameters={
                "command": ToolParameter(
                    type="string",
                    description="Command to execute"
                )
            },
            required=["command"]
        )
        assert tool.name == "bash"
        assert "command" in tool.parameters

    def test_tool_to_openai_format(self):
        """测试工具转换为 OpenAI 格式"""
        tool = Tool(
            name="bash",
            description="Execute bash command",
            parameters={
                "command": ToolParameter(type="string", description="Command")
            },
            required=["command"]
        )
        openai_format = tool.to_openai_format()
        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "bash"
        assert "parameters" in openai_format["function"]

    def test_tool_to_anthropic_format(self):
        """测试工具转换为 Anthropic 格式"""
        tool = Tool(
            name="bash",
            description="Execute bash command",
            parameters={
                "command": ToolParameter(type="string", description="Command")
            },
            required=["command"]
        )
        anthropic_format = tool.to_anthropic_format()
        assert anthropic_format["name"] == "bash"
        assert "input_schema" in anthropic_format


class TestContext:
    """上下文测试"""

    def test_context_creation(self):
        """测试上下文创建"""
        context = Context(system_prompt="You are a helpful assistant.")
        assert context.system_prompt == "You are a helpful assistant."
        assert context.messages == []
        assert context.tools == []

    def test_add_user_message(self):
        """测试添加用户消息"""
        context = Context()
        msg = context.add_user_message("Hello")
        assert len(context.messages) == 1
        assert isinstance(msg, UserMessage)
        assert msg.content[0].text == "Hello"

    def test_add_user_message_with_content(self):
        """测试添加带内容的用户消息"""
        context = Context()
        content = [TextContent(text="Hello")]
        msg = context.add_user_message(content)
        assert len(context.messages) == 1
        assert msg.content == content

    def test_add_assistant_message(self):
        """测试添加助手消息"""
        context = Context()
        msg = context.add_assistant_message([TextContent(text="Hi")])
        assert len(context.messages) == 1
        assert isinstance(msg, AssistantMessage)

    def test_add_tool_result(self):
        """测试添加工具结果"""
        context = Context()
        msg = context.add_tool_result("call_123", "Result")
        assert len(context.messages) == 1
        assert isinstance(msg, ToolResultMessage)
        assert msg.tool_call_id == "call_123"

    def test_to_openai_messages(self):
        """测试转换为 OpenAI 消息格式"""
        context = Context(system_prompt="You are helpful.")
        context.add_user_message("Hello")
        context.add_assistant_message([TextContent(text="Hi")])

        messages = context.to_openai_messages()
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    def test_to_anthropic_messages(self):
        """测试转换为 Anthropic 消息格式"""
        context = Context()
        context.add_user_message("Hello")

        messages = context.to_anthropic_messages()
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_context_copy(self):
        """测试上下文复制"""
        context = Context(system_prompt="Test")
        context.add_user_message("Hello")

        copy = context.copy()
        assert copy.system_prompt == context.system_prompt
        assert len(copy.messages) == len(context.messages)

        # 修改原上下文不影响副本
        context.add_user_message("World")
        assert len(context.messages) == 2
        assert len(copy.messages) == 1


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_context_messages(self):
        """测试空消息上下文"""
        context = Context()
        messages = context.to_openai_messages()
        assert messages == []

        anthropic_messages = context.to_anthropic_messages()
        assert anthropic_messages == []

    def test_context_without_system_prompt(self):
        """测试无系统提示的上下文"""
        context = Context()
        context.add_user_message("Hello")

        messages = context.to_openai_messages()
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_tool_call_with_empty_input(self):
        """测试空输入的工具调用"""
        tool_call = ToolCall(id="call_1", name="test", input={})
        assert tool_call.input == {}

    def test_model_cost_defaults(self):
        """测试模型成本默认值"""
        cost = ModelCost()
        assert cost.input == 0.0
        assert cost.output == 0.0
        assert cost.cache_read == 0.0
        assert cost.cache_write == 0.0

    def test_tool_without_parameters(self):
        """测试无参数工具"""
        tool = Tool(name="test", description="Test tool")
        assert tool.parameters == {}
        assert tool.required == []

        openai_format = tool.to_openai_format()
        assert openai_format["function"]["name"] == "test"

    def test_tool_parameter_with_enum(self):
        """测试带枚举的工具参数"""
        param = ToolParameter(
            type="string",
            description="Color",
            enum=["red", "green", "blue"]
        )
        assert param.enum == ["red", "green", "blue"]

    def test_assistant_message_with_only_tool_calls(self):
        """测试只有工具调用的助手消息"""
        msg = AssistantMessage(content=[
            ToolCall(id="call_1", name="test", input={})
        ])
        assert msg.text == ""

    def test_user_message_with_empty_text(self):
        """测试空文本用户消息"""
        msg = UserMessage.from_text("")
        assert msg.content[0].text == ""

    def test_context_with_tools(self):
        """测试带工具的上下文"""
        context = Context()
        tool = Tool(name="test", description="Test tool")
        context.tools.append(tool)
        assert len(context.tools) == 1

    def test_message_timestamp(self):
        """测试消息时间戳"""
        import time
        before = time.time()
        msg = UserMessage.from_text("Hello")
        after = time.time()
        assert before <= msg.timestamp <= after

    def test_parse_message_with_extra_fields(self):
        """测试带额外字段的消息解析"""
        data = {
            "role": "user",
            "content": [{"type": "text", "text": "Hello"}],
            "extra_field": "ignored"
        }
        msg = parse_message(data)
        assert isinstance(msg, UserMessage)

    def test_multiple_tool_calls_in_assistant_message(self):
        """测试助手消息中的多个工具调用"""
        msg = AssistantMessage(content=[
            TextContent(text="Let me help you."),
            ToolCall(id="call_1", name="bash", input={"cmd": "ls"}),
            ToolCall(id="call_2", name="read", input={"path": "/tmp"}),
        ])
        assert msg.text == "Let me help you."
        tool_calls = [c for c in msg.content if isinstance(c, ToolCall)]
        assert len(tool_calls) == 2