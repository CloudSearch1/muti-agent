"""
内置工具包

提供核心工具实现。
"""

from ..errors import ErrorCode, StandardError, ToolError
from ..base import ToolStatus, ToolResult
from .exec import (
    ExecRequest,
    ExecResponse,
    ExecTool,
    NodeTarget,
    ProcessSession,
    ProcessSessionManager,
    exec_command,
    get_session_manager,
)
from .process import (
    ProcessListRequest,
    ProcessListResponse,
    ProcessLogRequest,
    ProcessLogResponse,
    ProcessPollRequest,
    ProcessPollResponse,
    ProcessSessionInfo,
    ProcessTool,
    ProcessWriteRequest,
    create_process_tool,
)
from .web_fetch import (
    ContentExtractor,
    SSRFGuard,
    WebFetchCache,
    WebFetchRequest,
    WebFetchResponse,
    WebFetchTool,
    web_fetch,
)
from .web_search import (
    BingBackend,
    CacheInfo,
    DuckDuckGoBackend,
    SearchBackend,
    SearchCache,
    WebSearchRequest,
    WebSearchResponse,
    WebSearchResult,
    WebSearchTool,
    web_search,
)
from .memory import (
    MemoryBackend,
    MemoryEntry,
    MemoryGetTool,
    MemorySearchTool,
    InMemoryBackend,
)

__all__ = [
    # 错误模型
    "ErrorCode",
    "StandardError",
    "ToolError",
    "ToolStatus",
    "ToolResult",
    # Exec 工具
    "ExecTool",
    "ExecRequest",
    "ExecResponse",
    "NodeTarget",
    "ProcessSession",
    "ProcessSessionManager",
    "get_session_manager",
    "exec_command",
    # Process 工具
    "ProcessTool",
    "ProcessListRequest",
    "ProcessListResponse",
    "ProcessPollRequest",
    "ProcessPollResponse",
    "ProcessLogRequest",
    "ProcessLogResponse",
    "ProcessWriteRequest",
    "ProcessSessionInfo",
    "create_process_tool",
    # WebFetch 工具
    "WebFetchTool",
    "WebFetchRequest",
    "WebFetchResponse",
    "SSRFGuard",
    "ContentExtractor",
    "WebFetchCache",
    "web_fetch",
    # WebSearch 工具
    "WebSearchTool",
    "WebSearchRequest",
    "WebSearchResult",
    "WebSearchResponse",
    "CacheInfo",
    "SearchBackend",
    "DuckDuckGoBackend",
    "BingBackend",
    "SearchCache",
    "web_search",
    # Memory 工具
    "MemorySearchTool",
    "MemoryGetTool",
    "MemoryEntry",
    "MemoryBackend",
    "InMemoryBackend",
]
