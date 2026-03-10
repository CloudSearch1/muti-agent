"""
知识库系统测试

测试知识库核心功能：
- 文档管理
- 分块策略
- 向量存储
- RAG 引擎
- 问答系统
- 知识图谱
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.knowledge import (
    ChunkStrategy,
    Document,
    DocumentManager,
    DocumentStatus,
    DocumentType,
    KnowledgeGraph,
    KnowledgeVectorStore,
    QASystem,
    RAGEngine,
)
from src.knowledge.chunking import (
    ChunkerFactory,
    FixedSizeChunker,
    SemanticChunker,
    SentenceChunker,
)
from src.knowledge.exceptions import (
    ChunkingError,
    DocumentNotFoundError,
    DocumentProcessingError,
)
from src.knowledge.types import Chunk, Entity, KnowledgeQuery, QAResponse, Relation, SearchResult


# ============ 分块测试 ============


class TestTextChunkers:
    """测试文本分块器"""

    def test_fixed_size_chunker_basic(self):
        """测试固定大小分块器基本功能"""
        chunker = FixedSizeChunker(chunk_size=100, chunk_overlap=10)
        text = "这是一段测试文本。" * 10  # 约 100 字符

        chunks = chunker.chunk(text, "doc1")

        assert len(chunks) >= 1
        assert all(c.document_id == "doc1" for c in chunks)

    def test_fixed_size_chunker_empty_text(self):
        """测试空文本"""
        chunker = FixedSizeChunker()

        chunks = chunker.chunk("", "doc1")
        assert chunks == []

        chunks = chunker.chunk("   ", "doc1")
        assert chunks == []

    def test_sentence_chunker_basic(self):
        """测试句子分块器基本功能"""
        chunker = SentenceChunker(chunk_size=200)
        text = "这是第一句话。这是第二句话。这是第三句话。这是第四句话。"

        chunks = chunker.chunk(text, "doc1")

        assert len(chunks) >= 1
        assert all(c.document_id == "doc1" for c in chunks)

    def test_semantic_chunker_basic(self):
        """测试语义分块器基本功能"""
        chunker = SemanticChunker(chunk_size=300)
        text = """# 标题一

这是第一段内容。

# 标题二

这是第二段内容。
"""

        chunks = chunker.chunk(text, "doc1")

        assert len(chunks) >= 1
        # 标题应该被保留
        assert any("标题" in c.content for c in chunks)

    def test_chunker_factory(self):
        """测试分块器工厂"""
        # 测试创建各种策略
        fixed = ChunkerFactory.create(ChunkStrategy.FIXED)
        assert isinstance(fixed, FixedSizeChunker)

        sentence = ChunkerFactory.create(ChunkStrategy.SENTENCE)
        assert isinstance(sentence, SentenceChunker)

        semantic = ChunkerFactory.create(ChunkStrategy.SEMANTIC)
        assert isinstance(semantic, SemanticChunker)

        # 测试字符串参数
        semantic2 = ChunkerFactory.create("semantic")
        assert isinstance(semantic2, SemanticChunker)

        # 测试无效策略
        with pytest.raises(ChunkingError):
            ChunkerFactory.create("invalid_strategy")

    def test_chunker_factory_list_strategies(self):
        """测试列出策略"""
        strategies = ChunkerFactory.list_strategies()
        assert "fixed" in strategies
        assert "sentence" in strategies
        assert "semantic" in strategies


# ============ 文档管理测试 ============


class TestDocumentManager:
    """测试文档管理器"""

    @pytest.fixture
    def document_manager(self, tmp_path):
        """创建文档管理器实例"""
        return DocumentManager(
            storage_dir=str(tmp_path / "documents"),
            chunk_size=200,
            chunk_overlap=20,
        )

    def test_document_manager_init(self, document_manager):
        """测试初始化"""
        assert document_manager.storage_dir is not None
        assert document_manager.chunk_strategy == ChunkStrategy.SEMANTIC

    @pytest.mark.asyncio
    async def test_upload_document_from_text(self, document_manager, tmp_path):
        """测试上传文档（文本文件）"""
        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("这是测试内容。" * 10)

        # 不传 filename，让它从文件路径自动检测
        doc = await document_manager.upload_document(str(test_file))

        assert doc.id is not None
        assert doc.title == "test.txt"  # 文件名从路径获取
        assert doc.doc_type == DocumentType.TXT
        assert doc.status == DocumentStatus.PENDING

    @pytest.mark.asyncio
    async def test_process_document(self, document_manager, tmp_path):
        """测试处理文档"""
        # 创建并上传文档
        test_file = tmp_path / "test.txt"
        test_file.write_text("这是测试内容。这是更多内容。" * 10)

        doc = await document_manager.upload_document(str(test_file))
        processed_doc = await document_manager.process_document(doc.id)

        assert processed_doc.status == DocumentStatus.READY
        assert len(processed_doc.content) > 0
        assert len(processed_doc.chunks) > 0

    @pytest.mark.asyncio
    async def test_get_document(self, document_manager, tmp_path):
        """测试获取文档"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试内容")

        doc = await document_manager.upload_document(str(test_file))

        # 获取存在的文档
        retrieved = document_manager.get_document(doc.id)
        assert retrieved is not None
        assert retrieved.id == doc.id

        # 获取不存在的文档
        not_found = document_manager.get_document("nonexistent")
        assert not_found is None

    @pytest.mark.asyncio
    async def test_list_documents(self, document_manager, tmp_path):
        """测试列出文档"""
        # 创建多个文档
        for i in range(3):
            test_file = tmp_path / f"test{i}.txt"
            test_file.write_text(f"文档 {i} 内容")
            await document_manager.upload_document(str(test_file))

        # 列出所有文档
        docs = document_manager.list_documents()
        assert len(docs) == 3

        # 分页
        page1 = document_manager.list_documents(limit=2, offset=0)
        assert len(page1) == 2

    @pytest.mark.asyncio
    async def test_delete_document(self, document_manager, tmp_path):
        """测试删除文档"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试内容")

        doc = await document_manager.upload_document(str(test_file))

        # 删除文档
        result = await document_manager.delete_document(doc.id)
        assert result is True

        # 确认已删除
        assert document_manager.get_document(doc.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_document(self, document_manager):
        """测试删除不存在的文档"""
        with pytest.raises(DocumentNotFoundError):
            await document_manager.delete_document("nonexistent")

    def test_detect_document_type(self, document_manager):
        """测试检测文档类型"""
        assert document_manager._detect_document_type("test.pdf") == DocumentType.PDF
        assert document_manager._detect_document_type("test.docx") == DocumentType.WORD
        assert document_manager._detect_document_type("test.md") == DocumentType.MARKDOWN
        assert document_manager._detect_document_type("test.txt") == DocumentType.TXT
        assert document_manager._detect_document_type("test.html") == DocumentType.HTML
        assert document_manager._detect_document_type("test.unknown") == DocumentType.UNKNOWN

    def test_get_stats(self, document_manager):
        """测试获取统计信息"""
        stats = document_manager.get_stats()
        assert "total_documents" in stats
        assert "total_chunks" in stats
        assert "by_type" in stats
        assert "by_status" in stats


# ============ 向量存储测试 ============


class TestKnowledgeVectorStore:
    """测试知识库向量存储"""

    @pytest.fixture
    def mock_rag_store(self):
        """创建模拟的 RAGStore"""
        mock = MagicMock()
        mock.initialize = AsyncMock()
        mock.add_memories_batch = AsyncMock(return_value=["id1", "id2"])
        mock.search = AsyncMock(return_value=[
            {
                "memory_id": "chunk1",
                "content": "测试内容",
                "metadata": {"document_id": "doc1", "document_title": "测试文档"},
                "distance": 0.2,
            }
        ])
        mock.delete_memories_batch = AsyncMock(return_value=2)
        mock.get_stats = AsyncMock(return_value={
            "backend": "chroma",
            "total_memories": 10,
        })
        mock.count = AsyncMock(return_value=10)
        return mock

    @pytest.mark.asyncio
    async def test_add_document_chunks(self, mock_rag_store):
        """测试添加文档分块"""
        store = KnowledgeVectorStore(rag_store=mock_rag_store)
        await store.initialize()

        chunks = [
            Chunk(id="c1", document_id="doc1", content="内容1", position=0),
            Chunk(id="c2", document_id="doc1", content="内容2", position=1),
        ]

        ids = await store.add_document_chunks("doc1", chunks, "测试文档")

        assert len(ids) == 2
        mock_rag_store.add_memories_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_search(self, mock_rag_store):
        """测试搜索"""
        store = KnowledgeVectorStore(rag_store=mock_rag_store)
        await store.initialize()

        results = await store.search("查询", top_k=5)

        assert len(results) == 1
        assert results[0].chunk_id == "chunk1"
        assert results[0].document_id == "doc1"

    @pytest.mark.asyncio
    async def test_delete_document_chunks(self, mock_rag_store):
        """测试删除文档分块"""
        store = KnowledgeVectorStore(rag_store=mock_rag_store)
        await store.initialize()

        # 模拟搜索返回
        mock_rag_store.search = AsyncMock(return_value=[
            {"memory_id": "chunk1", "content": "内容", "metadata": {"document_id": "doc1"}, "distance": 0}
        ])

        deleted = await store.delete_document_chunks("doc1")

        assert deleted == 2
        mock_rag_store.delete_memories_batch.assert_called()

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_rag_store):
        """测试获取统计"""
        store = KnowledgeVectorStore(rag_store=mock_rag_store)
        await store.initialize()

        stats = await store.get_stats()

        assert stats["total_chunks"] == 10
        assert stats["backend"] == "chroma"


# ============ RAG 引擎测试 ============


class TestRAGEngine:
    """测试 RAG 引擎"""

    @pytest.fixture
    def mock_vector_store(self):
        """创建模拟的向量存储"""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[
            SearchResult(
                chunk_id="c1",
                document_id="doc1",
                content="这是相关内容，用于回答用户的问题。",
                score=0.8,
                metadata={},
                document_title="测试文档",
            )
        ])
        return mock

    @pytest.fixture
    def mock_llm_provider(self):
        """创建模拟的 LLM 提供者"""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="这是基于上下文的回答。")
        return mock

    @pytest.mark.asyncio
    async def test_retrieve(self, mock_vector_store, mock_llm_provider):
        """测试检索"""
        engine = RAGEngine(
            vector_store=mock_vector_store,
            llm_provider=mock_llm_provider,
        )

        results = await engine.retrieve("问题", top_k=5)

        assert len(results) == 1
        assert results[0].score == 0.8

    def test_build_context(self, mock_vector_store, mock_llm_provider):
        """测试构建上下文"""
        engine = RAGEngine(
            vector_store=mock_vector_store,
            llm_provider=mock_llm_provider,
        )

        results = [
            SearchResult(
                chunk_id="c1",
                document_id="doc1",
                content="内容1",
                score=0.8,
                document_title="文档1",
            ),
            SearchResult(
                chunk_id="c2",
                document_id="doc2",
                content="内容2",
                score=0.7,
                document_title="文档2",
            ),
        ]

        context = engine.build_context(results)

        assert "内容1" in context
        assert "内容2" in context
        assert "文档1" in context

    def test_format_sources(self, mock_vector_store, mock_llm_provider):
        """测试格式化来源"""
        engine = RAGEngine(
            vector_store=mock_vector_store,
            llm_provider=mock_llm_provider,
        )

        results = [
            SearchResult(
                chunk_id=f"c{i}",
                document_id=f"doc{i}",
                content=f"内容{i}" * 50,
                score=0.8 - i * 0.1,
                document_title=f"文档{i}",
            )
            for i in range(3)
        ]

        sources = engine.format_sources(results, max_sources=3)

        assert len(sources) <= 3
        assert all("document_id" in s for s in sources)


# ============ 问答系统测试 ============


class TestQASystem:
    """测试问答系统"""

    @pytest.fixture
    def mock_vector_store(self):
        """创建模拟的向量存储"""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[
            SearchResult(
                chunk_id="c1",
                document_id="doc1",
                content="RAG 是检索增强生成技术，结合了检索和生成。",
                score=0.85,
                metadata={},
                document_title="RAG 介绍",
            )
        ])
        return mock

    @pytest.fixture
    def mock_llm_provider(self):
        """创建模拟的 LLM 提供者"""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="RAG 是一种结合检索和生成的技术。")
        return mock

    @pytest.mark.asyncio
    async def test_answer(self, mock_vector_store, mock_llm_provider):
        """测试回答问题"""
        qa = QASystem(
            vector_store=mock_vector_store,
            llm_provider=mock_llm_provider,
        )

        response = await qa.answer("什么是 RAG?")

        assert response.answer is not None
        assert len(response.sources) > 0
        assert response.confidence > 0

    @pytest.mark.asyncio
    async def test_answer_empty_question(self, mock_vector_store, mock_llm_provider):
        """测试空问题"""
        qa = QASystem(
            vector_store=mock_vector_store,
            llm_provider=mock_llm_provider,
        )

        response = await qa.answer("")

        assert "请提供有效的问题" in response.answer
        assert response.confidence == 0.0

    @pytest.mark.asyncio
    async def test_answer_no_results(self, mock_vector_store, mock_llm_provider):
        """测试无检索结果"""
        mock_vector_store.search = AsyncMock(return_value=[])

        qa = QASystem(
            vector_store=mock_vector_store,
            llm_provider=mock_llm_provider,
        )

        response = await qa.answer("问题")

        assert "没有找到" in response.answer


# ============ 知识图谱测试 ============


class TestKnowledgeGraph:
    """测试知识图谱"""

    @pytest.fixture
    def mock_llm_provider(self):
        """创建模拟的 LLM 提供者"""
        mock = MagicMock()
        mock.generate_json = AsyncMock(return_value={
            "entities": [
                {"name": "张三", "type": "PERSON", "description": "软件工程师"},
                {"name": "科技公司", "type": "ORGANIZATION", "description": "一家科技公司"},
            ]
        })
        return mock

    @pytest.mark.asyncio
    async def test_extract_entities(self, mock_llm_provider):
        """测试提取实体"""
        kg = KnowledgeGraph(llm_provider=mock_llm_provider)

        text = "张三在科技公司工作。"
        entities = await kg.extract_entities(text)

        assert len(entities) == 2
        assert entities[0].name == "张三"
        assert entities[0].entity_type == "PERSON"

    @pytest.mark.asyncio
    async def test_extract_relations(self, mock_llm_provider):
        """测试提取关系"""
        mock_llm_provider.generate_json = AsyncMock(return_value={
            "relations": [
                {"source": "张三", "target": "科技公司", "type": "WORKS_FOR", "description": "工作关系"}
            ]
        })

        kg = KnowledgeGraph(llm_provider=mock_llm_provider)

        entities = [
            Entity(id="e1", name="张三", entity_type="PERSON"),
            Entity(id="e2", name="科技公司", entity_type="ORGANIZATION"),
        ]

        relations = await kg.extract_relations("张三在科技公司工作。", entities)

        assert len(relations) == 1
        assert relations[0].source_id == "e1"
        assert relations[0].target_id == "e2"

    def test_get_graph_data(self, mock_llm_provider):
        """测试获取图谱数据"""
        kg = KnowledgeGraph(llm_provider=mock_llm_provider)

        # 添加测试数据
        kg._entities["e1"] = Entity(id="e1", name="实体1", entity_type="PERSON")
        kg._entities["e2"] = Entity(id="e2", name="实体2", entity_type="ORGANIZATION")
        kg._relations["r1"] = Relation(
            id="r1", source_id="e1", target_id="e2", relation_type="WORKS_FOR"
        )

        data = kg.get_graph_data()

        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        assert data["stats"]["total_entities"] == 2
        assert data["stats"]["total_relations"] == 1

    def test_search_entities(self, mock_llm_provider):
        """测试搜索实体"""
        kg = KnowledgeGraph(llm_provider=mock_llm_provider)

        kg._entities["e1"] = Entity(id="e1", name="张三", entity_type="PERSON")
        kg._entities["e2"] = Entity(id="e2", name="李四", entity_type="PERSON")
        kg._entities["e3"] = Entity(id="e3", name="科技公司", entity_type="ORGANIZATION")

        results = kg.search_entities("张")

        assert len(results) == 1
        assert results[0].name == "张三"

    def test_get_relations_for_entity(self, mock_llm_provider):
        """测试获取实体的关系"""
        kg = KnowledgeGraph(llm_provider=mock_llm_provider)

        kg._entities["e1"] = Entity(id="e1", name="实体1", entity_type="PERSON")
        kg._entities["e2"] = Entity(id="e2", name="实体2", entity_type="ORGANIZATION")
        kg._relations["r1"] = Relation(
            id="r1", source_id="e1", target_id="e2", relation_type="WORKS_FOR"
        )

        relations = kg.get_relations_for_entity("e1")

        assert len(relations) == 1
        assert relations[0].source_id == "e1"


# ============ 类型测试 ============


class TestTypes:
    """测试数据类型"""

    def test_chunk_to_dict(self):
        """测试 Chunk 序列化"""
        chunk = Chunk(
            id="chunk1",
            document_id="doc1",
            content="测试内容",
            position=0,
        )

        d = chunk.to_dict()

        assert d["id"] == "chunk1"
        assert d["document_id"] == "doc1"
        assert d["content"] == "测试内容"

    def test_document_to_dict(self):
        """测试 Document 序列化"""
        doc = Document(
            id="doc1",
            title="测试文档",
            content="内容",
            doc_type=DocumentType.PDF,
            status=DocumentStatus.READY,
        )

        d = doc.to_dict()

        assert d["id"] == "doc1"
        assert d["title"] == "测试文档"
        assert d["doc_type"] == "pdf"
        assert d["status"] == "ready"

    def test_search_result_to_dict(self):
        """测试 SearchResult 序列化"""
        result = SearchResult(
            chunk_id="c1",
            document_id="doc1",
            content="内容",
            score=0.8,
        )

        d = result.to_dict()

        assert d["chunk_id"] == "c1"
        assert d["score"] == 0.8

    def test_qa_response_to_dict(self):
        """测试 QAResponse 序列化"""
        response = QAResponse(
            answer="回答",
            sources=[],
            confidence=0.9,
            query="问题",
        )

        d = response.to_dict()

        assert d["answer"] == "回答"
        assert d["confidence"] == 0.9
        assert d["query"] == "问题"

    def test_entity_to_dict(self):
        """测试 Entity 序列化"""
        entity = Entity(
            id="e1",
            name="张三",
            entity_type="PERSON",
            description="工程师",
        )

        d = entity.to_dict()

        assert d["name"] == "张三"
        assert d["entity_type"] == "PERSON"

    def test_relation_to_dict(self):
        """测试 Relation 序列化"""
        relation = Relation(
            id="r1",
            source_id="e1",
            target_id="e2",
            relation_type="WORKS_FOR",
        )

        d = relation.to_dict()

        assert d["source_id"] == "e1"
        assert d["target_id"] == "e2"
        assert d["relation_type"] == "WORKS_FOR"


# ============ 异常测试 ============


class TestExceptions:
    """测试异常类"""

    def test_document_not_found_error(self):
        """测试文档未找到异常"""
        error = DocumentNotFoundError("doc1")

        assert "doc1" in error.message
        assert error.details["document_id"] == "doc1"
        assert "DocumentNotFoundError" in error.to_dict()["error_type"]

    def test_document_processing_error(self):
        """测试文档处理异常"""
        error = DocumentProcessingError(
            "处理失败",
            document_id="doc1",
            stage="parsing",
        )

        assert error.details["document_id"] == "doc1"
        assert error.details["stage"] == "parsing"

    def test_chunking_error(self):
        """测试分块异常"""
        error = ChunkingError(
            "分块失败",
            document_id="doc1",
            strategy="semantic",
        )

        assert error.details["strategy"] == "semantic"