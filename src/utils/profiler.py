"""
性能分析工具

集成 cProfile、py-spy 等性能分析工具
"""

import cProfile
import io
import logging
import pstats
import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps

from fastapi import APIRouter

logger = logging.getLogger(__name__)


# ============ 函数性能分析 ============

def profile_function(func: Callable) -> Callable:
    """
    函数性能分析装饰器

    用法:
        @profile_function
        async def my_function():
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()

        try:
            profiler.enable()
            result = await func(*args, **kwargs)
            profiler.disable()

            # 输出统计
            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream)
            stats.sort_stats('cumulative')
            stats.print_stats(20)

            logger.info(f"Profile for {func.__name__}:\n{stream.getvalue()}")

            return result

        finally:
            profiler.disable()

    return wrapper


# ============ 代码块性能分析 ============

@contextmanager
def profile_block(name: str = "Code Block"):
    """
    代码块性能分析上下文管理器

    用法:
        with profile_block("Database Query"):
            result = await db.execute(...)
    """
    start_time = time.time()
    logger.info(f"Starting {name}")

    try:
        yield
    finally:
        elapsed = time.time() - start_time
        logger.info(f"Finished {name} in {elapsed:.3f}s")


# ============ 内存分析 ============

def get_memory_usage() -> dict:
    """
    获取内存使用情况

    Returns:
        内存使用字典
    """
    try:
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
        }
    except ImportError:
        return {"error": "psutil not installed"}


def log_memory_usage(label: str = "Memory"):
    """记录内存使用"""
    usage = get_memory_usage()

    if "error" not in usage:
        logger.info(
            f"{label}: RSS={usage['rss_mb']:.2f}MB, "
            f"VMS={usage['vms_mb']:.2f}MB, "
            f"Percent={usage['percent']:.2f}%"
        )


# ============ 请求性能分析 ============

class RequestProfiler:
    """
    请求性能分析器

    分析每个请求的性能
    """

    def __init__(self, slow_threshold: float = 1.0):
        self.slow_threshold = slow_threshold
        self._stats = {}

    def record(self, endpoint: str, duration: float):
        """记录请求性能"""
        if endpoint not in self._stats:
            self._stats[endpoint] = {
                "count": 0,
                "total_time": 0,
                "min_time": float('inf'),
                "max_time": 0,
                "slow_count": 0,
            }

        stats = self._stats[endpoint]
        stats["count"] += 1
        stats["total_time"] += duration
        stats["min_time"] = min(stats["min_time"], duration)
        stats["max_time"] = max(stats["max_time"], duration)

        if duration > self.slow_threshold:
            stats["slow_count"] += 1
            logger.warning(
                f"Slow request: {endpoint} took {duration:.3f}s"
            )

    def get_stats(self, endpoint: str | None = None) -> dict:
        """获取统计信息"""
        if endpoint:
            stats = self._stats.get(endpoint, {})
            if stats:
                stats["avg_time"] = stats["total_time"] / stats["count"]
            return stats

        # 返回所有端点统计
        result = {}
        for ep, stats in self._stats.items():
            stats["avg_time"] = stats["total_time"] / stats["count"]
            result[ep] = stats

        return result


# ============ 数据库查询分析 ============

class QueryProfiler:
    """
    数据库查询分析器

    分析慢查询
    """

    def __init__(self, slow_threshold: float = 0.1):
        self.slow_threshold = slow_threshold
        self._queries = []

    def record_query(self, query: str, duration: float, params: tuple = None):
        """记录查询"""
        self._queries.append({
            "query": query,
            "duration": duration,
            "params": params,
            "timestamp": time.time(),
        })

        if duration > self.slow_threshold:
            logger.warning(
                f"Slow query ({duration:.3f}s): {query[:200]}"
            )

    def get_slow_queries(self, limit: int = 10) -> list:
        """获取慢查询"""
        slow = [
            q for q in self._queries
            if q["duration"] > self.slow_threshold
        ]

        return sorted(slow, key=lambda x: x["duration"], reverse=True)[:limit]

    def get_stats(self) -> dict:
        """获取统计"""
        if not self._queries:
            return {}

        durations = [q["duration"] for q in self._queries]

        return {
            "total_queries": len(self._queries),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "slow_queries": len(self.get_slow_queries()),
        }


# ============ API 端点 ============

router = APIRouter(prefix="/profiler", tags=["性能分析"])


@router.get("/memory")
async def get_memory():
    """获取内存使用"""
    return get_memory_usage()


@router.get("/stats")
async def get_profiler_stats():
    """获取性能统计"""
    # 这里需要全局的 profiler 实例
    return {
        "message": "Profiler stats endpoint",
    }


# ============ 性能分析脚本 ============

PROFILER_SCRIPT = """
#!/usr/bin/env python3
\"\"\"
性能分析脚本

用法:
    python -m scripts.profiler --endpoint /api/v1/tasks --iterations 100
\"\"\"

import argparse
import asyncio
import time
import statistics
import requests

async def benchmark_endpoint(base_url: str, endpoint: str, iterations: int):
    \"\"\"基准测试端点\"\"\"
    url = f"{base_url}{endpoint}"
    times = []

    print(f"Benchmarking {url} ({iterations} iterations)")

    for i in range(iterations):
        start = time.time()
        response = requests.get(url)
        elapsed = time.time() - start
        times.append(elapsed)

        if response.status_code != 200:
            print(f"Request {i} failed: {response.status_code}")

    # 统计
    print(f"\\nResults:")
    print(f"  Total: {sum(times):.3f}s")
    print(f"  Mean: {statistics.mean(times)*1000:.2f}ms")
    print(f"  Median: {statistics.median(times)*1000:.2f}ms")
    print(f"  Min: {min(times)*1000:.2f}ms")
    print(f"  Max: {max(times)*1000:.2f}ms")
    print(f"  StdDev: {statistics.stdev(times)*1000:.2f}ms")
    print(f"  QPS: {iterations/sum(times):.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Performance Profiler")
    parser.add_argument("--url", default="http://localhost:8080", help="Base URL")
    parser.add_argument("--endpoint", default="/health", help="Endpoint to test")
    parser.add_argument("--iterations", type=int, default=100, help="Number of iterations")

    args = parser.parse_args()

    asyncio.run(benchmark_endpoint(args.url, args.endpoint, args.iterations))
"""
