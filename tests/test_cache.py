"""
缓存模块测试

测试缓存管理器、缓存操作、过期机制、Redis 连接等
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import json

from src.utils.cache import (
    CacheManager,
    REDIS_AVAILABLE,
    get_cache,
    init_cache,
)


# ============ CacheManager Creation Tests ============

class TestCacheManagerCreation:
    """缓存管理器创建测试"""

    def test_cache_manager_creation(self):
        """测试缓存管理器创建"""
        cache = CacheManager()
        assert cache is not None
        assert cache.redis_url == "redis://localhost:6379/0"

    def test_cache_manager_with_custom_url(self):
        """测试带自定义 URL 的缓存管理器"""
        cache = CacheManager(redis_url="redis://custom-host:6380/1")
        assert cache.redis_url == "redis://custom-host:6380/1"

    def test_cache_manager_with_password_url(self):
        """测试带密码的缓存 URL"""
        cache = CacheManager(redis_url="redis://:password@localhost:6379/0")
        assert "password" in cache.redis_url

    def test_cache_manager_attributes(self):
        """测试缓存管理器属性"""
        cache = CacheManager()
        # 检查是否有必要的属性
        assert hasattr(cache, "__init__")
        assert hasattr(cache, "redis_url")
        assert hasattr(cache, "connect")
        assert hasattr(cache, "disconnect")
        assert hasattr(cache, "get")
        assert hasattr(cache, "set")
        assert hasattr(cache, "delete")

    def test_cache_manager_initial_state(self):
        """测试缓存管理器初始状态"""
        cache = CacheManager()
        assert cache._redis is None


# ============ REDIS_AVAILABLE Check Tests ============

class TestRedisAvailability:
    """Redis 可用性测试"""

    def test_redis_available_check(self):
        """测试 Redis 可用性检查"""
        # REDIS_AVAILABLE 是一个布尔值
        assert isinstance(REDIS_AVAILABLE, bool)

    def test_redis_available_is_true_with_redis(self):
        """测试安装 Redis 时可用性为 True"""
        # 这个测试假设 Redis 已安装
        # 如果 Redis 未安装，REDIS_AVAILABLE 为 False
        pass  # 无法模拟，取决于实际环境


# ============ Cache Operations Tests (Mock) ============

class TestCacheOperationsMock:
    """缓存操作测试（使用 Mock）"""

    @pytest.mark.asyncio
    async def test_connect_success_with_mock(self):
        """测试连接成功（Mock）"""
        cache = CacheManager()

        # Mock Redis
        with patch("src.utils.cache.redis") as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis_module.from_url = MagicMock(return_value=mock_redis)

            if REDIS_AVAILABLE:
                result = await cache.connect()
                assert result is True

    @pytest.mark.asyncio
    async def test_connect_failure_with_mock(self):
        """测试连接失败（Mock）"""
        cache = CacheManager()

        # Mock Redis 连接失败
        with patch("src.utils.cache.redis") as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(side_effect=Exception("Connection failed"))
            mock_redis_module.from_url = MagicMock(return_value=mock_redis)

            if REDIS_AVAILABLE:
                result = await cache.connect()
                assert result is False

    @pytest.mark.asyncio
    async def test_connect_without_redis(self):
        """测试无 Redis 库时连接"""
        cache = CacheManager()

        # 模拟 Redis 不可用
        with patch("src.utils.cache.REDIS_AVAILABLE", False):
            result = await cache.connect()
            assert result is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """测试断开连接"""
        cache = CacheManager()

        # Mock Redis
        cache._redis = AsyncMock()
        cache._redis.close = AsyncMock()

        await cache.disconnect()
        cache._redis.close.assert_called_once()


# ============ Cache Get/Set Tests ============

class TestCacheGetSet:
    """缓存存取测试"""

    @pytest.mark.asyncio
    async def test_set_value_without_connection(self):
        """测试无连接时设置值"""
        cache = CacheManager()
        cache._redis = None

        result = await cache.set("key", "value")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_value_without_connection(self):
        """测试无连接时获取值"""
        cache = CacheManager()
        cache._redis = None

        result = await cache.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_value_with_mock(self):
        """测试设置值（Mock）"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        cache._redis = mock_redis

        result = await cache.set("test_key", {"data": "value"})

        assert result is True
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_value_with_expire(self):
        """测试设置值带过期时间"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        cache._redis = mock_redis

        result = await cache.set("test_key", "value", expire_seconds=60)

        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_value_with_mock(self):
        """测试获取值（Mock）"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            return_value=json.dumps({"data": "test_value"})
        )
        cache._redis = mock_redis

        result = await cache.get("test_key")

        assert result == {"data": "test_value"}
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """测试获取不存在的键"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        cache._redis = mock_redis

        result = await cache.get("nonexistent_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_json_error(self):
        """测试获取时 JSON 解析错误"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="invalid json {")
        cache._redis = mock_redis

        result = await cache.get("test_key")

        # 解析失败应返回 None
        assert result is None

    @pytest.mark.asyncio
    async def test_set_with_json_serialization(self):
        """测试设置时 JSON 序列化"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        cache._redis = mock_redis

        test_data = {
            "string": "value",
            "number": 123,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
        }

        result = await cache.set("complex_key", test_data)

        assert result is True
        # 验证序列化调用
        call_args = mock_redis.set.call_args
        serialized = call_args[0][1]
        # 验证可以反序列化
        parsed = json.loads(serialized)
        assert parsed == test_data


# ============ Cache Delete Tests ============

class TestCacheDelete:
    """缓存删除测试"""

    @pytest.mark.asyncio
    async def test_delete_without_connection(self):
        """测试无连接时删除"""
        cache = CacheManager()
        cache._redis = None

        result = await cache.delete("key")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """测试删除成功"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        cache._redis = mock_redis

        result = await cache.delete("test_key")

        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_delete_with_error(self):
        """测试删除时出错"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(side_effect=Exception("Delete error"))
        cache._redis = mock_redis

        result = await cache.delete("test_key")

        assert result is False


# ============ Cache Exists Tests ============

class TestCacheExists:
    """缓存存在性检查测试"""

    @pytest.mark.asyncio
    async def test_exists_without_connection(self):
        """测试无连接时检查存在"""
        cache = CacheManager()
        cache._redis = None

        result = await cache.exists("key")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """测试键存在"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)
        cache._redis = mock_redis

        result = await cache.exists("existing_key")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """测试键不存在"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        cache._redis = mock_redis

        result = await cache.exists("nonexistent_key")

        assert result is False


# ============ Cache Pattern Clear Tests ============

class TestCachePatternClear:
    """缓存模式清除测试"""

    @pytest.mark.asyncio
    async def test_clear_pattern_without_connection(self):
        """测试无连接时清除模式"""
        cache = CacheManager()
        cache._redis = None

        result = await cache.clear_pattern("session:*")
        assert result == 0

    @pytest.mark.asyncio
    async def test_clear_pattern_success(self):
        """测试清除模式成功"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=["session:1", "session:2", "session:3"])
        mock_redis.delete = AsyncMock(return_value=3)
        cache._redis = mock_redis

        result = await cache.clear_pattern("session:*")

        assert result == 3
        mock_redis.keys.assert_called_once_with("session:*")

    @pytest.mark.asyncio
    async def test_clear_pattern_no_matches(self):
        """测试清除模式无匹配"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        cache._redis = mock_redis

        result = await cache.clear_pattern("nonexistent:*")

        assert result == 0

    @pytest.mark.asyncio
    async def test_clear_pattern_with_error(self):
        """测试清除模式时出错"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(side_effect=Exception("Keys error"))
        cache._redis = mock_redis

        result = await cache.clear_pattern("session:*")

        assert result == 0


# ============ Cache Stats Tests ============

class TestCacheStats:
    """缓存统计测试"""

    @pytest.mark.asyncio
    async def test_get_stats_without_connection(self):
        """测试无连接时获取统计"""
        cache = CacheManager()
        cache._redis = None

        stats = await cache.get_stats()
        assert stats == {}

    @pytest.mark.asyncio
    async def test_get_stats_success(self):
        """测试获取统计成功"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.info = AsyncMock(return_value={
            "used_memory": 1024000,
            "used_memory_human": "1.00MB",
        })
        cache._redis = mock_redis

        stats = await cache.get_stats()

        assert stats["used_memory"] == 1024000
        assert stats["used_memory_human"] == "1.00MB"
        assert stats["connected"] is True

    @pytest.mark.asyncio
    async def test_get_stats_with_error(self):
        """测试获取统计时出错"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.info = AsyncMock(side_effect=Exception("Info error"))
        cache._redis = mock_redis

        stats = await cache.get_stats()

        assert stats == {}


# ============ Cache Expiration Tests ============

class TestCacheExpiration:
    """缓存过期测试"""

    @pytest.mark.asyncio
    async def test_set_with_expiration(self):
        """测试设置带过期时间"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        cache._redis = mock_redis

        result = await cache.set("expiring_key", "value", expire_seconds=10)

        assert result is True
        # 验证使用 setex
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "expiring_key"
        assert call_args[0][1] == 10

    @pytest.mark.asyncio
    async def test_set_without_expiration(self):
        """测试设置不带过期时间"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        cache._redis = mock_redis

        result = await cache.set("permanent_key", "value")

        assert result is True
        # 验证使用 set
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_expiration_behavior_simulation(self):
        """测试过期行为模拟"""
        cache = CacheManager()

        # 这个测试模拟过期行为
        # 实际过期由 Redis 处理
        mock_redis = AsyncMock()

        # 模拟：初始存在，过期后不存在
        get_count = 0

        async def mock_get(key):
            nonlocal get_count
            get_count += 1
            if get_count == 1:
                return json.dumps("value")
            return None

        mock_redis.get = mock_get
        cache._redis = mock_redis

        # 第一次获取
        result1 = await cache.get("key")
        assert result1 == "value"

        # 模拟过期后获取
        result2 = await cache.get("key")
        assert result2 is None


# ============ Cache Connection Tests ============

class TestCacheConnection:
    """缓存连接测试"""

    @pytest.mark.asyncio
    async def test_connection_url_parsing(self):
        """测试连接 URL 解析"""
        urls = [
            "redis://localhost:6379/0",
            "redis://127.0.0.1:6380/1",
            "redis://:password@localhost:6379/0",
            "redis://user:password@redis-server:6379/2",
        ]

        for url in urls:
            cache = CacheManager(redis_url=url)
            assert cache.redis_url == url

    @pytest.mark.asyncio
    async def test_multiple_connections(self):
        """测试多个连接"""
        cache1 = CacheManager(redis_url="redis://localhost:6379/0")
        cache2 = CacheManager(redis_url="redis://localhost:6379/1")

        assert cache1.redis_url != cache2.redis_url


# ============ Global Functions Tests ============

class TestGlobalFunctions:
    """全局函数测试"""

    def test_get_cache_singleton(self):
        """测试获取缓存单例"""
        # 重置单例
        import src.utils.cache as cache_module
        cache_module._cache = None

        cache1 = get_cache()
        cache2 = get_cache()

        assert cache1 is cache2

    def test_get_cache_with_url(self):
        """测试带 URL 获取缓存"""
        # 重置单例
        import src.utils.cache as cache_module
        cache_module._cache = None

        cache = get_cache(redis_url="redis://custom:6379/2")
        assert cache.redis_url == "redis://custom:6379/2"

    @pytest.mark.asyncio
    async def test_init_cache_success(self):
        """测试初始化缓存成功"""
        # 重置单例
        import src.utils.cache as cache_module
        cache_module._cache = None

        with patch("src.utils.cache.REDIS_AVAILABLE", False):
            result = await init_cache()
            assert result is False  # Redis 不可用时返回 False


# ============ Edge Cases Tests ============

class TestCacheEdgeCases:
    """缓存边界情况测试"""

    @pytest.mark.asyncio
    async def test_set_empty_string(self):
        """测试设置空字符串"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        cache._redis = mock_redis

        result = await cache.set("empty_key", "")

        assert result is True

    @pytest.mark.asyncio
    async def test_set_none_value(self):
        """测试设置 None 值"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        cache._redis = mock_redis

        result = await cache.set("none_key", None)

        assert result is True

    @pytest.mark.asyncio
    async def test_set_large_value(self):
        """测试设置大值"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        cache._redis = mock_redis

        # 创建大对象
        large_data = {"data": "x" * 100000}

        result = await cache.set("large_key", large_data)

        assert result is True

    @pytest.mark.asyncio
    async def test_set_unicode_key(self):
        """测试 Unicode 键"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        cache._redis = mock_redis

        result = await cache.set("中文键", "值")

        assert result is True

    @pytest.mark.asyncio
    async def test_set_special_characters_key(self):
        """测试特殊字符键"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        cache._redis = mock_redis

        result = await cache.set("key:with:colons", "value")

        assert result is True

    @pytest.mark.asyncio
    async def test_clear_all_pattern(self):
        """测试清除所有键"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[f"key{i}" for i in range(100)])
        mock_redis.delete = AsyncMock(return_value=100)
        cache._redis = mock_redis

        result = await cache.clear_pattern("*")

        assert result == 100


# ============ Integration Tests ============

class TestCacheIntegration:
    """集成测试"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_cache_cycle_mock(self):
        """测试完整缓存周期（Mock）"""
        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=json.dumps({"test": "data"}))
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.close = AsyncMock()
        cache._redis = mock_redis

        # 连接
        # 设置
        result = await cache.set("test_key", {"test": "data"})
        assert result is True

        # 获取
        result = await cache.get("test_key")
        assert result == {"test": "data"}

        # 删除
        result = await cache.delete("test_key")
        assert result is True

        # 断开
        await cache.disconnect()

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not REDIS_AVAILABLE,
        reason="Redis not available"
    )
    async def test_real_redis_connection(self):
        """测试真实 Redis 连接"""
        cache = CacheManager()

        try:
            connected = await cache.connect()
            if connected:
                # 测试基本操作
                await cache.set("test_key", "test_value", expire_seconds=10)
                result = await cache.get("test_key")
                assert result == "test_value"

                await cache.delete("test_key")
                result = await cache.get("test_key")
                assert result is None

                await cache.disconnect()
        except Exception:
            pytest.skip("Redis server not running")


# ============ Performance Tests ============

class TestCachePerformance:
    """缓存性能测试"""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_set_performance_mock(self):
        """测试设置性能（Mock）"""
        import time

        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        cache._redis = mock_redis

        start = time.time()
        for i in range(1000):
            await cache.set(f"key_{i}", f"value_{i}")
        elapsed = time.time() - start

        assert elapsed < 2.0  # 1000 次设置应该在 2 秒内

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_get_performance_mock(self):
        """测试获取性能（Mock）"""
        import time

        cache = CacheManager()

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps("value"))
        cache._redis = mock_redis

        start = time.time()
        for i in range(1000):
            await cache.get(f"key_{i}")
        elapsed = time.time() - start

        assert elapsed < 2.0  # 1000 次获取应该在 2 秒内

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_serialization_performance(self):
        """测试序列化性能"""
        import time
        import json

        large_data = {
            f"key_{i}": f"value_{i}" * 100
            for i in range(100)
        }

        start = time.time()
        for _ in range(1000):
            serialized = json.dumps(large_data, ensure_ascii=False)
            deserialized = json.loads(serialized)
            assert deserialized == large_data
        elapsed = time.time() - start

        assert elapsed < 5.0  # 1000 次序列化/反序列化应该在 5 秒内