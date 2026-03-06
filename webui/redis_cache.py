"""
Redis 缓存实现

生产环境缓存后端，支持多实例共享
"""

import json
import logging
from datetime import timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis-py not installed, Redis cache unavailable")


class RedisCache:
    """
    Redis 缓存实现
    
    功能:
    - 支持多实例共享缓存
    - 自动过期
    - 缓存统计
    - 支持 JSON 序列化
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 300,  # 5 分钟
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.default_ttl = default_ttl
        self._redis: Optional[redis.Redis] = None
        self._hits = 0
        self._misses = 0
        
        if not REDIS_AVAILABLE:
            logger.error("Redis not available: redis-py not installed")
    
    async def connect(self):
        """连接到 Redis"""
        if not REDIS_AVAILABLE:
            return False
        
        try:
            self._redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info(f"Redis connected: {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self._redis:
            await self._redis.close()
            logger.info("Redis disconnected")
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self._redis:
            return None
        
        try:
            data = await self._redis.get(key)
            if data:
                self._hits += 1
                return json.loads(data)
            self._misses += 1
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._misses += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存"""
        if not self._redis:
            return False
        
        try:
            data = json.dumps(value, ensure_ascii=False)
            expire = ttl or self.default_ttl
            await self._redis.setex(key, timedelta(seconds=expire), data)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self._redis:
            return False
        
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """批量删除匹配模式的键"""
        if not self._redis:
            return 0
        
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"Redis invalidate error: {e}")
            return 0
    
    def get_stats(self) -> dict:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "backend": "redis" if self._redis else "memory",
        }


# 全局缓存实例
_cache: Optional[RedisCache] = None


async def init_cache(
    host: str = "localhost",
    port: int = 6379,
    **kwargs,
) -> RedisCache:
    """初始化缓存"""
    global _cache
    _cache = RedisCache(host=host, port=port, **kwargs)
    await _cache.connect()
    return _cache


def get_cache() -> Optional[RedisCache]:
    """获取缓存实例"""
    return _cache


async def close_cache():
    """关闭缓存"""
    global _cache
    if _cache:
        await _cache.disconnect()
        _cache = None
