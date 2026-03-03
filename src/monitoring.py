"""
监控指标

职责：提供 Prometheus 监控指标
"""

from typing import Optional
import time
from functools import wraps


try:
    from prometheus_client import Counter, Histogram, Gauge, Summary
    
    # HTTP 请求指标
    HTTP_REQUESTS = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )
    
    HTTP_REQUEST_DURATION = Histogram(
        'http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint']
    )
    
    # Agent 指标
    AGENT_TASKS = Counter(
        'agent_tasks_total',
        'Total tasks executed by agents',
        ['agent_role', 'status']
    )
    
    AGENT_EXECUTION_TIME = Histogram(
        'agent_execution_time_seconds',
        'Agent execution time in seconds',
        ['agent_role']
    )
    
    AGENT_ACTIVE = Gauge(
        'agent_active_tasks',
        'Number of active agent tasks',
        ['agent_role']
    )
    
    # 工作流指标
    WORKFLOW_EXECUTIONS = Counter(
        'workflow_executions_total',
        'Total workflow executions',
        ['workflow_name', 'status']
    )
    
    WORKFLOW_DURATION = Histogram(
        'workflow_duration_seconds',
        'Workflow duration in seconds',
        ['workflow_name']
    )
    
    # 黑板指标
    BLACKBOARD_ENTRIES = Gauge(
        'blackboard_entries_total',
        'Number of entries in blackboard'
    )
    
    BLACKBOARD_MESSAGES = Counter(
        'blackboard_messages_total',
        'Total messages posted to blackboard'
    )
    
    PROMETHEUS_AVAILABLE = True
    
except ImportError:
    # Prometheus 未安装，使用空实现
    PROMETHEUS_AVAILABLE = False
    
    class DummyMetric:
        def __init__(self, *args, **kwargs):
            pass
        def inc(self, *args, **kwargs):
            pass
        def set(self, *args, **kwargs):
            pass
        def observe(self, *args, **kwargs):
            pass
        def time(self):
            return self
        def __enter__(self):
            pass
        def __exit__(self, *args):
            pass
    
    HTTP_REQUESTS = DummyMetric()
    HTTP_REQUEST_DURATION = DummyMetric()
    AGENT_TASKS = DummyMetric()
    AGENT_EXECUTION_TIME = DummyMetric()
    AGENT_ACTIVE = DummyMetric()
    WORKFLOW_EXECUTIONS = DummyMetric()
    WORKFLOW_DURATION = DummyMetric()
    BLACKBOARD_ENTRIES = DummyMetric()
    BLACKBOARD_MESSAGES = DummyMetric()


def track_request(method: str, endpoint: str):
    """装饰器：跟踪 HTTP 请求"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "200"
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "500"
                raise
            finally:
                duration = time.time() - start_time
                HTTP_REQUESTS.labels(method=method, endpoint=endpoint, status=status).inc()
                HTTP_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
        
        return wrapper
    return decorator


def track_agent_execution(agent_role: str):
    """装饰器：跟踪 Agent 执行"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            AGENT_ACTIVE.labels(agent_role=agent_role).inc()
            start_time = time.time()
            status = "success"
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "failed"
                raise
            finally:
                duration = time.time() - start_time
                AGENT_TASKS.labels(agent_role=agent_role, status=status).inc()
                AGENT_EXECUTION_TIME.labels(agent_role=agent_role).observe(duration)
                AGENT_ACTIVE.labels(agent_role=agent_role).dec()
        
        return wrapper
    return decorator


def track_workflow_execution(workflow_name: str):
    """装饰器：跟踪工作流执行"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "failed"
                raise
            finally:
                duration = time.time() - start_time
                WORKFLOW_EXECUTIONS.labels(workflow_name=workflow_name, status=status).inc()
                WORKFLOW_DURATION.labels(workflow_name=workflow_name).observe(duration)
        
        return wrapper
    return decorator
