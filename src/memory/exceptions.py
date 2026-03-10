"""
Memory 系统异常定义

提供统一的异常层次结构，便于错误处理和调试。
"""

from typing import Any


class MemoryError(Exception):
    """Memory 系统基础异常"""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        初始化异常

        Args:
            message: 错误消息
            details: 额外详情
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class MemoryConnectionError(MemoryError):
    """连接错误"""

    def __init__(
        self,
        message: str = "Failed to connect to memory backend",
        backend: str | None = None,
    ) -> None:
        details = {"backend": backend} if backend else {}
        super().__init__(message, details)


class MemoryStorageError(MemoryError):
    """存储错误"""

    def __init__(
        self,
        message: str = "Failed to store memory",
        memory_id: str | None = None,
        storage_type: str | None = None,
    ) -> None:
        details = {}
        if memory_id:
            details["memory_id"] = memory_id
        if storage_type:
            details["storage_type"] = storage_type
        super().__init__(message, details)


class MemoryRetrievalError(MemoryError):
    """检索错误"""

    def __init__(
        self,
        message: str = "Failed to retrieve memory",
        memory_id: str | None = None,
    ) -> None:
        details = {"memory_id": memory_id} if memory_id else {}
        super().__init__(message, details)


class MemoryNotFoundError(MemoryError):
    """记忆未找到错误"""

    def __init__(
        self,
        memory_id: str,
        storage_type: str | None = None,
    ) -> None:
        details = {"memory_id": memory_id}
        if storage_type:
            details["storage_type"] = storage_type
        super().__init__(f"Memory not found: {memory_id}", details)


class MemoryValidationError(MemoryError):
    """验证错误"""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
    ) -> None:
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]  # 限制长度
        super().__init__(message, details)


class MemoryDecayError(MemoryError):
    """记忆衰减错误"""

    def __init__(
        self,
        message: str = "Failed to apply memory decay",
        affected_count: int | None = None,
    ) -> None:
        details = {}
        if affected_count is not None:
            details["affected_count"] = affected_count
        super().__init__(message, details)


class VectorStoreError(MemoryError):
    """向量存储错误"""

    def __init__(
        self,
        message: str = "Vector store operation failed",
        operation: str | None = None,
        backend: str | None = None,
    ) -> None:
        details = {}
        if operation:
            details["operation"] = operation
        if backend:
            details["backend"] = backend
        super().__init__(message, details)


class EmbeddingError(MemoryError):
    """嵌入向量生成错误"""

    def __init__(
        self,
        message: str = "Failed to generate embedding",
        text_length: int | None = None,
    ) -> None:
        details = {}
        if text_length is not None:
            details["text_length"] = text_length
        super().__init__(message, details)


class SessionError(MemoryError):
    """会话错误"""

    def __init__(
        self,
        message: str,
        session_id: str | None = None,
    ) -> None:
        details = {"session_id": session_id} if session_id else {}
        super().__init__(message, details)


class CompressionError(MemoryError):
    """压缩错误"""

    def __init__(
        self,
        message: str = "Failed to compress content",
        content_length: int | None = None,
        strategy: str | None = None,
    ) -> None:
        details = {}
        if content_length is not None:
            details["content_length"] = content_length
        if strategy:
            details["strategy"] = strategy
        super().__init__(message, details)
