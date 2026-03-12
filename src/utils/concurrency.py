"""
并发控制模块

使用信号量、限流器等控制并发，防止资源耗尽

版本：3.0.0
更新时间：2026-03-12
修复问题：
- 修复 release 方法中同步调用 asyncio.create_task() 的问题
- 添加线程锁保证统计信息更新的原子性
- 完全移除同步/异步混用的问题
- 提供线程安全的统计信息更新机制
"""

import asyncio
import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """限流配置"""
    calls: int = 100  # 允许调用次数
    period: float = 60.0  # 时间窗口（秒）


class RateLimiter:
    """
    速率限制器

    功能:
    - 令牌桶算法
    - 滑动窗口
    - 支持多键值（如多用户）
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._requests: dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def acquire(self, key: str = "default") -> bool:
        """
        获取许可

        Args:
            key: 限流键（如用户 ID、IP 等）

        Returns:
            是否允许通过
        """
        async with self._lock:
            now = time.time()
            window_start = now - self.config.period

            # 清理过期请求
            self._requests[key] = [
                req_time for req_time in self._requests[key]
                if req_time > window_start
            ]

            # 检查是否超限
            if len(self._requests[key]) >= self.config.calls:
                logger.warning(f"Rate limit exceeded for {key}")
                return False

            # 记录请求
            self._requests[key].append(now)
            return True

    async def wait_and_acquire(self, key: str = "default") -> None:
        """等待并获取许可"""
        while not await self.acquire(key):
            # 计算等待时间
            async with self._lock:
                if self._requests[key]:
                    oldest = min(self._requests[key])
                    wait_time = oldest + self.config.period - time.time()
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                else:
                    await asyncio.sleep(0.1)


class SemaphoreController:
    """
    信号量控制器

    功能:
    - 限制并发数量
    - 支持多层级信号量
    - 超时控制

    使用方式：
        controller = SemaphoreController(max_concurrent=10)

        # 异步获取和释放
        if await controller.acquire():
            try:
                # 执行任务
                ...
            finally:
                await controller.release_async()

        # 或使用上下文管理器
        async with controller.semaphore_context():
            # 执行任务
            ...
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        timeout: float | None = None,
    ):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._timeout = timeout
        self._active = 0
        self._total_acquired = 0
        self._total_released = 0
        self._async_lock = asyncio.Lock()  # 用于异步操作的锁
        self._thread_lock = threading.Lock()  # 用于保护统计信息的线程锁

    async def acquire(self, timeout: float | None = None) -> bool:
        """
        获取信号量（异步）

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否成功获取
        """
        try:
            acquired = await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=timeout or self._timeout,
            )

            if acquired:
                # 使用线程锁保证统计信息更新的原子性
                with self._thread_lock:
                    self._active += 1
                    self._total_acquired += 1
                logger.debug(f"Semaphore acquired, active: {self._active}")

            return acquired

        except TimeoutError:
            logger.warning("Semaphore acquire timeout")
            return False

    def release(self) -> None:
        """
        释放信号量（同步版本）

        注意：此方法使用线程锁保护统计信息更新，确保线程安全。
        """
        self._semaphore.release()

        # 使用线程锁保证统计信息更新的原子性
        with self._thread_lock:
            self._active -= 1
            self._total_released += 1

        logger.debug(f"Semaphore released, active: {self._active}")

    async def release_async(self) -> None:
        """
        释放信号量（异步版本）

        此方法也使用线程锁保护统计信息更新，与同步版本保持一致。
        """
        self._semaphore.release()

        # 使用线程锁保证统计信息更新的原子性
        with self._thread_lock:
            self._active -= 1
            self._total_released += 1

        logger.debug(f"Semaphore released, active: {self._active}")

    async def __aenter__(self) -> "SemaphoreController":
        """异步上下文管理器入口"""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器退出"""
        await self.release_async()

    def semaphore_context(self):
        """
        获取信号量上下文管理器

        用法：
            async with controller.semaphore_context():
                # 执行任务
                ...
        """
        return _SemaphoreContext(self)

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "active": self._active,
            "total_acquired": self._total_acquired,
            "total_released": self._total_released,
            "max_concurrent": self._semaphore._value,
        }


class _SemaphoreContext:
    """信号量上下文管理器（内部类）"""

    def __init__(self, controller: SemaphoreController):
        self._controller = controller

    async def __aenter__(self) -> SemaphoreController:
        await self._controller.acquire()
        return self._controller

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._controller.release_async()


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5  # 失败次数阈值
    recovery_timeout: float = 30.0  # 恢复超时（秒）
    half_open_max_calls: int = 3  # 半开状态最大调用数


class CircuitBreakerState:
    """熔断器状态"""
    CLOSED = "closed"  # 正常
    OPEN = "open"  # 熔断
    HALF_OPEN = "half_open"  # 半开（测试恢复）


class CircuitBreaker:
    """
    熔断器

    功能:
    - 自动熔断
    - 半开测试
    - 自动恢复
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器调用函数

        Args:
            func: 要调用的函数（异步）
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpen: 熔断器打开时
        """
        async with self._lock:
            # 检查是否应该尝试恢复
            if self._state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker entering half-open state")
                else:
                    raise CircuitBreakerOpen("Circuit breaker is open")

        try:
            # 调用函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 调用成功
            await self._on_success()
            return result

        except Exception:
            # 调用失败
            await self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置"""
        if self._last_failure_time is None:
            return True

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.config.recovery_timeout

    async def _on_success(self):
        """成功回调"""
        async with self._lock:
            self._failure_count = 0

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.half_open_max_calls:
                    self._state = CircuitBreakerState.CLOSED
                    self._success_count = 0
                    logger.info("Circuit breaker closed (recovered)")

    async def _on_failure(self):
        """失败回调"""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.OPEN
                logger.warning("Circuit breaker opened (half-open failed)")
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker opened (failures={self._failure_count})")

    def get_state(self) -> dict:
        """获取状态"""
        return {
            "state": self._state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
        }


class CircuitBreakerOpen(Exception):
    """熔断器打开异常"""
    pass


# 装饰器：并发控制
def concurrent_limit(max_concurrent: int, timeout: float | None = None):
    """
    装饰器：限制并发数

    用法:
        @concurrent_limit(max_concurrent=10)
        async def process_task(task):
            ...
    """
    controller = SemaphoreController(max_concurrent=max_concurrent, timeout=timeout)

    def decorator(func):
        async def wrapper(*args, **kwargs):
            if await controller.acquire():
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                finally:
                    await controller.release_async()
            else:
                raise TimeoutError(f"Concurrent limit exceeded for {func.__name__}")

        return wrapper
    return decorator


# 装饰器：速率限制
def rate_limit(calls: int = 100, period: float = 60.0):
    """
    装饰器：速率限制

    用法:
        @rate_limit(calls=10, period=60)  # 每分钟 10 次
        async def api_call():
            ...
    """
    limiter = RateLimiter(RateLimitConfig(calls=calls, period=period))

    def decorator(func):
        async def wrapper(*args, **kwargs):
            await limiter.wait_and_acquire()

            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper
    return decorator


# 装饰器：熔断器
def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
):
    """
    装饰器：熔断器

    用法:
        @circuit_breaker(failure_threshold=5)
        async def external_api_call():
            ...
    """
    breaker = CircuitBreaker(
        CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
    )

    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)

        return wrapper
    return decorator


# 全局并发控制器（线程安全）
_global_controllers: dict[str, SemaphoreController] = {}
_global_controllers_lock = threading.Lock()


def get_concurrent_controller(name: str, max_concurrent: int = 10) -> SemaphoreController:
    """
    获取并发控制器（线程安全）

    Args:
        name: 控制器名称
        max_concurrent: 最大并发数

    Returns:
        SemaphoreController 实例
    """
    # 使用双重检查锁定模式，提高性能
    if name not in _global_controllers:
        with _global_controllers_lock:
            # 再次检查，防止在获取锁期间其他线程已创建
            if name not in _global_controllers:
                _global_controllers[name] = SemaphoreController(max_concurrent=max_concurrent)
                logger.debug(f"Created new concurrent controller: {name} (max_concurrent={max_concurrent})")
    return _global_controllers[name]
