"""
IntelliTeam 响应缓存模块

缓存 API 响应，减少重复计算
"""

import hashlib
import json
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
import logging

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ResponseCacher:
    """
    响应缓存器
    
    缓存 API 响应，支持 TTL
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/3"):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self.default_ttl = 300  # 默认 5 分钟
    
    async def connect(self) -> bool:
        """连接 Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis 不可用，响应缓存将禁用")
            return False
        
        try:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis.ping()
            logger.info("响应缓存已连接 Redis")
            return True
        except Exception as e:
            logger.error(f"响应缓存连接失败：{e}")
            return False
    
    def _generate_key(self, path: str, params: Optional[Dict] = None) -> str:
        """
        生成缓存键
        
        Args:
            path: API 路径
            params: 查询参数
            
        Returns:
            缓存键
        """
        key_data = f"{path}:{json.dumps(params or {}, sort_keys=True)}"
        return f"cache:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            key: 缓存键
            
        Returns:
            缓存数据
        """
        if not self._redis:
            return None
        
        try:
            cached = await self._redis.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error(f"获取缓存失败：{e}")
            return None
    
    async def set(
        self,
        key: str,
        data: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        设置缓存
        
        Args:
            key: 缓存键
            data: 缓存数据
            ttl: 过期时间（秒）
            
        Returns:
            是否成功
        """
        if not self._redis:
            return False
        
        try:
            expire = ttl or self.default_ttl
            serialized = json.dumps(data)
            await self._redis.setex(key, expire, serialized)
            return True
        except Exception as e:
            logger.error(f"设置缓存失败：{e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self._redis:
            return False
        
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"删除缓存失败：{e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        批量删除缓存
        
        Args:
            pattern: 匹配模式
            
        Returns:
            删除数量
        """
        if not self._redis:
            return 0
        
        try:
            keys = await self._redis.keys(f"cache:{pattern}")
            if keys:
                await self._redis.delete(*keys)
                logger.info(f"清除缓存：{len(keys)} 个")
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"清除缓存失败：{e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        if not self._redis:
            return {"enabled": False}
        
        try:
            info = await self._redis.info("memory")
            keys = await self._redis.keys("cache:*")
            
            return {
                "enabled": True,
                "keys_count": len(keys),
                "memory_used": info.get("used_memory_human", "0B"),
                "default_ttl": self.default_ttl
            }
        except Exception as e:
            logger.error(f"获取缓存统计失败：{e}")
            return {"enabled": False, "error": str(e)}


# 全局缓存实例
_response_cacher: Optional[ResponseCacher] = None


def get_response_cacher(redis_url: str = "redis://localhost:6379/3") -> ResponseCacher:
    """获取响应缓存器单例"""
    global _response_cacher
    if _response_cacher is None:
        _response_cacher = ResponseCacher(redis_url)
    return _response_cacher


async def init_response_cacher(redis_url: str = "redis://localhost:6379/3") -> bool:
    """初始化响应缓存"""
    cacher = get_response_cacher(redis_url)
    return await cacher.connect()


def cache_response(ttl: int = 300):
    """
    响应缓存装饰器
    
    Usage:
        @cache_response(ttl=300)
        async def get_data():
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cacher = get_response_cacher()
            
            # 生成缓存键
            key = cacher._generate_key(
                func.__name__,
                kwargs
            )
            
            # 尝试从缓存获取
            cached = await cacher.get(key)
            if cached is not None:
                logger.debug(f"缓存命中：{key}")
                return cached
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            await cacher.set(key, result, ttl)
            logger.debug(f"缓存已设置：{key}")
            
            return result
        
        return wrapper
    return decorator
