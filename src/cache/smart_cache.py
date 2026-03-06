"""
缓存预热和失效策略

智能缓存管理，提高命中率
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class CacheStrategy(str, Enum):
    """缓存策略"""
    LAZY_LOAD = "lazy_load"  # 懒加载
    PRE_WARM = "pre_warm"  # 预热
    TTL = "ttl"  # 固定过期时间
    SLIDING_TTL = "sliding_ttl"  # 滑动过期时间
    LRU = "lru"  # 最近最少使用
    LFU = "lfu"  # 最不经常使用


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_access: datetime = field(default_factory=datetime.utcnow)
    tags: Set[str] = field(default_factory=set)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def touch(self):
        """更新访问时间"""
        self.last_access = datetime.utcnow()
        self.access_count += 1


class SmartCache:
    """
    智能缓存
    
    功能:
    - 多种缓存策略
    - 缓存预热
    - 智能失效
    - 标签管理
    - 统计分析
    """
    
    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: int = 3600,
        strategy: CacheStrategy = CacheStrategy.LRU,
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.strategy = strategy
        
        self._cache: Dict[str, CacheEntry] = {}
        self._prewarm_tasks: List[str] = []
        self._invalidation_rules: Dict[str, Callable] = {}
        self._tags: Dict[str, Set[str]] = {}  # tag -> keys
        
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "prewarms": 0,
            "invalidations": 0,
        }
        
        logger.info(f"SmartCache initialized (max_size={max_size}, strategy={strategy.value})")
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        entry = self._cache.get(key)
        
        if entry is None:
            self._stats["misses"] += 1
            return None
        
        if entry.is_expired():
            await self.delete(key)
            self._stats["misses"] += 1
            return None
        
        # 更新访问统计
        entry.touch()
        self._stats["hits"] += 1
        
        return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ):
        """设置缓存"""
        # 检查容量
        if len(self._cache) >= self.max_size:
            await self._evict()
        
        # 计算过期时间
        if ttl is not None:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        elif self.strategy == CacheStrategy.TTL:
            expires_at = datetime.utcnow() + timedelta(seconds=self.default_ttl)
        else:
            expires_at = None
        
        # 创建条目
        entry = CacheEntry(
            key=key,
            value=value,
            expires_at=expires_at,
            tags=set(tags or []),
        )
        
        self._cache[key] = entry
        
        # 更新标签索引
        if tags:
            for tag in tags:
                if tag not in self._tags:
                    self._tags[tag] = set()
                self._tags[tag].add(key)
        
        logger.debug(f"Cache set: {key}")
    
    async def delete(self, key: str):
        """删除缓存"""
        if key in self._cache:
            entry = self._cache[key]
            
            # 清理标签索引
            for tag in entry.tags:
                if tag in self._tags:
                    self._tags[tag].discard(key)
            
            del self._cache[key]
            logger.debug(f"Cache deleted: {key}")
    
    async def invalidate_by_tag(self, tag: str):
        """按标签失效"""
        keys = self._tags.get(tag, set())
        
        for key in list(keys):
            await self.delete(key)
        
        self._stats["invalidations"] += len(keys)
        logger.info(f"Invalidated {len(keys)} entries by tag: {tag}")
    
    async def invalidate_by_pattern(self, pattern: str):
        """按模式失效"""
        import re
        
        regex = re.compile(pattern)
        keys_to_delete = [key for key in self._cache.keys() if regex.match(key)]
        
        for key in keys_to_delete:
            await self.delete(key)
        
        logger.info(f"Invalidated {len(keys_to_delete)} entries by pattern: {pattern}")
    
    async def prewarm(self, keys: List[str], loader: Callable):
        """
        缓存预热
        
        Args:
            keys: 要预热的键列表
            loader: 加载函数 async def loader(key) -> value
        """
        self._prewarm_tasks.extend(keys)
        
        for key in keys:
            try:
                value = await loader(key)
                await self.set(key, value)
                self._stats["prewarms"] += 1
                
                logger.info(f"Prewarmed: {key}")
                
            except Exception as e:
                logger.error(f"Prewarm failed for {key}: {e}")
        
        # 清理预热任务列表
        self._prewarm_tasks = [k for k in self._prewarm_tasks if k not in keys]
    
    async def _evict(self):
        """淘汰缓存"""
        if not self._cache:
            return
        
        if self.strategy == CacheStrategy.LRU:
            # 淘汰最近最少使用
            oldest = min(self._cache.values(), key=lambda e: e.last_access)
            await self.delete(oldest.key)
        
        elif self.strategy == CacheStrategy.LFU:
            # 淘汰最不经常使用
            least_frequent = min(self._cache.values(), key=lambda e: e.access_count)
            await self.delete(least_frequent.key)
        
        elif self.strategy == CacheStrategy.TTL:
            # 淘汰最早过期
            expiring = [e for e in self._cache.values() if e.expires_at]
            if expiring:
                oldest = min(expiring, key=lambda e: e.expires_at)
                await self.delete(oldest.key)
        
        self._stats["evictions"] += 1
        logger.debug(f"Evicted cache entry (strategy={self.strategy.value})")
    
    def add_invalidation_rule(self, pattern: str, rule: Callable):
        """
        添加失效规则
        
        Args:
            pattern: 键模式
            rule: 失效判断函数 async def rule(key, value) -> bool
        """
        self._invalidation_rules[pattern] = rule
        logger.info(f"Invalidation rule added: {pattern}")
    
    async def check_invalidation_rules(self):
        """检查失效规则"""
        for pattern, rule in self._invalidation_rules.items():
            keys_to_check = [k for k in self._cache.keys() if pattern in k]
            
            for key in keys_to_check:
                entry = self._cache[key]
                
                try:
                    should_invalidate = await rule(key, entry.value)
                    
                    if should_invalidate:
                        await self.delete(key)
                        logger.info(f"Invalidated by rule: {key}")
                        
                except Exception as e:
                    logger.error(f"Invalidation rule check failed for {key}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            **self._stats,
            "total_operations": total,
            "hit_rate": f"{hit_rate:.2f}%",
            "cache_size": len(self._cache),
            "max_size": self.max_size,
            "strategy": self.strategy.value,
            "prewarm_tasks": len(self._prewarm_tasks),
        }
    
    async def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._tags.clear()
        self._prewarm_tasks.clear()
        
        logger.info("Cache cleared")


# ============ 缓存装饰器 ============

def cached(
    key_prefix: str = "",
    ttl: Optional[int] = None,
    strategy: CacheStrategy = CacheStrategy.LRU,
    tags: Optional[List[str]] = None,
):
    """
    缓存装饰器
    
    用法:
        @cached(key_prefix="user", ttl=3600, tags=["user"])
        async def get_user(user_id: int):
            ...
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            cache = get_smart_cache()
            
            # 生成缓存键
            import hashlib
            key_data = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"
            key = hashlib.md5(key_data.encode()).hexdigest()
            
            # 尝试从缓存获取
            value = await cache.get(key)
            
            if value is not None:
                return value
            
            # 执行函数
            value = await func(*args, **kwargs)
            
            # 存入缓存
            await cache.set(key, value, ttl=ttl, tags=tags)
            
            return value
        
        return wrapper
    return decorator


# ============ 全局缓存 ============

_cache: Optional[SmartCache] = None


def get_smart_cache() -> SmartCache:
    """获取智能缓存"""
    global _cache
    if _cache is None:
        _cache = SmartCache()
    return _cache


def init_smart_cache(**kwargs) -> SmartCache:
    """初始化智能缓存"""
    global _cache
    _cache = SmartCache(**kwargs)
    logger.info("Smart cache initialized")
    return _cache


async def start_cache_maintenance(interval_seconds: int = 60):
    """启动缓存维护任务"""
    cache = get_smart_cache()
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await cache.check_invalidation_rules()
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Cache maintenance failed: {e}")
