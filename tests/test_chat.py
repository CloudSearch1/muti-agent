"""
聊天消息模块测试

测试 ChatMessageModel、CRUD 操作、API 端点等功能
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select

from src.db.database import Base, ChatMessageModel
from src.db import crud


# ============ Helper Functions ============

async def create_test_db():
    """创建测试用的 SQLite 内存数据库"""
    from sqlalchemy import MetaData
    
    # 为每个测试创建新的元数据，避免索引冲突
    test_metadata = MetaData()
    
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine, async_session


# ============ ChatMessageModel Tests ============

class TestChatMessageModel:
    """聊天消息模型测试"""

    @pytest.mark.asyncio
    async def test_create_message(self):
        """测试创建消息"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            message = ChatMessageModel(
                session_id="test-session-123",
                role="user",
                content="Hello, World!",
                metadata={"source": "test"},
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            
            assert message.id is not None
            assert message.session_id == "test-session-123"
            assert message.role == "user"
            assert message.content == "Hello, World!"
            assert message.metadata == {"source": "test"}
            assert message.timestamp is not None

    @pytest.mark.asyncio
    async def test_message_to_dict(self):
        """测试消息转换为字典"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            message = ChatMessageModel(
                session_id="test-session-456",
                role="assistant",
                content="Response message",
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            
            msg_dict = message.to_dict()
            
            assert msg_dict["id"] == message.id
            assert msg_dict["session_id"] == "test-session-456"
            assert msg_dict["role"] == "assistant"
            assert msg_dict["content"] == "Response message"
            assert "timestamp" in msg_dict
            assert msg_dict["metadata"] == {}

    @pytest.mark.asyncio
    async def test_message_with_all_roles(self):
        """测试所有角色类型"""
        engine, async_session = await create_test_db()
        
        for role in ["user", "assistant", "system"]:
            async with async_session() as session:
                message = ChatMessageModel(
                    session_id=f"test-{role}",
                    role=role,
                    content=f"Message from {role}",
                )
                session.add(message)
                await session.commit()
                
                assert message.role == role


# ============ Chat CRUD Tests ============

class TestChatCRUD:
    """聊天 CRUD 操作测试"""

    @pytest.mark.asyncio
    async def test_create_chat_message(self):
        """测试创建聊天消息"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            message = await crud.create_chat_message(
                session,
                session_id="crud-test-session",
                role="user",
                content="Test message content",
                metadata={"test": True},
            )
            
            assert message.id is not None
            assert message.session_id == "crud-test-session"
            assert message.role == "user"
            assert message.content == "Test message content"

    @pytest.mark.asyncio
    async def test_get_chat_messages_by_session(self):
        """测试获取会话消息"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            # 创建多条消息
            for i in range(5):
                await crud.create_chat_message(
                    session,
                    session_id="session-with-messages",
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"Message {i}",
                )
            
            # 获取消息
            messages = await crud.get_chat_messages_by_session(
                session,
                "session-with-messages",
                limit=10,
            )
            
            assert len(messages) == 5
            assert messages[0].content == "Message 0"
            assert messages[4].content == "Message 4"

    @pytest.mark.asyncio
    async def test_get_chat_messages_pagination(self):
        """测试消息分页"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            # 创建 10 条消息
            for i in range(10):
                await crud.create_chat_message(
                    session,
                    session_id="pagination-session",
                    role="user",
                    content=f"Message {i}",
                )
            
            # 第一页
            page1 = await crud.get_chat_messages_by_session(
                session,
                "pagination-session",
                limit=5,
                offset=0,
            )
            assert len(page1) == 5
            assert page1[0].content == "Message 0"
            
            # 第二页
            page2 = await crud.get_chat_messages_by_session(
                session,
                "pagination-session",
                limit=5,
                offset=5,
            )
            assert len(page2) == 5
            assert page2[0].content == "Message 5"

    @pytest.mark.asyncio
    async def test_get_chat_sessions(self):
        """测试获取会话列表"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            # 创建多个会话
            await crud.create_chat_message(
                session,
                session_id="session-1",
                role="user",
                content="Message 1",
            )
            await crud.create_chat_message(
                session,
                session_id="session-2",
                role="user",
                content="Message 2",
            )
            await crud.create_chat_message(
                session,
                session_id="session-1",
                role="assistant",
                content="Reply 1",
            )
            
            # 获取会话列表
            sessions = await crud.get_chat_sessions(session, limit=10)
            
            assert len(sessions) == 2
            # session-1 应该有 2 条消息
            session1 = next(s for s in sessions if s["session_id"] == "session-1")
            assert session1["message_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_chat_session(self):
        """测试删除会话"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            # 创建消息
            await crud.create_chat_message(
                session,
                session_id="session-to-delete",
                role="user",
                content="Test message",
            )
            
            # 删除会话
            success = await crud.delete_chat_session(session, "session-to-delete")
            assert success is True
            
            # 验证消息已删除
            messages = await crud.get_chat_messages_by_session(
                session,
                "session-to-delete",
            )
            assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self):
        """测试删除不存在的会话"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            success = await crud.delete_chat_session(session, "nonexistent-session")
            assert success is False

    @pytest.mark.asyncio
    async def test_get_chat_message_by_id(self):
        """测试根据 ID 获取消息"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            message = await crud.create_chat_message(
                session,
                session_id="test-session",
                role="user",
                content="Test content",
            )
            
            # 获取消息
            retrieved = await crud.get_chat_message_by_id(session, message.id)
            
            assert retrieved is not None
            assert retrieved.id == message.id
            assert retrieved.content == "Test content"

    @pytest.mark.asyncio
    async def test_get_nonexistent_message(self):
        """测试获取不存在的消息"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            message = await crud.get_chat_message_by_id(session, 99999)
            assert message is None

    @pytest.mark.asyncio
    async def test_update_chat_message_metadata(self):
        """测试更新消息元数据"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            message = await crud.create_chat_message(
                session,
                session_id="test-session",
                role="user",
                content="Test content",
                metadata={"original": True},
            )
            
            # 更新元数据
            updated = await crud.update_chat_message_metadata(
                session,
                message.id,
                {"updated": True, "new_key": "value"},
            )
            
            assert updated is not None
            assert updated.meta == {"updated": True, "new_key": "value"}

    @pytest.mark.asyncio
    async def test_get_chat_stats(self):
        """测试获取聊天统计"""
        engine, async_session = await create_test_db()
        
        async with async_session() as session:
            # 创建测试数据
            await crud.create_chat_message(
                session,
                session_id="session-1",
                role="user",
                content="User message 1",
            )
            await crud.create_chat_message(
                session,
                session_id="session-1",
                role="assistant",
                content="Assistant reply",
            )
            await crud.create_chat_message(
                session,
                session_id="session-2",
                role="user",
                content="User message 2",
            )
            
            # 获取统计
            stats = await crud.get_chat_stats(session)
            
            assert stats["total_sessions"] == 2
            assert stats["total_messages"] == 3
            assert stats["messages_by_role"]["user"] == 2
            assert stats["messages_by_role"]["assistant"] == 1


# ============ API Endpoint Tests ============

class TestChatAPI:
    """聊天 API 端点测试"""

    @pytest.fixture
    def test_app(self):
        """创建测试应用"""
        from fastapi import FastAPI
        from src.api.routes.chat import router
        
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, test_app):
        """测试获取空会话列表"""
        from httpx import AsyncClient, ASGITransport
        
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/chat/sessions")
            
            assert response.status_code == 200
            assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_save_message(self, test_app):
        """测试保存消息"""
        from httpx import AsyncClient, ASGITransport
        
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/chat/messages",
                json={
                    "session_id": "api-test-session",
                    "role": "user",
                    "content": "Test API message",
                    "metadata": {"test": "api"},
                },
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["session_id"] == "api-test-session"
            assert data["role"] == "user"
            assert data["content"] == "Test API message"

    @pytest.mark.asyncio
    async def test_save_message_invalid_role(self, test_app):
        """测试保存消息 - 无效角色"""
        from httpx import AsyncClient, ASGITransport
        
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/chat/messages",
                json={
                    "session_id": "test-session",
                    "role": "invalid_role",
                    "content": "Test message",
                },
            )
            
            assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_save_message_empty_content(self, test_app):
        """测试保存消息 - 空内容"""
        from httpx import AsyncClient, ASGITransport
        
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/chat/messages",
                json={
                    "session_id": "test-session",
                    "role": "user",
                    "content": "",
                },
            )
            
            assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_get_stats(self, test_app):
        """测试获取统计信息"""
        from httpx import AsyncClient, ASGITransport
        
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/chat/stats")
            
            assert response.status_code == 200
            data = response.json()
            assert "total_sessions" in data
            assert "total_messages" in data
            assert "messages_by_role" in data


# ============ Performance Tests ============

class TestChatPerformance:
    """聊天性能测试"""

    @pytest.mark.asyncio
    async def test_bulk_insert_performance(self):
        """测试批量插入性能"""
        engine, async_session = await create_test_db()
        
        import time
        start_time = time.time()
        
        async with async_session() as session:
            # 插入 100 条消息
            for i in range(100):
                await crud.create_chat_message(
                    session,
                    session_id="bulk-test-session",
                    role="user",
                    content=f"Bulk message {i}",
                )
        
        elapsed = time.time() - start_time
        
        # 100 条消息应该在 5 秒内完成
        assert elapsed < 5.0, f"Bulk insert took {elapsed:.2f}s, expected < 5s"
        
        # 验证插入数量
        async with async_session() as session:
            messages = await crud.get_chat_messages_by_session(
                session,
                "bulk-test-session",
                limit=200,
            )
            assert len(messages) == 100

    @pytest.mark.asyncio
    async def test_query_performance_with_index(self):
        """测试索引查询性能"""
        engine, async_session = await create_test_db()
        
        import time
        
        # 创建大量消息
        async with async_session() as session:
            for i in range(500):
                await crud.create_chat_message(
                    session,
                    session_id=f"perf-session-{i % 10}",
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"Message {i}",
                )
        
        # 测试按会话查询性能
        start_time = time.time()
        async with async_session() as session:
            messages = await crud.get_chat_messages_by_session(
                session,
                "perf-session-5",
                limit=100,
            )
        query_time = time.time() - start_time
        
        # 查询应该在 1 秒内完成
        assert query_time < 1.0, f"Query took {query_time:.2f}s, expected < 1s"
        assert len(messages) == 50  # 500 / 10 sessions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
