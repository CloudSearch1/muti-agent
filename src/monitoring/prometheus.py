"""
IntelliTeam Prometheus 监控模块

提供性能指标收集和监控
"""

import asyncio
import logging
import time
from functools import wraps

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
)

logger = logging.getLogger(__name__)

# ============ 指标定义 ============

# HTTP 请求指标
HTTP_REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
)

HTTP_REQUEST_IN_PROGRESS = Gauge(
    "http_requests_in_progress", "Number of HTTP requests in progress", ["method", "endpoint"]
)

# WebSocket 指标
WEBSOCKET_CONNECTIONS = Gauge("websocket_connections", "Number of active WebSocket connections")

WEBSOCKET_MESSAGES = Counter(
    "websocket_messages_total",
    "Total WebSocket messages sent/received",
    ["direction"],  # sent or received
)

# Agent 指标
AGENT_TASKS = Counter(
    "agent_tasks_total",
    "Total tasks executed by agents",
    ["agent_name", "status"],  # success or failed
)

AGENT_TASK_DURATION = Histogram(
    "agent_task_duration_seconds", "Agent task execution duration in seconds", ["agent_name"]
)

AGENT_ACTIVE = Gauge("agent_active_tasks", "Number of active agent tasks", ["agent_name"])

# 任务指标
TASKS_CREATED = Counter("tasks_created_total", "Total tasks created")

TASKS_COMPLETED = Counter(
    "tasks_completed_total", "Total tasks completed", ["status"]  # success, failed, cancelled
)

TASK_QUEUE_LENGTH = Gauge("task_queue_length", "Number of tasks in queue")

# 缓存指标
CACHE_HITS = Counter("cache_hits_total", "Total cache hits", ["cache_level"])  # l1 or l2

CACHE_MISSES = Counter("cache_misses_total", "Total cache misses", ["cache_level"])

CACHE_SIZE = Gauge("cache_size", "Current cache size", ["cache_level"])

# 数据库指标
DB_QUERIES = Counter("database_queries_total", "Total database queries")

DB_QUERY_DURATION = Histogram(
    "database_query_duration_seconds", "Database query duration in seconds"
)

DB_CONNECTIONS = Gauge("database_connections", "Number of active database connections")

# 系统指标
SYSTEM_CPU = Gauge("system_cpu_percent", "System CPU usage percent")

SYSTEM_MEMORY = Gauge("system_memory_bytes", "System memory usage in bytes")

# 性能摘要
RESPONSE_TIME = Summary("response_time_seconds", "Response time in seconds", ["endpoint"])


# ============ 监控装饰器 ============


def monitor_http_request(endpoint: str):
    """
    HTTP 请求监控装饰器

    Usage:
        @monitor_http_request("/api/v1/tasks")
        async def get_tasks():
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            method = kwargs.get("method", "GET")

            HTTP_REQUESTS.labels(method=method, endpoint=endpoint, status=200).inc()
            HTTP_REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                HTTP_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
                RESPONSE_TIME.labels(endpoint=endpoint).observe(duration)

                return result
            except Exception:
                HTTP_REQUESTS.labels(method=method, endpoint=endpoint, status=500).inc()
                raise
            finally:
                HTTP_REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

        return wrapper

    return decorator


def monitor_agent_task(agent_name: str):
    """
    Agent 任务监控装饰器

    Usage:
        @monitor_agent_task("Coder")
        async def execute_task(task):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            AGENT_ACTIVE.labels(agent_name=agent_name).inc()

            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "failed"
                logger.error(f"Agent {agent_name} task failed: {e}")
                raise
            finally:
                duration = time.time() - start_time
                AGENT_TASKS.labels(agent_name=agent_name, status=status).inc()
                AGENT_TASK_DURATION.labels(agent_name=agent_name).observe(duration)
                AGENT_ACTIVE.labels(agent_name=agent_name).dec()

        return wrapper

    return decorator


def monitor_cache_operation(cache_level: str = "l2"):
    """
    缓存操作监控装饰器

    Usage:
        @monitor_cache_operation("l2")
        async def get_cache(key):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            if result is not None:
                CACHE_HITS.labels(cache_level=cache_level).inc()
            else:
                CACHE_MISSES.labels(cache_level=cache_level).inc()

            return result

        return wrapper

    return decorator


# ============ 监控管理器 ============


class MetricsCollector:
    """
    指标收集器

    收集和报告系统指标
    """

    def __init__(self):
        self.registry = CollectorRegistry()

    def get_metrics(self) -> str:
        """获取所有指标"""
        return generate_latest(self.registry).decode("utf-8")

    def get_metrics_content_type(self) -> str:
        """获取指标内容类型"""
        return CONTENT_TYPE_LATEST

    def update_system_metrics(self, cpu: float, memory: float):
        """更新系统指标"""
        SYSTEM_CPU.set(cpu)
        SYSTEM_MEMORY.set(memory)

    def update_websocket_connections(self, count: int):
        """更新 WebSocket 连接数"""
        WEBSOCKET_CONNECTIONS.set(count)

    def update_task_queue(self, length: int):
        """更新任务队列长度"""
        TASK_QUEUE_LENGTH.set(length)

    def update_cache_size(self, level: str, size: int):
        """更新缓存大小"""
        CACHE_SIZE.labels(cache_level=level).set(size)

    def update_db_connections(self, count: int):
        """更新数据库连接数"""
        DB_CONNECTIONS.set(count)


# 全局指标收集器
metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """获取指标收集器单例"""
    return metrics_collector


# ============ FastAPI 集成 ============


async def collect_system_metrics():
    """
    收集系统指标

    后台任务：每分钟执行
    """
    import psutil

    while True:
        try:
            cpu = psutil.cpu_percent()
            memory = psutil.virtual_memory().used

            metrics_collector.update_system_metrics(cpu, memory)

            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"收集系统指标失败：{e}")
            await asyncio.sleep(60)


async def collect_queue_metrics():
    """
    收集队列指标

    后台任务：每 10 秒执行
    """
    while True:
        try:
            # 这里可以集成 Celery 队列长度
            # queue_length = celery_app.inspect().active()
            queue_length = 0

            metrics_collector.update_task_queue(queue_length)

            await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"收集队列指标失败：{e}")
            await asyncio.sleep(10)
