"""
工具模块

提供工具基类、注册中心、安全检查、错误模型、策略引擎和呈现器。

架构:
┌─────────────────────────────────────────────────────────────┐
│                       ToolRegistry                           │
│  (注册、发现、执行工具)                                       │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ToolPolicyEngine      ToolPresenter       LoopDetector
   (策略裁剪)            (双通道呈现)        (循环检测)
"""

# 基类和结果
from .base import BaseTool, ToolParameter, ToolResult, ToolStatus

# 错误模型
from .errors import (
    ErrorCode,
    StandardError,
    ToolError,
    forbidden_error,
    internal_error,
    not_found_error,
    security_blocked_error,
    timeout_error,
    unauthorized_error,
    validation_error,
)

# 注册中心
from .registry import ToolRegistry, execute_tool, get_registry, register_tool

# 安全性
from .security import (
    AWS_METADATA_PATTERNS,
    ConsentGate,
    SecurityError,
    ToolSecurity,
    get_security_checker,
    validate_command_safety,
    validate_path_safety,
    validate_url_safety,
)

# 策略引擎
from .policy import (
    AgentToolsConfig,
    ToolPolicyEngine,
    ToolsConfig,
    create_policy_engine,
    get_policy_engine,
)

# 呈现器
from .presenter import (
    ToolPresentation,
    ToolPresenter,
    generate_api_schemas,
    generate_system_prompt,
    present_tools,
)

# 循环检测
from .guardrails import (
    CallRecord,
    DetectorConfig,
    LoopDetectionConfig,
    LoopDetector,
    LoopLevel,
    LoopSignal,
    ToolCall,
    ToolResult as GuardrailsToolResult,
    get_loop_detector,
    setup_loop_detector,
)

# 内置工具
from .builtin import (
    # Exec
    ExecTool,
    ExecRequest,
    ExecResponse,
    ProcessSession,
    ProcessSessionManager,
    get_session_manager,
    exec_command,
    # Process
    ProcessTool,
    create_process_tool,
    # WebFetch
    WebFetchTool,
    web_fetch,
    # WebSearch
    WebSearchTool,
    web_search,
    # Memory
    MemorySearchTool,
    MemoryGetTool,
    MemoryBackend,
    InMemoryBackend,
)

# 旧版工具集合（保持向后兼容）
from .code_tools import CodeTools
from .file_tools import FileTools
from .git_tools import GitTools
from .search_tools import SearchTools
from .test_tools import TestingTools

__all__ = [
    # 基类和结果
    "BaseTool",
    "ToolParameter",
    "ToolResult",
    "ToolStatus",
    # 错误模型
    "ErrorCode",
    "StandardError",
    "ToolError",
    "validation_error",
    "unauthorized_error",
    "forbidden_error",
    "not_found_error",
    "timeout_error",
    "security_blocked_error",
    "internal_error",
    # 注册中心
    "ToolRegistry",
    "get_registry",
    "register_tool",
    "execute_tool",
    # 安全性
    "ToolSecurity",
    "SecurityError",
    "ConsentGate",
    "AWS_METADATA_PATTERNS",
    "get_security_checker",
    "validate_path_safety",
    "validate_command_safety",
    "validate_url_safety",
    # 策略引擎
    "ToolPolicyEngine",
    "ToolsConfig",
    "AgentToolsConfig",
    "create_policy_engine",
    "get_policy_engine",
    # 呈现器
    "ToolPresenter",
    "ToolPresentation",
    "present_tools",
    "generate_system_prompt",
    "generate_api_schemas",
    # 循环检测
    "LoopDetector",
    "LoopDetectionConfig",
    "DetectorConfig",
    "LoopLevel",
    "LoopSignal",
    "ToolCall",
    "GuardrailsToolResult",
    "CallRecord",
    "get_loop_detector",
    "setup_loop_detector",
    # Exec 工具
    "ExecTool",
    "ExecRequest",
    "ExecResponse",
    "ProcessSession",
    "ProcessSessionManager",
    "get_session_manager",
    "exec_command",
    # Process 工具
    "ProcessTool",
    "create_process_tool",
    # WebFetch 工具
    "WebFetchTool",
    "web_fetch",
    # WebSearch 工具
    "WebSearchTool",
    "web_search",
    # Memory 工具
    "MemorySearchTool",
    "MemoryGetTool",
    "MemoryBackend",
    "InMemoryBackend",
    # 旧版工具集合（向后兼容）
    "CodeTools",
    "FileTools",
    "GitTools",
    "SearchTools",
    "TestingTools",
]
