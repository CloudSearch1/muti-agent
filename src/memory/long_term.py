"""
长期记忆持久化模块

职责：将记忆持久化到数据库，支持历史检索和恢复

功能：
- 记忆持久化存储
- 历史记忆检索
- 记忆重要性排序
- 记忆衰减和清理
- 批量操作优化
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

import structlog

from .exceptions import (
    MemoryConnectionError,
    MemoryDecayError,
    MemoryNotFoundError,
    MemoryRetrievalError,
    MemoryStorageError,
    MemoryValidationError,
)
from .types import MemoryImportance, MemoryType

try:
    from sqlalchemy import (
        JSON,
        Boolean,
        Column,
        DateTime,
        Float,
        Index,
        Integer,
        String,
        Text,
        create_engine,
        desc,
        event,
        select,
    )
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session, declarative_base, sessionmaker
    from sqlalchemy.pool import StaticPool

    SQLALCHEMY_AVAILABLE = True
    Base = declarative_base()
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Base = None  # type: ignore
    Session = None  # type: ignore
    sessionmaker = None  # type: ignore
    SQLAlchemyError = Exception  # type: ignore


logger = structlog.get_logger(__name__)

# 默认配置
DEFAULT_DB_URL = "sqlite:///./data/memory/long_term.db"
MAX_MEMORIES_PER_QUERY = 100
DECAY_THRESHOLD = 0.1  # 衰减阈值，低于此值的记忆会被清理
MAX_CONTENT_LENGTH = 100000  # 最大内容长度
MAX_SUMMARY_LENGTH = 1000  # 最大摘要长度
MAX_TAGS_COUNT = 20  # 最大标签数量


if SQLALCHEMY_AVAILABLE:
    class LongTermMemoryModel(Base):
        """长期记忆数据库模型"""

        __tablename__ = "long_term_memories"

        id = Column(Integer, primary_key=True, autoincrement=True)
        memory_id = Column(String(64), unique=True, nullable=False, index=True)
        memory_type = Column(String(32), nullable=False, index=True)
        content = Column(Text, nullable=False)
        summary = Column(Text, nullable=True)

        # 元数据
        importance = Column(String(16), default=MemoryImportance.MEDIUM.value, index=True)
        tags = Column(JSON, default=list)
        extra_data = Column(JSON, default=dict)  # 避免使用 metadata (SQLAlchemy 保留字)

        # 关联信息
        agent_id = Column(String(64), nullable=True, index=True)
        session_id = Column(String(64), nullable=True, index=True)
        task_id = Column(String(64), nullable=True, index=True)

        # 时间信息
        created_at = Column(DateTime, default=datetime.utcnow, index=True)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        last_accessed_at = Column(DateTime, default=datetime.utcnow)

        # 访问统计
        access_count = Column(Integer, default=0)

        # 衰减因子（用于遗忘机制）
        decay_factor = Column(Float, default=1.0)

        # 向量 ID（关联 RAG 存储）
        vector_id = Column(String(64), nullable=True)

        # 复合索引
        __table_args__ = (
            Index("idx_importance_access", "importance", "access_count"),
            Index("idx_agent_created", "agent_id", "created_at"),
            Index("idx_session_created", "session_id", "created_at"),
        )

        def to_dict(self) -> dict[str, Any]:
            """转换为字典"""
            return {
                "id": self.id,
                "memory_id": self.memory_id,
                "memory_type": self.memory_type,
                "content": self.content,
                "summary": self.summary,
                "importance": self.importance,
                "tags": self.tags or [],
                "metadata": self.extra_data or {},
                "agent_id": self.agent_id,
                "session_id": self.session_id,
                "task_id": self.task_id,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
                "access_count": self.access_count,
                "decay_factor": self.decay_factor,
            }
else:
    LongTermMemoryModel = None  # type: ignore


class LongTermMemory:
    """
    长期记忆系统

    提供记忆的持久化存储、检索和管理功能。

    Attributes:
        db_url: 数据库连接 URL
        rag_store: RAG 存储实例（可选）
        engine: SQLAlchemy 引擎
        SessionLocal: 会话工厂

    Example:
        >>> ltm = LongTermMemory(db_url="sqlite:///memory.db")
        >>> memory_id = await ltm.store("重要记忆内容", importance=MemoryImportance.HIGH)
        >>> memory = await ltm.retrieve(memory_id)
    """

    def __init__(
        self,
        db_url: str = DEFAULT_DB_URL,
        auto_create_tables: bool = True,
        rag_store: Any | None = None,
        pool_size: int = 5,
        **kwargs: Any,
    ) -> None:
        """
        初始化长期记忆系统

        Args:
            db_url: 数据库连接 URL
            auto_create_tables: 是否自动创建表
            rag_store: RAG 存储实例（用于语义检索）
            pool_size: 连接池大小
            **kwargs: 其他配置参数

        Raises:
            MemoryConnectionError: SQLAlchemy 不可用时
        """
        if not SQLALCHEMY_AVAILABLE:
            raise MemoryConnectionError(
                message="SQLAlchemy is required. Install with: pip install sqlalchemy",
                backend="database",
            )

        self.db_url = db_url
        self.rag_store = rag_store
        self.pool_size = pool_size

        # 初始化数据库引擎
        engine_kwargs = {
            "echo": False,
            "pool_pre_ping": True,
        }

        # SQLite 特殊配置
        if db_url.startswith("sqlite"):
            engine_kwargs["poolclass"] = StaticPool
            engine_kwargs["connect_args"] = {"check_same_thread": False}

        self.engine = create_engine(db_url, **engine_kwargs)
        self.SessionLocal = sessionmaker(bind=self.engine)

        if auto_create_tables:
            Base.metadata.create_all(self.engine)

        # 配置
        self.decay_rate = kwargs.get("decay_rate", 0.01)  # 每日衰减率
        self.importance_boost = kwargs.get("importance_boost", {
            MemoryImportance.LOW.value: 1.0,
            MemoryImportance.MEDIUM.value: 1.5,
            MemoryImportance.HIGH.value: 2.0,
            MemoryImportance.CRITICAL.value: 3.0,
        })

        self.logger = logger.bind(component="long_term_memory")

        self.logger.info(
            "LongTermMemory initialized",
            db_url=db_url,
            rag_enabled=rag_store is not None,
        )

    @contextmanager
    def _get_session(self) -> Iterator[Session]:
        """
        获取数据库会话

        Yields:
            数据库会话

        Note:
            使用上下文管理器确保会话正确关闭
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _validate_content(self, content: str) -> str:
        """验证并清理内容"""
        if not content or not content.strip():
            raise MemoryValidationError(
                message="Content cannot be empty",
                field="content",
            )

        content = content.strip()
        if len(content) > MAX_CONTENT_LENGTH:
            self.logger.warning(
                "Content truncated",
                original_length=len(content),
                max_length=MAX_CONTENT_LENGTH,
            )
            content = content[:MAX_CONTENT_LENGTH]

        return content

    def _validate_tags(self, tags: list[str] | None) -> list[str]:
        """验证并清理标签"""
        if not tags:
            return []

        if len(tags) > MAX_TAGS_COUNT:
            raise MemoryValidationError(
                message=f"Too many tags: {len(tags)} > {MAX_TAGS_COUNT}",
                field="tags",
            )

        # 清理和去重
        cleaned = list({
            tag.strip().lower()
            for tag in tags
            if tag and tag.strip()
        })

        return cleaned[:MAX_TAGS_COUNT]

    async def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        summary: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        task_id: str | None = None,
    ) -> str:
        """
        存储长期记忆

        Args:
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性
            summary: 摘要
            tags: 标签
            metadata: 元数据
            agent_id: Agent ID
            session_id: 会话 ID
            task_id: 任务 ID

        Returns:
            记忆 ID

        Raises:
            MemoryStorageError: 存储失败时
            MemoryValidationError: 参数验证失败时
        """
        # 验证参数
        content = self._validate_content(content)
        tags = self._validate_tags(tags)

        if summary and len(summary) > MAX_SUMMARY_LENGTH:
            summary = summary[:MAX_SUMMARY_LENGTH]

        memory_id = str(uuid.uuid4())

        try:
            with self._get_session() as session:
                memory = LongTermMemoryModel(
                    memory_id=memory_id,
                    memory_type=memory_type.value,
                    content=content,
                    summary=summary,
                    importance=importance.value,
                    tags=tags,
                    extra_data=metadata or {},
                    agent_id=agent_id,
                    session_id=session_id,
                    task_id=task_id,
                    decay_factor=self.importance_boost.get(importance.value, 1.0),
                )

                session.add(memory)

                # 同步到 RAG 存储
                if self.rag_store:
                    try:
                        vector_id = await self.rag_store.add_memory(
                            content=content,
                            metadata={
                                "memory_id": memory_id,
                                "memory_type": memory_type.value,
                                "importance": importance.value,
                                "tags": tags,
                            },
                        )
                        memory.vector_id = vector_id
                    except Exception as e:
                        self.logger.warning(
                            "Failed to sync to RAG store",
                            memory_id=memory_id,
                            error=str(e),
                        )

            self.logger.info(
                "Memory stored",
                memory_id=memory_id,
                memory_type=memory_type.value,
                importance=importance.value,
            )

            return memory_id

        except MemoryValidationError:
            raise
        except SQLAlchemyError as e:
            self.logger.error("Database error during store", error=str(e))
            raise MemoryStorageError(
                message=f"Failed to store memory: {e}",
                memory_id=memory_id,
                storage_type="long_term",
            ) from e
        except Exception as e:
            self.logger.error("Unexpected error during store", error=str(e))
            raise MemoryStorageError(
                message=f"Unexpected error: {e}",
                storage_type="long_term",
            ) from e

    async def retrieve(
        self,
        memory_id: str,
        update_access: bool = True,
    ) -> dict[str, Any]:
        """
        检索记忆

        Args:
            memory_id: 记忆 ID
            update_access: 是否更新访问时间

        Returns:
            记忆数据

        Raises:
            MemoryNotFoundError: 记忆不存在时
            MemoryRetrievalError: 检索失败时
        """
        try:
            with self._get_session() as session:
                memory = session.query(LongTermMemoryModel).filter(
                    LongTermMemoryModel.memory_id == memory_id
                ).first()

                if not memory:
                    raise MemoryNotFoundError(
                        memory_id=memory_id,
                        storage_type="long_term",
                    )

                if update_access:
                    memory.last_accessed_at = datetime.utcnow()
                    memory.access_count += 1

                return memory.to_dict()

        except MemoryNotFoundError:
            raise
        except SQLAlchemyError as e:
            self.logger.error("Database error during retrieve", error=str(e))
            raise MemoryRetrievalError(
                message=f"Failed to retrieve memory: {e}",
                memory_id=memory_id,
            ) from e

    async def search(
        self,
        query: str | None = None,
        memory_type: MemoryType | None = None,
        importance: MemoryImportance | None = None,
        tags: list[str] | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        task_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = MAX_MEMORIES_PER_QUERY,
        offset: int = 0,
        order_by: str = "created_at",
        descending: bool = True,
    ) -> list[dict[str, Any]]:
        """
        搜索记忆

        Args:
            query: 全文搜索查询
            memory_type: 记忆类型过滤
            importance: 重要性过滤
            tags: 标签过滤
            agent_id: Agent ID 过滤
            session_id: 会话 ID 过滤
            task_id: 任务 ID 过滤
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量限制
            offset: 偏移量
            order_by: 排序字段
            descending: 是否降序

        Returns:
            记忆列表
        """
        # 语义搜索优先
        if query and self.rag_store:
            return await self._semantic_search(
                query=query,
                memory_type=memory_type,
                limit=limit,
            )

        try:
            with self._get_session() as session:
                q = session.query(LongTermMemoryModel)

                # 应用过滤条件
                if memory_type:
                    q = q.filter(LongTermMemoryModel.memory_type == memory_type.value)
                if importance:
                    q = q.filter(LongTermMemoryModel.importance == importance.value)
                if agent_id:
                    q = q.filter(LongTermMemoryModel.agent_id == agent_id)
                if session_id:
                    q = q.filter(LongTermMemoryModel.session_id == session_id)
                if task_id:
                    q = q.filter(LongTermMemoryModel.task_id == task_id)
                if start_date:
                    q = q.filter(LongTermMemoryModel.created_at >= start_date)
                if end_date:
                    q = q.filter(LongTermMemoryModel.created_at <= end_date)
                if tags:
                    for tag in tags:
                        q = q.filter(LongTermMemoryModel.tags.contains(tag))
                if query:
                    # 全文搜索（简单实现）
                    search_pattern = f"%{query}%"
                    q = q.filter(
                        LongTermMemoryModel.content.ilike(search_pattern) |
                        LongTermMemoryModel.summary.ilike(search_pattern)
                    )

                # 排序
                order_column = getattr(LongTermMemoryModel, order_by, LongTermMemoryModel.created_at)
                if descending:
                    q = q.order_by(desc(order_column))
                else:
                    q = q.order_by(order_column)

                # 分页
                q = q.offset(offset).limit(min(limit, MAX_MEMORIES_PER_QUERY))

                memories = q.all()
                return [m.to_dict() for m in memories]

        except Exception as e:
            self.logger.error("Search failed", error=str(e))
            return []

    async def _semantic_search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        语义搜索（通过 RAG 存储）

        Args:
            query: 查询文本
            memory_type: 记忆类型过滤
            limit: 返回数量限制

        Returns:
            记忆列表（带相似度分数）
        """
        if not self.rag_store:
            return []

        try:
            filter_metadata = {}
            if memory_type:
                filter_metadata["memory_type"] = memory_type.value

            results = await self.rag_store.search(
                query=query,
                top_k=limit,
                filter_metadata=filter_metadata if filter_metadata else None,
            )

            # 获取完整记忆并添加相似度分数
            memories = []
            for result in results:
                memory_id = result.get("metadata", {}).get("memory_id")
                if memory_id:
                    try:
                        memory = await self.retrieve(memory_id)
                        memory["similarity_score"] = result.get("distance", 0)
                        memories.append(memory)
                    except MemoryNotFoundError:
                        continue

            return memories

        except Exception as e:
            self.logger.error("Semantic search failed", error=str(e))
            return []

    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        summary: str | None = None,
        importance: MemoryImportance | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        更新记忆

        Args:
            memory_id: 记忆 ID
            content: 新内容
            summary: 新摘要
            importance: 新重要性
            tags: 新标签
            metadata: 新元数据

        Returns:
            是否成功
        """
        try:
            with self._get_session() as session:
                memory = session.query(LongTermMemoryModel).filter(
                    LongTermMemoryModel.memory_id == memory_id
                ).first()

                if not memory:
                    return False

                # 更新字段
                if content is not None:
                    memory.content = self._validate_content(content)
                if summary is not None:
                    memory.summary = summary[:MAX_SUMMARY_LENGTH] if summary else None
                if importance is not None:
                    memory.importance = importance.value
                    memory.decay_factor = self.importance_boost.get(
                        importance.value, memory.decay_factor
                    )
                if tags is not None:
                    memory.tags = self._validate_tags(tags)
                if metadata is not None:
                    memory.extra_data = {**(memory.extra_data or {}), **metadata}

                memory.updated_at = datetime.utcnow()

                self.logger.debug("Memory updated", memory_id=memory_id)
                return True

        except Exception as e:
            self.logger.error("Update failed", memory_id=memory_id, error=str(e))
            return False

    async def delete(self, memory_id: str) -> bool:
        """
        删除记忆

        Args:
            memory_id: 记忆 ID

        Returns:
            是否成功
        """
        try:
            with self._get_session() as session:
                memory = session.query(LongTermMemoryModel).filter(
                    LongTermMemoryModel.memory_id == memory_id
                ).first()

                if not memory:
                    return False

                # 从 RAG 存储删除
                if self.rag_store and memory.vector_id:
                    try:
                        await self.rag_store.delete_memory(memory.vector_id)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to delete from RAG store",
                            memory_id=memory_id,
                            error=str(e),
                        )

                session.delete(memory)

                self.logger.info("Memory deleted", memory_id=memory_id)
                return True

        except Exception as e:
            self.logger.error("Delete failed", memory_id=memory_id, error=str(e))
            return False

    async def batch_delete(self, memory_ids: list[str]) -> int:
        """
        批量删除记忆

        Args:
            memory_ids: 记忆 ID 列表

        Returns:
            成功删除的数量
        """
        if not memory_ids:
            return 0

        deleted_count = 0
        for memory_id in memory_ids:
            if await self.delete(memory_id):
                deleted_count += 1

        return deleted_count

    async def apply_decay(self, days: int = 1) -> int:
        """
        应用记忆衰减

        根据记忆重要性和访问频率衰减记忆，清理低于阈值的记忆。

        Args:
            days: 衰减天数

        Returns:
            清理的记忆数量

        Raises:
            MemoryDecayError: 衰减操作失败时
        """
        decay_amount = self.decay_rate * days
        cleaned_count = 0

        try:
            with self._get_session() as session:
                memories = session.query(LongTermMemoryModel).all()

                for memory in memories:
                    memory.decay_factor *= (1 - decay_amount)

                    # 检查是否需要清理
                    if memory.decay_factor < DECAY_THRESHOLD:
                        # 从 RAG 存储删除
                        if self.rag_store and memory.vector_id:
                            try:
                                await self.rag_store.delete_memory(memory.vector_id)
                            except Exception:
                                pass

                        session.delete(memory)
                        cleaned_count += 1

            self.logger.info(
                "Decay applied",
                days=days,
                cleaned_count=cleaned_count,
            )

            return cleaned_count

        except Exception as e:
            self.logger.error("Decay operation failed", error=str(e))
            raise MemoryDecayError(
                message=f"Failed to apply decay: {e}",
                affected_count=cleaned_count,
            ) from e

    async def get_important_memories(
        self,
        limit: int = 10,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取重要记忆

        获取高重要性和关键性的记忆，按访问次数排序。

        Args:
            limit: 返回数量
            agent_id: Agent ID 过滤

        Returns:
            重要记忆列表
        """
        try:
            with self._get_session() as session:
                q = session.query(LongTermMemoryModel).filter(
                    LongTermMemoryModel.importance.in_([
                        MemoryImportance.HIGH.value,
                        MemoryImportance.CRITICAL.value,
                    ])
                )

                if agent_id:
                    q = q.filter(LongTermMemoryModel.agent_id == agent_id)

                memories = q.order_by(
                    desc(LongTermMemoryModel.access_count)
                ).limit(limit).all()

                return [m.to_dict() for m in memories]

        except Exception as e:
            self.logger.error("Failed to get important memories", error=str(e))
            return []

    async def get_recent_memories(
        self,
        hours: int = 24,
        limit: int = 50,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取最近的记忆

        Args:
            hours: 时间范围（小时）
            limit: 返回数量
            agent_id: Agent ID 过滤

        Returns:
            最近记忆列表
        """
        start_time = datetime.utcnow() - timedelta(hours=hours)

        try:
            with self._get_session() as session:
                q = session.query(LongTermMemoryModel).filter(
                    LongTermMemoryModel.created_at >= start_time
                )

                if agent_id:
                    q = q.filter(LongTermMemoryModel.agent_id == agent_id)

                memories = q.order_by(
                    desc(LongTermMemoryModel.created_at)
                ).limit(limit).all()

                return [m.to_dict() for m in memories]

        except Exception as e:
            self.logger.error("Failed to get recent memories", error=str(e))
            return []

    async def get_stats(self) -> dict[str, Any]:
        """
        获取记忆统计信息

        Returns:
            统计信息字典
        """
        try:
            with self._get_session() as session:
                total_count = session.query(LongTermMemoryModel).count()

                # 按类型统计
                type_counts = {}
                for mt in MemoryType:
                    count = session.query(LongTermMemoryModel).filter(
                        LongTermMemoryModel.memory_type == mt.value
                    ).count()
                    type_counts[mt.value] = count

                # 按重要性统计
                importance_counts = {}
                for imp in MemoryImportance:
                    count = session.query(LongTermMemoryModel).filter(
                        LongTermMemoryModel.importance == imp.value
                    ).count()
                    importance_counts[imp.value] = count

                # 最近活跃
                recent_count = session.query(LongTermMemoryModel).filter(
                    LongTermMemoryModel.last_accessed_at >= datetime.utcnow() - timedelta(hours=24)
                ).count()

                return {
                    "total_count": total_count,
                    "by_type": type_counts,
                    "by_importance": importance_counts,
                    "recently_accessed_24h": recent_count,
                    "rag_enabled": self.rag_store is not None,
                }

        except Exception as e:
            self.logger.error("Failed to get stats", error=str(e))
            return {
                "total_count": 0,
                "error": str(e),
            }

    async def count(
        self,
        memory_type: MemoryType | None = None,
        importance: MemoryImportance | None = None,
        agent_id: str | None = None,
    ) -> int:
        """
        计数记忆

        Args:
            memory_type: 记忆类型过滤
            importance: 重要性过滤
            agent_id: Agent ID 过滤

        Returns:
            记忆数量
        """
        try:
            with self._get_session() as session:
                q = session.query(LongTermMemoryModel)

                if memory_type:
                    q = q.filter(LongTermMemoryModel.memory_type == memory_type.value)
                if importance:
                    q = q.filter(LongTermMemoryModel.importance == importance.value)
                if agent_id:
                    q = q.filter(LongTermMemoryModel.agent_id == agent_id)

                return q.count()

        except Exception as e:
            self.logger.error("Count failed", error=str(e))
            return 0


def create_long_term_memory(
    db_url: str = DEFAULT_DB_URL,
    **kwargs: Any,
) -> LongTermMemory:
    """
    创建长期记忆系统

    Args:
        db_url: 数据库 URL
        **kwargs: 其他配置参数

    Returns:
        LongTermMemory 实例
    """
    return LongTermMemory(db_url=db_url, **kwargs)
