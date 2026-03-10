"""
Knowledge System 异常定义

提供知识库系统特定的异常类。
"""

from typing import Any


class KnowledgeError(Exception):
    """知识库系统基础异常"""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
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


class DocumentNotFoundError(KnowledgeError):
    """文档未找到错误"""

    def __init__(self, document_id: str) -> None:
        super().__init__(
            f"Document not found: {document_id}",
            {"document_id": document_id},
        )


class DocumentProcessingError(KnowledgeError):
    """文档处理错误"""

    def __init__(
        self,
        message: str,
        document_id: str | None = None,
        stage: str | None = None,
    ) -> None:
        details = {}
        if document_id:
            details["document_id"] = document_id
        if stage:
            details["stage"] = stage
        super().__init__(message, details)


class ChunkingError(KnowledgeError):
    """分块错误"""

    def __init__(
        self,
        message: str,
        document_id: str | None = None,
        strategy: str | None = None,
    ) -> None:
        details = {}
        if document_id:
            details["document_id"] = document_id
        if strategy:
            details["strategy"] = strategy
        super().__init__(message, details)


class EmbeddingGenerationError(KnowledgeError):
    """嵌入向量生成错误"""

    def __init__(
        self,
        message: str,
        text_length: int | None = None,
    ) -> None:
        details = {}
        if text_length is not None:
            details["text_length"] = text_length
        super().__init__(message, details)


class VectorStoreOperationError(KnowledgeError):
    """向量存储操作错误"""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
    ) -> None:
        details = {}
        if operation:
            details["operation"] = operation
        super().__init__(message, details)


class QASystemError(KnowledgeError):
    """问答系统错误"""

    def __init__(
        self,
        message: str,
        query: str | None = None,
    ) -> None:
        details = {}
        if query:
            details["query"] = query[:100]  # 限制长度
        super().__init__(message, details)


class KnowledgeGraphError(KnowledgeError):
    """知识图谱错误"""

    def __init__(
        self,
        message: str,
        entity_id: str | None = None,
    ) -> None:
        details = {}
        if entity_id:
            details["entity_id"] = entity_id
        super().__init__(message, details)


class UnsupportedDocumentTypeError(KnowledgeError):
    """不支持的文档类型错误"""

    def __init__(self, doc_type: str) -> None:
        super().__init__(
            f"Unsupported document type: {doc_type}",
            {"doc_type": doc_type},
        )


class FileParseError(KnowledgeError):
    """文件解析错误"""

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        file_type: str | None = None,
    ) -> None:
        details = {}
        if file_path:
            details["file_path"] = file_path
        if file_type:
            details["file_type"] = file_type
        super().__init__(message, details)
