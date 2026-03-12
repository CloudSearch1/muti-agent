"""
PI-Python: Python 版 AI Agent 工具包

基于 pi-mono 架构设计，提供统一的 LLM API 和 Agent 运行时
"""

from .agent import (
    Agent,
    AgentEvent,
    AgentEventType,
    AgentState,
    AgentTool,
    Session,
    ToolResult,
)
from .ai import (
    # 类型
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
    ToolResultMessage,
    UserMessage,
    complete,
    # 函数
    get_model,
    get_provider,
    register_provider,
    stream,
    stream_simple,
)
from .extensions import (
    ExtensionAPI,
    ExtensionContext,
    ExtensionLoader,
)
from .skills import (
    Skill,
    SkillLoader,
    SkillRegistry,
)
from .skills.registry import (
    get_skill_registry,
    register_skill,
    find_skills,
)

__version__ = "0.1.0"
__all__ = [
    # AI 模块
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
    "Context",
    "get_model",
    "stream",
    "stream_simple",
    "complete",
    "get_provider",
    "register_provider",
    # Agent 模块
    "Agent",
    "AgentState",
    "AgentEvent",
    "AgentEventType",
    "AgentTool",
    "ToolResult",
    "Session",
    # Extensions 模块
    "ExtensionAPI",
    "ExtensionLoader",
    "ExtensionContext",
    # Skills 模块
    "Skill",
    "SkillLoader",
    "SkillRegistry",
    "get_skill_registry",
    "register_skill",
    "find_skills",
]
