"""
RAG 检索引擎模块

提供检索增强生成（RAG）核心功能。

版本：2.0.0
更新时间：2026-03-12
改进：
- 实现混合检索（语义 + 关键词）
- 支持 BM25 关键词搜索
- 结果融合和重排序
"""

import re
from collections import Counter
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


def simple_tokenize(text: str) -> list[str]:
    """
    简单分词器
    
    支持中英文混合文本
    """
    # 转小写
    text = text.lower()
    # 分割中文字符
    chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
    # 分割英文单词
    english_words = re.findall(r'[a-z]+', text)
    # 合并结果
    tokens = []
    for chars in chinese_chars:
        # 中文按字符分割
        tokens.extend(list(chars))
    tokens.extend(english_words)
    return tokens


class BM25Scorer:
    """
    BM25 相关性评分器
    
    用于关键词搜索的排序算法
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs: dict[str, int] = {}
        self.doc_lens: list[int] = []
        self.avgdl = 0.0
        self.n_docs = 0
    
    def fit(self, documents: list[str]):
        """训练 BM25 模型"""
        self.n_docs = len(documents)
        self.doc_freqs = Counter()
        self.doc_lens = []
        
        for doc in documents:
            tokens = simple_tokenize(doc)
            self.doc_lens.append(len(tokens))
            # 文档词频
            seen = set()
            for token in tokens:
                if token not in seen:
                    self.doc_freqs[token] += 1
                    seen.add(token)
        
        # 平均文档长度
        self.avgdl = sum(self.doc_lens) / self.n_docs if self.n_docs > 0 else 0
    
    def score(self, query: str, documents: list[str]) -> list[float]:
        """
        计算 BM25 分数
        
        Args:
            query: 查询文本
            documents: 文档列表
            
        Returns:
            每个文档的 BM25 分数
        """
        query_tokens = simple_tokenize(query)
        scores = []
        
        for i, doc in enumerate(documents):
            doc_tokens = simple_tokenize(doc)
            doc_len = self.doc_lens[i] if i < len(self.doc_lens) else len(doc_tokens)
            
            score = 0.0
            for token in query_tokens:
                # IDF
                df = self.doc_freqs.get(token, 0)
                idf = (
                    (self.n_docs - df + 0.5) / (df + 0.5) + 1
                    if df > 0 else 0
                )
                
                # TF
                tf = doc_tokens.count(token)
                
                # BM25 公式
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += idf * numerator / denominator
            
            scores.append(score)
        
        return scores


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
        alpha: float = 0.5,
    ) -> list[SearchResult]:
        """
        混合搜索（语义 + 关键词）

        结合语义向量搜索和关键词 BM25 搜索，通过加权融合获得更好的检索效果。

        Args:
            query: 语义查询
            keyword_query: 关键词查询（如未提供，使用 query）
            top_k: 检索数量
            alpha: 语义搜索权重（0-1），1-alpha 为关键词搜索权重

        Returns:
            检索结果列表

        算法说明：
            1. 执行语义向量搜索，获取 top_k * 2 个结果
            2. 执行关键词 BM25 搜索，获取 top_k * 2 个结果
            3. 使用 RR（Reciprocal Rank）融合两种结果
            4. 按融合分数排序返回 top_k 个结果
        """
        top_k = top_k or self.top_k
        keyword_query = keyword_query or query
        
        # 如果关键词查询与语义查询相同，且 alpha 为 1，直接使用语义搜索
        if keyword_query == query and alpha >= 1.0:
            return await self.retrieve(query, top_k=top_k)

        # 1. 语义搜索（获取更多结果以便融合）
        semantic_results = await self.retrieve(query, top_k=top_k * 2)
        
        # 如果没有关键词查询或 alpha 为 1，直接返回语义结果
        if not keyword_query or alpha >= 1.0:
            return semantic_results[:top_k]
        
        # 2. 关键词搜索
        keyword_results = await self._keyword_search(keyword_query, top_k * 2)
        
        # 3. 结果融合
        merged_results = self._merge_results(
            semantic_results=semantic_results,
            keyword_results=keyword_results,
            alpha=alpha,
            top_k=top_k,
        )

        self.logger.debug(
            "Hybrid search completed",
            query=query[:50],
            keyword_query=keyword_query[:50] if keyword_query else None,
            semantic_count=len(semantic_results),
            keyword_count=len(keyword_results),
            merged_count=len(merged_results),
            alpha=alpha,
        )

        return merged_results

    async def _keyword_search(
        self,
        query: str,
        top_k: int,
    ) -> list[SearchResult]:
        """
        关键词搜索（BM25）
        
        Args:
            query: 关键词查询
            top_k: 返回数量
            
        Returns:
            搜索结果列表
        """
        try:
            # 从向量存储获取所有文档（或使用缓存）
            # 这里我们使用向量存储的搜索功能，但使用不同的查询方式
            # 先获取语义搜索结果作为候选集
            candidate_results = await self.retrieve(query, top_k=top_k * 3)
            
            if not candidate_results:
                return []
            
            # 提取候选文档内容
            documents = [r.content for r in candidate_results]
            
            # 使用 BM25 评分
            scorer = BM25Scorer()
            scorer.fit(documents)
            scores = scorer.score(query, documents)
            
            # 按分数排序
            scored_results = list(zip(scores, candidate_results))
            scored_results.sort(key=lambda x: x[0], reverse=True)
            
            # 更新结果的分数
            results = []
            for score, result in scored_results[:top_k]:
                # 创建新的 SearchResult，更新分数
                results.append(SearchResult(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    document_title=result.document_title,
                    content=result.content,
                    score=score,  # 使用 BM25 分数
                    metadata=result.metadata,
                ))
            
            return results
            
        except Exception as e:
            self.logger.warning("Keyword search failed", error=str(e))
            return []

    def _merge_results(
        self,
        semantic_results: list[SearchResult],
        keyword_results: list[SearchResult],
        alpha: float,
        top_k: int,
    ) -> list[SearchResult]:
        """
        融合语义搜索和关键词搜索结果
        
        使用 Reciprocal Rank Fusion (RRF) 算法
        
        Args:
            semantic_results: 语义搜索结果
            keyword_results: 关键词搜索结果
            alpha: 语义搜索权重
            top_k: 返回数量
            
        Returns:
            融合后的结果
        """
        # 使用 chunk_id 作为唯一标识
        result_map: dict[str, SearchResult] = {}
        
        # RRF 参数
        k = 60  # RRF 常数
        
        # 计算语义搜索的 RRF 分数
        semantic_scores: dict[str, float] = {}
        for rank, result in enumerate(semantic_results):
            chunk_id = result.chunk_id
            result_map[chunk_id] = result
            semantic_scores[chunk_id] = 1.0 / (k + rank + 1)
        
        # 计算关键词搜索的 RRF 分数
        keyword_scores: dict[str, float] = {}
        for rank, result in enumerate(keyword_results):
            chunk_id = result.chunk_id
            if chunk_id not in result_map:
                result_map[chunk_id] = result
            keyword_scores[chunk_id] = 1.0 / (k + rank + 1)
        
        # 融合分数
        final_scores: dict[str, float] = {}
        for chunk_id in result_map:
            sem_score = semantic_scores.get(chunk_id, 0.0)
            kw_score = keyword_scores.get(chunk_id, 0.0)
            # 加权融合
            final_scores[chunk_id] = alpha * sem_score + (1 - alpha) * kw_score
        
        # 按融合分数排序
        sorted_chunk_ids = sorted(
            final_scores.keys(),
            key=lambda x: final_scores[x],
            reverse=True
        )
        
        # 构建最终结果
        results = []
        for chunk_id in sorted_chunk_ids[:top_k]:
            result = result_map[chunk_id]
            # 创建新的 SearchResult，更新分数
            results.append(SearchResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                document_title=result.document_title,
                content=result.content,
                score=final_scores[chunk_id],
                metadata={
                    **result.metadata,
                    "semantic_score": semantic_scores.get(chunk_id, 0.0),
                    "keyword_score": keyword_scores.get(chunk_id, 0.0),
                    "fusion_score": final_scores[chunk_id],
                },
            ))
        
        return results

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
