"""
Memory API 测试

测试 Memory 系统的 CRUD API 端点
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# ===========================================
# Fixtures
# ===========================================


@pytest.fixture
def mock_short_term_memory():
    """Mock 短期记忆"""
    memory = MagicMock()
    memory.set = AsyncMock(return_value=True)
    memory.get = AsyncMock(return_value={
        "content": "test content",
        "memory_type": "episodic",
        "importance": "medium",
        "tags": ["test"],
        "metadata": {},
        "created_at": datetime.now().isoformat(),
    })
    memory.delete = AsyncMock(return_value=True)
    memory.get_stats = AsyncMock(return_value={
        "total_keys": 10,
        "used_memory": 1024,
    })
    return memory


@pytest.fixture
def mock_long_term_memory():
    """Mock 长期记忆"""
    memory = MagicMock()
    memory.store = AsyncMock(return_value="test-memory-id-123")
    memory.retrieve = AsyncMock(return_value={
        "id": 1,
        "memory_id": "test-memory-id-123",
        "content": "test content",
        "memory_type": "episodic",
        "importance": "medium",
        "summary": "test summary",
        "tags": ["test"],
        "metadata": {},
        "agent_id": None,
        "session_id": None,
        "task_id": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "access_count": 1,
    })
    memory.search = AsyncMock(return_value=[])
    memory.delete = AsyncMock(return_value=True)
    memory.get_stats = AsyncMock(return_value={
        "total_count": 100,
        "by_type": {"episodic": 50, "semantic": 30, "procedural": 20},
        "by_importance": {"low": 20, "medium": 50, "high": 25, "critical": 5},
        "recently_accessed_24h": 10,
        "rag_enabled": False,
    })
    memory.get_important_memories = AsyncMock(return_value=[])
    return memory


@pytest.fixture
def mock_rag_store():
    """Mock RAG 存储"""
    store = MagicMock()
    store.initialize = AsyncMock()
    store.add_memory = AsyncMock(return_value="vector-id-456")
    store.get_memory = AsyncMock(return_value={
        "memory_id": "vector-id-456",
        "content": "test content",
        "metadata": {
            "memory_type": "episodic",
            "importance": "medium",
        },
    })
    store.search = AsyncMock(return_value=[
        {
            "memory_id": "result-1",
            "content": "similar content",
            "metadata": {"memory_type": "episodic"},
            "distance": 0.85,
        }
    ])
    store.delete_memory = AsyncMock(return_value=True)
    store.get_stats = AsyncMock(return_value={
        "total_memories": 50,
        "backend": "chroma",
    })
    return store


# ===========================================
# Request/Response Model Tests
# ===========================================


class TestMemoryStoreRequest:
    """存储记忆请求测试"""

    def test_valid_request(self):
        """测试有效请求"""
        from src.api.routes.memory import MemoryStoreRequest

        request = MemoryStoreRequest(
            content="Test memory content",
            memory_type="episodic",
            storage="long_term",
            importance="high",
        )
        assert request.content == "Test memory content"
        assert request.memory_type == "episodic"
        assert request.storage == "long_term"
        assert request.importance == "high"

    def test_default_values(self):
        """测试默认值"""
        from src.api.routes.memory import MemoryStoreRequest

        request = MemoryStoreRequest(content="Test")
        assert request.memory_type == "episodic"
        assert request.storage == "long_term"
        assert request.importance == "medium"
        assert request.tags == []
        assert request.metadata == {}

    def test_with_tags_and_metadata(self):
        """测试带标签和元数据"""
        from src.api.routes.memory import MemoryStoreRequest

        request = MemoryStoreRequest(
            content="Test",
            tags=["important", "project"],
            metadata={"key": "value"},
        )
        assert "important" in request.tags
        assert request.metadata["key"] == "value"


class TestMemorySearchRequest:
    """搜索记忆请求测试"""

    def test_valid_request(self):
        """测试有效请求"""
        from src.api.routes.memory import MemorySearchRequest

        request = MemorySearchRequest(
            query="test query",
            limit=20,
        )
        assert request.query == "test query"
        assert request.limit == 20

    def test_default_values(self):
        """测试默认值"""
        from src.api.routes.memory import MemorySearchRequest

        request = MemorySearchRequest()
        assert request.storage == "long_term"
        assert request.limit == 10
        assert request.offset == 0


class TestMemoryResponse:
    """记忆响应测试"""

    def test_create_response(self):
        """测试创建响应"""
        from src.api.routes.memory import MemoryResponse

        response = MemoryResponse(
            id="test-id",
            content="test content",
            memory_type="episodic",
            importance="high",
        )
        assert response.id == "test-id"
        assert response.content == "test content"
        assert response.memory_type == "episodic"
        assert response.importance == "high"


# ===========================================
# API Endpoint Tests
# ===========================================


class TestStoreMemory:
    """存储记忆端点测试"""

    @pytest.mark.asyncio
    async def test_store_long_term_memory(self, mock_long_term_memory):
        """测试存储长期记忆"""
        from src.api.routes.memory import store_memory, MemoryStoreRequest

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            request = MemoryStoreRequest(
                content="Test content",
                memory_type="episodic",
                storage="long_term",
                importance="high",
            )

            response = await store_memory(request)

            assert response.id == "test-memory-id-123"
            assert response.content == "Test content"
            mock_long_term_memory.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_short_term_memory(self, mock_short_term_memory):
        """测试存储短期记忆"""
        from src.api.routes.memory import store_memory, MemoryStoreRequest

        with patch(
            "src.api.routes.memory.get_short_term_memory",
            return_value=mock_short_term_memory,
        ):
            request = MemoryStoreRequest(
                content="Test content",
                storage="short_term",
                ttl=3600,
            )

            response = await store_memory(request)

            assert response.id is not None
            assert response.content == "Test content"
            mock_short_term_memory.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_vector_memory(self, mock_rag_store):
        """测试存储向量记忆"""
        from src.api.routes.memory import store_memory, MemoryStoreRequest

        with patch(
            "src.api.routes.memory.get_rag_store",
            return_value=mock_rag_store,
        ):
            request = MemoryStoreRequest(
                content="Test content",
                storage="vector",
            )

            response = await store_memory(request)

            assert response.id == "vector-id-456"
            mock_rag_store.add_memory.assert_called_once()


class TestGetMemory:
    """获取记忆端点测试"""

    @pytest.mark.asyncio
    async def test_get_long_term_memory(self, mock_long_term_memory):
        """测试获取长期记忆"""
        from src.api.routes.memory import get_memory

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            response = await get_memory("test-memory-id-123", storage="long_term")

            assert response.id == "test-memory-id-123"
            assert response.content == "test content"
            mock_long_term_memory.retrieve.assert_called_once_with("test-memory-id-123")

    @pytest.mark.asyncio
    async def test_get_short_term_memory(self, mock_short_term_memory):
        """测试获取短期记忆"""
        from src.api.routes.memory import get_memory

        with patch(
            "src.api.routes.memory.get_short_term_memory",
            return_value=mock_short_term_memory,
        ):
            response = await get_memory("test-key", storage="short_term")

            assert response.id == "test-key"
            mock_short_term_memory.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_memory_not_found(self, mock_long_term_memory):
        """测试获取不存在的记忆"""
        from src.api.routes.memory import get_memory
        from fastapi import HTTPException

        mock_long_term_memory.retrieve = AsyncMock(return_value=None)

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_memory("non-existent", storage="long_term")

            assert exc_info.value.status_code == 404


class TestDeleteMemory:
    """删除记忆端点测试"""

    @pytest.mark.asyncio
    async def test_delete_long_term_memory(self, mock_long_term_memory):
        """测试删除长期记忆"""
        from src.api.routes.memory import delete_memory

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            response = await delete_memory("test-memory-id-123", storage="long_term")

            assert response["status"] == "deleted"
            mock_long_term_memory.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_memory_not_found(self, mock_long_term_memory):
        """测试删除不存在的记忆"""
        from src.api.routes.memory import delete_memory
        from fastapi import HTTPException

        mock_long_term_memory.delete = AsyncMock(return_value=False)

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await delete_memory("non-existent", storage="long_term")

            assert exc_info.value.status_code == 404


class TestSearchMemories:
    """搜索记忆端点测试"""

    @pytest.mark.asyncio
    async def test_search_long_term_memory(self, mock_long_term_memory):
        """测试搜索长期记忆"""
        from src.api.routes.memory import search_memories, MemorySearchRequest

        mock_long_term_memory.search = AsyncMock(return_value=[
            {
                "memory_id": "result-1",
                "content": "test result",
                "memory_type": "episodic",
                "importance": "medium",
                "tags": [],
                "metadata": {},
            }
        ])

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            request = MemorySearchRequest(
                query="test",
                storage="long_term",
            )

            response = await search_memories(request)

            assert len(response.memories) == 1
            assert response.memories[0].content == "test result"

    @pytest.mark.asyncio
    async def test_search_vector_memory(self, mock_rag_store):
        """测试向量搜索"""
        from src.api.routes.memory import search_memories, MemorySearchRequest

        with patch(
            "src.api.routes.memory.get_rag_store",
            return_value=mock_rag_store,
        ):
            request = MemorySearchRequest(
                query="test query",
                storage="vector",
            )

            response = await search_memories(request)

            assert len(response.memories) == 1
            assert response.memories[0].similarity_score == 0.85
            mock_rag_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_search_requires_query(self, mock_rag_store):
        """测试向量搜索需要查询"""
        from src.api.routes.memory import search_memories, MemorySearchRequest
        from fastapi import HTTPException

        with patch(
            "src.api.routes.memory.get_rag_store",
            return_value=mock_rag_store,
        ):
            request = MemorySearchRequest(
                query=None,
                storage="vector",
            )

            with pytest.raises(HTTPException) as exc_info:
                await search_memories(request)

            assert exc_info.value.status_code == 400


class TestListMemories:
    """列出记忆端点测试"""

    @pytest.mark.asyncio
    async def test_list_long_term_memories(self, mock_long_term_memory):
        """测试列出长期记忆"""
        from src.api.routes.memory import list_memories

        mock_long_term_memory.search = AsyncMock(return_value=[
            {
                "memory_id": "mem-1",
                "content": "content 1",
                "memory_type": "episodic",
                "importance": "medium",
                "tags": [],
                "metadata": {},
            },
            {
                "memory_id": "mem-2",
                "content": "content 2",
                "memory_type": "semantic",
                "importance": "high",
                "tags": [],
                "metadata": {},
            }
        ])

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            response = await list_memories(
                storage="long_term",
                memory_type=None,
                importance=None,
                agent_id=None,
                session_id=None,
                limit=10,
                offset=0,
            )

            assert len(response.memories) == 2
            assert response.limit == 10


class TestGetMemoryStats:
    """获取记忆统计端点测试"""

    @pytest.mark.asyncio
    async def test_get_long_term_stats(self, mock_long_term_memory):
        """测试获取长期记忆统计"""
        from src.api.routes.memory import get_memory_stats

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            response = await get_memory_stats(storage="long_term")

            assert response.storage_type == "long_term"
            assert response.total_count == 100
            assert response.by_type is not None

    @pytest.mark.asyncio
    async def test_get_short_term_stats(self, mock_short_term_memory):
        """测试获取短期记忆统计"""
        from src.api.routes.memory import get_memory_stats

        with patch(
            "src.api.routes.memory.get_short_term_memory",
            return_value=mock_short_term_memory,
        ):
            response = await get_memory_stats(storage="short_term")

            assert response.storage_type == "short_term"
            assert response.total_count == 10


class TestGetImportantMemories:
    """获取重要记忆端点测试"""

    @pytest.mark.asyncio
    async def test_get_important_memories(self, mock_long_term_memory):
        """测试获取重要记忆"""
        from src.api.routes.memory import get_important_memories

        mock_long_term_memory.get_important_memories = AsyncMock(return_value=[
            {
                "memory_id": "important-1",
                "content": "critical info",
                "memory_type": "episodic",
                "importance": "critical",
                "tags": [],
                "metadata": {},
            }
        ])

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            response = await get_important_memories(limit=5)

            assert len(response.memories) == 1
            assert response.memories[0].importance == "critical"


# ===========================================
# Edge Cases Tests
# ===========================================


class TestMemoryAPIEdgeCases:
    """Memory API 边界情况测试"""

    @pytest.mark.asyncio
    async def test_store_with_invalid_memory_type(self, mock_long_term_memory):
        """测试无效记忆类型"""
        from src.api.routes.memory import store_memory, MemoryStoreRequest
        from fastapi import HTTPException

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            request = MemoryStoreRequest(
                content="Test",
                memory_type="invalid_type",
                storage="long_term",
            )

            with pytest.raises(HTTPException):
                await store_memory(request)

    @pytest.mark.asyncio
    async def test_store_with_invalid_importance(self, mock_long_term_memory):
        """测试无效重要性"""
        from src.api.routes.memory import store_memory, MemoryStoreRequest
        from fastapi import HTTPException

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            request = MemoryStoreRequest(
                content="Test",
                importance="invalid",
                storage="long_term",
            )

            with pytest.raises(HTTPException):
                await store_memory(request)

    @pytest.mark.asyncio
    async def test_search_with_pagination(self, mock_long_term_memory):
        """测试分页搜索"""
        from src.api.routes.memory import search_memories, MemorySearchRequest

        mock_long_term_memory.search = AsyncMock(return_value=[])

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            request = MemorySearchRequest(
                query="test",
                limit=50,
                offset=100,
            )

            response = await search_memories(request)

            assert response.limit == 50
            assert response.offset == 100

    def test_memory_response_with_none_values(self):
        """测试响应包含 None 值"""
        from src.api.routes.memory import MemoryResponse

        response = MemoryResponse(
            id="test",
            content="content",
            memory_type=None,
            importance=None,
        )

        assert response.id == "test"
        assert response.memory_type is None

    def test_memory_list_response_empty(self):
        """测试空记忆列表响应"""
        from src.api.routes.memory import MemoryListResponse

        response = MemoryListResponse(
            memories=[],
            total=0,
            limit=10,
            offset=0,
        )

        assert len(response.memories) == 0
        assert response.total == 0


# ===========================================
# Integration Tests
# ===========================================


class TestMemoryAPIIntegration:
    """Memory API 集成测试"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_memory_lifecycle(self, mock_long_term_memory):
        """测试完整记忆生命周期"""
        from src.api.routes.memory import (
            store_memory,
            get_memory,
            delete_memory,
            MemoryStoreRequest,
        )

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            # 存储
            store_request = MemoryStoreRequest(
                content="Lifecycle test",
                storage="long_term",
            )
            stored = await store_memory(store_request)
            assert stored.id is not None

            # 获取
            retrieved = await get_memory(stored.id, storage="long_term")
            assert retrieved.id == stored.id

            # 删除
            deleted = await delete_memory(stored.id, storage="long_term")
            assert deleted["status"] == "deleted"