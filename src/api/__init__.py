# IntelliTeam 高级模块

"""
高级功能模块：
- API 中间件（限流、安全、性能监控）
- 缓存管理（Redis 支持）
- 性能分析工具
"""

from .cache import CacheManager, get_cache, init_cache
from .middleware import (
    RateLimitMiddleware,
    RequestTimingMiddleware,
    SecurityHeadersMiddleware,
    setup_middlewares,
)
from .performance import PerformanceMonitor, get_perf_monitor, timing_decorator

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
]
