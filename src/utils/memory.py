"""
内存优化模块

LRU 缓存、分页加载、内存监控等
"""

import asyncio
import gc
import logging
import tracemalloc
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class LRUCache(Generic[T]):
    """
    LRU 缓存

    功能:
    - 自动淘汰最久未使用
    - 支持 TTL
    - 线程安全
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._cache: OrderedDict[str, T] = OrderedDict()
        self._timestamps: dict[str, datetime] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> T | None:
        """获取缓存"""
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            # 检查是否过期
            if self._is_expired(key):
                await self._delete(key)
                self._misses += 1
                return None

            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]

    async def set(self, key: str, value: T):
        """设置缓存"""
        async with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)

            self._cache[key] = value
            self._timestamps[key] = datetime.now()

            # 限制大小
            while len(self._cache) > self._max_size:
                oldest_key = next(iter(self._cache))
                await self._delete(oldest_key)

    async def delete(self, key: str):
        """删除缓存"""
        async with self._lock:
            await self._delete(key)

    async def _delete(self, key: str):
        """内部删除方法"""
        if key in self._cache:
            del self._cache[key]
        if key in self._timestamps:
            del self._timestamps[key]

    def _is_expired(self, key: str) -> bool:
        """检查是否过期"""
        if key not in self._timestamps:
            return True

        age = (datetime.now() - self._timestamps[key]).total_seconds()
        return age > self._ttl_seconds

    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    def get_stats(self) -> dict:
        """获取统计"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
        }


@dataclass
class MemoryStats:
    """内存统计"""
    current_mb: float = 0.0
    peak_mb: float = 0.0
    gc_objects: int = 0
    gc_collections: int = 0


class MemoryMonitor:
    """
    内存监控器

    功能:
    - 实时监控内存使用
    - 内存泄漏检测
    - 自动垃圾回收
    """

    def __init__(self, warning_threshold_mb: float = 500.0):
        self._warning_threshold = warning_threshold_mb
        self._peak_memory = 0.0
        self._history: list[MemoryStats] = []
        self._monitoring = False
        self._monitor_task: asyncio.Task | None = None

    def start_monitoring(self, interval_seconds: float = 10.0):
        """开始监控"""
        tracemalloc.start()
        self._monitoring = True

        async def monitor_loop():
            while self._monitoring:
                stats = self.get_stats()
                self._history.append(stats)

                # 限制历史记录
                if len(self._history) > 100:
                    self._history = self._history[-100:]

                # 检查是否超限
                if stats.current_mb > self._warning_threshold:
                    logger.warning(f"High memory usage: {stats.current_mb:.2f} MB")

                    # 自动 GC
                    gc.collect()

                await asyncio.sleep(interval_seconds)

        self._monitor_task = asyncio.create_task(monitor_loop())
        logger.info(f"Memory monitoring started (threshold={self._warning_threshold}MB)")

    def stop_monitoring(self):
        """停止监控"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
        tracemalloc.stop()
        logger.info("Memory monitoring stopped")

    def get_stats(self) -> MemoryStats:
        """获取内存统计"""
        current, peak = tracemalloc.get_traced_memory()

        return MemoryStats(
            current_mb=current / 1024 / 1024,
            peak_mb=peak / 1024 / 1024,
            gc_objects=len(gc.get_objects()),
            gc_collections=gc.get_count(),
        )

    def get_history(self, limit: int = 100) -> list[MemoryStats]:
        """获取历史记录"""
        return self._history[-limit:]

    def force_gc(self):
        """强制垃圾回收"""
        collected = gc.collect()
        logger.info(f"GC collected {collected} objects")
        return collected


class PaginatedLoader:
    """
    分页加载器

    功能:
    - 大数据集分页加载
    - 懒加载
    - 内存优化
    """

    def __init__(
        self,
        loader: Callable,
        page_size: int = 50,
        max_cached_pages: int = 10,
    ):
        self._loader = loader  # async function(page, page_size)
        self._page_size = page_size
        self._max_cached_pages = max_cached_pages
        self._cache: LRUCache = LRUCache(max_size=max_cached_pages)
        self._total_count: int | None = None

    async def get_page(self, page: int) -> list:
        """获取指定页"""
        cache_key = f"page_{page}"

        # 检查缓存
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        # 加载数据
        items = await self._loader(page, self._page_size)

        # 缓存
        await self._cache.set(cache_key, items)

        return items

    async def get_all(self) -> list[Any]:
        """获取所有数据（谨慎使用）"""
        if self._total_count is None:
            # 先获取总数
            first_page = await self.get_page(0)
            self._total_count = len(first_page)

            if len(first_page) < self._page_size:
                return first_page

            # 估算总页数
            total_pages = (self._total_count + self._page_size - 1) // self._page_size

            # 加载剩余页
            all_items = first_page
            for page in range(1, total_pages):
                page_items = await self.get_page(page)
                all_items.extend(page_items)

            return all_items

        return first_page

    def set_total_count(self, count: int):
        """设置总数"""
        self._total_count = count


@dataclass
class ObjectPoolStats:
    """对象池统计"""
    pool_size: int = 0
    in_use: int = 0
    available: int = 0
    total_created: int = 0
    total_released: int = 0


class ObjectPool(Generic[T]):
    """
    对象池

    功能:
    - 重用昂贵对象
    - 限制最大数量
    - 自动清理
    """

    def __init__(
        self,
        factory: Callable[[], T],
        max_size: int = 10,
        cleanup: Callable[[T], None] | None = None,
    ):
        self._factory = factory
        self._max_size = max_size
        self._cleanup = cleanup or (lambda x: None)
        self._pool: list[T] = []
        self._in_use: set = set()
        self._total_created = 0
        self._total_released = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> T:
        """获取对象"""
        async with self._lock:
            if self._pool:
                obj = self._pool.pop()
                self._in_use.add(id(obj))
                logger.debug(f"Object acquired from pool, in_use={len(self._in_use)}")
                return obj

            # 创建新对象
            obj = self._factory()
            self._total_created += 1
            self._in_use.add(id(obj))
            logger.debug(f"Object created, total={self._total_created}")
            return obj

    async def release(self, obj: T):
        """释放对象"""
        async with self._lock:
            obj_id = id(obj)
            if obj_id in self._in_use:
                self._in_use.discard(obj_id)
                self._total_released += 1

                # 如果池未满，回收对象
                if len(self._pool) < self._max_size:
                    self._cleanup(obj)
                    self._pool.append(obj)
                    logger.debug(f"Object released to pool, pool_size={len(self._pool)}")
                else:
                    logger.debug("Pool full, object discarded")

    def get_stats(self) -> ObjectPoolStats:
        """获取统计"""
        return ObjectPoolStats(
            pool_size=len(self._pool),
            in_use=len(self._in_use),
            available=self._max_size - len(self._pool) - len(self._in_use),
            total_created=self._total_created,
            total_released=self._total_released,
        )


# 全局内存监控器
_memory_monitor: MemoryMonitor | None = None


def get_memory_monitor() -> MemoryMonitor:
    """获取内存监控器"""
    global _memory_monitor
    if _memory_monitor is None:
        _memory_monitor = MemoryMonitor()
    return _memory_monitor


def start_memory_monitoring(interval: float = 10.0):
    """启动内存监控"""
    monitor = get_memory_monitor()
    monitor.start_monitoring(interval)


def stop_memory_monitoring():
    """停止内存监控"""
    monitor = get_memory_monitor()
    monitor.stop_monitoring()
