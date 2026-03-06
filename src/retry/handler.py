"""
智能重试机制

指数退避、抖动、电路 breaker 集成
"""

import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class RetryStrategy(str, Enum):
    """重试策略"""
    FIXED = "fixed"  # 固定间隔
    LINEAR = "linear"  # 线性退避
    EXPONENTIAL = "exponential"  # 指数退避
    EXPONENTIAL_WITH_JITTER = "exponential_with_jitter"  # 指数退避 + 抖动


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0  # 秒
    max_delay: float = 60.0  # 秒
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_WITH_JITTER
    jitter: float = 0.1  # 抖动比例 (0-1)
    retryable_exceptions: List[Type[Exception]] = field(default_factory=lambda: [Exception])
    retryable_status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])


@dataclass
class RetryState:
    """重试状态"""
    attempt: int = 0
    last_error: Optional[Exception] = None
    last_attempt_time: Optional[datetime] = None
    total_time: float = 0.0


class RetryHandler:
    """
    重试处理器
    
    功能:
    - 多种重试策略
    - 指数退避
    - 随机抖动
    - 电路 breaker 集成
    - 重试统计
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._stats = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "total_attempts": 0,
        }
        
        logger.info(f"RetryHandler initialized (max_retries={self.config.max_retries})")
    
    def calculate_delay(self, attempt: int) -> float:
        """计算延迟时间"""
        if self.config.strategy == RetryStrategy.FIXED:
            delay = self.config.base_delay
        
        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = self.config.base_delay * attempt
        
        elif self.config.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.config.base_delay * (2 ** (attempt - 1))
        
        elif self.config.strategy == RetryStrategy.EXPONENTIAL_WITH_JITTER:
            base_delay = self.config.base_delay * (2 ** (attempt - 1))
            jitter_range = base_delay * self.config.jitter
            jitter = random.uniform(-jitter_range, jitter_range)
            delay = base_delay + jitter
        
        else:
            delay = self.config.base_delay
        
        # 限制最大延迟
        return min(delay, self.config.max_delay)
    
    def should_retry(self, attempt: int, exception: Optional[Exception] = None) -> bool:
        """判断是否应该重试"""
        if attempt >= self.config.max_retries:
            return False
        
        if exception is None:
            return True
        
        # 检查是否是可重试的异常
        for exc_type in self.config.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True
        
        return False
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """
        带重试执行
        
        Args:
            func: 要执行的函数（异步）
            *args: 位置参数
            **kwargs: 关键字参数
        
        Returns:
            函数执行结果
        
        Raises:
            最后一次尝试的异常
        """
        state = RetryState()
        start_time = time.time()
        
        for attempt in range(1, self.config.max_retries + 1):
            state.attempt = attempt
            state.last_attempt_time = datetime.utcnow()
            self._stats["total_attempts"] += 1
            
            try:
                # 执行函数
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # 成功
                if attempt > 1:
                    self._stats["successful_retries"] += 1
                    logger.info(f"Retry succeeded after {attempt} attempts")
                
                return result
                
            except Exception as e:
                state.last_error = e
                
                # 检查是否应该重试
                if not self.should_retry(attempt, e):
                    self._stats["failed_retries"] += 1
                    logger.error(f"Retry failed: {e}")
                    raise
                
                # 计算延迟
                delay = self.calculate_delay(attempt)
                
                logger.warning(
                    f"Attempt {attempt} failed: {e}. Retrying in {delay:.2f}s..."
                )
                
                # 等待
                await asyncio.sleep(delay)
                self._stats["total_retries"] += 1
        
        # 所有重试都失败
        self._stats["failed_retries"] += 1
        state.total_time = time.time() - start_time
        
        if state.last_error:
            raise state.last_error
        
        raise RuntimeError("All retry attempts failed")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            **self._stats,
            "success_rate": (
                self._stats["successful_retries"] / self._stats["total_retries"] * 100
                if self._stats["total_retries"] > 0 else 0
            ),
        }


# ============ 装饰器 ============

def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_WITH_JITTER,
    retryable_exceptions: Optional[List[Type[Exception]]] = None,
):
    """
    重试装饰器
    
    用法:
        @with_retry(max_retries=3, strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER)
        async def call_external_api():
            ...
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        strategy=strategy,
        retryable_exceptions=retryable_exceptions or [Exception],
    )
    
    handler = RetryHandler(config)
    
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            return await handler.execute_with_retry(func, *args, **kwargs)
        
        return wrapper
    return decorator


# ============ HTTP 重试 ============

class HTTPRetryHandler(RetryHandler):
    """HTTP 请求重试处理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        if config is None:
            config = RetryConfig(
                max_retries=3,
                base_delay=1.0,
                strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER,
                retryable_exceptions=[
                    ConnectionError,
                    TimeoutError,
                ],
                retryable_status_codes=[429, 500, 502, 503, 504],
            )
        
        super().__init__(config)
    
    async def request(
        self,
        method: str,
        url: str,
        session: Any,
        **kwargs,
    ) -> Any:
        """
        带重试的 HTTP 请求
        
        Args:
            method: HTTP 方法
            url: URL
            session: aiohttp session
            **kwargs: 其他参数
        
        Returns:
            响应对象
        """
        async def make_request():
            async with session.request(method, url, **kwargs) as response:
                # 检查状态码
                if response.status in self.config.retryable_status_codes:
                    raise HTTPRetryError(f"HTTP {response.status}", response.status)
                
                return response
        
        return await self.execute_with_retry(make_request)


class HTTPRetryError(Exception):
    """HTTP 重试错误"""
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


# ============ 数据库重试 ============

class DatabaseRetryHandler(RetryHandler):
    """数据库操作重试处理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        if config is None:
            config = RetryConfig(
                max_retries=3,
                base_delay=0.5,
                max_delay=10.0,
                strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER,
                retryable_exceptions=[
                    ConnectionError,
                    TimeoutError,
                ],
            )
        
        super().__init__(config)
    
    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """带重试执行数据库操作"""
        return await self.execute_with_retry(func, *args, **kwargs)


# ============ 全局限重试器 ============

_handler: Optional[RetryHandler] = None


def get_retry_handler() -> RetryHandler:
    """获取重试处理器"""
    global _handler
    if _handler is None:
        _handler = RetryHandler()
    return _handler


def init_retry_handler(**kwargs) -> RetryHandler:
    """初始化重试处理器"""
    global _handler
    _handler = RetryHandler(**kwargs)
    logger.info("Retry handler initialized")
    return _handler
