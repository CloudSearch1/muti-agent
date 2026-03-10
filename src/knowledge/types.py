"""
Knowledge System 类型定义

提供知识库系统所需的枚举、数据类和协议。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class DocumentStatus(str, Enum):
    """文档状态"""

    PENDING = "pending"  # 等待处理
    PROCESSING = "processing"  # 处理中
    READY = "ready"  # 已就绪
    FAILED = "failed"  # 处理失败


class DocumentType(str, Enum):
    """文档类型"""

    PDF = "pdf"
    WORD = "word"
    MARKDOWN = "markdown"
    TXT = "txt"
    HTML = "html"
    UNKNOWN = "unknown"


class ChunkStrategy(str, Enum):
    """分块策略"""

    FIXED = "fixed"  # 固定大小分块
    SEMANTIC = "semantic"  # 语义分块
    SENTENCE = "sentence"  # 句子分块


@dataclass
class Chunk:
    """文档分块"""

    id: str
    document_id: str
    content: str
    embedding: Optional[list[float]] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    position: int = 0
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "position": self.position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class Document:
    """文档"""

    id: str
    title: str
    content: str
    doc_type: DocumentType = DocumentType.UNKNOWN
    status: DocumentStatus = DocumentStatus.PENDING
    chunks: list[Chunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    file_path: Optional[str] = None
    file_size: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "doc_type": self.doc_type.value,
            "status": self.status.value,
            "chunks_count": len(self.chunks),
            "metadata": self.metadata,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class KnowledgeQuery:
    """知识库查询"""

    query: str
    filters: Optional[dict[str, Any]] = None
    top_k: int = 5
    min_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "query": self.query,
            "filters": self.filters,
            "top_k": self.top_k,
            "min_score": self.min_score,
        }


@dataclass
class SearchResult:
    """搜索结果"""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    document_title: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
            "document_title": self.document_title,
        }


@dataclass
class QAResponse:
    """问答响应"""

    answer: str
    sources: list[SearchResult]
    confidence: float
    query: str

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "answer": self.answer,
            "sources": [s.to_dict() for s in self.sources],
            "confidence": self.confidence,
            "query": self.query,
        }


@dataclass
class Entity:
    """知识图谱实体"""

    id: str
    name: str
    entity_type: str
    description: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "metadata": self.metadata,
        }


@dataclass
class Relation:
    """知识图谱关系"""

    id: str
    source_id: str
    target_id: str
    relation_type: str
    description: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "description": self.description,
            "metadata": self.metadata,
        }


@dataclass
class KnowledgeStats:
    """知识库统计"""

    total_documents: int
    total_chunks: int
    total_entities: int
    total_relations: int
    storage_size: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total_documents": self.total_documents,
            "total_chunks": self.total_chunks,
            "total_entities": self.total_entities,
            "total_relations": self.total_relations,
            "storage_size": self.storage_size,
            "by_type": self.by_type,
            "by_status": self.by_status,
        }


# 类型别名
DocumentId = str
ChunkId = str