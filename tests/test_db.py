"""
数据库模块测试

测试 DatabaseManager、TransactionManager、QueryPerformanceMonitor、健康检查等功能

注意：SQLite 不支持连接池参数（pool_size, max_overflow等），测试时使用简化的配置
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import time

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select

from src.db.database import (
    DatabaseManager,
    TransactionManager,
    QueryPerformanceMonitor,
    Base,
    TaskModel,
    AgentModel,
    WorkflowModel,
    UserModel,
    get_database_manager,
    get_query_monitor,
)


# ============ Helper Functions ============

async def create_test_db():
    """创建测试用的 SQLite 内存数据库"""
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


# ============ QueryPerformanceMonitor Tests ============

class TestQueryPerformanceMonitor:
    """查询性能监控器测试"""

    def test_create_monitor(self):
        """测试创建监控器"""
        monitor = QueryPerformanceMonitor(slow_query_threshold_ms=100)
        assert monitor.slow_query_threshold_ms == 100
        assert monitor._total_queries == 0
        assert monitor._slow_queries == 0

    def test_record_query(self):
        """测试记录查询"""
        monitor = QueryPerformanceMonitor()
        monitor.record_query("SELECT", 50.0)

        assert monitor._total_queries == 1
        assert monitor._slow_queries == 0

    def test_record_slow_query(self):
        """测试记录慢查询"""
        monitor = QueryPerformanceMonitor(slow_query_threshold_ms=50)
        monitor.record_query("SELECT", 100.0)

        assert monitor._total_queries == 1
        assert monitor._slow_queries == 1

    def test_get_stats_empty(self):
        """测试获取空统计"""
        monitor = QueryPerformanceMonitor()
        stats = monitor.get_stats()

        assert stats["total_queries"] == 0
        assert stats["slow_queries"] == 0
        assert stats["slow_query_ratio"] == 0

    def test_get_stats_with_queries(self):
        """测试获取有查询的统计"""
        monitor = QueryPerformanceMonitor()
        monitor.record_query("SELECT", 30.0)
        monitor.record_query("SELECT", 50.0)
        monitor.record_query("INSERT", 20.0)

        stats = monitor.get_stats()

        assert stats["total_queries"] == 3
        assert "SELECT" in stats["queries"]
        assert "INSERT" in stats["queries"]
        assert stats["queries"]["SELECT"]["count"] == 2
        assert stats["queries"]["SELECT"]["avg_ms"] == 40.0

    def test_get_stats_with_p95(self):
        """测试获取 P95 统计"""
        monitor = QueryPerformanceMonitor()

        # 记录足够多的查询以计算 P95
        for i in range(25):
            monitor.record_query("SELECT", float(i))

        stats = monitor.get_stats()
        assert "p95_ms" in stats["queries"]["SELECT"]

    def test_reset(self):
        """测试重置统计"""
        monitor = QueryPerformanceMonitor()
        monitor.record_query("SELECT", 50.0)
        monitor.reset()

        assert monitor._total_queries == 0
        assert monitor._slow_queries == 0
        assert len(monitor._query_stats) == 0

    def test_slow_query_ratio(self):
        """测试慢查询比例"""
        monitor = QueryPerformanceMonitor(slow_query_threshold_ms=50)
        monitor.record_query("SELECT", 30.0)  # 快
        monitor.record_query("SELECT", 100.0)  # 慢
        monitor.record_query("SELECT", 150.0)  # 慢

        stats = monitor.get_stats()
        assert stats["slow_query_ratio"] == pytest.approx(2/3, rel=0.01)


# ============ TransactionManager Tests ============

class TestTransactionManager:
    """事务管理器测试"""

    def test_create_transaction_manager(self):
        """测试创建事务管理器"""
        session = AsyncMock()
        tx = TransactionManager(session)
        assert tx.session == session
        assert tx._is_active is False

    @pytest.mark.asyncio
    async def test_begin_transaction(self):
        """测试开始事务"""
        session = AsyncMock()
        session.begin = AsyncMock()
        tx = TransactionManager(session)

        await tx.begin()

        session.begin.assert_called_once()
        assert tx._is_active is True

    @pytest.mark.asyncio
    async def test_commit_transaction(self):
        """测试提交事务"""
        session = AsyncMock()
        session.begin = AsyncMock()
        session.commit = AsyncMock()
        tx = TransactionManager(session)

        await tx.begin()
        await tx.commit()

        session.commit.assert_called_once()
        assert tx._is_active is False

    @pytest.mark.asyncio
    async def test_rollback_transaction(self):
        """测试回滚事务"""
        session = AsyncMock()
        session.begin = AsyncMock()
        session.rollback = AsyncMock()
        tx = TransactionManager(session)

        await tx.begin()
        await tx.rollback()

        session.rollback.assert_called_once()
        assert tx._is_active is False

    @pytest.mark.asyncio
    async def test_commit_without_begin(self):
        """测试未开始就提交"""
        session = AsyncMock()
        session.commit = AsyncMock()
        tx = TransactionManager(session)

        await tx.commit()

        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """测试上下文管理器成功"""
        session = AsyncMock()
        session.begin = AsyncMock()
        session.commit = AsyncMock()
        tx = TransactionManager(session)

        async with tx:
            pass

        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self):
        """测试上下文管理器异常"""
        session = AsyncMock()
        session.begin = AsyncMock()
        session.rollback = AsyncMock()
        tx = TransactionManager(session)

        with pytest.raises(ValueError):
            async with tx:
                raise ValueError("Test error")

        session.rollback.assert_called_once()


# ============ DatabaseManager Tests ============

class TestDatabaseManager:
    """数据库管理器测试"""

    def test_create_database_manager(self):
        """测试创建数据库管理器"""
        db = DatabaseManager(database_url="sqlite+aiosqlite:///:memory:")
        assert db.database_url == "sqlite+aiosqlite:///:memory:"
        assert db.engine is None

    def test_create_with_custom_pool_config(self):
        """测试自定义连接池配置（仅适用于 PostgreSQL 等支持连接池的数据库）"""
        db = DatabaseManager(
            database_url="postgresql+asyncpg://localhost/test",
            pool_size=30,
            max_overflow=15,
            pool_timeout=60,
            pool_recycle=7200,
        )
        assert db.pool_size == 30
        assert db.max_overflow == 15
        assert db.pool_timeout == 60
        assert db.pool_recycle == 7200

    def test_get_pool_stats_not_connected(self):
        """测试未连接时获取连接池统计"""
        db = DatabaseManager()
        stats = db.get_pool_stats()

        assert "error" in stats


class TestDatabaseManagerSQLite:
    """SQLite 数据库测试"""

    @pytest.mark.asyncio
    async def test_sqlite_basic_operations(self):
        """测试 SQLite 基本操作"""
        engine, async_session = await create_test_db()

        async with async_session() as session:
            # 创建任务
            task = TaskModel(
                title="Test Task",
                description="Test Description",
                status="pending",
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            assert task.id is not None
            assert task.title == "Test Task"

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_sqlite_query_task(self):
        """测试 SQLite 查询任务"""
        engine, async_session = await create_test_db()

        async with async_session() as session:
            # 创建任务
            task = TaskModel(title="Query Test")
            session.add(task)
            await session.commit()

        async with async_session() as session:
            # 查询任务
            result = await session.execute(
                select(TaskModel).where(TaskModel.title == "Query Test")
            )
            found = result.scalar_one_or_none()

            assert found is not None
            assert found.title == "Query Test"

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_sqlite_update_task(self):
        """测试 SQLite 更新任务"""
        engine, async_session = await create_test_db()

        async with async_session() as session:
            # 创建任务
            task = TaskModel(title="Update Test")
            session.add(task)
            await session.commit()
            await session.refresh(task)

            # 更新任务
            task.status = "completed"
            await session.commit()

        async with async_session() as session:
            # 验证更新
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == task.id)
            )
            found = result.scalar_one()
            assert found.status == "completed"

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_sqlite_delete_task(self):
        """测试 SQLite 删除任务"""
        engine, async_session = await create_test_db()

        async with async_session() as session:
            # 创建任务
            task = TaskModel(title="Delete Test")
            session.add(task)
            await session.commit()
            await session.refresh(task)
            task_id = task.id

        async with async_session() as session:
            # 删除任务
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == task_id)
            )
            found = result.scalar_one_or_none()
            if found:
                await session.delete(found)
                await session.commit()

        async with async_session() as session:
            # 验证删除
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == task_id)
            )
            found = result.scalar_one_or_none()
            assert found is None

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_sqlite_agent_operations(self):
        """测试 SQLite Agent 操作"""
        engine, async_session = await create_test_db()

        async with async_session() as session:
            agent = AgentModel(
                name="TestAgent",
                role="coder",
                description="Test Agent",
            )
            session.add(agent)
            await session.commit()

        async with async_session() as session:
            result = await session.execute(
                select(AgentModel).where(AgentModel.name == "TestAgent")
            )
            found = result.scalar_one()
            assert found.role == "coder"

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_sqlite_workflow_operations(self):
        """测试 SQLite Workflow 操作"""
        engine, async_session = await create_test_db()

        async with async_session() as session:
            workflow = WorkflowModel(
                name="Test Workflow",
                state="running",
            )
            session.add(workflow)
            await session.commit()

        async with async_session() as session:
            result = await session.execute(
                select(WorkflowModel).where(WorkflowModel.name == "Test Workflow")
            )
            found = result.scalar_one()
            assert found.state == "running"

        await engine.dispose()


# ============ Model Tests ============

class TestModels:
    """数据模型测试"""

    def test_task_model_creation(self):
        """测试任务模型创建"""
        task = TaskModel(
            title="Test Task",
            description="Description",
            status="pending",
            priority="normal",
        )
        assert task.title == "Test Task"
        assert task.status == "pending"

    def test_agent_model_creation(self):
        """测试 Agent 模型创建"""
        agent = AgentModel(
            name="TestAgent",
            role="coder",
            description="Test",
            tasks_completed=0,
        )
        assert agent.name == "TestAgent"
        assert agent.tasks_completed == 0

    def test_workflow_model_creation(self):
        """测试工作流模型创建"""
        workflow = WorkflowModel(
            name="Test Workflow",
            state="running",
        )
        assert workflow.name == "Test Workflow"
        assert workflow.state == "running"

    def test_user_model_creation(self):
        """测试用户模型创建"""
        user = UserModel(
            username="testuser",
            email="test@example.com",
            password_hash="hashed",
            is_active=True,
        )
        assert user.username == "testuser"
        assert user.is_active is True


# ============ Global Functions Tests ============

class TestGlobalFunctions:
    """全局函数测试"""

    def test_get_query_monitor_singleton(self):
        """测试获取查询监控器单例"""
        monitor1 = get_query_monitor()
        monitor2 = get_query_monitor()

        assert monitor1 is monitor2

    def test_get_database_manager(self):
        """测试获取数据库管理器"""
        # 重置单例
        import src.db.database as db_module
        db_module._db_manager = None

        db = get_database_manager()
        assert db is not None


# ============ Performance Tests ============

class TestDatabasePerformance:
    """数据库性能测试"""

    @pytest.mark.slow
    def test_monitor_performance(self):
        """测试监控器性能"""
        import time

        monitor = QueryPerformanceMonitor()

        start = time.time()
        for i in range(10000):
            monitor.record_query("SELECT", float(i % 100))
        elapsed = time.time() - start

        assert elapsed < 1.0  # 10000 次记录应该在 1 秒内

        # 获取统计
        start = time.time()
        stats = monitor.get_stats()
        elapsed = time.time() - start

        assert elapsed < 0.1  # 获取统计应该很快

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_batch_insert_performance(self):
        """测试批量插入性能"""
        import time

        engine, async_session = await create_test_db()

        start = time.time()

        async with async_session() as session:
            for i in range(100):
                task = TaskModel(title=f"Task {i}")
                session.add(task)
            await session.commit()

        elapsed = time.time() - start

        assert elapsed < 5.0  # 100 条记录应该在 5 秒内

        await engine.dispose()