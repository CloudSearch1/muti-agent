"""
PI-Python 核心类型定义

定义 LLM API 的核心类型，与 pi-mono 类型系统对应
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = [
    # API 类型
    "ApiType",
    "StopReason",
    # 内容类型
    "TextContent",
    "ImageContent",
    "ThinkingContent",
    "ToolCall",
    "Content",
    # 消息类型
    "UserMessage",
    "AssistantMessage",
    "ToolResultMessage",
    "Message",
    "parse_message",
    # 模型定义
    "ModelCost",
    "Model",
    # 工具定义
    "ToolParameter",
    "Tool",
    # 上下文
    "Context",
]

# ============ API 类型 ============

class ApiType(str, Enum):
    """已知 API 类型"""
    OPENAI_COMPLETIONS = "openai-completions"
    OPENAI_RESPONSES = "openai-responses"
    ANTHROPIC_MESSAGES = "anthropic-messages"
    GOOGLE_GENERATIVE_AI = "google-generative-ai"
    GOOGLE_VERTEX = "google-vertex"
    MISTRAL_CONVERSATIONS = "mistral-conversations"
    BEDROCK_CONVERSE_STREAM = "bedrock-converse-stream"
    BAILIAN = "bailian"
    OLLAMA = "ollama"
    VLLM = "vllm"
    CUSTOM = "custom"


class StopReason(str, Enum):
    """停止原因"""
    STOP = "stop"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    ABORTED = "aborted"
    ERROR = "error"


# ============ 内容类型 ============

class TextContent(BaseModel):
    """文本内容"""
    type: Literal["text"] = "text"
    text: str


class ImageContent(BaseModel):
    """图片内容"""
    type: Literal["image"] = "image"
    source: dict = Field(description="图片源: {type: url|base64, media_type, data}")


class ThinkingContent(BaseModel):
    """思考内容（Claude 扩展思考）"""
    type: Literal["thinking"] = "thinking"
    thinking: str


class ToolCall(BaseModel):
    """工具调用"""
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


Content = TextContent | ImageContent | ThinkingContent | ToolCall


# ============ 消息类型 ============

class UserMessage(BaseModel):
    """用户消息"""
    role: Literal["user"] = "user"
    content: list[Content] = Field(default_factory=list)
    timestamp: float = Field(default_factory=lambda: time.time())

    @classmethod
    def from_text(cls, text: str) -> UserMessage:
        """从文本创建用户消息"""
        return cls(content=[TextContent(text=text)])


class AssistantMessage(BaseModel):
    """助手消息"""
    role: Literal["assistant"] = "assistant"
    content: list[Content] = Field(default_factory=list)
    timestamp: float = Field(default_factory=lambda: time.time())

    @property
    def text(self) -> str:
        """获取文本内容"""
        return "".join(
            c.text for c in self.content
            if isinstance(c, TextContent)
        )


class ToolResultMessage(BaseModel):
    """工具结果消息"""
    role: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    content: list[Content] = Field(default_factory=list)
    timestamp: float = Field(default_factory=lambda: time.time())


Message = UserMessage | AssistantMessage | ToolResultMessage


def parse_message(data: dict[str, Any]) -> Message:
    """
    解析消息

    将字典数据转换为对应的消息类型。

    Args:
        data: 消息数据字典，必须包含 'role' 字段

    Returns:
        Message: 解析后的消息对象

    Raises:
        ValueError: 当角色未知或数据格式无效时
    """
    role = data.get("role")
    if role == "user":
        return UserMessage(**data)
    elif role == "assistant":
        return AssistantMessage(**data)
    elif role == "tool_result":
        return ToolResultMessage(**data)

    valid_roles = ("user", "assistant", "tool_result")
    raise ValueError(
        f"Unknown message role: '{role}'. "
        f"Valid roles are: {', '.join(valid_roles)}. "
        f"Please ensure the message data contains a valid 'role' field."
    )


# ============ 模型定义 ============

class ModelCost(BaseModel):
    """模型成本"""
    input: float = 0.0       # $/million tokens
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0


class Model(BaseModel):
    """模型定义"""
    id: str
    name: str
    api: ApiType
    provider: str
    base_url: str = ""
    reasoning: bool = False
    input_types: list[Literal["text", "image"]] = Field(default_factory=lambda: ["text"])
    cost: ModelCost = Field(default_factory=ModelCost)
    context_window: int = 4096
    max_tokens: int = 2048

    def __repr__(self) -> str:
        return f"Model({self.provider}/{self.id})"


# ============ 工具定义 ============

class ToolParameter(BaseModel):
    """工具参数"""
    type: str
    description: str | None = None
    enum: list[str] | None = None
    default: Any | None = None


class Tool(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: dict[str, ToolParameter] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def _build_properties(self) -> dict[str, Any]:
        """构建参数属性字典"""
        properties = {}
        for name, param in self.parameters.items():
            prop: dict[str, Any] = {"type": param.type}
            if param.description:
                prop["description"] = param.description
            if param.enum:
                prop["enum"] = param.enum
            properties[name] = prop
        return properties

    def to_openai_format(self) -> dict[str, Any]:
        """转换为 OpenAI 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self._build_properties(),
                    "required": self.required,
                }
            }
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """转换为 Anthropic 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self._build_properties(),
                "required": self.required,
            }
        }


# ============ 上下文 ============

def _extract_text_content(content: list[Content]) -> str:
    """提取文本内容"""
    return " ".join(c.text for c in content if isinstance(c, TextContent))


def _convert_user_message_to_openai(msg: UserMessage) -> dict[str, Any]:
    """转换用户消息为 OpenAI 格式"""
    text = _extract_text_content(msg.content)
    return {"role": "user", "content": text}


def _convert_assistant_message_to_openai(msg: AssistantMessage) -> dict[str, Any]:
    """转换助手消息为 OpenAI 格式"""
    content_parts = []
    tool_calls = []

    for c in msg.content:
        if isinstance(c, TextContent):
            content_parts.append(c.text)
        elif isinstance(c, ToolCall):
            tool_calls.append({
                "id": c.id,
                "type": "function",
                "function": {
                    "name": c.name,
                    "arguments": c.input
                }
            })
        # OpenAI 不支持 thinking，跳过

    assistant_msg: dict[str, Any] = {"role": "assistant"}
    if content_parts:
        assistant_msg["content"] = " ".join(content_parts)
    if tool_calls:
        assistant_msg["tool_calls"] = tool_calls

    return assistant_msg


def _convert_tool_result_to_openai(msg: ToolResultMessage) -> dict[str, Any]:
    """转换工具结果消息为 OpenAI 格式"""
    text = _extract_text_content(msg.content)
    return {
        "role": "tool",
        "tool_call_id": msg.tool_call_id,
        "content": text
    }


def _convert_user_message_to_anthropic(msg: UserMessage) -> dict[str, Any]:
    """转换用户消息为 Anthropic 格式"""
    content = []
    for c in msg.content:
        if isinstance(c, TextContent):
            content.append({"type": "text", "text": c.text})
        elif isinstance(c, ImageContent):
            content.append({"type": "image", "source": c.source})
    return {"role": "user", "content": content}


def _convert_assistant_message_to_anthropic(msg: AssistantMessage) -> dict[str, Any]:
    """转换助手消息为 Anthropic 格式"""
    content = []
    for c in msg.content:
        if isinstance(c, TextContent):
            content.append({"type": "text", "text": c.text})
        elif isinstance(c, ThinkingContent):
            content.append({"type": "thinking", "thinking": c.thinking})
        elif isinstance(c, ToolCall):
            content.append({
                "type": "tool_use",
                "id": c.id,
                "name": c.name,
                "input": c.input
            })
    return {"role": "assistant", "content": content}


def _convert_tool_result_to_anthropic(msg: ToolResultMessage) -> dict[str, Any]:
    """转换工具结果消息为 Anthropic 格式"""
    content = [{"type": "text", "text": c.text}
               for c in msg.content if isinstance(c, TextContent)]
    return {
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": msg.tool_call_id,
            "content": content
        }]
    }


class Context(BaseModel):
    """LLM 调用上下文"""
    system_prompt: str | None = None
    messages: list[Message] = Field(default_factory=list)
    tools: list[Tool] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    def add_user_message(self, content: str | list[Content]) -> UserMessage:
        """添加用户消息"""
        if isinstance(content, str):
            content = [TextContent(text=content)]
        msg = UserMessage(content=content)
        self.messages.append(msg)
        return msg

    def add_assistant_message(self, content: list[Content]) -> AssistantMessage:
        """添加助手消息"""
        msg = AssistantMessage(content=content)
        self.messages.append(msg)
        return msg

    def add_tool_result(
        self,
        tool_call_id: str,
        content: str | list[Content]
    ) -> ToolResultMessage:
        """添加工具结果"""
        if isinstance(content, str):
            content = [TextContent(text=content)]
        msg = ToolResultMessage(tool_call_id=tool_call_id, content=content)
        self.messages.append(msg)
        return msg

    def to_openai_messages(self) -> list[dict[str, Any]]:
        """转换为 OpenAI 消息格式"""
        result = []

        if self.system_prompt:
            result.append({"role": "system", "content": self.system_prompt})

        for msg in self.messages:
            if isinstance(msg, UserMessage):
                result.append(_convert_user_message_to_openai(msg))
            elif isinstance(msg, AssistantMessage):
                result.append(_convert_assistant_message_to_openai(msg))
            elif isinstance(msg, ToolResultMessage):
                result.append(_convert_tool_result_to_openai(msg))

        return result

    def to_anthropic_messages(self) -> list[dict[str, Any]]:
        """转换为 Anthropic 消息格式"""
        result = []

        for msg in self.messages:
            if isinstance(msg, UserMessage):
                result.append(_convert_user_message_to_anthropic(msg))
            elif isinstance(msg, AssistantMessage):
                result.append(_convert_assistant_message_to_anthropic(msg))
            elif isinstance(msg, ToolResultMessage):
                result.append(_convert_tool_result_to_anthropic(msg))

        return result

    def copy(self) -> Context:
        """创建副本"""
        return Context(
            system_prompt=self.system_prompt,
            messages=self.messages.copy(),
            tools=self.tools.copy()
        )
