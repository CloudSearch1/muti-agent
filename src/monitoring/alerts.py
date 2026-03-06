"""
监控告警模块

集成 Prometheus + Grafana，实现完整监控告警
"""

from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time
import logging

logger = logging.getLogger(__name__)


# ============ Prometheus 指标 ============

# 请求计数器
REQUEST_COUNT = Counter(
    'app_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

# 请求耗时直方图
REQUEST_DURATION = Histogram(
    'app_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# 活跃请求数
REQUESTS_IN_PROGRESS = Gauge(
    'app_requests_in_progress',
    'Requests in progress',
    ['method', 'endpoint']
)

# LLM 调用计数器
LLM_CALL_COUNT = Counter(
    'app_llm_calls_total',
    'Total LLM calls',
    ['provider', 'model', 'status']
)

# LLM 调用耗时
LLM_CALL_DURATION = Histogram(
    'app_llm_call_duration_seconds',
    'LLM call duration',
    ['provider', 'model'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

# Token 使用量
TOKEN_USAGE = Counter(
    'app_llm_tokens_total',
    'Total tokens used',
    ['provider', 'type']  # type: prompt, completion
)

# 数据库查询耗时
DB_QUERY_DURATION = Histogram(
    'app_db_query_duration_seconds',
    'Database query duration',
    ['operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

# 缓存命中率
CACHE_HIT = Counter(
    'app_cache_hits_total',
    'Cache hits',
    ['cache_type']
)

CACHE_MISS = Counter(
    'app_cache_misses_total',
    'Cache misses',
    ['cache_type']
)

# Agent 执行指标
AGENT_EXECUTION_COUNT = Counter(
    'app_agent_executions_total',
    'Agent executions',
    ['agent', 'status']
)

AGENT_EXECUTION_DURATION = Histogram(
    'app_agent_execution_duration_seconds',
    'Agent execution duration',
    ['agent'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
)

# 任务指标
TASK_COUNT = Gauge(
    'app_tasks_total',
    'Total tasks',
    ['status', 'priority']
)

# 系统指标
MEMORY_USAGE = Gauge(
    'app_memory_usage_bytes',
    'Memory usage'
)

CPU_USAGE = Gauge(
    'app_cpu_usage_percent',
    'CPU usage'
)


# ============ 监控中间件 ============

class MonitoringMiddleware:
    """
    监控中间件
    
    自动收集请求指标
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        method = scope["method"]
        path = scope["path"]
        
        # 增加活跃请求数
        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=path).inc()
        
        start_time = time.time()
        
        try:
            # 包装发送函数以捕获状态码
            status_code = None
            
            async def send_wrapper(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
            
        finally:
            # 记录指标
            duration = time.time() - start_time
            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status=status_code or 500
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            
            REQUESTS_IN_PROGRESS.labels(
                method=method,
                endpoint=path
            ).dec()


# ============ 监控端点 ============

def setup_monitoring(app: FastAPI):
    """
    设置监控端点
    
    Args:
        app: FastAPI 应用实例
    """
    
    @app.get("/metrics")
    async def get_metrics():
        """Prometheus 指标端点"""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )
    
    @app.get("/health/metrics")
    async def get_health_metrics():
        """健康指标（简化版）"""
        return {
            "status": "healthy",
            "timestamp": time.time(),
        }
    
    logger.info("Monitoring endpoints configured")


# ============ 告警规则 ============

ALERT_RULES = """
# Prometheus 告警规则

groups:
  - name: IntelliTeam Alerts
    interval: 30s
    rules:
      # 高错误率
      - alert: HighErrorRate
        expr: sum(rate(app_requests_total{status=~"5.."}[5m])) / sum(rate(app_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"
      
      # 慢请求
      - alert: SlowRequests
        expr: histogram_quantile(0.95, rate(app_request_duration_seconds_bucket[5m])) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow requests detected"
          description: "95th percentile latency is {{ $value }}s"
      
      # LLM 调用失败
      - alert: LLMCallFailures
        expr: sum(rate(app_llm_calls_total{status="error"}[5m])) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "LLM call failures detected"
          description: "LLM error rate is high"
      
      # 数据库慢查询
      - alert: SlowDatabaseQueries
        expr: histogram_quantile(0.95, rate(app_db_query_duration_seconds_bucket[5m])) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow database queries detected"
          description: "95th percentile query latency is {{ $value }}s"
      
      # 缓存命中率低
      - alert: LowCacheHitRate
        expr: sum(rate(app_cache_hits_total[5m])) / (sum(rate(app_cache_hits_total[5m])) + sum(rate(app_cache_misses_total[5m]))) < 0.5
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit rate"
          description: "Cache hit rate is {{ $value | humanizePercentage }}"
      
      # Agent 执行失败
      - alert: AgentExecutionFailures
        expr: sum(rate(app_agent_executions_total{status="failed"}[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Agent execution failures detected"
          description: "Agent failure rate is high"
      
      # 内存使用过高
      - alert: HighMemoryUsage
        expr: app_memory_usage_bytes / 1024 / 1024 / 1024 > 1.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}GB"
      
      # 服务不可用
      - alert: ServiceDown
        expr: up{job="intelliteam"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service is down"
          description: "IntelliTeam service is not responding"
"""

# ============ Grafana 仪表板配置 ============

GRAFANA_DASHBOARD = """
{
  "dashboard": {
    "title": "IntelliTeam Monitoring",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(app_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Request Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(app_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(app_request_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(app_requests_total{status=~\"5..\"}[5m])) / sum(rate(app_requests_total[5m]))",
            "legendFormat": "Error Rate"
          }
        ]
      },
      {
        "title": "LLM Calls",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(app_llm_calls_total[5m])",
            "legendFormat": "{{provider}} {{model}}"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(app_cache_hits_total[5m])) / (sum(rate(app_cache_hits_total[5m])) + sum(rate(app_cache_misses_total[5m])))",
            "legendFormat": "Hit Rate"
          }
        ]
      },
      {
        "title": "Agent Executions",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(app_agent_executions_total[5m])",
            "legendFormat": "{{agent}} {{status}}"
          }
        ]
      }
    ]
  }
}
"""
