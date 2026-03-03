# IntelliTeam 监控模块

"""
监控模块：
- Prometheus 指标收集
- 性能监控
- 健康检查
"""

from .prometheus import (
    # 指标
    HTTP_REQUESTS,
    HTTP_REQUEST_DURATION,
    WEBSOCKET_CONNECTIONS,
    AGENT_TASKS,
    AGENT_TASK_DURATION,
    CACHE_HITS,
    CACHE_MISSES,
    DB_QUERIES,
    DB_QUERY_DURATION,
    
    # 装饰器
    monitor_http_request,
    monitor_agent_task,
    monitor_cache_operation,
    
    # 收集器
    MetricsCollector,
    get_metrics_collector,
    
    # 后台任务
    collect_system_metrics,
    collect_queue_metrics
)

__all__ = [
    # 指标
    "HTTP_REQUESTS",
    "HTTP_REQUEST_DURATION",
    "WEBSOCKET_CONNECTIONS",
    "AGENT_TASKS",
    "AGENT_TASK_DURATION",
    "CACHE_HITS",
    "CACHE_MISSES",
    "DB_QUERIES",
    "DB_QUERY_DURATION",
    
    # 装饰器
    "monitor_http_request",
    "monitor_agent_task",
    "monitor_cache_operation",
    
    # 收集器
    "MetricsCollector",
    "get_metrics_collector",
    
    # 后台任务
    "collect_system_metrics",
    "collect_queue_metrics"
]
