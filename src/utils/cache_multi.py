"""
IntelliTeam 多级缓存模块

提供 L1（内存）+ L2（Redis）多级缓存支持
"""

import json
from functools import wraps
from typing import Any

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class MemoryCache:
    """L1 内存缓存"""

    def __init__(self, max_size: int = 1000):
        self.cache: dict[str, Any] = {}
        self.max_size = max_size

    def get(self, key: str) -> Any | None:
        """获取缓存"""
        return self.cache.get(key)

    def set(self, key: str, value: Any) -> None:
        """设置缓存"""
        if len(self.cache) >= self.max_size:
            # 简单的 LRU：删除第一个
            self.cache.pop(next(iter(self.cache)), None)
        self.cache[key] = value

    def delete(self, key: str) -> bool:
        """删除缓存"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()


class MultiLevelCache:
    """
    多级缓存管理器

    L1: 内存缓存（快速）
    L2: Redis 缓存（持久）
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.l1_cache = MemoryCache(max_size=1000)
        self.redis_url = redis_url
        self._redis: redis.Redis | None = None
        self.default_ttl = 300  # 默认 5 分钟

    async def connect(self) -> bool:
        """连接 Redis"""
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
        获取缓存（L1 → L2）

        Args:
            key: 缓存键

        Returns:
            缓存值
        """
        # L1: 内存缓存
        value = self.l1_cache.get(key)
        if value is not None:
            return value

        # L2: Redis 缓存
        if self._redis:
            try:
                cached = await self._redis.get(key)
                if cached:
                    value = json.loads(cached)
                    # 回填 L1
                    self.l1_cache.set(key, value)
                    return value
            except Exception:
                pass

        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        设置缓存（L1 + L2）

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）

        Returns:
            是否成功
        """
        # L1: 内存缓存
        self.l1_cache.set(key, value)

        # L2: Redis 缓存
        if self._redis:
            try:
                expire = ttl or self.default_ttl
                serialized = json.dumps(value, ensure_ascii=False)
                await self._redis.setex(key, expire, serialized)
                return True
            except Exception:
                pass

        return True

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        # L1
        self.l1_cache.delete(key)

        # L2
        if self._redis:
            try:
                await self._redis.delete(key)
                return True
            except Exception:
                pass

        return False

    async def clear_pattern(self, pattern: str) -> int:
        """批量删除匹配模式的缓存"""
        count = 0

        if self._redis:
            try:
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
                    count = len(keys)
            except Exception:
                pass

        return count

    async def warm_cache(self, data: dict[str, Any], ttl: int | None = None):
        """
        缓存预热

        Args:
            data: 要预热的数据字典 {key: value}
            ttl: 过期时间
        """
        for key, value in data.items():
            await self.set(key, value, ttl)

    async def get_stats(self) -> dict:
        """获取缓存统计"""
        stats = {
            "l1_size": len(self.l1_cache.cache),
            "l1_max_size": self.l1_cache.max_size,
            "l2_connected": self._redis is not None,
        }

        if self._redis:
            try:
                info = await self._redis.info("memory")
                stats["l2_memory"] = info.get("used_memory_human", "0B")
            except Exception:
                pass

        return stats


# 全局缓存实例
_cache: MultiLevelCache | None = None


def get_cache(redis_url: str = "redis://localhost:6379/0") -> MultiLevelCache:
    """获取缓存管理器单例"""
    global _cache
    if _cache is None:
        _cache = MultiLevelCache(redis_url)
    return _cache


async def init_cache(redis_url: str = "redis://localhost:6379/0") -> bool:
    """初始化缓存连接"""
    cache = get_cache(redis_url)
    return await cache.connect()


def cache(ttl: int = 300, prefix: str = ""):
    """
    缓存装饰器

    Usage:
        @cache(ttl=300, prefix="tasks")
        async def get_task(task_id: int):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"

            # 尝试从缓存获取
            cache = get_cache()
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached

            # 执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            await cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator
