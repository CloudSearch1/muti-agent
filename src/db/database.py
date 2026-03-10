"""
数据库模块（增强版）

提供 SQLAlchemy 异步数据库支持，包含：
- 连接池优化
- 事务管理
- 性能监控
- 健康检查
"""

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text, event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 基础模型类
Base = declarative_base()

T = TypeVar("T")


# ============ 数据模型 ============


class TaskModel(Base):
    """任务模型"""

    __tablename__ = "tasks"

    # 复合索引 - 优化常用查询
    __table_args__ = (
        Index("ix_tasks_status_priority", "status", "priority"),
        Index("ix_tasks_assignee_status", "assignee", "status"),
        Index("ix_tasks_created_status", "created_at", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, default="")
    status = Column(String(50), default="pending", index=True)
    priority = Column(String(50), default="normal", index=True)
    assignee = Column(String(100), index=True)
    agent = Column(String(100), index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    completed_at = Column(DateTime, nullable=True, index=True)


class AgentModel(Base):
    """Agent 模型"""

    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    role = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    status = Column(String(50), default="idle", index=True)
    tasks_completed = Column(Integer, default=0)
    avg_time = Column(Float, default=0.0)
    success_rate = Column(Float, default=100.0)
    created_at = Column(DateTime, default=datetime.now, index=True)


class WorkflowModel(Base):
    """工作流模型"""

    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    state = Column(String(50), default="running", index=True)
    input_data = Column(Text)
    output_data = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    completed_at = Column(DateTime, nullable=True, index=True)


class UserModel(Base):
    """用户模型"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class SkillModel(Base):
    """技能模型"""

    __tablename__ = "skills"

    __table_args__ = (
        Index("ix_skills_category_enabled", "category", "enabled"),
        Index("ix_skills_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    category = Column(String(50), default="general", index=True)
    version = Column(String(20), default="1.0.0")
    config = Column(Text, default="{}")  # JSON 配置
    enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now)  # 索引在 __table_args__ 中定义
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ============ 性能监控 ============


class QueryPerformanceMonitor:
    """查询性能监控器"""

    def __init__(self, slow_query_threshold_ms: float = 100):
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self._query_stats: dict[str, list[float]] = {}
        self._total_queries = 0
        self._slow_queries = 0

    def record_query(self, query_name: str, duration_ms: float) -> None:
        """记录查询执行时间"""
        if query_name not in self._query_stats:
            self._query_stats[query_name] = []

        self._query_stats[query_name].append(duration_ms)
        self._total_queries += 1

        if duration_ms > self.slow_query_threshold_ms:
            self._slow_queries += 1
            logger.warning(
                f"Slow query detected: {query_name} took {duration_ms:.2f}ms"
            )

    def get_stats(self) -> dict[str, Any]:
        """获取性能统计"""
        stats = {
            "total_queries": self._total_queries,
            "slow_queries": self._slow_queries,
            "slow_query_ratio": (
                self._slow_queries / self._total_queries
                if self._total_queries > 0
                else 0
            ),
            "queries": {},
        }

        for query_name, durations in self._query_stats.items():
            if durations:
                stats["queries"][query_name] = {
                    "count": len(durations),
                    "avg_ms": sum(durations) / len(durations),
                    "min_ms": min(durations),
                    "max_ms": max(durations),
                    "p95_ms": sorted(durations)[int(len(durations) * 0.95)]
                    if len(durations) > 20
                    else max(durations),
                }

        return stats

    def reset(self) -> None:
        """重置统计"""
        self._query_stats.clear()
        self._total_queries = 0
        self._slow_queries = 0


# 全局性能监控器
_query_monitor = QueryPerformanceMonitor()


def get_query_monitor() -> QueryPerformanceMonitor:
    """获取查询性能监控器"""
    return _query_monitor


# ============ 事务管理器 ============


class TransactionManager:
    """事务管理器"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._is_active = False

    async def begin(self) -> None:
        """开始事务"""
        if not self._is_active:
            await self.session.begin()
            self._is_active = True

    async def commit(self) -> None:
        """提交事务"""
        if self._is_active:
            await self.session.commit()
            self._is_active = False

    async def rollback(self) -> None:
        """回滚事务"""
        if self._is_active:
            await self.session.rollback()
            self._is_active = False

    async def __aenter__(self) -> "TransactionManager":
        await self.begin()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()


# ============ 数据库管理器 ============


class DatabaseManager:
    """数据库管理器（增强版）"""

    # 默认配置
    DEFAULT_POOL_SIZE = 20
    DEFAULT_MAX_OVERFLOW = 10
    DEFAULT_POOL_TIMEOUT = 30
    DEFAULT_POOL_RECYCLE = 3600

    def __init__(self, database_url: str | None = None, **kwargs):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./intelliteam.db"
        )
        self.engine = None
        self.async_session_maker = None

        # 连接池配置
        self.pool_size = kwargs.get("pool_size", self.DEFAULT_POOL_SIZE)
        self.max_overflow = kwargs.get("max_overflow", self.DEFAULT_MAX_OVERFLOW)
        self.pool_timeout = kwargs.get("pool_timeout", self.DEFAULT_POOL_TIMEOUT)
        self.pool_recycle = kwargs.get("pool_recycle", self.DEFAULT_POOL_RECYCLE)

        # 性能监控
        self.query_monitor = get_query_monitor()

    def connect(self) -> None:
        """连接数据库 - 优化连接池配置"""
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            future=True,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_pre_ping=True,
            pool_recycle=self.pool_recycle,
            pool_timeout=self.pool_timeout,
        )

        # 注册查询事件监听
        @event.listens_for(self.engine.sync_engine, "before_cursor_execute")
        def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
            context._query_statement = statement

        @event.listens_for(self.engine.sync_engine, "after_cursor_execute")
        def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if hasattr(context, "_query_start_time"):
                duration_ms = (time.time() - context._query_start_time) * 1000
                query_name = statement.split()[0] if statement else "unknown"
                self.query_monitor.record_query(query_name, duration_ms)

        self.async_session_maker = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        logger.info(
            f"Database connected: pool_size={self.pool_size}, "
            f"max_overflow={self.max_overflow}"
        )

    async def disconnect(self) -> None:
        """断开连接"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database disconnected")

    def get_pool_stats(self) -> dict[str, Any]:
        """获取连接池统计"""
        if not self.engine or not self.engine.pool:
            return {"error": "Database not connected"}

        return {
            "pool_size": self.engine.pool.size(),
            "checked_in": self.engine.pool.checkedin(),
            "checked_out": self.engine.pool.checkedout(),
            "overflow": self.engine.pool.overflow(),
            "invalid": self.engine.pool.invalidated if hasattr(self.engine.pool, "invalidated") else 0,
        }

    async def health_check(self) -> dict[str, Any]:
        """数据库健康检查"""
        start_time = time.time()
        try:
            async with self.async_session_maker() as session:
                await session.execute(select(1))

            latency_ms = (time.time() - start_time) * 1000

            return {
                "healthy": True,
                "latency_ms": round(latency_ms, 2),
                "pool_stats": self.get_pool_stats(),
                "query_stats": self.query_monitor.get_stats(),
            }
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "healthy": False,
                "error": str(e),
                "latency_ms": round(latency_ms, 2),
            }

    async def create_tables(self) -> None:
        """创建所有表"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[TransactionManager, None]:
        """获取事务管理器"""
        async with self.async_session_maker() as session:
            tx_manager = TransactionManager(session)
            try:
                async with tx_manager:
                    yield tx_manager
            except Exception:
                await session.rollback()
                raise

    async def execute_with_retry(
        self,
        operation: Callable[[], T],
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ) -> T:
        """带重试的操作执行"""
        last_error = None

        for attempt in range(max_retries):
            try:
                return await operation()
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2**attempt))
                    logger.warning(
                        f"Database operation failed, retrying ({attempt + 1}/{max_retries}): {e}"
                    )

        raise last_error


# ============ 全局实例 ============

_db_manager: DatabaseManager | None = None


def get_database_manager(database_url: str | None = None, **kwargs) -> DatabaseManager:
    """获取数据库管理器单例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(database_url, **kwargs)
        _db_manager.connect()
    return _db_manager


async def init_database(database_url: str | None = None, **kwargs) -> None:
    """初始化数据库"""
    db = get_database_manager(database_url, **kwargs)
    await db.create_tables()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（依赖注入用）"""
    db = get_database_manager()
    async for session in db.get_session():
        yield session


@asynccontextmanager
async def get_transaction() -> AsyncGenerator[TransactionManager, None]:
    """获取事务管理器"""
    db = get_database_manager()
    async with db.transaction() as tx:
        yield tx


async def database_health_check() -> dict[str, Any]:
    """数据库健康检查"""
    db = get_database_manager()
    return await db.health_check()
