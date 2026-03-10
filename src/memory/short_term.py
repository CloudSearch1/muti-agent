"""
短期记忆系统

职责：基于 Redis 的短期记忆存储，保存会话上下文和临时数据

特性：
- 支持 TTL 自动过期
- 异步操作
- 连接池管理
- 批量操作优化
"""

import json
from typing import Any

import structlog

from .exceptions import (
    MemoryConnectionError,
    MemoryRetrievalError,
    MemoryStorageError,
    MemoryValidationError,
)

try:
    import redis.asyncio as redis
    from redis.asyncio.connection import ConnectionPool

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None  # type: ignore
    ConnectionPool = None  # type: ignore


logger = structlog.get_logger(__name__)

# 默认配置
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_TTL = 3600  # 1 小时
MAX_KEY_LENGTH = 250
MAX_VALUE_SIZE = 10 * 1024 * 1024  # 10 MB


class ShortTermMemory:
    """
    短期记忆系统

    使用 Redis 存储临时数据，支持 TTL 自动过期。

    Attributes:
        redis_url: Redis 连接 URL
        default_ttl: 默认 TTL（秒）
        _redis: Redis 客户端实例
        _pool: 连接池

    Example:
        >>> memory = ShortTermMemory(redis_url="redis://localhost:6379/0")
        >>> await memory.set("key", {"data": "value"}, ttl=60)
        >>> data = await memory.get("key")
    """

    def __init__(
        self,
        redis_url: str = DEFAULT_REDIS_URL,
        default_ttl: int = DEFAULT_TTL,
        max_connections: int = 10,
        **kwargs: Any,
    ) -> None:
        """
        初始化短期记忆

        Args:
            redis_url: Redis 连接 URL
            default_ttl: 默认 TTL（秒）
            max_connections: 最大连接数
            **kwargs: 额外配置参数

        Raises:
            MemoryConnectionError: Redis 不可用时
        """
        if not REDIS_AVAILABLE:
            raise MemoryConnectionError(
                message="Redis library not installed. Install with: pip install redis",
                backend="redis",
            )

        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        self._redis: redis.Redis | None = None
        self._pool: ConnectionPool | None = None
        self._kwargs = kwargs

        self.logger = logger.bind(component="short_term_memory")
        self.logger.info(
            "ShortTermMemory initialized",
            redis_url=redis_url,
            default_ttl=default_ttl,
            max_connections=max_connections,
        )

    async def connect(self) -> None:
        """
        连接到 Redis

        Raises:
            MemoryConnectionError: 连接失败时
        """
        if self._redis is not None:
            return

        try:
            # 创建连接池
            self._pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                decode_responses=True,
            )

            self._redis = redis.Redis(connection_pool=self._pool)
            # 测试连接
            await self._redis.ping()

            self.logger.info("Connected to Redis successfully")

        except Exception as e:
            self._redis = None
            self._pool = None
            raise MemoryConnectionError(
                message=f"Failed to connect to Redis: {e}",
                backend="redis",
            ) from e

    async def disconnect(self) -> None:
        """断开 Redis 连接"""
        if self._redis:
            try:
                await self._redis.close()
            except Exception as e:
                self.logger.warning("Error closing Redis connection", error=str(e))
            finally:
                self._redis = None
                self._pool = None
                self.logger.info("Disconnected from Redis")

    async def _ensure_connected(self) -> redis.Redis:
        """确保已连接"""
        if self._redis is None:
            await self.connect()
        return self._redis  # type: ignore

    def _make_key(self, key: str) -> str:
        """
        生成带前缀的键名

        Args:
            key: 原始键名

        Returns:
            带前缀的键名

        Raises:
            MemoryValidationError: 键名无效时
        """
        if not key or not isinstance(key, str):
            raise MemoryValidationError(
                message="Key must be a non-empty string",
                field="key",
                value=key,
            )

        key = key.strip()
        if len(key) > MAX_KEY_LENGTH:
            raise MemoryValidationError(
                message=f"Key too long: {len(key)} > {MAX_KEY_LENGTH}",
                field="key",
                value=key[:50] + "...",
            )

        return f"memory:{key}"

    def _serialize(self, value: Any) -> str:
        """
        序列化值

        Args:
            value: 待序列化的值

        Returns:
            JSON 字符串

        Raises:
            MemoryValidationError: 值过大或无法序列化时
        """
        try:
            serialized = json.dumps(value, default=str, ensure_ascii=False)

            if len(serialized) > MAX_VALUE_SIZE:
                raise MemoryValidationError(
                    message=f"Value too large: {len(serialized)} > {MAX_VALUE_SIZE}",
                    field="value",
                    value=f"<{len(serialized)} bytes>",
                )

            return serialized

        except (TypeError, ValueError) as e:
            raise MemoryValidationError(
                message=f"Failed to serialize value: {e}",
                field="value",
            ) from e

    def _deserialize(self, data: str | None) -> Any:
        """
        反序列化值

        Args:
            data: JSON 字符串

        Returns:
            反序列化后的值
        """
        if data is None:
            return None

        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to deserialize data", error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        设置记忆

        Args:
            key: 键名
            value: 值（会自动序列化）
            ttl: 过期时间（秒），None 则使用默认值

        Returns:
            是否成功

        Raises:
            MemoryStorageError: 存储失败时
            MemoryValidationError: 参数验证失败时
        """
        try:
            client = await self._ensure_connected()
            full_key = self._make_key(key)
            serialized = self._serialize(value)
            expire_seconds = ttl if ttl is not None else self.default_ttl

            await client.setex(full_key, expire_seconds, serialized)

            self.logger.debug(
                "Memory set",
                key=key,
                ttl=expire_seconds,
                size=len(serialized),
            )

            return True

        except (MemoryValidationError, MemoryConnectionError):
            raise
        except Exception as e:
            self.logger.error("Failed to set memory", key=key, error=str(e))
            raise MemoryStorageError(
                message=f"Failed to set memory: {e}",
                memory_id=key,
                storage_type="short_term",
            ) from e

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

        Raises:
            MemoryRetrievalError: 获取失败时
        """
        try:
            client = await self._ensure_connected()
            full_key = self._make_key(key)
            value = await client.get(full_key)

            if value is None:
                return default

            return self._deserialize(value)

        except (MemoryValidationError, MemoryConnectionError):
            raise
        except Exception as e:
            self.logger.error("Failed to get memory", key=key, error=str(e))
            raise MemoryRetrievalError(
                message=f"Failed to get memory: {e}",
                memory_id=key,
            ) from e

    async def delete(self, key: str) -> bool:
        """
        删除记忆

        Args:
            key: 键名

        Returns:
            是否成功删除
        """
        try:
            client = await self._ensure_connected()
            full_key = self._make_key(key)
            result = await client.delete(full_key)

            deleted = result > 0
            self.logger.debug("Memory delete", key=key, deleted=deleted)
            return deleted

        except (MemoryValidationError, MemoryConnectionError):
            raise
        except Exception as e:
            self.logger.error("Failed to delete memory", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """
        检查记忆是否存在

        Args:
            key: 键名

        Returns:
            是否存在
        """
        try:
            client = await self._ensure_connected()
            full_key = self._make_key(key)
            return await client.exists(full_key) > 0
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
        """
        递增计数

        Args:
            key: 键名
            amount: 递增量

        Returns:
            递增后的值
        """
        try:
            client = await self._ensure_connected()
            full_key = self._make_key(key)
            return await client.incrby(full_key, amount)
        except Exception as e:
            self.logger.error(
                "Failed to increment memory",
                key=key,
                error=str(e),
            )
            return 0

    async def get_ttl(self, key: str) -> int:
        """
        获取剩余 TTL

        Args:
            key: 键名

        Returns:
            剩余秒数，-1 表示无过期时间，-2 表示不存在
        """
        try:
            client = await self._ensure_connected()
            full_key = self._make_key(key)
            return await client.ttl(full_key)
        except Exception as e:
            self.logger.error("Failed to get TTL", key=key, error=str(e))
            return -2

    async def set_ttl(self, key: str, ttl: int) -> bool:
        """
        设置 TTL

        Args:
            key: 键名
            ttl: 过期时间（秒）

        Returns:
            是否成功
        """
        try:
            client = await self._ensure_connected()
            full_key = self._make_key(key)
            return await client.expire(full_key, ttl)
        except Exception as e:
            self.logger.error("Failed to set TTL", key=key, error=str(e))
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        批量删除匹配模式的键

        注意：大量键时可能阻塞，建议在低峰期使用

        Args:
            pattern: 匹配模式（支持通配符 * 和 ?）

        Returns:
            删除的键数量
        """
        try:
            client = await self._ensure_connected()
            full_pattern = f"memory:{pattern}"

            # 使用 scan 替代 keys，避免阻塞
            keys = []
            async for key in client.scan_iter(match=full_pattern):
                keys.append(key)

            if keys:
                deleted = await client.delete(*keys)
                self.logger.info(
                    "Cleared memories",
                    pattern=pattern,
                    count=deleted,
                )
                return deleted

            return 0

        except Exception as e:
            self.logger.error(
                "Failed to clear memories",
                pattern=pattern,
                error=str(e),
            )
            return 0

    async def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            包含内存使用、键数量等统计信息的字典
        """
        try:
            client = await self._ensure_connected()

            # 并行获取信息
            pipe = client.pipeline()
            pipe.info("memory")
            pipe.dbsize()
            results = await pipe.execute()

            info = results[0]
            total_keys = results[1]

            return {
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_keys": total_keys,
                "connected": True,
                "max_connections": self.max_connections,
                "default_ttl": self.default_ttl,
            }

        except Exception as e:
            self.logger.error("Failed to get stats", error=str(e))
            return {
                "used_memory": 0,
                "total_keys": 0,
                "connected": False,
                "error": str(e),
            }

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        """
        批量获取多个键的值

        Args:
            keys: 键名列表

        Returns:
            键值对字典（不存在的键不会包含在结果中）
        """
        if not keys:
            return {}

        try:
            client = await self._ensure_connected()
            full_keys = [self._make_key(k) for k in keys]
            values = await client.mget(full_keys)

            result = {}
            for i, key in enumerate(keys):
                if values[i] is not None:
                    result[key] = self._deserialize(values[i])

            return result

        except Exception as e:
            self.logger.error("Failed to mget", error=str(e))
            return {}

    async def mset(
        self,
        items: dict[str, Any],
        ttl: int | None = None,
    ) -> int:
        """
        批量设置多个键值对

        Args:
            items: 键值对字典
            ttl: 过期时间（秒）

        Returns:
            成功设置的键数量
        """
        if not items:
            return 0

        try:
            client = await self._ensure_connected()
            expire_seconds = ttl if ttl is not None else self.default_ttl

            # 使用 pipeline 提高性能
            pipe = client.pipeline()
            count = 0

            for key, value in items.items():
                full_key = self._make_key(key)
                serialized = self._serialize(value)
                pipe.setex(full_key, expire_seconds, serialized)
                count += 1

            await pipe.execute()

            self.logger.debug("Batch set memories", count=count)
            return count

        except Exception as e:
            self.logger.error("Failed to mset", error=str(e))
            return 0

    async def health_check(self) -> dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态信息
        """
        try:
            client = await self._ensure_connected()
            start_time = __import__("time").time()
            await client.ping()
            latency_ms = (__import__("time").time() - start_time) * 1000

            return {
                "status": "healthy",
                "backend": "redis",
                "latency_ms": round(latency_ms, 2),
                "connected": True,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "redis",
                "error": str(e),
                "connected": False,
            }

    async def __aenter__(self) -> "ShortTermMemory":
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器出口"""
        await self.disconnect()
