"""
记忆模块

提供完整的记忆系统，包括：
- 短期记忆（Redis）
- 长期记忆（数据库持久化）
- RAG 向量存储
- 上下文压缩
- 会话管理

Example:
    >>> from src.memory import ShortTermMemory, LongTermMemory, RAGStore
    >>> stm = ShortTermMemory()
    >>> ltm = LongTermMemory()
    >>> rag = RAGStore()
"""

# 异常类
from .exceptions import (
    CompressionError,
    EmbeddingError,
    MemoryConnectionError,
    MemoryDecayError,
    MemoryError,
    MemoryNotFoundError,
    MemoryRetrievalError,
    MemoryStorageError,
    MemoryValidationError,
    SessionError,
    VectorStoreError,
)

# 类型定义
from .types import (
    CompressionStrategyType,
    EmbeddingProviderProtocol,
    FilterDict,
    MemoryEntry,
    MemoryId,
    MemoryImportance,
    MemoryStats,
    MemoryStorageProtocol,
    MemoryType,
    Metadata,
    SearchResult,
    StorageType,
    Vector,
    validate_content,
    validate_importance,
    validate_memory_type,
    validate_metadata,
    validate_storage_type,
    validate_tags,
)

# 核心模块
from .context_compressor import (
    CompressionResult,
    ContextCompressor,
    ContextWindow,
    IncrementalCompressor,
    LLMProviderProtocol,
    create_compressor,
)
from .long_term import (
    LongTermMemory,
    create_long_term_memory,
)
from .rag_store import (
    BaseEmbeddingProvider,
    EmbeddingProviderProtocol as RAGEmbeddingProviderProtocol,
    MemoryItem,
    RAGStore,
    SimpleEmbeddingProvider,
    create_rag_store,
)
from .session import SessionInfo, SessionManager
from .short_term import ShortTermMemory

__all__ = [
    # 异常类
    "MemoryError",
    "MemoryConnectionError",
    "MemoryStorageError",
    "MemoryRetrievalError",
    "MemoryNotFoundError",
    "MemoryValidationError",
    "MemoryDecayError",
    "VectorStoreError",
    "EmbeddingError",
    "SessionError",
    "CompressionError",
    # 类型定义
    "MemoryType",
    "MemoryImportance",
    "StorageType",
    "CompressionStrategyType",
    "MemoryEntry",
    "SearchResult",
    "MemoryStats",
    "MemoryId",
    "Vector",
    "Metadata",
    "FilterDict",
    "EmbeddingProviderProtocol",
    "MemoryStorageProtocol",
    # 验证函数
    "validate_memory_type",
    "validate_importance",
    "validate_storage_type",
    "validate_content",
    "validate_tags",
    "validate_metadata",
    # 短期记忆
    "ShortTermMemory",
    # 会话管理
    "SessionManager",
    "SessionInfo",
    # RAG 存储
    "RAGStore",
    "MemoryItem",
    "BaseEmbeddingProvider",
    "SimpleEmbeddingProvider",
    "RAGEmbeddingProviderProtocol",
    "create_rag_store",
    # 上下文压缩
    "ContextCompressor",
    "ContextWindow",
    "CompressionResult",
    "IncrementalCompressor",
    "LLMProviderProtocol",
    "create_compressor",
    # 长期记忆
    "LongTermMemory",
    "create_long_term_memory",
]