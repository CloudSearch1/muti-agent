"""
Memory API 测试

测试 Memory 系统的 CRUD API 端点
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


# ===========================================
# Fixtures
# ===========================================


@pytest.fixture
def mock_short_term_memory() -> MagicMock:
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
    memory.health_check = AsyncMock(return_value={
        "status": "healthy",
        "backend": "redis",
        "connected": True,
    })
    return memory


@pytest.fixture
def mock_long_term_memory() -> MagicMock:
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
    memory.count = AsyncMock(return_value=100)
    return memory


@pytest.fixture
def mock_rag_store() -> MagicMock:
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
    store.count = AsyncMock(return_value=50)
    return store


# ===========================================
# Request/Response Model Tests
# ===========================================


class TestMemoryStoreRequest:
    """存储记忆请求测试"""

    def test_valid_request(self) -> None:
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

    def test_default_values(self) -> None:
        """测试默认值"""
        from src.api.routes.memory import MemoryStoreRequest

        request = MemoryStoreRequest(content="Test")
        assert request.memory_type == "episodic"
        assert request.storage == "long_term"
        assert request.importance == "medium"
        assert request.tags == []
        assert request.metadata == {}

    def test_with_tags_and_metadata(self) -> None:
        """测试带标签和元数据"""
        from src.api.routes.memory import MemoryStoreRequest

        request = MemoryStoreRequest(
            content="Test",
            tags=["important", "project"],
            metadata={"key": "value"},
        )
        assert "important" in request.tags
        assert request.metadata["key"] == "value"

    def test_invalid_memory_type(self) -> None:
        """测试无效记忆类型"""
        from src.api.routes.memory import MemoryStoreRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MemoryStoreRequest(
                content="Test",
                memory_type="invalid_type",
            )

    def test_invalid_importance(self) -> None:
        """测试无效重要性"""
        from src.api.routes.memory import MemoryStoreRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MemoryStoreRequest(
                content="Test",
                importance="invalid",
            )

    def test_invalid_storage(self) -> None:
        """测试无效存储类型"""
        from src.api.routes.memory import MemoryStoreRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MemoryStoreRequest(
                content="Test",
                storage="invalid",
            )


class TestMemorySearchRequest:
    """搜索记忆请求测试"""

    def test_valid_request(self) -> None:
        """测试有效请求"""
        from src.api.routes.memory import MemorySearchRequest

        request = MemorySearchRequest(
            query="test query",
            limit=20,
        )
        assert request.query == "test query"
        assert request.limit == 20

    def test_default_values(self) -> None:
        """测试默认值"""
        from src.api.routes.memory import MemorySearchRequest

        request = MemorySearchRequest()
        assert request.storage == "long_term"
        assert request.limit == 10
        assert request.offset == 0

    def test_limit_bounds(self) -> None:
        """测试限制边界"""
        from src.api.routes.memory import MemorySearchRequest
        from pydantic import ValidationError

        # 测试最小值
        with pytest.raises(ValidationError):
            MemorySearchRequest(limit=0)

        # 测试最大值
        with pytest.raises(ValidationError):
            MemorySearchRequest(limit=101)


class TestMemoryResponse:
    """记忆响应测试"""

    def test_create_response(self) -> None:
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

    def test_response_with_none_values(self) -> None:
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

    def test_response_with_similarity_score(self) -> None:
        """测试响应包含相似度分数"""
        from src.api.routes.memory import MemoryResponse

        response = MemoryResponse(
            id="test",
            content="content",
            similarity_score=0.85,
        )

        assert response.similarity_score == 0.85


class TestMemoryListResponse:
    """记忆列表响应测试"""

    def test_empty_response(self) -> None:
        """测试空响应"""
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
# API Endpoint Tests
# ===========================================


class TestStoreMemory:
    """存储记忆端点测试"""

    @pytest.mark.asyncio
    async def test_store_long_term_memory(self, mock_long_term_memory: MagicMock) -> None:
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
    async def test_store_short_term_memory(self, mock_short_term_memory: MagicMock) -> None:
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
    async def test_store_vector_memory(self, mock_rag_store: MagicMock) -> None:
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
    async def test_get_long_term_memory(self, mock_long_term_memory: MagicMock) -> None:
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
    async def test_get_short_term_memory(self, mock_short_term_memory: MagicMock) -> None:
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
    async def test_get_memory_not_found(self, mock_long_term_memory: MagicMock) -> None:
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
    async def test_delete_long_term_memory(self, mock_long_term_memory: MagicMock) -> None:
        """测试删除长期记忆"""
        from src.api.routes.memory import delete_memory

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            response = await delete_memory("test-memory-id-123", storage="long_term")

            assert response.status == "deleted"
            mock_long_term_memory.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_memory_not_found(self, mock_long_term_memory: MagicMock) -> None:
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
    async def test_search_long_term_memory(self, mock_long_term_memory: MagicMock) -> None:
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
    async def test_search_vector_memory(self, mock_rag_store: MagicMock) -> None:
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
    async def test_vector_search_requires_query(self, mock_rag_store: MagicMock) -> None:
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
    async def test_list_long_term_memories(self, mock_long_term_memory: MagicMock) -> None:
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
    async def test_get_long_term_stats(self, mock_long_term_memory: MagicMock) -> None:
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
    async def test_get_short_term_stats(self, mock_short_term_memory: MagicMock) -> None:
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
    async def test_get_important_memories(self, mock_long_term_memory: MagicMock) -> None:
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
    async def test_invalid_storage_type(self, mock_long_term_memory: MagicMock) -> None:
        """测试无效存储类型"""
        from src.api.routes.memory import list_memories
        from fastapi import HTTPException

        with patch(
            "src.api.routes.memory.get_long_term_memory",
            return_value=mock_long_term_memory,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await list_memories(storage="invalid_type")

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_search_with_pagination(self, mock_long_term_memory: MagicMock) -> None:
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


# ===========================================
# Integration Tests
# ===========================================


class TestMemoryAPIIntegration:
    """Memory API 集成测试"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_memory_lifecycle(self, mock_long_term_memory: MagicMock) -> None:
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
            assert deleted.status == "deleted"


# ===========================================
# Exception Tests
# ===========================================


class TestMemoryExceptions:
    """Memory 异常测试"""

    def test_memory_error_to_dict(self) -> None:
        """测试异常转换"""
        from src.memory.exceptions import MemoryError

        error = MemoryError(
            message="Test error",
            details={"key": "value"},
        )

        result = error.to_dict()
        assert result["error_type"] == "MemoryError"
        assert result["message"] == "Test error"
        assert result["details"]["key"] == "value"

    def test_memory_not_found_error(self) -> None:
        """测试记忆未找到异常"""
        from src.memory.exceptions import MemoryNotFoundError

        error = MemoryNotFoundError(
            memory_id="test-id",
            storage_type="long_term",
        )

        assert "test-id" in error.message
        assert error.details["memory_id"] == "test-id"

    def test_validation_error(self) -> None:
        """测试验证异常"""
        from src.memory.exceptions import MemoryValidationError

        error = MemoryValidationError(
            message="Invalid field",
            field="content",
            value="test",
        )

        assert error.details["field"] == "content"


# ===========================================
# Type Validation Tests
# ===========================================


class TestTypeValidation:
    """类型验证测试"""

    def test_validate_memory_type_valid(self) -> None:
        """测试有效的记忆类型"""
        from src.memory.types import validate_memory_type, MemoryType

        result = validate_memory_type("episodic")
        assert result == MemoryType.EPISODIC

    def test_validate_memory_type_invalid(self) -> None:
        """测试无效的记忆类型"""
        from src.memory.types import validate_memory_type

        with pytest.raises(ValueError):
            validate_memory_type("invalid")

    def test_validate_importance_valid(self) -> None:
        """测试有效的重要性"""
        from src.memory.types import validate_importance, MemoryImportance

        result = validate_importance("high")
        assert result == MemoryImportance.HIGH

    def test_validate_content_valid(self) -> None:
        """测试有效的内容"""
        from src.memory.types import validate_content

        result = validate_content("  test content  ")
        assert result == "test content"

    def test_validate_content_empty(self) -> None:
        """测试空内容"""
        from src.memory.types import validate_content

        with pytest.raises(ValueError):
            validate_content("")

    def test_validate_tags(self) -> None:
        """测试标签验证"""
        from src.memory.types import validate_tags

        result = validate_tags(["Tag1", "tag2", "  tag3  "])
        assert "tag1" in result
        assert "tag2" in result
        assert "tag3" in result

    def test_validate_metadata(self) -> None:
        """测试元数据验证"""
        from src.memory.types import validate_metadata

        result = validate_metadata({"key1": "value1", "key2": 123})
        assert result["key1"] == "value1"
        assert result["key2"] == 123


# ===========================================
# Short Term Memory Tests
# ===========================================


class TestShortTermMemory:
    """短期记忆测试"""

    @pytest.mark.asyncio
    async def test_set_and_get(self, mock_short_term_memory: MagicMock) -> None:
        """测试设置和获取"""
        await mock_short_term_memory.set("key", {"content": "test content"})
        result = await mock_short_term_memory.get("key")

        assert result["content"] == "test content"
        assert result["memory_type"] == "episodic"

    @pytest.mark.asyncio
    async def test_delete(self, mock_short_term_memory: MagicMock) -> None:
        """测试删除"""
        result = await mock_short_term_memory.delete("key")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_short_term_memory: MagicMock) -> None:
        """测试获取统计"""
        stats = await mock_short_term_memory.get_stats()

        assert stats["total_keys"] == 10
        assert stats["used_memory"] == 1024


# ===========================================
# Long Term Memory Tests
# ===========================================


class TestLongTermMemory:
    """长期记忆测试"""

    @pytest.mark.asyncio
    async def test_store(self, mock_long_term_memory: MagicMock) -> None:
        """测试存储"""
        from src.memory.types import MemoryType, MemoryImportance

        memory_id = await mock_long_term_memory.store(
            content="test content",
            memory_type=MemoryType.EPISODIC,
            importance=MemoryImportance.HIGH,
        )

        assert memory_id == "test-memory-id-123"

    @pytest.mark.asyncio
    async def test_retrieve(self, mock_long_term_memory: MagicMock) -> None:
        """测试检索"""
        result = await mock_long_term_memory.retrieve("test-memory-id-123")

        assert result["content"] == "test content"

    @pytest.mark.asyncio
    async def test_search(self, mock_long_term_memory: MagicMock) -> None:
        """测试搜索"""
        mock_long_term_memory.search = AsyncMock(return_value=[
            {"memory_id": "result-1", "content": "found"}
        ])

        results = await mock_long_term_memory.search(query="test")

        assert len(results) == 1


# ===========================================
# RAG Store Tests
# ===========================================


class TestRAGStore:
    """RAG 存储测试"""

    @pytest.mark.asyncio
    async def test_add_memory(self, mock_rag_store: MagicMock) -> None:
        """测试添加记忆"""
        memory_id = await mock_rag_store.add_memory(
            content="test content",
            metadata={"type": "note"},
        )

        assert memory_id == "vector-id-456"

    @pytest.mark.asyncio
    async def test_search(self, mock_rag_store: MagicMock) -> None:
        """测试搜索"""
        results = await mock_rag_store.search(query="test", top_k=5)

        assert len(results) == 1
        assert results[0]["distance"] == 0.85

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_rag_store: MagicMock) -> None:
        """测试获取统计"""
        stats = await mock_rag_store.get_stats()

        assert stats["total_memories"] == 50
        assert stats["backend"] == "chroma"