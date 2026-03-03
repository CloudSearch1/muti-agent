"""
短期记忆系统

职责：基于 Redis 的短期记忆存储，保存会话上下文和临时数据
"""

from typing import Any, Optional
from datetime import datetime, timedelta
import json
import structlog

try:
    import redis.asyncio as redis
except ImportError:
    import redis


logger = structlog.get_logger(__name__)


class ShortTermMemory:
    """
    短期记忆系统
    
    使用 Redis 存储临时数据，支持 TTL 自动过期
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        default_ttl: int = 3600,
        **kwargs,
    ):
        """
        初始化短期记忆
        
        Args:
            redis_url: Redis 连接 URL
            default_ttl: 默认 TTL (秒)
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._redis: Optional[redis.Redis] = None
        
        self.logger = logger.bind(component="short_term_memory")
        self.logger.info(
            "ShortTermMemory initialized",
            redis_url=redis_url,
            default_ttl=default_ttl,
        )
    
    async def connect(self) -> None:
        """连接到 Redis"""
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            self.logger.info("Connected to Redis")
    
    async def disconnect(self) -> None:
        """断开 Redis 连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self.logger.info("Disconnected from Redis")
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        设置记忆
        
        Args:
            key: 键名
            value: 值 (会自动序列化)
            ttl: 过期时间 (秒)，None 则使用默认值
            
        Returns:
            是否成功
        """
        if not self._redis:
            await self.connect()
        
        try:
            # 序列化值
            serialized = json.dumps(value, default=str)
            
            # 设置 TTL
            expire_seconds = ttl or self.default_ttl
            
            await self._redis.setex(
                f"memory:{key}",
                expire_seconds,
                serialized,
            )
            
            self.logger.debug(
                "Memory set",
                key=key,
                ttl=expire_seconds,
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to set memory",
                key=key,
                error=str(e),
            )
            return False
    
    async def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        获取记忆
        
        Args:
            key: 键名
            default: 默认值
            
        Returns:
            值，不存在则返回默认值
        """
        if not self._redis:
            await self.connect()
        
        try:
            value = await self._redis.get(f"memory:{key}")
            
            if value is None:
                return default
            
            # 反序列化
            return json.loads(value)
            
        except Exception as e:
            self.logger.error(
                "Failed to get memory",
                key=key,
                error=str(e),
            )
            return default
    
    async def delete(self, key: str) -> bool:
        """删除记忆"""
        if not self._redis:
            await self.connect()
        
        try:
            await self._redis.delete(f"memory:{key}")
            self.logger.debug("Memory deleted", key=key)
            return True
        except Exception as e:
            self.logger.error(
                "Failed to delete memory",
                key=key,
                error=str(e),
            )
            return False
    
    async def exists(self, key: str) -> bool:
        """检查记忆是否存在"""
        if not self._redis:
            await self.connect()
        
        try:
            return await self._redis.exists(f"memory:{key}") > 0
        except Exception as e:
            self.logger.error(
                "Failed to check memory existence",
                key=key,
                error=str(e),
            )
            return False
    
    async def increment(
        self,
        key: str,
        amount: int = 1,
    ) -> int:
        """递增计数"""
        if not self._redis:
            await self.connect()
        
        try:
            return await self._redis.incrby(f"memory:{key}", amount)
        except Exception as e:
            self.logger.error(
                "Failed to increment memory",
                key=key,
                error=str(e),
            )
            return 0
    
    async def get_ttl(self, key: str) -> int:
        """获取剩余 TTL"""
        if not self._redis:
            await self.connect()
        
        try:
            return await self._redis.ttl(f"memory:{key}")
        except Exception as e:
            self.logger.error(
                "Failed to get TTL",
                key=key,
                error=str(e),
            )
            return -1
    
    async def clear_pattern(self, pattern: str) -> int:
        """批量删除匹配模式的键"""
        if not self._redis:
            await self.connect()
        
        try:
            keys = await self._redis.keys(f"memory:{pattern}")
            if keys:
                await self._redis.delete(*keys)
                self.logger.info(
                    "Cleared memories",
                    pattern=pattern,
                    count=len(keys),
                )
                return len(keys)
            return 0
        except Exception as e:
            self.logger.error(
                "Failed to clear memories",
                pattern=pattern,
                error=str(e),
            )
            return 0
    
    async def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        if not self._redis:
            await self.connect()
        
        try:
            info = await self._redis.info("memory")
            keys = await self._redis.keys("memory:*")
            
            return {
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_keys": len(keys),
                "connected": self._redis is not None,
            }
        except Exception as e:
            self.logger.error(
                "Failed to get stats",
                error=str(e),
            )
            return {
                "used_memory": 0,
                "total_keys": 0,
                "connected": False,
            }
