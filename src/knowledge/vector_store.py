"""
知识库向量存储模块

封装 RAGStore，提供知识库专用的向量存储功能。
"""

from typing import Any, Optional

import structlog

from ..memory import RAGStore, SimpleEmbeddingProvider
from .exceptions import VectorStoreOperationError
from .types import Chunk, KnowledgeStats, SearchResult

logger = structlog.get_logger(__name__)

# 默认配置
DEFAULT_COLLECTION = "intelliteam_knowledge"
DEFAULT_PERSIST_DIR = "./data/knowledge/vectordb"


class KnowledgeVectorStore:
    """
    知识库向量存储

    封装 RAGStore，提供文档分块的向量存储和语义搜索功能。

    Example:
        >>> store = KnowledgeVectorStore()
        >>> await store.initialize()
        >>> await store.add_document_chunks("doc1", chunks)
        >>> results = await store.search("query", top_k=5)
    """

    def __init__(
        self,
        rag_store: RAGStore | None = None,
        persist_directory: str = DEFAULT_PERSIST_DIR,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        """
        初始化向量存储

        Args:
            rag_store: RAGStore 实例（可选）
            persist_directory: 持久化目录
            collection_name: 集合名称
        """
        if rag_store:
            self._rag_store = rag_store
        else:
            # 创建默认的 RAGStore
            self._rag_store = RAGStore(
                backend="chroma",
                persist_directory=persist_directory,
                collection_name=collection_name,
                embedding_provider=SimpleEmbeddingProvider(),
            )

        self._initialized = False
        self.logger = logger.bind(component="knowledge_vector_store")

    async def initialize(self) -> None:
        """初始化向量存储"""
        if self._initialized:
            return

        try:
            await self._rag_store.initialize()
            self._initialized = True
            self.logger.info("KnowledgeVectorStore initialized")
        except Exception as e:
            raise VectorStoreOperationError(
                f"Failed to initialize vector store: {e}",
                operation="initialize",
            ) from e

    async def add_document_chunks(
        self,
        document_id: str,
        chunks: list[Chunk],
        document_title: str | None = None,
    ) -> list[str]:
        """
        添加文档分块到向量存储

        Args:
            document_id: 文档 ID
            chunks: 分块列表
            document_title: 文档标题（用于元数据）

        Returns:
            分块 ID 列表

        Raises:
            VectorStoreOperationError: 操作失败
        """
        if not self._initialized:
            await self.initialize()

        if not chunks:
            return []

        try:
            # 准备批量数据
            items = []
            for chunk in chunks:
                metadata = {
                    **chunk.metadata,
                    "document_id": document_id,
                    "position": chunk.position,
                    "document_title": document_title or "",
                }
                items.append({
                    "content": chunk.content,
                    "metadata": metadata,
                    "memory_id": chunk.id,  # 使用 chunk.id 作为 memory_id
                })

            # 批量添加
            ids = await self._rag_store.add_memories_batch(items)

            self.logger.info(
                "Document chunks added",
                document_id=document_id,
                chunks_count=len(ids),
            )

            return ids

        except Exception as e:
            self.logger.error(
                "Failed to add document chunks",
                document_id=document_id,
                error=str(e),
            )
            raise VectorStoreOperationError(
                f"Failed to add document chunks: {e}",
                operation="add_document_chunks",
            ) from e

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """
        语义搜索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_metadata: 元数据过滤条件
            min_score: 最小分数阈值

        Returns:
            搜索结果列表
        """
        if not self._initialized:
            await self.initialize()

        if not query or not query.strip():
            return []

        try:
            # 调用 RAGStore 搜索
            results = await self._rag_store.search(
                query=query,
                top_k=top_k,
                filter_metadata=filter_metadata,
            )

            # 转换为 SearchResult
            search_results = []
            for result in results:
                # 计算相似度分数（ChromaDB 返回的是距离，需要转换）
                distance = result.get("distance", 0)
                # 假设使用余弦距离，分数 = 1 - distance
                score = 1.0 - distance if distance <= 1 else 0.0

                if score < min_score:
                    continue

                metadata = result.get("metadata", {})
                search_results.append(SearchResult(
                    chunk_id=result.get("memory_id", ""),
                    document_id=metadata.get("document_id", ""),
                    content=result.get("content", ""),
                    score=score,
                    metadata=metadata,
                    document_title=metadata.get("document_title"),
                ))

            return search_results

        except Exception as e:
            self.logger.error("Search failed", error=str(e))
            return []

    async def delete_document_chunks(self, document_id: str) -> int:
        """
        删除文档的所有分块

        Args:
            document_id: 文档 ID

        Returns:
            删除的数量
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 搜索该文档的所有分块
            results = await self._rag_store.search(
                query="",  # 空查询
                top_k=1000,  # 足够大的数量
                filter_metadata={"document_id": document_id},
            )

            if not results:
                return 0

            # 批量删除
            chunk_ids = [r.get("memory_id") for r in results if r.get("memory_id")]
            deleted = await self._rag_store.delete_memories_batch(chunk_ids)

            self.logger.info(
                "Document chunks deleted",
                document_id=document_id,
                count=deleted,
            )

            return deleted

        except Exception as e:
            self.logger.error(
                "Failed to delete document chunks",
                document_id=document_id,
                error=str(e),
            )
            return 0

    async def get_chunk(self, chunk_id: str) -> SearchResult | None:
        """
        获取单个分块

        Args:
            chunk_id: 分块 ID

        Returns:
            搜索结果，不存在则返回 None
        """
        if not self._initialized:
            await self.initialize()

        try:
            result = await self._rag_store.get_memory(chunk_id)
            if not result:
                return None

            metadata = result.get("metadata", {})
            return SearchResult(
                chunk_id=chunk_id,
                document_id=metadata.get("document_id", ""),
                content=result.get("content", ""),
                score=1.0,  # 直接获取，分数为 1
                metadata=metadata,
                document_title=metadata.get("document_title"),
            )

        except Exception as e:
            self.logger.error("Failed to get chunk", chunk_id=chunk_id, error=str(e))
            return None

    async def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息
        """
        if not self._initialized:
            await self.initialize()

        try:
            stats = await self._rag_store.get_stats()
            return {
                "backend": stats.get("backend", "unknown"),
                "total_chunks": stats.get("total_memories", 0),
                "embedding_dimension": stats.get("embedding_dimension", 0),
                "persist_directory": stats.get("persist_directory", ""),
            }
        except Exception as e:
            self.logger.error("Failed to get stats", error=str(e))
            return {"error": str(e)}

    async def count(self) -> int:
        """
        获取分块总数

        Returns:
            分块数量
        """
        if not self._initialized:
            await self.initialize()

        try:
            return await self._rag_store.count()
        except Exception:
            return 0

    async def clear(self) -> int:
        """
        清空所有数据

        Returns:
            删除的数量
        """
        if not self._initialized:
            await self.initialize()

        try:
            return await self._rag_store.clear_all()
        except Exception as e:
            self.logger.error("Failed to clear vector store", error=str(e))
            return 0