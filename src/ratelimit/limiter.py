"""
API 限流完善

多层级限流：全局、用户、IP、端点
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitScope(str, Enum):
    """限流范围"""
    GLOBAL = "global"
    USER = "user"
    IP = "ip"
    ENDPOINT = "endpoint"


@dataclass
class RateLimitConfig:
    """限流配置"""
    scope: RateLimitScope
    requests: int
    window_seconds: int
    burst: int = 0  # 突发请求数
    
    def __post_init__(self):
        if self.burst == 0:
            self.burst = self.requests


@dataclass
class RateLimitState:
    """限流状态"""
    count: int = 0
    window_start: float = field(default_factory=time.time)
    burst_remaining: int = 0
    
    def __post_init__(self):
        self.burst_remaining = self.count


class TokenBucket:
    """
    令牌桶限流器
    
    支持突发请求
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = capacity
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """消耗令牌"""
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False
    
    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self.last_refill
        
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def get_tokens(self) -> float:
        """获取当前令牌数"""
        self._refill()
        return self.tokens


class SlidingWindowCounter:
    """
    滑动窗口计数器
    
    更精确的限流
    """
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: List[float] = []
    
    def is_allowed(self) -> bool:
        """检查是否允许请求"""
        now = time.time()
        window_start = now - self.window_seconds
        
        # 清理过期请求
        self.requests = [t for t in self.requests if t > window_start]
        
        # 检查是否超限
        if len(self.requests) >= self.max_requests:
            return False
        
        # 记录请求
        self.requests.append(now)
        return True
    
    def get_remaining(self) -> int:
        """获取剩余请求数"""
        now = time.time()
        window_start = now - self.window_seconds
        
        current_requests = len([t for t in self.requests if t > window_start])
        return max(0, self.max_requests - current_requests)
    
    def get_reset_time(self) -> float:
        """获取重置时间"""
        if not self.requests:
            return 0
        
        return self.requests[0] + self.window_seconds - time.time()


class RateLimiter:
    """
    多层级限流器
    
    功能:
    - 全局限流
    - 用户限流
    - IP 限流
    - 端点限流
    - 令牌桶算法
    - 滑动窗口
    """
    
    def __init__(self):
        self.configs: Dict[str, RateLimitConfig] = {}
        self.global_state: Dict[str, RateLimitState] = {}
        self.user_buckets: Dict[str, TokenBucket] = {}
        self.ip_counters: Dict[str, SlidingWindowCounter] = {}
        self.endpoint_buckets: Dict[str, TokenBucket] = {}
        
        logger.info("RateLimiter initialized")
    
    def add_config(self, name: str, config: RateLimitConfig):
        """添加限流配置"""
        self.configs[name] = config
        logger.info(f"Rate limit config added: {name} ({config.requests}/{config.window_seconds}s)")
    
    def is_allowed(
        self,
        identifier: str,
        scope: RateLimitScope,
        endpoint: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        检查请求是否允许
        
        Args:
            identifier: 标识符（用户 ID 或 IP）
            scope: 限流范围
            endpoint: 端点路径
        
        Returns:
            (是否允许，限流信息)
        """
        # 检查全局限流
        if not self._check_global():
            return False, self._get_limit_info("global")
        
        # 检查用户/IP 限流
        if scope in [RateLimitScope.USER, RateLimitScope.IP]:
            config_name = f"{scope.value}:{identifier}"
            if not self._check_identifier(config_name, identifier):
                return False, self._get_limit_info(config_name)
        
        # 检查端点限流
        if endpoint and scope == RateLimitScope.ENDPOINT:
            config_name = f"endpoint:{endpoint}"
            if not self._check_endpoint(config_name, endpoint):
                return False, self._get_limit_info(config_name)
        
        return True, {}
    
    def _check_global(self) -> bool:
        """检查全局限流"""
        config = self.configs.get("global")
        if not config:
            return True
        
        state = self.global_state.setdefault("global", RateLimitState())
        
        now = time.time()
        window_elapsed = now - state.window_start
        
        # 窗口过期，重置
        if window_elapsed >= config.window_seconds:
            state.count = 0
            state.window_start = now
            state.burst_remaining = config.burst
        
        # 检查限流
        if state.count >= config.requests:
            return False
        
        state.count += 1
        return True
    
    def _check_identifier(self, config_name: str, identifier: str) -> bool:
        """检查用户/IP 限流"""
        config = self.configs.get(config_name)
        if not config:
            return True
        
        # 使用滑动窗口
        if identifier not in self.ip_counters:
            self.ip_counters[identifier] = SlidingWindowCounter(
                config.requests,
                config.window_seconds,
            )
        
        counter = self.ip_counters[identifier]
        return counter.is_allowed()
    
    def _check_endpoint(self, config_name: str, endpoint: str) -> bool:
        """检查端点限流"""
        config = self.configs.get(config_name)
        if not config:
            return True
        
        # 使用令牌桶
        if endpoint not in self.endpoint_buckets:
            refill_rate = config.requests / config.window_seconds
            self.endpoint_buckets[endpoint] = TokenBucket(
                config.burst,
                refill_rate,
            )
        
        bucket = self.endpoint_buckets[endpoint]
        return bucket.consume()
    
    def _get_limit_info(self, config_name: str) -> Dict[str, Any]:
        """获取限流信息"""
        config = self.configs.get(config_name)
        if not config:
            return {}
        
        return {
            "limit": config.requests,
            "window": config.window_seconds,
            "burst": config.burst,
            "retry_after": config.window_seconds,
        }
    
    def get_headers(self, config_name: str) -> Dict[str, str]:
        """获取限流响应头"""
        config = self.configs.get(config_name)
        if not config:
            return {}
        
        if config_name.startswith("ip:") or config_name.startswith("user:"):
            identifier = config_name.split(":", 1)[1]
            counter = self.ip_counters.get(identifier)
            
            if counter:
                return {
                    "X-RateLimit-Limit": str(config.requests),
                    "X-RateLimit-Remaining": str(counter.get_remaining()),
                    "X-RateLimit-Reset": str(int(counter.get_reset_time())),
                }
        
        return {
            "X-RateLimit-Limit": str(config.requests),
            "X-RateLimit-Window": str(config.window_seconds),
        }


# ============ 中间件 ============

class RateLimitMiddleware:
    """限流中间件"""
    
    def __init__(self, app, limiter: RateLimiter):
        self.app = app
        self.limiter = limiter
    
    async def __call__(self, scope, receive, send):
        from fastapi import Request
        from fastapi.responses import JSONResponse
        
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        request = Request(scope, receive)
        
        # 获取标识符
        user_id = request.headers.get("X-User-ID")
        client_ip = request.client.host
        endpoint = request.url.path
        
        # 检查限流
        identifier = user_id or client_ip
        allowed, info = self.limiter.is_allowed(
            identifier,
            RateLimitScope.USER if user_id else RateLimitScope.IP,
            endpoint,
        )
        
        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={
                    "Retry-After": str(info.get("retry_after", 60)),
                },
            )
            return await response(scope, receive, send)
        
        return await self.app(scope, receive, send)


# ============ 装饰器 ============

def rate_limit(
    requests: int,
    window_seconds: int,
    scope: RateLimitScope = RateLimitScope.ENDPOINT,
):
    """限流装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 这里可以添加具体的限流逻辑
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============ 全局限流器 ============

_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """获取限流器"""
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
        
        # 默认配置
        _limiter.add_config("global", RateLimitConfig(
            scope=RateLimitScope.GLOBAL,
            requests=10000,
            window_seconds=60,
        ))
        
        _limiter.add_config("user", RateLimitConfig(
            scope=RateLimitScope.USER,
            requests=100,
            window_seconds=60,
            burst=150,
        ))
        
        _limiter.add_config("ip", RateLimitConfig(
            scope=RateLimitScope.IP,
            requests=60,
            window_seconds=60,
        ))
    
    return _limiter


def init_rate_limiter(**kwargs) -> RateLimiter:
    """初始化限流器"""
    global _limiter
    _limiter = RateLimiter()
    logger.info("Rate limiter initialized")
    return _limiter
