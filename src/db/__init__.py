"""
数据库连接管理
"""

from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config.settings import Settings, get_settings

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, settings: Settings = None):
        self.settings = settings or get_settings()
        self.engine = None
        self.async_session_maker = None

        logger.info(
            "DatabaseManager initialized",
            url=self.settings.database_url,
        )

    def connect(self) -> None:
        """连接数据库"""
        if self.settings.is_production():
            # 生产环境：使用连接池
            self.engine = create_async_engine(
                self.settings.database_url,
                pool_size=20,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False,
            )
        else:
            # 开发环境：简单连接
            self.engine = create_async_engine(
                self.settings.database_url,
                echo=self.settings.debug,
            )

        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info("Database connected")

    async def disconnect(self) -> None:
        """断开数据库连接"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database disconnected")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        if not self.async_session_maker:
            self.connect()

        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def create_tables(self) -> None:
        """创建数据库表"""
        if not self.engine:
            self.connect()

        from .models import Base

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created")


# 全局单例
_db_manager: DatabaseManager | None = None


def get_database_manager() -> DatabaseManager:
    """获取数据库管理器单例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.connect()
    return _db_manager


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（用于依赖注入）"""
    db_manager = get_database_manager()
    async for session in db_manager.get_session():
        yield session
