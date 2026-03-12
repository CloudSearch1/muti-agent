"""
PI-Python 核心类型定义

定义 LLM API 的核心类型，与 pi-mono 类型系统对应
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

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
    """解析消息"""
    role = data.get("role")
    if role == "user":
        return UserMessage(**data)
    elif role == "assistant":
        return AssistantMessage(**data)
    elif role == "tool_result":
        return ToolResultMessage(**data)
    raise ValueError(f"Unknown message role: {role}")


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

    def to_openai_format(self) -> dict[str, Any]:
        """转换为 OpenAI 格式"""
        properties = {}
        for name, param in self.parameters.items():
            prop = {"type": param.type}
            if param.description:
                prop["description"] = param.description
            if param.enum:
                prop["enum"] = param.enum
            properties[name] = prop

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": self.required,
                }
            }
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """转换为 Anthropic 格式"""
        properties = {}
        for name, param in self.parameters.items():
            prop = {"type": param.type}
            if param.description:
                prop["description"] = param.description
            if param.enum:
                prop["enum"] = param.enum
            properties[name] = prop

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": self.required,
            }
        }


# ============ 上下文 ============

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
                # 简化处理：只取文本
                text = " ".join(
                    c.text for c in msg.content
                    if isinstance(c, TextContent)
                )
                result.append({"role": "user", "content": text})

            elif isinstance(msg, AssistantMessage):
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
                    elif isinstance(c, ThinkingContent):
                        # OpenAI 不支持 thinking，跳过
                        pass

                assistant_msg = {"role": "assistant"}
                if content_parts:
                    assistant_msg["content"] = " ".join(content_parts)
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls

                result.append(assistant_msg)

            elif isinstance(msg, ToolResultMessage):
                text = " ".join(
                    c.text for c in msg.content
                    if isinstance(c, TextContent)
                )
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": text
                })

        return result

    def to_anthropic_messages(self) -> list[dict[str, Any]]:
        """转换为 Anthropic 消息格式"""
        result = []

        for msg in self.messages:
            if isinstance(msg, UserMessage):
                content = []
                for c in msg.content:
                    if isinstance(c, TextContent):
                        content.append({"type": "text", "text": c.text})
                    elif isinstance(c, ImageContent):
                        content.append({
                            "type": "image",
                            "source": c.source
                        })

                result.append({"role": "user", "content": content})

            elif isinstance(msg, AssistantMessage):
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

                result.append({"role": "assistant", "content": content})

            elif isinstance(msg, ToolResultMessage):
                content = []
                for c in msg.content:
                    if isinstance(c, TextContent):
                        content.append({"type": "text", "text": c.text})

                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": content
                    }]
                })

        return result

    def copy(self) -> Context:
        """创建副本"""
        return Context(
            system_prompt=self.system_prompt,
            messages=self.messages.copy(),
            tools=self.tools.copy()
        )
