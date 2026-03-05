"""
IntelliTeam 性能分析模块

提供性能监控和分析工具
"""

import asyncio
import logging
import time
from collections.abc import Callable
from functools import wraps

logger = logging.getLogger(__name__)


def timing_decorator(func: Callable) -> Callable:
    """
    性能分析装饰器

    记录函数执行时间

    Usage:
        @timing_decorator
        def my_function():
            pass
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        process_time = end_time - start_time

        logger.info(f"{func.__name__} executed in {process_time:.4f}s")

        if process_time > 1.0:  # 超过 1 秒记录警告
            logger.warning(f"{func.__name__} took {process_time:.4f}s (slow)")

        return result

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        process_time = end_time - start_time

        logger.info(f"{func.__name__} executed in {process_time:.4f}s")

        if process_time > 1.0:
            logger.warning(f"{func.__name__} took {process_time:.4f}s (slow)")

        return result

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class PerformanceMonitor:
    """
    性能监控器

    统计和分析性能指标
    """

    def __init__(self):
        self.metrics = {}

    def start_timer(self, name: str):
        """开始计时"""
        self.metrics[name] = {
            "start_time": time.time(),
            "calls": 0,
            "total_time": 0,
            "min_time": float("inf"),
            "max_time": 0,
        }

    def stop_timer(self, name: str):
        """停止计时"""
        if name not in self.metrics:
            return

        metric = self.metrics[name]
        end_time = time.time()
        process_time = end_time - metric["start_time"]

        metric["calls"] += 1
        metric["total_time"] += process_time
        metric["min_time"] = min(metric["min_time"], process_time)
        metric["max_time"] = max(metric["max_time"], process_time)

    def get_stats(self, name: str) -> dict:
        """获取统计信息"""
        if name not in self.metrics:
            return {}

        metric = self.metrics[name]
        avg_time = metric["total_time"] / metric["calls"] if metric["calls"] > 0 else 0

        return {
            "calls": metric["calls"],
            "total_time": metric["total_time"],
            "avg_time": avg_time,
            "min_time": metric["min_time"],
            "max_time": metric["max_time"],
        }

    def get_all_stats(self) -> dict:
        """获取所有统计信息"""
        return {name: self.get_stats(name) for name in self.metrics}

    def reset(self):
        """重置所有统计"""
        self.metrics = {}


# 全局性能监控器
perf_monitor = PerformanceMonitor()


def get_perf_monitor() -> PerformanceMonitor:
    """获取性能监控器单例"""
    return perf_monitor
