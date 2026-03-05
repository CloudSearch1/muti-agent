"""
IntelliTeam 数据库模块

提供 SQLAlchemy 异步数据库支持
"""

import os
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# 基础模型类
Base = declarative_base()


# ============ 数据模型 ============


class TaskModel(Base):
    """任务模型"""

    __tablename__ = "tasks"

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
    input_data = Column(Text)  # JSON string
    output_data = Column(Text)  # JSON string
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


# ============ 数据库管理器 ============


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./intelliteam.db"
        )
        self.engine = None
        self.async_session_maker = None

    def connect(self) -> None:
        """连接数据库"""
        # 优化连接池配置
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            future=True,
            pool_size=20,  # 连接池大小
            max_overflow=10,  # 最大溢出连接数
            pool_pre_ping=True,  # 连接前检查
            pool_recycle=3600,  # 连接回收时间（秒）
            pool_timeout=30,  # 连接超时
        )
        self.async_session_maker = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def disconnect(self) -> None:
        """断开连接"""
        if self.engine:
            await self.engine.dispose()

    async def create_tables(self) -> None:
        """创建所有表"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


# ============ 全局实例 ============

_db_manager: DatabaseManager | None = None


def get_database_manager(database_url: str | None = None) -> DatabaseManager:
    """获取数据库管理器单例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(database_url)
        _db_manager.connect()
    return _db_manager


async def init_database(database_url: str | None = None) -> None:
    """初始化数据库"""
    db = get_database_manager(database_url)
    await db.create_tables()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（依赖注入用）"""
    db = get_database_manager()
    async for session in db.get_session():
        yield session
