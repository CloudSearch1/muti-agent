"""
记忆模块

提供完整的记忆系统，包括：
- 短期记忆（Redis）
- 长期记忆（数据库持久化）
- RAG 向量存储
- 上下文压缩
"""

from .context_compressor import (
    CompressionStrategy,
    ContextCompressor,
    ContextWindow,
    IncrementalCompressor,
    create_compressor,
)
from .long_term import (
    LongTermMemory,
    MemoryImportance,
    MemoryType,
    create_long_term_memory,
)
from .rag_store import (
    EmbeddingProvider,
    MemoryItem,
    RAGStore,
    SimpleEmbeddingProvider,
    create_rag_store,
)
from .session import SessionInfo, SessionManager
from .short_term import ShortTermMemory

__all__ = [
    # 短期记忆
    "ShortTermMemory",
    # 会话管理
    "SessionManager",
    "SessionInfo",
    # RAG 存储
    "RAGStore",
    "MemoryItem",
    "EmbeddingProvider",
    "SimpleEmbeddingProvider",
    "create_rag_store",
    # 上下文压缩
    "ContextCompressor",
    "ContextWindow",
    "CompressionStrategy",
    "IncrementalCompressor",
    "create_compressor",
    # 长期记忆
    "LongTermMemory",
    "MemoryType",
    "MemoryImportance",
    "create_long_term_memory",
]