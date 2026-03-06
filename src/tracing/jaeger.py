"""
分布式追踪集成

集成 Jaeger/Zipkin，实现全链路追踪
"""

import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)


class DistributedTracer:
    """
    分布式追踪器
    
    支持:
    - Jaeger
    - Zipkin
    - OpenTelemetry
    """
    
    def __init__(
        self,
        service_name: str = "intelliteam",
        agent_host: str = "localhost",
        agent_port: int = 6831,
    ):
        self.service_name = service_name
        self.agent_host = agent_host
        self.agent_port = agent_port
        
        self._tracer = None
        self._scope_manager = None
        
        logger.info(f"DistributedTracer initialized: {service_name}")
    
    def initialize(self):
        """初始化追踪器"""
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.jaeger.thrift import JaegerExporter
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            
            # 设置追踪提供者
            provider = TracerProvider()
            trace.set_tracer_provider(provider)
            
            # 配置 Jaeger 导出器
            exporter = JaegerExporter(
                agent_host_name=self.agent_host,
                agent_port=self.agent_port,
            )
            
            # 添加批量处理器
            span_processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(span_processor)
            
            self._tracer = trace.get_tracer(self.service_name)
            
            logger.info(f"Jaeger tracer initialized: {self.agent_host}:{self.agent_port}")
            
        except ImportError:
            logger.warning("OpenTelemetry not installed, tracing disabled")
        except Exception as e:
            logger.error(f"Tracer initialization failed: {e}")
    
    @contextmanager
    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        开始追踪跨度
        
        用法:
            with tracer.start_span("database_query", {"table": "tasks"}):
                # 执行数据库查询
                pass
        """
        if not self._tracer:
            yield
            return
        
        with self._tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            
            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
    
    def inject_context(self, headers: Dict[str, str]):
        """注入追踪上下文到请求头"""
        if not self._tracer:
            return headers
        
        from opentelemetry import trace
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        
        propagator = TraceContextTextMapPropagator()
        propagator.inject(headers)
        
        return headers
    
    def extract_context(self, headers: Dict[str, str]):
        """从请求头提取追踪上下文"""
        if not self._tracer:
            return
        
        from opentelemetry import trace
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        
        propagator = TraceContextTextMapPropagator()
        context = propagator.extract(headers)
        
        return context


# ============ 性能分析装饰器 ============

def trace_operation(operation_name: str):
    """
    追踪操作装饰器
    
    用法:
        @trace_operation("database_query")
        async def query_database():
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            
            with tracer.start_span(
                operation_name,
                attributes={
                    "function": func.__name__,
                    "module": func.__module__,
                },
            ) as span:
                start_time = time.time()
                
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    span.set_attribute("duration_ms", duration * 1000)
                    span.set_attribute("success", True)
                    
                    return result
                    
                except Exception as e:
                    duration = time.time() - start_time
                    
                    span.set_attribute("duration_ms", duration * 1000)
                    span.set_attribute("success", False)
                    span.set_attribute("error", str(e))
                    
                    raise
        
        return wrapper
    return decorator


# ============ 全局追踪器 ============

_tracer: Optional[DistributedTracer] = None


def get_tracer() -> DistributedTracer:
    """获取追踪器"""
    global _tracer
    if _tracer is None:
        _tracer = DistributedTracer()
        _tracer.initialize()
    return _tracer


async def init_tracer(**kwargs) -> DistributedTracer:
    """初始化追踪器"""
    global _tracer
    _tracer = DistributedTracer(**kwargs)
    _tracer.initialize()
    logger.info("Distributed tracer initialized")
    return _tracer


async def close_tracer():
    """关闭追踪器"""
    global _tracer
    if _tracer:
        _tracer = None
        logger.info("Distributed tracer closed")
