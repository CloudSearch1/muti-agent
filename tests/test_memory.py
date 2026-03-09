"""
记忆系统测试

测试 RAG 存储、上下文压缩、长期记忆等功能
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from src.memory import (
    RAGStore,
    MemoryItem,
    SimpleEmbeddingProvider,
    ContextCompressor,
    ContextWindow,
    CompressionStrategy,
    IncrementalCompressor,
    LongTermMemory,
    MemoryType,
    MemoryImportance,
    create_rag_store,
    create_compressor,
    create_long_term_memory,
)


# ============ Embedding Provider Tests ============

class TestSimpleEmbeddingProvider:
    """简单嵌入提供者测试"""

    def test_create_provider(self):
        """测试创建提供者"""
        provider = SimpleEmbeddingProvider(dimension=384)
        assert provider.dimension == 384

    def test_embed_returns_correct_dimension(self):
        """测试嵌入向量维度"""
        provider = SimpleEmbeddingProvider(dimension=128)
        vector = provider.embed("test text")
        assert len(vector) == 128

    def test_embed_normalizes_vector(self):
        """测试向量归一化"""
        provider = SimpleEmbeddingProvider()
        vector = provider.embed("test text")
        # L2 范数应该接近 1
        norm = sum(v * v for v in vector) ** 0.5
        assert abs(norm - 1.0) < 0.0001

    def test_embed_is_deterministic(self):
        """测试嵌入是确定性的"""
        provider = SimpleEmbeddingProvider()
        text = "deterministic test"
        vector1 = provider.embed(text)
        vector2 = provider.embed(text)
        assert vector1 == vector2

    def test_embed_batch(self):
        """测试批量嵌入"""
        provider = SimpleEmbeddingProvider()
        texts = ["text 1", "text 2", "text 3"]
        vectors = provider.embed_batch(texts)
        assert len(vectors) == 3
        for v in vectors:
            assert len(v) == 384


# ============ MemoryItem Tests ============

class TestMemoryItem:
    """记忆项测试"""

    def test_create_memory_item(self):
        """测试创建记忆项"""
        item = MemoryItem(
            content="test content",
            metadata={"key": "value"},
        )
        assert item.content == "test content"
        assert item.metadata == {"key": "value"}
        assert item.memory_id is not None

    def test_memory_item_auto_id(self):
        """测试自动生成 ID"""
        item1 = MemoryItem(content="content 1")
        item2 = MemoryItem(content="content 2")
        assert item1.memory_id != item2.memory_id

    def test_memory_item_to_dict(self):
        """测试转换为字典"""
        item = MemoryItem(
            content="test content",
            metadata={"type": "test"},
        )
        d = item.to_dict()
        assert d["content"] == "test content"
        assert d["metadata"] == {"type": "test"}
        assert "memory_id" in d
        assert "created_at" in d


# ============ RAG Store Tests ============

class TestRAGStore:
    """RAG 存储测试"""

    def test_create_rag_store(self):
        """测试创建 RAG 存储"""
        store = RAGStore(backend="chroma")
        assert store.backend == "chroma"
        assert store.collection_name == "intelliteam_memory"

    def test_create_rag_store_with_custom_config(self):
        """测试自定义配置创建"""
        store = RAGStore(
            backend="chroma",
            persist_directory="/tmp/test_vectordb",
            collection_name="test_collection",
        )
        assert store.persist_directory == "/tmp/test_vectordb"
        assert store.collection_name == "test_collection"

    def test_unsupported_backend_raises_error(self):
        """测试不支持的后端抛出错误"""
        store = RAGStore(backend="unsupported")
        with pytest.raises(ValueError, match="Unsupported backend"):
            asyncio.get_event_loop().run_until_complete(store.initialize())

    @pytest.mark.asyncio
    async def test_add_memory_with_mock(self):
        """测试添加记忆（使用 Mock）"""
        store = RAGStore(backend="chroma")
        store._collection = MagicMock()
        store._collection.add = MagicMock()

        memory_id = await store.add_memory(
            content="test memory content",
            metadata={"type": "test"},
        )

        assert memory_id is not None
        store._collection.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_mock(self):
        """测试搜索（使用 Mock）"""
        store = RAGStore(backend="chroma")
        store._collection = MagicMock()
        store._collection.query = MagicMock(return_value={
            "ids": [["mem-1", "mem-2"]],
            "documents": [["content 1", "content 2"]],
            "metadatas": [[{}, {}]],
            "distances": [[0.1, 0.2]],
        })

        results = await store.search("test query", top_k=2)

        assert len(results) == 2
        assert results[0]["memory_id"] == "mem-1"
        store._collection.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_memory_with_mock(self):
        """测试删除记忆（使用 Mock）"""
        store = RAGStore(backend="chroma")
        store._collection = MagicMock()
        store._collection.delete = MagicMock()

        result = await store.delete_memory("mem-001")

        assert result is True
        store._collection.delete.assert_called_once_with(ids=["mem-001"])

    @pytest.mark.asyncio
    async def test_get_stats_with_mock(self):
        """测试获取统计信息（使用 Mock）"""
        store = RAGStore(backend="chroma")
        store._collection = MagicMock()
        store._collection.count = MagicMock(return_value=10)

        stats = await store.get_stats()

        assert stats["backend"] == "chroma"
        assert stats["total_memories"] == 10


class TestRAGStoreBatch:
    """RAG 批量操作测试"""

    @pytest.mark.asyncio
    async def test_add_memories_batch(self):
        """测试批量添加记忆"""
        store = RAGStore(backend="chroma")
        store._collection = MagicMock()
        store._collection.add = MagicMock()

        items = [
            {"content": "content 1", "metadata": {"type": "a"}},
            {"content": "content 2", "metadata": {"type": "b"}},
            {"content": "content 3", "metadata": {"type": "c"}},
        ]

        ids = await store.add_memories_batch(items)

        assert len(ids) == 3
        store._collection.add.assert_called_once()


# ============ Context Window Tests ============

class TestContextWindow:
    """上下文窗口测试"""

    def test_create_context_window(self):
        """测试创建上下文窗口"""
        window = ContextWindow(max_tokens=4096, reserved_tokens=512)
        assert window.max_tokens == 4096
        assert window.reserved_tokens == 512
        assert window.available_tokens == 3584

    def test_estimate_tokens(self):
        """测试 token 估算"""
        window = ContextWindow()
        # 1 token ≈ 4 字符
        text = "a" * 100
        tokens = window.estimate_tokens(text)
        assert tokens == 26  # 100 // 4 + 1

    def test_can_fit_text(self):
        """测试文本是否适合窗口"""
        window = ContextWindow(max_tokens=100, reserved_tokens=10)
        short_text = "a" * 80
        long_text = "a" * 400

        assert window.can_fit(short_text) is True
        assert window.can_fit(long_text) is False

    def test_add_text_to_window(self):
        """测试添加文本到窗口"""
        window = ContextWindow(max_tokens=100, reserved_tokens=10)
        text = "a" * 80

        result = window.add(text)
        assert result is True
        assert window._current_usage > 0

    def test_add_exceeds_capacity(self):
        """测试添加超出容量"""
        window = ContextWindow(max_tokens=100, reserved_tokens=10)
        text = "a" * 400

        result = window.add(text)
        assert result is False
        assert window._current_usage == 0

    def test_remove_text_from_window(self):
        """测试从窗口移除文本"""
        window = ContextWindow(max_tokens=100, reserved_tokens=10)
        text = "a" * 80
        window.add(text)

        window.remove(text)
        assert window._current_usage == 0

    def test_usage_percent(self):
        """测试使用率百分比"""
        window = ContextWindow(max_tokens=100, reserved_tokens=0)
        window._current_usage = 50

        assert window.usage_percent == 50.0

    def test_reset_window(self):
        """测试重置窗口"""
        window = ContextWindow(max_tokens=100, reserved_tokens=10)
        window.add("a" * 80)

        window.reset()
        assert window._current_usage == 0


# ============ Context Compressor Tests ============

class TestContextCompressor:
    """上下文压缩器测试"""

    def test_create_compressor(self):
        """测试创建压缩器"""
        compressor = ContextCompressor(
            strategy=CompressionStrategy.HYBRID,
            max_tokens=4096,
        )
        assert compressor.strategy == CompressionStrategy.HYBRID
        assert compressor.max_tokens == 4096

    @pytest.mark.asyncio
    async def test_compress_short_content(self):
        """测试压缩短内容（不压缩）"""
        compressor = ContextCompressor()
        short_content = "short content"

        result = await compressor.compress(short_content)

        assert result["compressed"] == short_content
        assert result["strategy"] == "none"

    @pytest.mark.asyncio
    async def test_compress_with_truncate(self):
        """测试截断压缩"""
        compressor = ContextCompressor(strategy=CompressionStrategy.SLIDING_WINDOW)
        long_content = "a" * 1000

        result = await compressor.compress(long_content, target_ratio=0.5)

        assert len(result["compressed"]) < len(long_content)
        assert result["strategy"] == "sliding_window"

    @pytest.mark.asyncio
    async def test_compress_with_key_points(self):
        """测试关键点提取"""
        compressor = ContextCompressor(strategy=CompressionStrategy.KEY_POINTS)
        # Content must be at least MIN_CONTENT_LENGTH (100 chars)
        content = "这是一个重要内容，需要重点关注和记录，请务必仔细阅读。这是关键结论，对整体方案有决定性影响，不可忽视。这是普通句子，没有特殊含义，仅供参考。需要注意这一点，否则可能导致严重问题。还有其他一些补充说明内容，确保方案的完整性和可操作性。"  # noqa: E501

        result = await compressor.compress(content, target_ratio=0.5)

        assert "compressed" in result
        assert result["strategy"] in ["key_points", "key_points_simple"]

    @pytest.mark.asyncio
    async def test_compress_conversation(self):
        """测试压缩对话历史"""
        compressor = ContextCompressor()
        messages = [
            {"role": "user", "content": "message 1"},
            {"role": "assistant", "content": "response 1"},
            {"role": "user", "content": "message 2"},
            {"role": "assistant", "content": "response 2"},
            {"role": "user", "content": "recent message"},
        ]

        compressed = await compressor.compress_conversation(messages, keep_recent=2)

        assert len(compressed) == 3  # 1 summary + 2 recent
        assert compressed[0]["role"] == "system"
        assert compressed[-1]["role"] == "user"

    def test_get_compression_stats(self):
        """测试获取压缩统计"""
        compressor = ContextCompressor()
        stats = compressor.get_compression_stats()

        assert "strategy" in stats
        assert "max_tokens" in stats
        assert "context_window_usage" in stats


class TestIncrementalCompressor:
    """增量压缩器测试"""

    def test_create_incremental_compressor(self):
        """测试创建增量压缩器"""
        compressor = IncrementalCompressor()
        assert compressor._compressed_cache == {}
        assert compressor._original_cache == {}

    @pytest.mark.asyncio
    async def test_first_compression(self):
        """测试首次压缩"""
        compressor = IncrementalCompressor()
        content = "a" * 200

        result = await compressor.update_content("test-id", content)

        assert result["changed"] is True
        assert "compressed" in result
        assert "test-id" in compressor._original_cache

    @pytest.mark.asyncio
    async def test_unchanged_content(self):
        """测试未变化内容"""
        compressor = IncrementalCompressor()
        content = "a" * 200

        await compressor.update_content("test-id", content)
        result = await compressor.update_content("test-id", content)

        assert result["changed"] is False

    @pytest.mark.asyncio
    async def test_incremental_add(self):
        """测试增量添加"""
        compressor = IncrementalCompressor()
        original = "a" * 200
        added = "b" * 100

        await compressor.update_content("test-id", original)
        result = await compressor.update_content("test-id", original + added)

        assert result["changed"] is True
        assert result["strategy"] == "incremental_add"

    def test_clear_cache(self):
        """测试清空缓存"""
        compressor = IncrementalCompressor()
        compressor._compressed_cache["id1"] = "compressed"
        compressor._original_cache["id1"] = "original"

        compressor.clear_cache()

        assert len(compressor._compressed_cache) == 0
        assert len(compressor._original_cache) == 0


# ============ Long Term Memory Tests ============

class TestMemoryEnums:
    """记忆枚举测试"""

    def test_memory_type_values(self):
        """测试记忆类型值"""
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.PROCEDURAL.value == "procedural"
        assert MemoryType.CONVERSATION.value == "conversation"
        assert MemoryType.TASK_RESULT.value == "task_result"

    def test_memory_importance_values(self):
        """测试记忆重要性值"""
        assert MemoryImportance.LOW.value == "low"
        assert MemoryImportance.MEDIUM.value == "medium"
        assert MemoryImportance.HIGH.value == "high"
        assert MemoryImportance.CRITICAL.value == "critical"


class TestLongTermMemory:
    """长期记忆测试"""

    @pytest.mark.skipif(
        not hasattr(LongTermMemory, '__module__'),
        reason="Requires SQLAlchemy"
    )
    def test_create_long_term_memory(self):
        """测试创建长期记忆"""
        # 使用内存数据库
        ltm = LongTermMemory(db_url="sqlite:///:memory:")
        assert ltm.db_url == "sqlite:///:memory:"


# ============ Factory Functions Tests ============

class TestFactoryFunctions:
    """工厂函数测试"""

    def test_create_rag_store_factory(self):
        """测试 RAG 存储工厂函数"""
        store = create_rag_store(backend="chroma")
        assert isinstance(store, RAGStore)

    def test_create_compressor_factory(self):
        """测试压缩器工厂函数"""
        compressor = create_compressor(strategy=CompressionStrategy.HYBRID)
        assert isinstance(compressor, ContextCompressor)


# ============ Edge Cases Tests ============

class TestEdgeCases:
    """边界情况测试"""

    @pytest.mark.asyncio
    async def test_compress_empty_content(self):
        """测试压缩空内容"""
        compressor = ContextCompressor()
        result = await compressor.compress("")

        assert result["compressed"] == ""
        assert result["original_length"] == 0

    @pytest.mark.asyncio
    async def test_compress_none_content(self):
        """测试压缩 None 内容"""
        compressor = ContextCompressor()
        # 应该抛出异常或返回空
        with pytest.raises((TypeError, AttributeError)):
            await compressor.compress(None)

    def test_context_window_zero_max_tokens(self):
        """测试零最大 token"""
        window = ContextWindow(max_tokens=0, reserved_tokens=0)
        assert window.available_tokens == 0
        assert window.can_fit("any text") is False

    @pytest.mark.asyncio
    async def test_search_empty_query(self):
        """测试空查询"""
        store = RAGStore(backend="chroma")
        store._collection = MagicMock()
        store._collection.query = MagicMock(return_value={
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        })

        results = await store.search("", top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_compress_conversation_empty_messages(self):
        """测试压缩空消息列表"""
        compressor = ContextCompressor()
        result = await compressor.compress_conversation([])
        assert result == []

    @pytest.mark.asyncio
    async def test_compress_conversation_single_message(self):
        """测试压缩单条消息"""
        compressor = ContextCompressor()
        messages = [{"role": "user", "content": "single message"}]
        result = await compressor.compress_conversation(messages)
        assert result == messages


# ============ Performance Tests ============

class TestPerformance:
    """性能测试"""

    @pytest.mark.slow
    def test_embedding_performance(self):
        """测试嵌入性能"""
        import time
        provider = SimpleEmbeddingProvider()

        start = time.time()
        for _ in range(100):
            provider.embed("test text for performance")
        elapsed = time.time() - start

        # 100 次嵌入应该在 1 秒内完成
        assert elapsed < 1.0

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_batch_vs_single_performance(self):
        """测试批量 vs 单个性能"""
        provider = SimpleEmbeddingProvider()
        texts = [f"text {i}" for i in range(100)]

        import time

        # 批量
        start = time.time()
        provider.embed_batch(texts)
        batch_time = time.time() - start

        # 单个
        start = time.time()
        for text in texts:
            provider.embed(text)
        single_time = time.time() - start

        # 批量应该更快
        assert batch_time <= single_time * 1.5  # 允许一些开销