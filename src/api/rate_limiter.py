"""
IntelliTeam 高级速率限制模块

基于 Redis 的分布式速率限制
"""

import logging
import time
from datetime import datetime
from typing import Any

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    速率限制器

    支持多种限流算法
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/2"):
        self.redis_url = redis_url
        self._redis: redis.Redis | None = None

    async def connect(self) -> bool:
        """连接 Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis 不可用，速率限制将使用内存模式")
            return False

        try:
            self._redis = redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
            await self._redis.ping()
            logger.info("速率限制器已连接 Redis")
            return True
        except Exception as e:
            logger.error(f"速率限制器连接失败：{e}")
            return False

    async def is_allowed(
        self, key: str, max_requests: int = 60, window_seconds: int = 60
    ) -> dict[str, Any]:
        """
        检查请求是否允许（滑动窗口算法）

        Args:
            key: 限流键（如 user_id 或 IP）
            max_requests: 最大请求数
            window_seconds: 时间窗口（秒）

        Returns:
            限流结果
        """
        now = time.time()
        window_start = now - window_seconds

        if self._redis:
            # Redis 模式
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()

            current_requests = results[2]
            allowed = current_requests <= max_requests

            return {
                "allowed": allowed,
                "current_requests": current_requests,
                "max_requests": max_requests,
                "remaining": max(0, max_requests - current_requests),
                "reset_at": datetime.fromtimestamp(now + window_seconds).isoformat(),
            }
        else:
            # 内存模式（降级）
            return {
                "allowed": True,
                "current_requests": 0,
                "max_requests": max_requests,
                "remaining": max_requests,
                "reset_at": datetime.fromtimestamp(now + window_seconds).isoformat(),
            }

    async def is_allowed_token_bucket(
        self, key: str, max_tokens: int = 100, refill_rate: float = 10.0
    ) -> dict[str, Any]:
        """
        检查请求是否允许（令牌桶算法）

        Args:
            key: 限流键
            max_tokens: 桶容量
            refill_rate: 补充速率（个/秒）

        Returns:
            限流结果
        """
        now = time.time()

        if self._redis:
            # Redis 模式
            pipe = self._redis.pipeline()
            pipe.hget(key, "tokens")
            pipe.hget(key, "last_update")
            results = await pipe.execute()

            tokens = float(results[0] or max_tokens)
            last_update = float(results[1] or now)

            # 补充令牌
            time_passed = now - last_update
            tokens = min(max_tokens, tokens + time_passed * refill_rate)

            allowed = tokens >= 1
            if allowed:
                tokens -= 1

            # 更新状态
            pipe.hset(key, "tokens", tokens)
            pipe.hset(key, "last_update", now)
            pipe.expire(key, 3600)
            await pipe.execute()

            return {
                "allowed": allowed,
                "current_tokens": int(tokens),
                "max_tokens": max_tokens,
                "remaining": int(tokens),
                "reset_at": datetime.fromtimestamp(now + 3600).isoformat(),
            }
        else:
            # 内存模式
            return {
                "allowed": True,
                "current_tokens": max_tokens,
                "max_tokens": max_tokens,
                "remaining": max_tokens,
                "reset_at": datetime.fromtimestamp(now + 3600).isoformat(),
            }

    async def get_usage(self, key: str) -> dict[str, Any]:
        """
        获取使用情况

        Args:
            key: 限流键

        Returns:
            使用情况
        """
        if self._redis:
            usage = await self._redis.hgetall(key)
            return {"key": key, "usage": usage, "timestamp": datetime.now().isoformat()}
        else:
            return {"key": key, "usage": {}, "timestamp": datetime.now().isoformat()}

    async def reset(self, key: str) -> bool:
        """
        重置限流状态

        Args:
            key: 限流键

        Returns:
            是否成功
        """
        if self._redis:
            await self._redis.delete(key)
            return True
        return False


# 全局速率限制器实例
_rate_limiter: RateLimiter | None = None


def get_rate_limiter(redis_url: str = "redis://localhost:6379/2") -> RateLimiter:
    """获取速率限制器单例"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(redis_url)
    return _rate_limiter


async def init_rate_limiter(redis_url: str = "redis://localhost:6379/2") -> bool:
    """初始化速率限制器"""
    limiter = get_rate_limiter(redis_url)
    return await limiter.connect()
