"""
IntelliTeam 性能监控模块

API 性能分析和监控工具
"""

import time
import functools
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    性能监控器
    
    追踪 API 响应时间和性能指标
    """
    
    def __init__(self):
        self._metrics: Dict[str, Dict[str, Any]] = {}
        self._slow_requests: list = []
        self._slow_threshold = 1.0  # 1 秒
    
    def record_request(
        self,
        endpoint: str,
        duration: float,
        status_code: int = 200,
        error: Optional[str] = None
    ) -> None:
        """
        记录请求
        
        Args:
            endpoint: API 端点
            duration: 耗时（秒）
            status_code: HTTP 状态码
            error: 错误信息
        """
        if endpoint not in self._metrics:
            self._metrics[endpoint] = {
                "total_requests": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "min_time": float('inf'),
                "max_time": 0.0,
                "errors": 0,
                "last_request": None
            }
        
        metrics = self._metrics[endpoint]
        metrics["total_requests"] += 1
        metrics["total_time"] += duration
        metrics["avg_time"] = metrics["total_time"] / metrics["total_requests"]
        metrics["min_time"] = min(metrics["min_time"], duration)
        metrics["max_time"] = max(metrics["max_time"], duration)
        metrics["last_request"] = datetime.now().isoformat()
        
        if error or status_code >= 400:
            metrics["errors"] += 1
        
        # 记录慢请求
        if duration > self._slow_threshold:
            self._slow_requests.append({
                "endpoint": endpoint,
                "duration": duration,
                "timestamp": datetime.now().isoformat(),
                "status_code": status_code,
                "error": error
            })
            # 只保留最近 100 个慢请求
            if len(self._slow_requests) > 100:
                self._slow_requests = self._slow_requests[-100:]
    
    def get_metrics(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        获取性能指标
        
        Args:
            endpoint: 指定端点，为 None 时返回全部
            
        Returns:
            性能指标
        """
        if endpoint:
            return self._metrics.get(endpoint, {})
        
        total_requests = sum(
            m["total_requests"] for m in self._metrics.values()
        )
        total_errors = sum(
            m["errors"] for m in self._metrics.values()
        )
        
        return {
            "endpoints": dict(self._metrics),
            "summary": {
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate": total_errors / total_requests if total_requests > 0 else 0,
                "slow_requests": len(self._slow_requests),
                "slow_threshold": self._slow_threshold
            },
            "slow_requests": self._slow_requests[-20:]  # 最近 20 个慢请求
        }
    
    def reset(self) -> None:
        """重置所有指标"""
        self._metrics.clear()
        self._slow_requests.clear()
    
    def set_slow_threshold(self, threshold: float) -> None:
        """设置慢请求阈值"""
        self._slow_threshold = threshold


# 全局性能监控器
_perf_monitor: Optional[PerformanceMonitor] = None


def get_perf_monitor() -> PerformanceMonitor:
    """获取性能监控器单例"""
    global _perf_monitor
    if _perf_monitor is None:
        _perf_monitor = PerformanceMonitor()
    return _perf_monitor


def timing_decorator(func: Callable) -> Callable:
    """
    计时装饰器
    
    自动记录函数执行时间
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            duration = time.perf_counter() - start
            monitor = get_perf_monitor()
            monitor.record_request(func.__name__, duration)
            return result
        except Exception as e:
            duration = time.perf_counter() - start
            monitor = get_perf_monitor()
            monitor.record_request(
                func.__name__, 
                duration, 
                error=str(e)
            )
            raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start
            monitor = get_perf_monitor()
            monitor.record_request(func.__name__, duration)
            return result
        except Exception as e:
            duration = time.perf_counter() - start
            monitor = get_perf_monitor()
            monitor.record_request(
                func.__name__, 
                duration, 
                error=str(e)
            )
            raise
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


__all__ = [
    "PerformanceMonitor",
    "get_perf_monitor",
    "timing_decorator"
]