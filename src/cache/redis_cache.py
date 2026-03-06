"""
Redis 缓存层完善

完整的 Redis 缓存实现，支持分布式缓存
"""

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Union

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Redis 缓存层
    
    功能:
    - 字符串缓存
    - JSON 缓存
    - 批量操作
    - 缓存统计
    - 键过期管理
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_connections: int = 50,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
        }
        
        self._max_connections = max_connections
        self._socket_timeout = socket_timeout
        self._socket_connect_timeout = socket_connect_timeout
    
    async def connect(self):
        """连接 Redis"""
        try:
            self._pool = redis.ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self._max_connections,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._socket_connect_timeout,
                decode_responses=True,
            )
            
            self._client = redis.Redis(connection_pool=self._pool)
            
            # 测试连接
            await self._client.ping()
            
            logger.info(
                f"Redis connected: {self.host}:{self.port}:{self.db}"
            )
            
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self._stats["errors"] += 1
            raise
    
    async def disconnect(self):
        """断开连接"""
        if self._client:
            await self._client.close()
            logger.info("Redis disconnected")
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            value = await self._client.get(key)
            
            if value:
                self._stats["hits"] += 1
                # 尝试 JSON 解码
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            else:
                self._stats["misses"] += 1
                return None
                
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._stats["errors"] += 1
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None,
    ) -> bool:
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            expire: 过期时间（秒）
        
        Returns:
            是否成功
        """
        try:
            # JSON 序列化
            if isinstance(value, (dict, list, bool, int, float)):
                value = json.dumps(value, ensure_ascii=False)
            elif value is not None:
                value = str(value)
            
            if expire:
                await self._client.setex(key, timedelta(seconds=expire), value)
            else:
                await self._client.set(key, value)
            
            self._stats["sets"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            self._stats["errors"] += 1
            return False
    
    async def delete(self, *keys: str) -> int:
        """删除缓存"""
        try:
            count = await self._client.delete(*keys)
            self._stats["deletes"] += count
            return count
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            self._stats["errors"] += 1
            return 0
    
    async def exists(self, *keys: str) -> int:
        """检查键是否存在"""
        try:
            return await self._client.exists(*keys)
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        try:
            return await self._client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis expire error: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """获取剩余过期时间"""
        try:
            return await self._client.ttl(key)
        except Exception as e:
            logger.error(f"Redis ttl error: {e}")
            return -2
    
    # ============ 批量操作 ============
    
    async def mget(self, *keys: str) -> List[Any]:
        """批量获取"""
        try:
            values = await self._client.mget(*keys)
            
            # 统计
            hits = sum(1 for v in values if v is not None)
            misses = len(values) - hits
            self._stats["hits"] += hits
            self._stats["misses"] += misses
            
            # JSON 解码
            result = []
            for value in values:
                if value:
                    try:
                        result.append(json.loads(value))
                    except (json.JSONDecodeError, TypeError):
                        result.append(value)
                else:
                    result.append(None)
            
            return result
            
        except Exception as e:
            logger.error(f"Redis mget error: {e}")
            self._stats["errors"] += 1
            return [None] * len(keys)
    
    async def mset(self, mapping: Dict[str, Any], expire: Optional[int] = None):
        """批量设置"""
        try:
            # JSON 序列化
            serialized = {}
            for key, value in mapping.items():
                if isinstance(value, (dict, list, bool, int, float)):
                    serialized[key] = json.dumps(value, ensure_ascii=False)
                elif value is not None:
                    serialized[key] = str(value)
                else:
                    serialized[key] = value
            
            await self._client.mset(serialized)
            self._stats["sets"] += len(mapping)
            
            # 设置过期时间
            if expire and mapping:
                pipe = self._client.pipeline()
                for key in mapping.keys():
                    pipe.expire(key, expire)
                await pipe.execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Redis mset error: {e}")
            self._stats["errors"] += 1
            return False
    
    # ============ 计数器 ============
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """自增"""
        try:
            return await self._client.incr(key, amount)
        except Exception as e:
            logger.error(f"Redis incr error: {e}")
            return 0
    
    async def decr(self, key: str, amount: int = 1) -> int:
        """自减"""
        try:
            return await self._client.decr(key, amount)
        except Exception as e:
            logger.error(f"Redis decr error: {e}")
            return 0
    
    # ============ 集合操作 ============
    
    async def sadd(self, key: str, *members: Any) -> int:
        """集合添加"""
        try:
            return await self._client.sadd(key, *members)
        except Exception as e:
            logger.error(f"Redis sadd error: {e}")
            return 0
    
    async def smembers(self, key: str) -> set:
        """集合获取"""
        try:
            return await self._client.smembers(key)
        except Exception as e:
            logger.error(f"Redis smembers error: {e}")
            return set()
    
    async def srem(self, key: str, *members: Any) -> int:
        """集合删除"""
        try:
            return await self._client.srem(key, *members)
        except Exception as e:
            logger.error(f"Redis srem error: {e}")
            return 0
    
    # ============ 列表操作 ============
    
    async def lpush(self, key: str, *values: Any) -> int:
        """列表左推"""
        try:
            return await self._client.lpush(key, *values)
        except Exception as e:
            logger.error(f"Redis lpush error: {e}")
            return 0
    
    async def rpush(self, key: str, *values: Any) -> int:
        """列表右推"""
        try:
            return await self._client.rpush(key, *values)
        except Exception as e:
            logger.error(f"Redis rpush error: {e}")
            return 0
    
    async def lrange(self, key: str, start: int, end: int) -> List[Any]:
        """列表范围"""
        try:
            return await self._client.lrange(key, start, end)
        except Exception as e:
            logger.error(f"Redis lrange error: {e}")
            return []
    
    # ============ 排序集合 ============
    
    async def zadd(self, key: str, mapping: Dict[str, float]) -> int:
        """排序集合添加"""
        try:
            return await self._client.zadd(key, mapping)
        except Exception as e:
            logger.error(f"Redis zadd error: {e}")
            return 0
    
    async def zrange(self, key: str, start: int, end: int) -> List[Any]:
        """排序集合范围"""
        try:
            return await self._client.zrange(key, start, end)
        except Exception as e:
            logger.error(f"Redis zrange error: {e}")
            return []
    
    async def zrem(self, key: str, *members: Any) -> int:
        """排序集合删除"""
        try:
            return await self._client.zrem(key, *members)
        except Exception as e:
            logger.error(f"Redis zrem error: {e}")
            return 0
    
    # ============ 统计 ============
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            **self._stats,
            "total_operations": total + self._stats["sets"] + self._stats["deletes"],
            "hit_rate": f"{hit_rate:.2f}%",
        }
    
    async def flush_stats(self):
        """清空统计"""
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
        }
    
    # ============ 键管理 ============
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配的键"""
        try:
            return await self._client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis keys error: {e}")
            return []
    
    async def scan_iter(self, match: Optional[str] = None, count: int = 100):
        """迭代键"""
        try:
            async for key in self._client.scan_iter(match=match, count=count):
                yield key
        except Exception as e:
            logger.error(f"Redis scan_iter error: {e}")
    
    async def flushdb(self):
        """清空当前数据库"""
        try:
            await self._client.flushdb()
            logger.warning("Redis database flushed")
        except Exception as e:
            logger.error(f"Redis flushdb error: {e}")
    
    async def flushall(self):
        """清空所有数据库"""
        try:
            await self._client.flushall()
            logger.warning("All Redis databases flushed")
        except Exception as e:
            logger.error(f"Redis flushall error: {e}")


# ============ 全局缓存实例 ============

_cache: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    """获取 Redis 缓存实例"""
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache


async def init_redis_cache(
    host: str = "localhost",
    port: int = 6379,
    **kwargs,
) -> RedisCache:
    """初始化 Redis 缓存"""
    global _cache
    _cache = RedisCache(host=host, port=port, **kwargs)
    await _cache.connect()
    logger.info("Redis cache initialized")
    return _cache


async def close_redis_cache():
    """关闭 Redis 缓存"""
    global _cache
    if _cache:
        await _cache.disconnect()
        _cache = None
