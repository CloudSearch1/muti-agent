"""
PI-Python AI 模块 - 统一 LLM API

提供多提供商的统一接口
"""

from .model import (
    ModelRegistry,
    get_model,
    get_provider,
    list_models,
    register_model,
    register_provider,
)
from .providers import (
    AnthropicProvider,
    AzureProvider,
    BailianProvider,
    BaseProvider,
    BedrockProvider,
    GoogleProvider,
    GroqProvider,
    MistralProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
    VLLMProvider,
)
from .stream import (
    AssistantMessageEvent,
    AssistantMessageEventStream,
    StreamOptions,
    complete,
    stream,
    stream_simple,
)
from .types import (
    ApiType,
    AssistantMessage,
    Content,
    Context,
    ImageContent,
    Message,
    Model,
    ModelCost,
    StopReason,
    TextContent,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolParameter,
    ToolResultMessage,
    UserMessage,
    parse_message,
)

__all__ = [
    # 类型
    "ApiType",
    "StopReason",
    "TextContent",
    "ImageContent",
    "ThinkingContent",
    "ToolCall",
    "Content",
    "UserMessage",
    "AssistantMessage",
    "ToolResultMessage",
    "Message",
    "ModelCost",
    "Model",
    "Tool",
    "ToolParameter",
    "Context",
    "parse_message",
    # 流式 API
    "AssistantMessageEvent",
    "AssistantMessageEventStream",
    "StreamOptions",
    "stream",
    "stream_simple",
    "complete",
    # 模型管理
    "get_model",
    "list_models",
    "register_model",
    "get_provider",
    "register_provider",
    "ModelRegistry",
    # 提供商
    "BaseProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    "AzureProvider",
    "BedrockProvider",
    "MistralProvider",
    "GroqProvider",
    "OpenRouterProvider",
    "BailianProvider",
    "OllamaProvider",
    "VLLMProvider",
]
