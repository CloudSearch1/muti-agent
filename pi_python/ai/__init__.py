"""
PI-Python AI 模块 - 统一 LLM API

提供多提供商的统一接口
"""

from .types import (
    ApiType,
    StopReason,
    TextContent,
    ImageContent,
    ThinkingContent,
    ToolCall,
    Content,
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    Message,
    ModelCost,
    Model,
    Tool,
    ToolParameter,
    Context,
    parse_message,
)

from .stream import (
    AssistantMessageEvent,
    AssistantMessageEventStream,
    StreamOptions,
    stream,
    stream_simple,
    complete,
)

from .model import (
    get_model,
    list_models,
    register_model,
    get_provider,
    register_provider,
    ModelRegistry,
)

from .providers import (
    BaseProvider,
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    AzureProvider,
    BedrockProvider,
    MistralProvider,
    GroqProvider,
    OpenRouterProvider,
    BailianProvider,
    OllamaProvider,
    VLLMProvider,
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