"""
LLM 语义缓存

使用语义相似度进行智能缓存，命中相似 prompt
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# 线程池用于异步执行同步的嵌入计算
_executor = ThreadPoolExecutor(max_workers=2)

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not installed, semantic cache unavailable")

try:
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed, semantic cache unavailable")


class SemanticCache:
    """
    语义缓存

    功能:
    - 基于语义相似度缓存
    - 支持相似度阈值
    - 自动过期清理
    - 统计命中率
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.9,
        max_cache_size: int = 1000,
        ttl_seconds: int = 3600,
    ):
        self.similarity_threshold = similarity_threshold
        self.max_cache_size = max_cache_size
        self.ttl_seconds = ttl_seconds

        # 缓存存储：embedding_hash -> {embedding, response, timestamp}
        self._cache: dict[str, dict[str, Any]] = {}
        self._stats = {
            "hits": 0,
            "misses": 0,
            "semantic_hits": 0,
        }

        # 初始化模型
        self._model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self._model = SentenceTransformer(model_name)
                logger.info(f"Semantic cache initialized with model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load semantic model: {e}")

    def _get_embedding_sync(self, text: str) -> np.ndarray | None:
        """获取文本的语义嵌入（同步版本）"""
        if not self._model:
            return None

        try:
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return None

    async def _get_embedding(self, text: str) -> np.ndarray | None:
        """获取文本的语义嵌入（异步版本）"""
        if not self._model:
            return None

        try:
            # 在线程池中执行同步的嵌入计算
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                _executor,
                self._get_embedding_sync,
                text,
            )
            return embedding
        except Exception as e:
            logger.error(f"Failed to get embedding asynchronously: {e}")
            return None

    def _compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """计算两个嵌入的相似度"""
        if not SKLEARN_AVAILABLE:
            return 0.0

        try:
            similarity = cosine_similarity([emb1], [emb2])[0][0]
            return float(similarity)
        except Exception as e:
            logger.error(f"Failed to compute similarity: {e}")
            return 0.0

    def _compute_hash(self, text: str) -> str:
        """计算文本哈希（用于精确匹配）"""
        return hashlib.sha256(text.encode()).hexdigest()

    async def get(
        self,
        prompt: str,
        model: str = "default",
        **kwargs,
    ) -> tuple[str | None, str]:
        """
        获取缓存

        Args:
            prompt: 提示词
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            (缓存响应，命中类型) - 命中类型："exact" | "semantic" | "miss"
        """
        # 1. 精确匹配
        exact_key = self._compute_hash(f"{prompt}:{model}:{json.dumps(kwargs, sort_keys=True)}")

        if exact_key in self._cache:
            cache_entry = self._cache[exact_key]

            # 检查是否过期
            if datetime.now() < cache_entry["expires"]:
                self._stats["hits"] += 1
                logger.debug(f"Exact cache hit: {exact_key[:30]}")
                return cache_entry["response"], "exact"
            else:
                # 过期删除
                del self._cache[exact_key]

        # 2. 语义匹配
        if self._model:
            prompt_embedding = await self._get_embedding(prompt)

            if prompt_embedding is not None:
                best_match = None
                best_similarity = 0.0

                # 查找最相似的缓存
                for _cache_key, cache_entry in self._cache.items():
                    if cache_entry.get("model") != model:
                        continue

                    if datetime.now() >= cache_entry["expires"]:
                        continue

                    similarity = self._compute_similarity(
                        prompt_embedding,
                        cache_entry["embedding"],
                    )

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = cache_entry

                # 检查是否达到阈值
                if best_match and best_similarity >= self.similarity_threshold:
                    self._stats["semantic_hits"] += 1
                    self._stats["hits"] += 1
                    logger.debug(
                        f"Semantic cache hit: similarity={best_similarity:.3f}",
                    )
                    return best_match["response"], "semantic"

        # 3. 未命中
        self._stats["misses"] += 1
        return None, "miss"

    async def set(
        self,
        prompt: str,
        response: str,
        model: str = "default",
        ttl_seconds: int | None = None,
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
        ttl = ttl_seconds or self.ttl_seconds
        exact_key = self._compute_hash(f"{prompt}:{model}:{json.dumps(kwargs, sort_keys=True)}")

        # 获取语义嵌入
        embedding = None
        if self._model:
            embedding = await self._get_embedding(prompt)

        # 存储缓存
        self._cache[exact_key] = {
            "prompt": prompt,
            "response": response,
            "model": model,
            "embedding": embedding,
            "created_at": datetime.now(),
            "expires": datetime.now() + timedelta(seconds=ttl),
        }

        # 限制缓存大小
        if len(self._cache) > self.max_cache_size:
            await self._evict_oldest()

        logger.debug(f"Cache set: {exact_key[:30]}")

    async def _evict_oldest(self):
        """淘汰最旧的缓存"""
        if not self._cache:
            return

        # 找到最旧的 10%
        evict_count = max(1, int(self.max_cache_size * 0.1))
        oldest_keys = sorted(
            self._cache.keys(),
            key=lambda k: self._cache[k]["created_at"],
        )[:evict_count]

        for key in oldest_keys:
            del self._cache[key]

        logger.debug(f"Evicted {evict_count} old cache entries")

    async def clear(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("Semantic cache cleared")

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        semantic_rate = (self._stats["semantic_hits"] / self._stats["hits"] * 100) if self._stats["hits"] > 0 else 0

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "semantic_hits": self._stats["semantic_hits"],
            "hit_rate": f"{hit_rate:.2f}%",
            "semantic_hit_rate": f"{semantic_rate:.2f}%",
            "cache_size": len(self._cache),
            "max_cache_size": self.max_cache_size,
            "model_available": self._model is not None,
        }


# 全局缓存实例
_semantic_cache: SemanticCache | None = None


def get_semantic_cache(
    model_name: str = "all-MiniLM-L6-v2",
    similarity_threshold: float = 0.9,
    **kwargs,
) -> SemanticCache:
    """获取语义缓存实例"""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCache(
            model_name=model_name,
            similarity_threshold=similarity_threshold,
            **kwargs,
        )
    return _semantic_cache


async def init_semantic_cache(
    model_name: str = "all-MiniLM-L6-v2",
    similarity_threshold: float = 0.9,
    **kwargs,
) -> SemanticCache:
    """初始化语义缓存"""
    global _semantic_cache
    _semantic_cache = SemanticCache(
        model_name=model_name,
        similarity_threshold=similarity_threshold,
        **kwargs,
    )
    logger.info("Semantic cache initialized")
    return _semantic_cache


# 装饰器：自动使用语义缓存
def semantic_cache_response(
    model_name: str = "default",
    similarity_threshold: float = 0.9,
    ttl_seconds: int = 3600,
):
    """
    装饰器：自动使用语义缓存

    用法:
        @semantic_cache_response(similarity_threshold=0.95)
        async def generate(prompt: str, model: str) -> str:
            ...
    """
    def decorator(func):
        async def wrapper(self, prompt: str, model: str = model_name, **kwargs):
            # 获取缓存
            cache = get_semantic_cache(similarity_threshold=similarity_threshold)
            cached, hit_type = await cache.get(prompt, model, **kwargs)

            if cached:
                logger.debug(f"Cache {hit_type} hit for {func.__name__}")
                return cached

            # 调用函数
            result = await func(self, prompt, model, **kwargs)

            # 缓存结果
            await cache.set(prompt, result, model, ttl_seconds, **kwargs)

            return result

        return wrapper
    return decorator
