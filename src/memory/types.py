"""
Memory 系统类型定义

提供统一的类型注解，提高代码可读性和类型安全。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, TypeVar, runtime_checkable

from src.utils.compat import StrEnum

# ===========================================
# 枚举类型
# ===========================================


class MemoryType(StrEnum):
    """记忆类型"""

    EPISODIC = "episodic"  # 情节记忆（具体事件）
    SEMANTIC = "semantic"  # 语义记忆（事实知识）
    PROCEDURAL = "procedural"  # 程序记忆（技能方法）
    CONVERSATION = "conversation"  # 对话记忆
    TASK_RESULT = "task_result"  # 任务结果


class MemoryImportance(StrEnum):
    """记忆重要性"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StorageType(StrEnum):
    """存储类型"""

    SHORT_TERM = "short_term"  # 短期记忆 (Redis)
    LONG_TERM = "long_term"  # 长期记忆 (数据库)
    VECTOR = "vector"  # 向量存储 (RAG)


class CompressionStrategyType(StrEnum):
    """压缩策略类型"""

    SUMMARY = "summary"
    KEY_POINTS = "key_points"
    SLIDING_WINDOW = "sliding_window"
    HYBRID = "hybrid"


# ===========================================
# 数据类
# ===========================================


@dataclass
class MemoryEntry:
    """记忆条目"""

    id: str
    content: str
    memory_type: str | None = None
    importance: str | None = None
    summary: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    agent_id: str | None = None
    session_id: str | None = None
    task_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    access_count: int = 0
    similarity_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "summary": self.summary,
            "tags": self.tags,
            "metadata": self.metadata,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "access_count": self.access_count,
            "similarity_score": self.similarity_score,
        }


@dataclass
class SearchResult:
    """搜索结果"""

    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    query: str | None = None
    storage_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "items": self.items,
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "query": self.query,
            "storage_type": self.storage_type,
        }


@dataclass
class MemoryStats:
    """记忆统计"""

    storage_type: str
    total_count: int
    by_type: dict[str, int] | None = None
    by_importance: dict[str, int] | None = None
    recently_accessed_24h: int | None = None
    rag_enabled: bool | None = None
    used_memory: int | None = None
    used_memory_human: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result: dict[str, Any] = {
            "storage_type": self.storage_type,
            "total_count": self.total_count,
        }
        if self.by_type is not None:
            result["by_type"] = self.by_type
        if self.by_importance is not None:
            result["by_importance"] = self.by_importance
        if self.recently_accessed_24h is not None:
            result["recently_accessed_24h"] = self.recently_accessed_24h
        if self.rag_enabled is not None:
            result["rag_enabled"] = self.rag_enabled
        if self.used_memory is not None:
            result["used_memory"] = self.used_memory
        if self.used_memory_human is not None:
            result["used_memory_human"] = self.used_memory_human
        return result


# ===========================================
# 协议类型
# ===========================================


@runtime_checkable
class EmbeddingProviderProtocol(Protocol):
    """嵌入向量提供者协议"""

    def embed(self, text: str) -> list[float]:
        """生成单个文本的嵌入向量"""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成嵌入向量"""
        ...


@runtime_checkable
class MemoryStorageProtocol(Protocol):
    """记忆存储协议"""

    async def store(self, content: str, **kwargs: Any) -> str:
        """存储记忆，返回 ID"""
        ...

    async def retrieve(self, memory_id: str) -> dict[str, Any] | None:
        """检索记忆"""
        ...

    async def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        ...

    async def search(
        self,
        query: str | None = None,
        limit: int = 10,
        offset: int = 0,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """搜索记忆"""
        ...


# ===========================================
# 类型别名
# ===========================================


# 记忆 ID 类型
MemoryId = str

# 向量类型
Vector = list[float]

# 元数据类型
Metadata = dict[str, Any]

# 过滤条件类型
FilterDict = dict[str, Any]


# ===========================================
# 泛型类型
# ===========================================


T = TypeVar("T")


# ===========================================
# 验证辅助函数
# ===========================================


def validate_memory_type(value: str) -> MemoryType:
    """验证记忆类型"""
    try:
        return MemoryType(value)
    except ValueError:
        valid_types = [t.value for t in MemoryType]
        raise ValueError(
            f"Invalid memory type: {value}. Valid types: {valid_types}"
        ) from None


def validate_importance(value: str) -> MemoryImportance:
    """验证重要性"""
    try:
        return MemoryImportance(value)
    except ValueError:
        valid_values = [v.value for v in MemoryImportance]
        raise ValueError(
            f"Invalid importance: {value}. Valid values: {valid_values}"
        ) from None


def validate_storage_type(value: str) -> StorageType:
    """验证存储类型"""
    try:
        return StorageType(value)
    except ValueError:
        valid_types = [t.value for t in StorageType]
        raise ValueError(
            f"Invalid storage type: {value}. Valid types: {valid_types}"
        ) from None


def validate_content(content: str, max_length: int = 100000) -> str:
    """验证内容"""
    if not content or not content.strip():
        raise ValueError("Content cannot be empty")

    content = content.strip()
    if len(content) > max_length:
        raise ValueError(
            f"Content too long: {len(content)} > {max_length}"
        )

    return content


def validate_tags(tags: list[str], max_tags: int = 20) -> list[str]:
    """验证标签"""
    if not tags:
        return []

    if len(tags) > max_tags:
        raise ValueError(f"Too many tags: {len(tags)} > {max_tags}")

    # 清理和去重
    cleaned = list({tag.strip().lower() for tag in tags if tag.strip()})
    return cleaned


def validate_metadata(
    metadata: dict[str, Any],
    max_keys: int = 50,
    max_key_length: int = 100,
    max_value_length: int = 10000,
) -> dict[str, Any]:
    """验证元数据"""
    if not metadata:
        return {}

    if len(metadata) > max_keys:
        raise ValueError(f"Too many metadata keys: {len(metadata)} > {max_keys}")

    validated: dict[str, Any] = {}
    for key, value in metadata.items():
        # 验证 key
        if not isinstance(key, str):
            raise ValueError(f"Metadata key must be string: {key}")
        if len(key) > max_key_length:
            raise ValueError(f"Metadata key too long: {key}")

        # 验证 value
        if isinstance(value, str) and len(value) > max_value_length:
            value = value[:max_value_length]

        validated[key] = value

    return validated
