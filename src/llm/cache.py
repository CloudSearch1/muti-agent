"""
LLM 调用缓存

缓存 LLM 响应，减少重复调用，节省费用
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class LLMCache:
    """
    LLM 缓存
    
    功能:
    - 基于 prompt 哈希缓存响应
    - 支持 TTL
    - 缓存统计
    - 支持 Redis 或内存存储
    """
    
    def __init__(self, use_redis: bool = False, redis_url: Optional[str] = None):
        self._use_redis = use_redis
        self._redis = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "saves": 0,
        }
        
        if use_redis:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(redis_url or "redis://localhost:6379")
                logger.info("LLM cache using Redis")
            except Exception as e:
                logger.warning(f"Redis not available, using memory cache: {e}")
                self._use_redis = False
        else:
            logger.info("LLM cache using memory")
    
    def _compute_key(self, prompt: str, model: str, **kwargs) -> str:
        """计算缓存键"""
        # 包含所有影响响应的参数
        cache_data = {
            "prompt": prompt,
            "model": model,
            **kwargs,
        }
        
        # 计算哈希
        cache_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return f"llm:{model}:{hashlib.sha256(cache_str.encode()).hexdigest()}"
    
    async def get(self, prompt: str, model: str, **kwargs) -> Optional[str]:
        """
        获取缓存
        
        Args:
            prompt: 提示词
            model: 模型名称
            **kwargs: 其他参数（temperature 等）
        
        Returns:
            缓存的响应，如果不存在返回 None
        """
        key = self._compute_key(prompt, model, **kwargs)
        
        try:
            if self._use_redis and self._redis:
                # 从 Redis 获取
                data = await self._redis.get(key)
                if data:
                    self._stats["hits"] += 1
                    logger.debug(f"LLM cache hit (Redis): {key[:50]}")
                    return data.decode() if isinstance(data, bytes) else data
            else:
                # 从内存获取
                if key in self._memory_cache:
                    cache_entry = self._memory_cache[key]
                    
                    # 检查是否过期
                    if datetime.now() < cache_entry["expires"]:
                        self._stats["hits"] += 1
                        logger.debug(f"LLM cache hit (memory): {key[:50]}")
                        return cache_entry["response"]
                    else:
                        # 过期删除
                        del self._memory_cache[key]
            
            self._stats["misses"] += 1
            return None
            
        except Exception as e:
            logger.error(f"LLM cache get error: {e}")
            self._stats["misses"] += 1
            return None
    
    async def set(
        self,
        prompt: str,
        response: str,
        model: str,
        ttl_seconds: int = 3600,
        **kwargs,
    ):
        """
        设置缓存
        
        Args:
            prompt: 提示词
            response: LLM 响应
            model: 模型名称
            ttl_seconds: 缓存时间（秒）
            **kwargs: 其他参数
        """
        key = self._compute_key(prompt, model, **kwargs)
        
        try:
            if self._use_redis and self._redis:
                # 存储到 Redis
                await self._redis.setex(key, timedelta(seconds=ttl_seconds), response)
            else:
                # 存储到内存
                self._memory_cache[key] = {
                    "response": response,
                    "expires": datetime.now() + timedelta(seconds=ttl_seconds),
                    "created_at": datetime.now(),
                }
                
                # 限制缓存大小
                if len(self._memory_cache) > 1000:
                    # 删除最旧的 10%
                    oldest_keys = sorted(
                        self._memory_cache.keys(),
                        key=lambda k: self._memory_cache[k]["created_at"],
                    )[:100]
                    for k in oldest_keys:
                        del self._memory_cache[k]
            
            self._stats["saves"] += 1
            logger.debug(f"LLM cache saved: {key[:50]}")
            
        except Exception as e:
            logger.error(f"LLM cache set error: {e}")
    
    async def delete(self, prompt: str, model: str, **kwargs):
        """删除缓存"""
        key = self._compute_key(prompt, model, **kwargs)
        
        try:
            if self._use_redis and self._redis:
                await self._redis.delete(key)
            else:
                if key in self._memory_cache:
                    del self._memory_cache[key]
            
            logger.debug(f"LLM cache deleted: {key[:50]}")
            
        except Exception as e:
            logger.error(f"LLM cache delete error: {e}")
    
    async def clear(self):
        """清空缓存"""
        try:
            if self._use_redis and self._redis:
                # 使用 scan_iter 替代 keys()，避免阻塞
                keys = []
                async for key in self._redis.scan_iter(match="llm:*"):
                    keys.append(key)
                if keys:
                    await self._redis.delete(*keys)
            else:
                self._memory_cache.clear()

            logger.info("LLM cache cleared")

        except Exception as e:
            logger.error(f"LLM cache clear error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "saves": self._stats["saves"],
            "hit_rate": f"{hit_rate:.2f}%",
            "backend": "redis" if self._use_redis else "memory",
            "memory_cache_size": len(self._memory_cache),
        }
    
    async def close(self):
        """关闭连接"""
        if self._redis:
            await self._redis.close()
            logger.info("LLM cache Redis connection closed")


# 全局缓存实例
_cache: Optional[LLMCache] = None


def get_llm_cache(use_redis: bool = False, redis_url: Optional[str] = None) -> LLMCache:
    """获取 LLM 缓存实例"""
    global _cache
    if _cache is None:
        _cache = LLMCache(use_redis=use_redis, redis_url=redis_url)
    return _cache


async def init_llm_cache(use_redis: bool = False, redis_url: Optional[str] = None) -> LLMCache:
    """初始化 LLM 缓存"""
    global _cache
    _cache = LLMCache(use_redis=use_redis, redis_url=redis_url)
    logger.info("LLM cache initialized")
    return _cache


# 装饰器：自动缓存 LLM 调用
def cache_llm_response(ttl_seconds: int = 3600):
    """
    装饰器：自动缓存 LLM 调用
    
    用法:
        @cache_llm_response(ttl_seconds=3600)
        async def generate(prompt: str, model: str) -> str:
            ...
    """
    def decorator(func):
        async def wrapper(self, prompt: str, model: str = "default", **kwargs):
            # 获取缓存
            cache = get_llm_cache()
            cached = await cache.get(prompt, model, **kwargs)
            
            if cached:
                return cached
            
            # 调用函数
            result = await func(self, prompt, model, **kwargs)
            
            # 缓存结果
            await cache.set(prompt, result, model, ttl_seconds, **kwargs)
            
            return result
        
        return wrapper
    return decorator
