"""
文本分块策略模块

提供多种文本分块策略：
- 固定大小分块
- 句子分块
- 语义分块
"""

import re
import uuid
from abc import ABC, abstractmethod
from typing import Any

import structlog

from .exceptions import ChunkingError
from .types import Chunk, ChunkStrategy

logger = structlog.get_logger(__name__)

# 默认配置
DEFAULT_CHUNK_SIZE = 500  # 字符数
DEFAULT_CHUNK_OVERLAP = 50  # 重叠字符数
DEFAULT_MIN_CHUNK_SIZE = 100  # 最小分块大小
DEFAULT_MAX_CHUNK_SIZE = 2000  # 最大分块大小


class TextChunker(ABC):
    """文本分块器基类"""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        """
        初始化分块器

        Args:
            chunk_size: 分块大小（字符数）
            chunk_overlap: 分块重叠大小
        """
        self.chunk_size = max(DEFAULT_MIN_CHUNK_SIZE, min(chunk_size, DEFAULT_MAX_CHUNK_SIZE))
        self.chunk_overlap = min(chunk_overlap, self.chunk_size // 2)
        self.logger = logger.bind(component="chunker")

    @abstractmethod
    def chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """
        分块文本

        Args:
            text: 待分块的文本
            document_id: 文档 ID
            metadata: 元数据

        Returns:
            分块列表
        """
        pass

    def _create_chunk(
        self,
        content: str,
        document_id: str,
        position: int,
        metadata: dict[str, Any] | None = None,
    ) -> Chunk:
        """创建分块对象"""
        from datetime import datetime

        return Chunk(
            id=str(uuid.uuid4()),
            document_id=document_id,
            content=content.strip(),
            metadata=metadata or {},
            position=position,
            created_at=datetime.now(),
        )


class FixedSizeChunker(TextChunker):
    """
    固定大小分块器

    按固定字符数分块，支持重叠。
    """

    def chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """
        固定大小分块

        Args:
            text: 待分块的文本
            document_id: 文档 ID
            metadata: 元数据

        Returns:
            分块列表
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        chunks = []
        start = 0
        position = 0

        while start < len(text):
            # 计算结束位置
            end = start + self.chunk_size

            # 如果不是最后一块，尝试在句子边界断开
            if end < len(text):
                # 寻找最近的句子边界
                boundary = self._find_boundary(text, start, end)
                if boundary > start:
                    end = boundary

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(self._create_chunk(
                    content=chunk_text,
                    document_id=document_id,
                    position=position,
                    metadata=metadata,
                ))
                position += 1

            # 移动到下一个位置（考虑重叠）
            start = end - self.chunk_overlap if end < len(text) else end

        self.logger.debug(
            "Fixed size chunking completed",
            document_id=document_id,
            chunks_count=len(chunks),
            chunk_size=self.chunk_size,
        )

        return chunks

    def _find_boundary(self, text: str, start: int, end: int) -> int:
        """寻找句子边界"""
        # 在 end 附近寻找句子结束符
        search_start = max(start, end - 100)
        search_text = text[search_start:end]

        # 查找句号、问号、感叹号
        for match in re.finditer(r'[。！？.!?]\s*', search_text):
            return search_start + match.end()

        # 如果没有找到，尝试在空格处断开
        for match in re.finditer(r'\s+', search_text):
            return search_start + match.end()

        return end


class SentenceChunker(TextChunker):
    """
    句子分块器

    按句子分块，保持句子完整性。
    """

    # 中英文句子分隔符
    SENTENCE_PATTERN = re.compile(
        r'(?<=[。！？.!?])\s*'
        r'|(?<=\n)\s*'
    )

    def chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """
        句子分块

        Args:
            text: 待分块的文本
            document_id: 文档 ID
            metadata: 元数据

        Returns:
            分块列表
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        # 分割句子
        sentences = self._split_sentences(text)
        if not sentences:
            return []

        chunks = []
        current_chunk_sentences: list[str] = []
        current_length = 0
        position = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            # 如果单个句子超过最大大小，需要进一步分割
            if sentence_length > self.chunk_size:
                # 先保存当前块
                if current_chunk_sentences:
                    chunks.append(self._create_chunk(
                        content=" ".join(current_chunk_sentences),
                        document_id=document_id,
                        position=position,
                        metadata=metadata,
                    ))
                    position += 1
                    current_chunk_sentences = []
                    current_length = 0

                # 分割大句子
                sub_chunks = self._split_large_sentence(
                    sentence, document_id, position, metadata
                )
                chunks.extend(sub_chunks)
                position += len(sub_chunks)
                continue

            # 检查是否需要创建新块
            if current_length + sentence_length > self.chunk_size:
                if current_chunk_sentences:
                    chunks.append(self._create_chunk(
                        content=" ".join(current_chunk_sentences),
                        document_id=document_id,
                        position=position,
                        metadata=metadata,
                    ))
                    position += 1

                # 开始新块（考虑重叠）
                if self.chunk_overlap > 0 and current_chunk_sentences:
                    overlap_sentences = self._get_overlap_sentences(
                        current_chunk_sentences
                    )
                    current_chunk_sentences = overlap_sentences
                    current_length = sum(len(s) for s in overlap_sentences)
                else:
                    current_chunk_sentences = []
                    current_length = 0

            current_chunk_sentences.append(sentence)
            current_length += sentence_length

        # 保存最后一块
        if current_chunk_sentences:
            chunks.append(self._create_chunk(
                content=" ".join(current_chunk_sentences),
                document_id=document_id,
                position=position,
                metadata=metadata,
            ))

        self.logger.debug(
            "Sentence chunking completed",
            document_id=document_id,
            chunks_count=len(chunks),
        )

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """分割句子"""
        sentences = self.SENTENCE_PATTERN.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def _split_large_sentence(
        self,
        sentence: str,
        document_id: str,
        start_position: int,
        metadata: dict[str, Any] | None,
    ) -> list[Chunk]:
        """分割过大的句子"""
        chunks = []
        start = 0
        position = start_position

        while start < len(sentence):
            end = min(start + self.chunk_size, len(sentence))
            chunk_text = sentence[start:end].strip()
            if chunk_text:
                chunks.append(self._create_chunk(
                    content=chunk_text,
                    document_id=document_id,
                    position=position,
                    metadata=metadata,
                ))
                position += 1
            start = end

        return chunks

    def _get_overlap_sentences(self, sentences: list[str]) -> list[str]:
        """获取重叠的句子"""
        overlap_length = 0
        overlap_sentences = []

        for sentence in reversed(sentences):
            overlap_length += len(sentence)
            overlap_sentences.insert(0, sentence)
            if overlap_length >= self.chunk_overlap:
                break

        return overlap_sentences


class SemanticChunker(TextChunker):
    """
    语义分块器

    按段落和语义单元分块，保持语义完整性。
    """

    # 段落分隔符
    PARAGRAPH_PATTERN = re.compile(r'\n\s*\n')
    # 标题模式
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    def chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """
        语义分块

        Args:
            text: 待分块的文本
            document_id: 文档 ID
            metadata: 元数据

        Returns:
            分块列表
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        # 首先按段落分割
        paragraphs = self._split_paragraphs(text)
        if not paragraphs:
            return []

        chunks = []
        current_content = ""
        position = 0

        for para in paragraphs:
            para_text = para.strip()
            if not para_text:
                continue

            # 检查是否是标题
            is_heading = self.HEADING_PATTERN.match(para_text)

            # 如果当前块不为空且加入这段会超过大小限制
            if current_content and len(current_content) + len(para_text) > self.chunk_size:
                # 如果是标题，先保存当前块
                if is_heading or len(current_content) >= DEFAULT_MIN_CHUNK_SIZE:
                    chunks.append(self._create_chunk(
                        content=current_content.strip(),
                        document_id=document_id,
                        position=position,
                        metadata=metadata,
                    ))
                    position += 1
                    current_content = para_text if is_heading else ""
                    continue

            # 添加到当前块
            if current_content:
                current_content += "\n\n" + para_text
            else:
                current_content = para_text

            # 如果单个块已经很大，保存它
            if len(current_content) >= self.chunk_size:
                chunks.append(self._create_chunk(
                    content=current_content.strip(),
                    document_id=document_id,
                    position=position,
                    metadata=metadata,
                ))
                position += 1
                current_content = ""

        # 保存最后一块
        if current_content.strip():
            chunks.append(self._create_chunk(
                content=current_content.strip(),
                document_id=document_id,
                position=position,
                metadata=metadata,
            ))

        self.logger.debug(
            "Semantic chunking completed",
            document_id=document_id,
            chunks_count=len(chunks),
        )

        return chunks

    def _split_paragraphs(self, text: str) -> list[str]:
        """分割段落"""
        paragraphs = self.PARAGRAPH_PATTERN.split(text)
        return [p.strip() for p in paragraphs if p.strip()]


class ChunkerFactory:
    """分块器工厂"""

    _chunkers: dict[ChunkStrategy, type[TextChunker]] = {
        ChunkStrategy.FIXED: FixedSizeChunker,
        ChunkStrategy.SENTENCE: SentenceChunker,
        ChunkStrategy.SEMANTIC: SemanticChunker,
    }

    @classmethod
    def create(
        cls,
        strategy: ChunkStrategy | str = ChunkStrategy.SEMANTIC,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> TextChunker:
        """
        创建分块器

        Args:
            strategy: 分块策略
            chunk_size: 分块大小
            chunk_overlap: 重叠大小

        Returns:
            分块器实例

        Raises:
            ChunkingError: 不支持的策略
        """
        if isinstance(strategy, str):
            try:
                strategy = ChunkStrategy(strategy.lower())
            except ValueError:
                raise ChunkingError(
                    f"Unknown chunking strategy: {strategy}",
                    strategy=strategy,
                ) from None

        chunker_class = cls._chunkers.get(strategy)
        if not chunker_class:
            raise ChunkingError(
                f"Unsupported chunking strategy: {strategy}",
                strategy=strategy.value,
            )

        return chunker_class(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    @classmethod
    def register(cls, strategy: ChunkStrategy, chunker_class: type[TextChunker]) -> None:
        """注册自定义分块器"""
        cls._chunkers[strategy] = chunker_class

    @classmethod
    def list_strategies(cls) -> list[str]:
        """列出所有支持的策略"""
        return [s.value for s in cls._chunkers.keys()]
