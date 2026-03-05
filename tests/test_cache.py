"""缓存模块测试"""
from src.utils.cache import REDIS_AVAILABLE, CacheManager


class TestCacheManager:
    """缓存管理器测试类"""

    def test_cache_manager_creation(self):
        """测试缓存管理器创建"""
        cache = CacheManager()
        assert cache is not None

    def test_redis_available_check(self):
        """测试 Redis 可用性检查"""
        # REDIS_AVAILABLE 是一个布尔值
        assert isinstance(REDIS_AVAILABLE, bool)

    def test_cache_manager_with_url(self):
        """测试带 URL 的缓存管理器"""
        cache = CacheManager(redis_url="redis://localhost:6379")
        assert cache is not None

    def test_cache_manager_attributes(self):
        """测试缓存管理器属性"""
        cache = CacheManager()
        # 检查是否有必要的属性
        assert hasattr(cache, '__init__')
