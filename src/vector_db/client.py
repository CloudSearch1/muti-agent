"""
向量数据库集成

支持 Milvus、Qdrant 等向量数据库，用于语义搜索和 RAG
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """向量文档"""
    id: str
    vector: List[float]
    metadata: Dict[str, Any]
    text: Optional[str] = None


class VectorDatabase:
    """
    向量数据库客户端
    
    支持:
    - Milvus
    - Qdrant
    - Chroma (TODO)
    - Weaviate (TODO)
    """
    
    def __init__(
        self,
        provider: str = "milvus",
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "default",
    ):
        self.provider = provider
        self.host = host
        self.port = port
        self.collection_name = collection_name
        
        self._client = None
        self._collection = None
        
        logger.info(f"VectorDatabase initialized ({provider})")
    
    async def connect(self):
        """连接向量数据库"""
        if self.provider == "milvus":
            await self._connect_milvus()
        elif self.provider == "qdrant":
            await self._connect_qdrant()
        else:
            logger.warning(f"Unsupported provider: {self.provider}")
    
    async def _connect_milvus(self):
        """连接 Milvus"""
        try:
            from pymilvus import connections, Collection
            
            connections.connect(
                host=self.host,
                port=self.port,
            )
            
            self._client = connections
            
            logger.info(f"Milvus connected: {self.host}:{self.port}")
            
        except ImportError:
            logger.warning("pymilvus not installed, using mock mode")
        except Exception as e:
            logger.error(f"Milvus connection failed: {e}")
    
    async def _connect_qdrant(self):
        """连接 Qdrant"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            
            self._client = QdrantClient(
                host=self.host,
                port=self.port,
            )
            
            logger.info(f"Qdrant connected: {self.host}:{self.port}")
            
        except ImportError:
            logger.warning("qdrant_client not installed, using mock mode")
        except Exception as e:
            logger.error(f"Qdrant connection failed: {e}")
    
    async def disconnect(self):
        """断开连接"""
        if self._client:
            if self.provider == "milvus":
                from pymilvus import connections
                connections.disconnect("default")
            logger.info("VectorDatabase disconnected")
    
    async def create_collection(
        self,
        dimension: int,
        metric_type: str = "COSINE",
    ):
        """创建集合"""
        if self.provider == "milvus":
            await self._create_milvus_collection(dimension, metric_type)
        elif self.provider == "qdrant":
            await self._create_qdrant_collection(dimension, metric_type)
    
    async def _create_milvus_collection(self, dimension: int, metric_type: str):
        """创建 Milvus 集合"""
        try:
            from pymilvus import FieldSchema, CollectionSchema, DataType, Collection
            
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            ]
            
            schema = CollectionSchema(fields, "Vector collection")
            
            self._collection = Collection(self.collection_name, schema)
            
            # 创建索引
            index_params = {
                "index_type": "IVF_FLAT",
                "metric_type": metric_type,
                "params": {"nlist": 1024},
            }
            
            self._collection.create_index("vector", index_params)
            
            logger.info(f"Milvus collection created: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Create Milvus collection failed: {e}")
    
    async def _create_qdrant_collection(self, dimension: int, metric_type: str):
        """创建 Qdrant 集合"""
        try:
            from qdrant_client.http import models
            
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE if metric_type == "COSINE" else models.Distance.EUCLID,
                ),
            )
            
            logger.info(f"Qdrant collection created: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Create Qdrant collection failed: {e}")
    
    async def insert(self, documents: List[VectorDocument]):
        """插入文档"""
        if self.provider == "milvus":
            await self._insert_milvus(documents)
        elif self.provider == "qdrant":
            await self._insert_qdrant(documents)
    
    async def _insert_milvus(self, documents: List[VectorDocument]):
        """插入到 Milvus"""
        try:
            if not self._collection:
                logger.warning("Collection not created")
                return
            
            data = [
                [doc.id for doc in documents],
                [doc.vector for doc in documents],
                [doc.metadata for doc in documents],
                [doc.text or "" for doc in documents],
            ]
            
            self._collection.insert(data)
            logger.info(f"Inserted {len(documents)} documents to Milvus")
            
        except Exception as e:
            logger.error(f"Insert to Milvus failed: {e}")
    
    async def _insert_qdrant(self, documents: List[VectorDocument]):
        """插入到 Qdrant"""
        try:
            from qdrant_client.http import models
            
            points = [
                models.PointStruct(
                    id=doc.id,
                    vector=doc.vector,
                    payload={
                        "metadata": doc.metadata,
                        "text": doc.text,
                    },
                )
                for doc in documents
            ]
            
            self._client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            
            logger.info(f"Inserted {len(documents)} documents to Qdrant")
            
        except Exception as e:
            logger.error(f"Insert to Qdrant failed: {e}")
    
    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        filter_expr: Optional[str] = None,
    ) -> List[Tuple[VectorDocument, float]]:
        """
        向量搜索
        
        Args:
            query_vector: 查询向量
            limit: 返回数量
            filter_expr: 过滤表达式
        
        Returns:
            (文档，相似度分数) 列表
        """
        if self.provider == "milvus":
            return await self._search_milvus(query_vector, limit, filter_expr)
        elif self.provider == "qdrant":
            return await self._search_qdrant(query_vector, limit, filter_expr)
        
        return []
    
    async def _search_milvus(
        self,
        query_vector: List[float],
        limit: int,
        filter_expr: Optional[str],
    ) -> List[Tuple[VectorDocument, float]]:
        """Milvus 搜索"""
        try:
            if not self._collection:
                return []
            
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
            
            results = self._collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=limit,
                expr=filter_expr,
                output_fields=["metadata", "text"],
            )
            
            documents = []
            for hits in results:
                for hit in hits:
                    doc = VectorDocument(
                        id=hit.entity.id,
                        vector=[],  # 不返回向量
                        metadata=hit.entity.metadata,
                        text=hit.entity.text,
                    )
                    documents.append((doc, hit.score))
            
            return documents
            
        except Exception as e:
            logger.error(f"Milvus search failed: {e}")
            return []
    
    async def _search_qdrant(
        self,
        query_vector: List[float],
        limit: int,
        filter_expr: Optional[str],
    ) -> List[Tuple[VectorDocument, float]]:
        """Qdrant 搜索"""
        try:
            from qdrant_client.http import models
            
            results = self._client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
            )
            
            documents = []
            for result in results:
                doc = VectorDocument(
                    id=str(result.id),
                    vector=[],
                    metadata=result.payload.get("metadata", {}),
                    text=result.payload.get("text"),
                )
                documents.append((doc, result.score))
            
            return documents
            
        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            return []
    
    async def delete(self, ids: List[str]):
        """删除文档"""
        if self.provider == "milvus":
            await self._delete_milvus(ids)
        elif self.provider == "qdrant":
            await self._delete_qdrant(ids)
    
    async def _delete_milvus(self, ids: List[str]):
        """从 Milvus 删除"""
        try:
            if self._collection:
                expr = f'id in {ids}'
                self._collection.delete(expr)
                logger.info(f"Deleted {len(ids)} documents from Milvus")
        except Exception as e:
            logger.error(f"Delete from Milvus failed: {e}")
    
    async def _delete_qdrant(self, ids: List[str]):
        """从 Qdrant 删除"""
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[int(id) if id.isdigit() else id for id in ids],
                ),
            )
            logger.info(f"Deleted {len(ids)} documents from Qdrant")
        except Exception as e:
            logger.error(f"Delete from Qdrant failed: {e}")
    
    async def count(self) -> int:
        """获取文档数量"""
        if self.provider == "milvus" and self._collection:
            return self._collection.num_entities
        return 0


# ============ 全局客户端 ============

_client: Optional[VectorDatabase] = None


def get_vector_db() -> VectorDatabase:
    """获取向量数据库客户端"""
    global _client
    if _client is None:
        _client = VectorDatabase()
    return _client


async def init_vector_db(**kwargs) -> VectorDatabase:
    """初始化向量数据库"""
    global _client
    _client = VectorDatabase(**kwargs)
    await _client.connect()
    logger.info("Vector database initialized")
    return _client


async def close_vector_db():
    """关闭向量数据库"""
    global _client
    if _client:
        await _client.disconnect()
        _client = None
