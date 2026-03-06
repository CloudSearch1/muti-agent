"""
性能基准测试模块

测试系统各项性能指标
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean, median, stdev
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    median_time: float
    std_dev: float
    qps: float  # 每秒查询数
    timestamps: List[float] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_seconds": self.total_time,
            "avg_time_ms": self.avg_time * 1000,
            "min_time_ms": self.min_time * 1000,
            "max_time_ms": self.max_time * 1000,
            "median_time_ms": self.median_time * 1000,
            "std_dev_ms": self.std_dev * 1000,
            "qps": self.qps,
            "timestamp": datetime.now().isoformat(),
        }


class BenchmarkRunner:
    """
    基准测试运行器
    
    功能:
    - 多次迭代测试
    - 统计分析
    - 结果导出
    """
    
    def __init__(self, warmup_iterations: int = 10):
        self.warmup_iterations = warmup_iterations
        self.results: List[BenchmarkResult] = []
    
    async def run(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        *args,
        **kwargs,
    ) -> BenchmarkResult:
        """
        运行基准测试
        
        Args:
            name: 测试名称
            func: 测试函数（异步）
            iterations: 迭代次数
            *args: 位置参数
            **kwargs: 关键字参数
        
        Returns:
            基准测试结果
        """
        logger.info(f"Starting benchmark: {name} ({iterations} iterations)")
        
        # 预热
        if self.warmup_iterations > 0:
            logger.debug(f"Warming up with {self.warmup_iterations} iterations")
            for _ in range(self.warmup_iterations):
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
        
        # 正式测试
        times = []
        start_total = time.time()
        
        for i in range(iterations):
            start = time.time()
            
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
            
            elapsed = time.time() - start
            times.append(elapsed)
        
        total_time = time.time() - start_total
        
        # 统计分析
        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            avg_time=mean(times),
            min_time=min(times),
            max_time=max(times),
            median_time=median(times),
            std_dev=stdev(times) if len(times) > 1 else 0,
            qps=iterations / total_time,
            timestamps=times,
        )
        
        self.results.append(result)
        
        logger.info(
            f"Benchmark complete: {name}",
            extra={
                "avg_ms": result.avg_time * 1000,
                "median_ms": result.median_time * 1000,
                "qps": result.qps,
            },
        )
        
        return result
    
    def get_summary(self) -> dict:
        """获取测试摘要"""
        return {
            "total_benchmarks": len(self.results),
            "results": [r.to_dict() for r in self.results],
            "timestamp": datetime.now().isoformat(),
        }
    
    def export_json(self, file_path: str):
        """导出结果为 JSON"""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.get_summary(), f, indent=2, ensure_ascii=False)
        logger.info(f"Benchmark results exported to {file_path}")
    
    def export_markdown(self, file_path: str):
        """导出结果为 Markdown"""
        md = "# 性能基准测试报告\n\n"
        md += f"_生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n"
        
        for result in self.results:
            md += f"## {result.name}\n\n"
            md += f"- **迭代次数**: {result.iterations}\n"
            md += f"- **总耗时**: {result.total_time:.2f} 秒\n"
            md += f"- **平均耗时**: {result.avg_time * 1000:.2f} ms\n"
            md += f"- **中位数**: {result.median_time * 1000:.2f} ms\n"
            md += f"- **最小值**: {result.min_time * 1000:.2f} ms\n"
            md += f"- **最大值**: {result.max_time * 1000:.2f} ms\n"
            md += f"- **标准差**: {result.std_dev * 1000:.2f} ms\n"
            md += f"- **QPS**: {result.qps:.2f}\n\n"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md)
        
        logger.info(f"Benchmark results exported to {file_path}")


# ============ 预定义基准测试 ============

async def benchmark_llm_call(runner: BenchmarkRunner, llm, prompt: str = "test"):
    """LLM 调用基准测试"""
    async def llm_call():
        await llm.generate(prompt, max_tokens=10)
    
    return await runner.run("LLM Call", llm_call, iterations=50)


async def benchmark_db_query(runner: BenchmarkRunner, db_session):
    """数据库查询基准测试"""
    from sqlalchemy import select, func
    from ..db.models import TaskModel
    
    async def db_query():
        result = await db_session.execute(select(func.count(TaskModel.id)))
        return result.scalar()
    
    return await runner.run("Database Query", db_query, iterations=100)


async def benchmark_cache_operation(runner: BenchmarkRunner, cache):
    """缓存操作基准测试"""
    async def cache_set_get():
        await cache.set("test_key", "test_value")
        await cache.get("test_key")
    
    return await runner.run("Cache Operation", cache_set_get, iterations=200)


async def benchmark_agent_execution(runner: BenchmarkRunner, agent, task):
    """Agent 执行基准测试"""
    async def execute():
        await agent.execute(task)
    
    return await runner.run("Agent Execution", execute, iterations=20)


# ============ 负载测试 ============

@dataclass
class LoadTestResult:
    """负载测试结果"""
    concurrent_users: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time: float
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    qps: float
    error_rate: float
    
    def to_dict(self) -> dict:
        return {
            "concurrent_users": self.concurrent_users,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_time_seconds": self.total_time,
            "avg_response_time_ms": self.avg_response_time * 1000,
            "p95_response_time_ms": self.p95_response_time * 1000,
            "p99_response_time_ms": self.p99_response_time * 1000,
            "qps": self.qps,
            "error_rate_percent": self.error_rate * 100,
        }


async def run_load_test(
    func: Callable,
    concurrent_users: int = 10,
    requests_per_user: int = 10,
) -> LoadTestResult:
    """
    运行负载测试
    
    Args:
        func: 测试函数（异步）
        concurrent_users: 并发用户数
        requests_per_user: 每个用户请求数
    
    Returns:
        负载测试结果
    """
    total_requests = concurrent_users * requests_per_user
    successful = 0
    failed = 0
    response_times = []
    
    async def user_session(user_id: int):
        nonlocal successful, failed
        
        for i in range(requests_per_user):
            start = time.time()
            try:
                if asyncio.iscoroutinefunction(func):
                    await func()
                else:
                    func()
                successful += 1
            except Exception as e:
                failed += 1
                logger.error(f"User {user_id} request {i} failed: {e}")
            finally:
                elapsed = time.time() - start
                response_times.append(elapsed)
    
    start_time = time.time()
    
    # 创建并发用户
    tasks = [user_session(i) for i in range(concurrent_users)]
    await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    
    # 计算百分位数
    sorted_times = sorted(response_times)
    p95_idx = int(len(sorted_times) * 0.95)
    p99_idx = int(len(sorted_times) * 0.99)
    
    result = LoadTestResult(
        concurrent_users=concurrent_users,
        total_requests=total_requests,
        successful_requests=successful,
        failed_requests=failed,
        total_time=total_time,
        avg_response_time=mean(response_times) if response_times else 0,
        p95_response_time=sorted_times[p95_idx] if p95_idx < len(sorted_times) else 0,
        p99_response_time=sorted_times[p99_idx] if p99_idx < len(sorted_times) else 0,
        qps=successful / total_time,
        error_rate=failed / total_requests if total_requests > 0 else 0,
    )
    
    logger.info(
        f"Load test complete: {concurrent_users} users, {successful}/{total_requests} success",
        extra={
            "qps": result.qps,
            "p95_ms": result.p95_response_time * 1000,
            "error_rate": result.error_rate * 100,
        },
    )
    
    return result


# ============ 命令行接口 ============

async def run_all_benchmarks():
    """运行所有基准测试"""
    runner = BenchmarkRunner(warmup_iterations=10)
    
    print("=" * 60)
    print("  Multi-Agent 性能基准测试")
    print("=" * 60)
    print()
    
    # 这里需要根据实际情况初始化组件
    # 示例：
    # llm = get_llm()
    # await benchmark_llm_call(runner, llm)
    
    print("基准测试完成！")
    print()
    
    # 导出结果
    runner.export_markdown("benchmark_report.md")
    runner.export_json("benchmark_results.json")
    
    return runner.get_summary()


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())
