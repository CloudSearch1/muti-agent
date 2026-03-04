"""
IntelliTeam 缓存管理模块

统一的缓存管理接口
"""

from typing import Optional, Any, Dict
import logging

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CacheManager:
    """
    缓存管理器
    
    统一的缓存管理接口
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/2"):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """连接 Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis 不可用，缓存将使用内存模式")
            self._memory_cache: Dict[str, Any] = {}
            return True
        
        try:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis.ping()
            self._connected = True
            logger.info("缓存已连接 Redis")
            return True
        except Exception as e:
            logger.warning(f"缓存连接失败，使用内存模式：{e}")
            self._memory_cache: Dict[str, Any] = {}
            return True
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if self._redis and self._connected:
            try:
                return await self._redis.get(key)
            except Exception as e:
                logger.error(f"获取缓存失败：{e}")
                return None
        else:
            return self._memory_cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存"""
        if self._redis and self._connected:
            try:
                await self._redis.setex(key, ttl, value)
                return True
            except Exception as e:
                logger.error(f"设置缓存失败：{e}")
                return False
        else:
            self._memory_cache[key] = value
            return True
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if self._redis and self._connected:
            try:
                await self._redis.delete(key)
                return True
            except Exception as e:
                logger.error(f"删除缓存失败：{e}")
                return False
        else:
            self._memory_cache.pop(key, None)
            return True
    
    async def clear(self) -> bool:
        """清空缓存"""
        if self._redis and self._connected:
            try:
                await self._redis.flushdb()
                return True
            except Exception as e:
                logger.error(f"清空缓存失败：{e}")
                return False
        else:
            self._memory_cache.clear()
            return True
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected or hasattr(self, '_memory_cache')


# 全局缓存实例
_cache_manager: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """获取缓存管理器单例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


async def init_cache(redis_url: str = "redis://localhost:6379/2") -> bool:
    """初始化缓存"""
    cache = get_cache()
    cache.redis_url = redis_url
    return await cache.connect()


__all__ = [
    "CacheManager",
    "get_cache",
    "init_cache"
]