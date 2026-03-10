"""
RAG 检索引擎模块

提供检索增强生成（RAG）核心功能。
"""

from typing import Any

import structlog

from ..llm.llm_provider import BaseProvider, get_llm
from .types import SearchResult
from .vector_store import KnowledgeVectorStore

logger = structlog.get_logger(__name__)

# 默认配置
DEFAULT_TOP_K = 5
DEFAULT_MAX_CONTEXT_TOKENS = 3000
DEFAULT_MIN_SCORE = 0.3


class RAGEngine:
    """
    RAG 检索引擎

    提供文档检索、上下文构建等功能。

    Example:
        >>> engine = RAGEngine(vector_store)
        >>> chunks = await engine.retrieve("query", top_k=5)
        >>> context = engine.build_context(chunks)
    """

    def __init__(
        self,
        vector_store: KnowledgeVectorStore,
        llm_provider: BaseProvider | None = None,
        top_k: int = DEFAULT_TOP_K,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> None:
        """
        初始化 RAG 引擎

        Args:
            vector_store: 向量存储
            llm_provider: LLM 提供者（可选）
            top_k: 检索数量
            max_context_tokens: 最大上下文 token 数
            min_score: 最小相似度分数
        """
        self.vector_store = vector_store
        self.llm_provider = llm_provider or get_llm()
        self.top_k = top_k
        self.max_context_tokens = max_context_tokens
        self.min_score = min_score

        self.logger = logger.bind(component="rag_engine")

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        """
        检索相关文档

        Args:
            query: 查询文本
            top_k: 检索数量
            filters: 过滤条件
            min_score: 最小分数

        Returns:
            检索结果列表
        """
        top_k = top_k or self.top_k
        min_score = min_score if min_score is not None else self.min_score

        if not query or not query.strip():
            return []

        try:
            results = await self.vector_store.search(
                query=query,
                top_k=top_k,
                filter_metadata=filters,
                min_score=min_score,
            )

            self.logger.debug(
                "Retrieval completed",
                query=query[:50],
                results_count=len(results),
            )

            return results

        except Exception as e:
            self.logger.error("Retrieval failed", error=str(e))
            return []

    async def hybrid_search(
        self,
        query: str,
        keyword_query: str | None = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        混合搜索（语义 + 关键词）

        Args:
            query: 语义查询
            keyword_query: 关键词查询
            top_k: 检索数量

        Returns:
            检索结果列表
        """
        top_k = top_k or self.top_k

        # 语义搜索
        semantic_results = await self.retrieve(query, top_k=top_k)

        # 如果没有关键词查询，直接返回语义结果
        if not keyword_query:
            return semantic_results

        # TODO: 实现关键词搜索和融合
        # 目前简单返回语义搜索结果
        return semantic_results

    def build_context(
        self,
        results: list[SearchResult],
        max_tokens: int | None = None,
        include_metadata: bool = True,
    ) -> str:
        """
        构建上下文

        Args:
            results: 检索结果
            max_tokens: 最大 token 数
            include_metadata: 是否包含元数据

        Returns:
            构建的上下文字符串
        """
        max_tokens = max_tokens or self.max_context_tokens

        if not results:
            return ""

        context_parts = []
        total_length = 0
        # 简单估计：1 token ≈ 4 字符（中文）或 0.75 词（英文）
        chars_per_token = 2  # 保守估计

        for i, result in enumerate(results):
            # 构建单个片段
            if include_metadata:
                source_info = f"[来源 {i + 1}"
                if result.document_title:
                    source_info += f": {result.document_title}"
                source_info += "]"
                chunk_text = f"{source_info}\n{result.content}\n"
            else:
                chunk_text = f"{result.content}\n"

            chunk_length = len(chunk_text)
            estimated_tokens = chunk_length // chars_per_token

            if total_length + estimated_tokens > max_tokens:
                # 超出限制，截断
                remaining_tokens = max_tokens - total_length
                remaining_chars = remaining_tokens * chars_per_token
                if remaining_chars > 100:  # 至少保留 100 字符
                    chunk_text = chunk_text[:remaining_chars] + "..."
                    context_parts.append(chunk_text)
                break

            context_parts.append(chunk_text)
            total_length += estimated_tokens

        context = "\n".join(context_parts)

        self.logger.debug(
            "Context built",
            chunks_count=len(context_parts),
            total_chars=len(context),
            estimated_tokens=total_length,
        )

        return context

    def format_sources(
        self,
        results: list[SearchResult],
        max_sources: int = 5,
    ) -> list[dict[str, Any]]:
        """
        格式化来源信息

        Args:
            results: 检索结果
            max_sources: 最大来源数

        Returns:
            来源信息列表
        """
        sources = []
        seen_documents = set()

        for result in results[:max_sources * 2]:  # 多获取一些以去重
            doc_id = result.document_id
            if doc_id in seen_documents:
                continue

            seen_documents.add(doc_id)
            sources.append({
                "document_id": doc_id,
                "document_title": result.document_title,
                "chunk_id": result.chunk_id,
                "score": round(result.score, 3),
                "preview": result.content[:200] + "..." if len(result.content) > 200 else result.content,
            })

            if len(sources) >= max_sources:
                break

        return sources

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        重排序结果

        使用 LLM 对结果进行重排序。

        Args:
            query: 查询
            results: 原始结果
            top_k: 返回数量

        Returns:
            重排序后的结果
        """
        top_k = top_k or len(results)

        if len(results) <= 1:
            return results

        try:
            # 使用 LLM 进行重排序
            prompt = self._build_rerank_prompt(query, results[:10])  # 最多处理 10 个

            # 调用 LLM
            response = await self.llm_provider.generate(
                prompt=prompt,
                temperature=0.1,  # 低温度以获得一致性
                max_tokens=500,
            )

            # 解析响应
            ranked_indices = self._parse_rerank_response(response, len(results))

            # 按新顺序排列
            reranked = []
            for idx in ranked_indices[:top_k]:
                if 0 <= idx < len(results):
                    reranked.append(results[idx])

            # 补充未在响应中的结果
            for result in results:
                if result not in reranked and len(reranked) < top_k:
                    reranked.append(result)

            return reranked

        except Exception as e:
            self.logger.warning("Rerank failed, using original order", error=str(e))
            return results[:top_k]

    def _build_rerank_prompt(
        self,
        query: str,
        results: list[SearchResult],
    ) -> str:
        """构建重排序提示"""
        prompt = f"""请根据查询与以下文档片段的相关性，对它们进行排序。

查询: {query}

文档片段:
"""
        for i, result in enumerate(results):
            prompt += f"\n[{i}] {result.content[:300]}...\n"

        prompt += """

请按照相关性从高到低排序，返回排序后的编号列表（JSON 数组格式）。
例如: [2, 0, 3, 1, 4]

只返回 JSON 数组，不要有其他文字。"""

        return prompt

    def _parse_rerank_response(
        self,
        response: str,
        max_index: int,
    ) -> list[int]:
        """解析重排序响应"""
        import json
        import re

        try:
            # 尝试提取 JSON 数组
            match = re.search(r'\[[\d,\s]+\]', response)
            if match:
                indices = json.loads(match.group())
                # 验证索引
                return [i for i in indices if isinstance(i, int) and 0 <= i < max_index]
        except Exception:
            pass

        return list(range(max_index))
