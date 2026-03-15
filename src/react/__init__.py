"""
ReAct Agent 模块

提供基于 LangChain 的 ReAct (Reasoning + Acting) Agent 实现。

核心组件:
- ReActAgent: ReAct Agent 基类
- ToolAdapter: 工具适配器
- Prompt 模板: ReAct 推理 Prompt
- Callbacks: 执行监控和回调

版本: 1.0.0
创建时间: 2026-03-14
"""

from .agent import ReActAgent
from .callbacks import ReActCallbackHandler, LoopDetectionCallback
from .exceptions import (
    ReActError,
    ReActMaxIterationsError,
    ReActTimeoutError,
    ReActToolExecutionError,
    ReActLoopDetectedError,
)
from .prompts import (
    get_default_react_prompt,
    get_role_specific_prompt,
    REACT_PROMPT_TEMPLATE,
)
from .tool_adapter import (
    ToolAdapter,
    adapt_tool,
    adapt_tools,
    adapt_tool_with_timeout,
    adapt_tools_with_timeout,
)
from .types import (
    ReActStep,
    ReActResult,
    ReActConfig,
)

__all__ = [
    # Agent
    "ReActAgent",
    # Tool Adapter
    "ToolAdapter",
    "adapt_tool",
    "adapt_tools",
    "adapt_tool_with_timeout",
    "adapt_tools_with_timeout",
    # Prompts
    "get_default_react_prompt",
    "get_role_specific_prompt",
    "REACT_PROMPT_TEMPLATE",
    # Callbacks
    "ReActCallbackHandler",
    "LoopDetectionCallback",
    # Exceptions
    "ReActError",
    "ReActMaxIterationsError",
    "ReActTimeoutError",
    "ReActToolExecutionError",
    "ReActLoopDetectedError",
    # Types
    "ReActStep",
    "ReActResult",
    "ReActConfig",
]
