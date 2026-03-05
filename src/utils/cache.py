"""
IntelliTeam 缓存模块

提供 Redis 缓存支持
"""

import json
from typing import Any

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class CacheManager:
    """
    缓存管理器

    提供统一的缓存操作接口
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis: redis.Redis | None = None

    async def connect(self) -> bool:
        """连接到 Redis"""
        if not REDIS_AVAILABLE:
            return False

        try:
            self._redis = redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
            await self._redis.ping()
            return True
        except Exception:
            return False

    async def disconnect(self):
        """断开连接"""
        if self._redis:
            await self._redis.close()

    async def get(self, key: str) -> Any | None:
        """
        获取缓存

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回 None
        """
        if not self._redis:
            return None

        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception:
            return None

    async def set(self, key: str, value: Any, expire_seconds: int | None = None) -> bool:
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值
            expire_seconds: 过期时间（秒）

        Returns:
            是否成功
        """
        if not self._redis:
            return False

        try:
            serialized = json.dumps(value, ensure_ascii=False)
            if expire_seconds:
                await self._redis.setex(key, expire_seconds, serialized)
            else:
                await self._redis.set(key, serialized)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self._redis:
            return False

        try:
            await self._redis.delete(key)
            return True
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        if not self._redis:
            return False

        try:
            return await self._redis.exists(key) > 0
        except Exception:
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        批量删除匹配模式的缓存

        Args:
            pattern: 匹配模式（支持通配符）

        Returns:
            删除的数量
        """
        if not self._redis:
            return 0

        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
                return len(keys)
            return 0
        except Exception:
            return 0

    async def get_stats(self) -> dict:
        """获取缓存统计信息"""
        if not self._redis:
            return {}

        try:
            info = await self._redis.info("memory")
            return {
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "connected": True,
            }
        except Exception:
            return {}


# 全局缓存实例
_cache: CacheManager | None = None


def get_cache(redis_url: str = "redis://localhost:6379/0") -> CacheManager:
    """获取缓存管理器单例"""
    global _cache
    if _cache is None:
        _cache = CacheManager(redis_url)
    return _cache


async def init_cache(redis_url: str = "redis://localhost:6379/0") -> bool:
    """初始化缓存连接"""
    cache = get_cache(redis_url)
    return await cache.connect()
