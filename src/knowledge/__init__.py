"""
Knowledge System 模块

提供企业级知识库管理功能：
- 文档管理（上传、解析、分块）
- 向量存储与语义搜索
- RAG 智能问答
- 基础知识图谱

Example:
    >>> from src.knowledge import DocumentManager, QASystem
    >>> dm = DocumentManager()
    >>> doc = await dm.upload_document("report.pdf")
    >>> qa = QASystem()
    >>> response = await qa.answer("What is the report about?")
"""

# 异常类
# 核心模块
from .chunking import (
    ChunkerFactory,
    FixedSizeChunker,
    SemanticChunker,
    SentenceChunker,
    TextChunker,
)
from .document_manager import DocumentManager
from .exceptions import (
    ChunkingError,
    DocumentNotFoundError,
    DocumentProcessingError,
    EmbeddingGenerationError,
    FileParseError,
    KnowledgeError,
    KnowledgeGraphError,
    QASystemError,
    UnsupportedDocumentTypeError,
    VectorStoreOperationError,
)
from .knowledge_graph import KnowledgeGraph
from .qa_system import QASystem
from .rag_engine import RAGEngine

# 类型定义
from .types import (
    Chunk,
    ChunkId,
    ChunkStrategy,
    Document,
    DocumentId,
    DocumentStatus,
    DocumentType,
    Entity,
    KnowledgeQuery,
    KnowledgeStats,
    QAResponse,
    Relation,
    SearchResult,
)
from .vector_store import KnowledgeVectorStore

__all__ = [
    # 异常类
    "KnowledgeError",
    "DocumentNotFoundError",
    "DocumentProcessingError",
    "ChunkingError",
    "EmbeddingGenerationError",
    "VectorStoreOperationError",
    "QASystemError",
    "KnowledgeGraphError",
    "UnsupportedDocumentTypeError",
    "FileParseError",
    # 类型定义
    "DocumentStatus",
    "DocumentType",
    "ChunkStrategy",
    "Document",
    "Chunk",
    "KnowledgeQuery",
    "SearchResult",
    "QAResponse",
    "Entity",
    "Relation",
    "KnowledgeStats",
    "DocumentId",
    "ChunkId",
    # 分块
    "TextChunker",
    "FixedSizeChunker",
    "SentenceChunker",
    "SemanticChunker",
    "ChunkerFactory",
    # 核心组件
    "DocumentManager",
    "KnowledgeVectorStore",
    "RAGEngine",
    "QASystem",
    "KnowledgeGraph",
]
