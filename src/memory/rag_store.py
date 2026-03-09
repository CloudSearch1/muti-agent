"""
RAG 向量存储模块

职责：提供基于向量数据库的 RAG（检索增强生成）功能

支持：
- ChromaDB 向量存储（默认）
- Milvus 向量存储（可选）
- 语义搜索
- 记忆检索
"""

import json
from datetime import datetime
from typing import Any

import structlog

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    chromadb = None
    ChromaSettings = None

try:
    from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False
    connections = None
    Collection = None
    CollectionSchema = None
    FieldSchema = None
    DataType = None

logger = structlog.get_logger(__name__)


class EmbeddingProvider:
    """嵌入向量提供者基类"""

    def embed(self, text: str) -> list[float]:
        """生成文本嵌入向量"""
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成嵌入向量"""
        return [self.embed(t) for t in texts]


class SimpleEmbeddingProvider(EmbeddingProvider):
    """
    简单嵌入提供者（备用）

    使用简单的哈希方法生成固定维度的向量。
    生产环境应替换为真实的嵌入模型。
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        """生成文本嵌入向量"""
        # 使用简单的哈希方法生成向量
        import hashlib

        # 生成确定性向量
        vector = []
        for i in range(self.dimension):
            hash_input = f"{text}_{i}"
            hash_val = hashlib.md5(hash_input.encode()).hexdigest()
            # 归一化到 [-1, 1]
            val = (int(hash_val[:8], 16) / (16**8)) * 2 - 1
            vector.append(val)

        # L2 归一化
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成嵌入向量"""
        return [self.embed(t) for t in texts]


class MemoryItem:
    """记忆项"""

    def __init__(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
        embedding: list[float] | None = None,
    ):
        self.memory_id = memory_id or self._generate_id()
        self.content = content
        self.metadata = metadata or {}
        self.embedding = embedding
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def _generate_id(self) -> str:
        import uuid

        return str(uuid.uuid4())

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class RAGStore:
    """
    RAG 向量存储

    支持 ChromaDB 和 Milvus 作为后端。
    提供语义搜索和记忆检索功能。
    """

    DEFAULT_COLLECTION = "intelliteam_memory"

    def __init__(
        self,
        backend: str = "chroma",
        persist_directory: str = "./data/vectordb",
        embedding_provider: EmbeddingProvider | None = None,
        collection_name: str = DEFAULT_COLLECTION,
        **kwargs,
    ):
        """
        初始化 RAG 存储

        Args:
            backend: 向量数据库类型 ('chroma' 或 'milvus')
            persist_directory: 持久化目录
            embedding_provider: 嵌入向量提供者
            collection_name: 集合名称
            **kwargs: 其他配置参数
        """
        self.backend = backend
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.kwargs = kwargs

        # 嵌入提供者
        self.embedding_provider = embedding_provider or SimpleEmbeddingProvider()

        # 向量存储客户端
        self._client = None
        self._collection = None

        self.logger = logger.bind(
            component="rag_store",
            backend=backend,
            collection=collection_name,
        )

        self.logger.info(
            "RAGStore initialized",
            backend=backend,
            persist_directory=persist_directory,
        )

    async def initialize(self) -> None:
        """初始化向量存储"""
        if self.backend == "chroma":
            await self._init_chroma()
        elif self.backend == "milvus":
            await self._init_milvus()
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    async def _init_chroma(self) -> None:
        """初始化 ChromaDB"""
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "ChromaDB is not installed. Install with: pip install chromadb"
            )

        import os

        os.makedirs(self.persist_directory, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # 获取或创建集合
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        self.logger.info(
            "ChromaDB initialized",
            collection=self.collection_name,
            count=self._collection.count(),
        )

    async def _init_milvus(self) -> None:
        """初始化 Milvus"""
        if not MILVUS_AVAILABLE:
            raise ImportError(
                "Milvus is not installed. Install with: pip install pymilvus"
            )

        host = self.kwargs.get("host", "localhost")
        port = self.kwargs.get("port", 19530)

        connections.connect(
            alias="default",
            host=host,
            port=port,
        )

        # 定义集合 schema
        fields = [
            FieldSchema(name="memory_id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_provider.dimension if hasattr(self.embedding_provider, 'dimension') else 384),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=64),
        ]

        schema = CollectionSchema(fields=fields, description="IntelliTeam Memory Collection")

        # 创建或获取集合
        if utility.has_collection(self.collection_name):
            self._collection = Collection(self.collection_name)
        else:
            self._collection = Collection(self.collection_name, schema=schema)
            # 创建索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }
            self._collection.create_index(field_name="embedding", index_params=index_params)

        self._collection.load()

        self.logger.info(
            "Milvus initialized",
            collection=self.collection_name,
            host=host,
            port=port,
        )

    async def add_memory(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
    ) -> str:
        """
        添加记忆

        Args:
            content: 记忆内容
            metadata: 元数据
            memory_id: 记忆 ID（可选）

        Returns:
            记忆 ID
        """
        if self._collection is None:
            await self.initialize()

        memory = MemoryItem(
            content=content,
            metadata=metadata or {},
            memory_id=memory_id,
        )

        # 生成嵌入向量
        memory.embedding = self.embedding_provider.embed(content)

        if self.backend == "chroma":
            self._collection.add(
                ids=[memory.memory_id],
                documents=[memory.content],
                embeddings=[memory.embedding],
                metadatas=[{
                    **memory.metadata,
                    "created_at": memory.created_at.isoformat(),
                }],
            )
        elif self.backend == "milvus":
            self._collection.insert([
                [memory.memory_id],
                [memory.content],
                [memory.embedding],
                [memory.metadata],
                [memory.created_at.isoformat()],
            ])

        self.logger.debug(
            "Memory added",
            memory_id=memory.memory_id,
            content_length=len(content),
        )

        return memory.memory_id

    async def add_memories_batch(
        self,
        items: list[dict[str, Any]],
    ) -> list[str]:
        """
        批量添加记忆

        Args:
            items: 记忆项列表，每项包含 content 和 metadata

        Returns:
            记忆 ID 列表
        """
        if self._collection is None:
            await self.initialize()

        memories = []
        for item in items:
            memory = MemoryItem(
                content=item.get("content", ""),
                metadata=item.get("metadata", {}),
            )
            memory.embedding = self.embedding_provider.embed(memory.content)
            memories.append(memory)

        # 批量插入
        ids = [m.memory_id for m in memories]
        documents = [m.content for m in memories]
        embeddings = [m.embedding for m in memories]
        metadatas = [{
            **m.metadata,
            "created_at": m.created_at.isoformat(),
        } for m in memories]

        if self.backend == "chroma":
            self._collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        elif self.backend == "milvus":
            self._collection.insert([
                ids,
                documents,
                embeddings,
                [m.metadata for m in memories],
                [m.created_at.isoformat() for m in memories],
            ])

        self.logger.info(
            "Batch memories added",
            count=len(memories),
        )

        return ids

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        语义搜索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_metadata: 元数据过滤条件

        Returns:
            搜索结果列表
        """
        if self._collection is None:
            await self.initialize()

        # 生成查询向量
        query_embedding = self.embedding_provider.embed(query)

        if self.backend == "chroma":
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_metadata,
            )

            # 格式化结果
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "memory_id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                })

            return formatted_results

        elif self.backend == "milvus":
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
            results = self._collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["memory_id", "content", "metadata", "created_at"],
            )

            formatted_results = []
            for hits in results:
                for hit in hits:
                    formatted_results.append({
                        "memory_id": hit.entity.get("memory_id"),
                        "content": hit.entity.get("content"),
                        "metadata": hit.entity.get("metadata", {}),
                        "distance": hit.distance,
                    })

            return formatted_results

        return []

    async def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        """
        获取单个记忆

        Args:
            memory_id: 记忆 ID

        Returns:
            记忆数据，不存在则返回 None
        """
        if self._collection is None:
            await self.initialize()

        if self.backend == "chroma":
            results = self._collection.get(ids=[memory_id])
            if results["ids"]:
                return {
                    "memory_id": results["ids"][0],
                    "content": results["documents"][0] if results["documents"] else "",
                    "metadata": results["metadatas"][0] if results["metadatas"] else {},
                }
        elif self.backend == "milvus":
            results = self._collection.query(
                expr=f'memory_id == "{memory_id}"',
                output_fields=["memory_id", "content", "metadata", "created_at"],
            )
            if results:
                return {
                    "memory_id": results[0].get("memory_id"),
                    "content": results[0].get("content"),
                    "metadata": results[0].get("metadata", {}),
                }

        return None

    async def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆

        Args:
            memory_id: 记忆 ID

        Returns:
            是否成功
        """
        if self._collection is None:
            await self.initialize()

        try:
            if self.backend == "chroma":
                self._collection.delete(ids=[memory_id])
            elif self.backend == "milvus":
                self._collection.delete(f'memory_id == "{memory_id}"')

            self.logger.debug("Memory deleted", memory_id=memory_id)
            return True
        except Exception as e:
            self.logger.error(
                "Failed to delete memory",
                memory_id=memory_id,
                error=str(e),
            )
            return False

    async def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        更新记忆

        Args:
            memory_id: 记忆 ID
            content: 新内容（可选）
            metadata: 新元数据（可选）

        Returns:
            是否成功
        """
        if self._collection is None:
            await self.initialize()

        try:
            # 先获取现有记忆
            existing = await self.get_memory(memory_id)
            if not existing:
                return False

            # 更新内容
            new_content = content or existing["content"]
            new_metadata = {**existing["metadata"], **(metadata or {})}

            # 删除旧记忆
            await self.delete_memory(memory_id)

            # 添加新记忆
            await self.add_memory(
                content=new_content,
                metadata=new_metadata,
                memory_id=memory_id,
            )

            self.logger.debug("Memory updated", memory_id=memory_id)
            return True
        except Exception as e:
            self.logger.error(
                "Failed to update memory",
                memory_id=memory_id,
                error=str(e),
            )
            return False

    async def clear_all(self) -> int:
        """
        清空所有记忆

        Returns:
            删除的记忆数量
        """
        if self._collection is None:
            await self.initialize()

        try:
            if self.backend == "chroma":
                count = self._collection.count()
                self._client.delete_collection(self.collection_name)
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                return count
            elif self.backend == "milvus":
                count = self._collection.num_entities
                self._collection.drop()
                await self._init_milvus()
                return count
        except Exception as e:
            self.logger.error("Failed to clear memories", error=str(e))
            return 0

        return 0

    async def get_stats(self) -> dict[str, Any]:
        """
        获取存储统计信息

        Returns:
            统计信息
        """
        if self._collection is None:
            await self.initialize()

        try:
            if self.backend == "chroma":
                count = self._collection.count()
            elif self.backend == "milvus":
                count = self._collection.num_entities
            else:
                count = 0

            return {
                "backend": self.backend,
                "collection": self.collection_name,
                "total_memories": count,
                "persist_directory": self.persist_directory,
            }
        except Exception as e:
            self.logger.error("Failed to get stats", error=str(e))
            return {
                "backend": self.backend,
                "error": str(e),
            }


# 便捷函数
def create_rag_store(
    backend: str = "chroma",
    **kwargs,
) -> RAGStore:
    """
    创建 RAG 存储

    Args:
        backend: 向量数据库类型
        **kwargs: 其他配置参数

    Returns:
        RAGStore 实例
    """
    return RAGStore(backend=backend, **kwargs)