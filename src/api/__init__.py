# IntelliTeam 高级模块

"""
高级功能模块：
- API 中间件（限流、安全、性能监控）
- 缓存管理（Redis 支持）
- 性能分析工具
- 响应标准化
- 参数验证
"""

from .cache import CacheManager, get_cache, init_cache
from .middleware import (
    RateLimitMiddleware,
    RequestTimingMiddleware,
    SecurityHeadersMiddleware,
    setup_middlewares,
)
from .performance import PerformanceMonitor, get_perf_monitor, timing_decorator
from .response import (
    APIErrors,
    APIResponse,
    ErrorResponse,
    PaginatedResponse,
    ResponseBuilder,
    error_response,
    paginated_response,
    success_response,
)

# 从 validators 导入存在的类
from .validators import (
    AgentExecuteRequest,
    BatchOperationRequest,
    CodeExecutionRequest,
    LLMGenerateRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
)

__all__ = [
    # 中间件
    "RateLimitMiddleware",
    "RequestTimingMiddleware",
    "SecurityHeadersMiddleware",
    "setup_middlewares",
    # 缓存
    "CacheManager",
    "get_cache",
    "init_cache",
    # 性能
    "timing_decorator",
    "PerformanceMonitor",
    "get_perf_monitor",
    # 响应
    "APIResponse",
    "PaginatedResponse",
    "ErrorResponse",
    "ResponseBuilder",
    "APIErrors",
    "success_response",
    "error_response",
    "paginated_response",
    # 验证
    "TaskCreateRequest",
    "TaskUpdateRequest",
    "AgentExecuteRequest",
    "LLMGenerateRequest",
    "CodeExecutionRequest",
    "BatchOperationRequest",
]
