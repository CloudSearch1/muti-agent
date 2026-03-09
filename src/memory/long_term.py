"""
长期记忆持久化模块

职责：将记忆持久化到数据库，支持历史检索和恢复

功能：
- 记忆持久化存储
- 历史记忆检索
- 记忆重要性排序
- 记忆衰减和清理
"""

import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import structlog

try:
    from sqlalchemy import (
        JSON,
        Boolean,
        Column,
        DateTime,
        Float,
        Integer,
        String,
        Text,
        create_engine,
        desc,
        select,
    )
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import Session, sessionmaker

    SQLALCHEMY_AVAILABLE = True
    Base = declarative_base()
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Base = None
    Session = None
    sessionmaker = None

logger = structlog.get_logger(__name__)


class MemoryType(str, Enum):
    """记忆类型"""
    EPISODIC = "episodic"  # 情节记忆（具体事件）
    SEMANTIC = "semantic"  # 语义记忆（事实知识）
    PROCEDURAL = "procedural"  # 程序记忆（技能方法）
    CONVERSATION = "conversation"  # 对话记忆
    TASK_RESULT = "task_result"  # 任务结果


class MemoryImportance(str, Enum):
    """记忆重要性"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


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
        importance = Column(String(16), default=MemoryImportance.MEDIUM.value)
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

        def to_dict(self) -> dict[str, Any]:
            return {
                "id": self.id,
                "memory_id": self.memory_id,
                "memory_type": self.memory_type,
                "content": self.content,
                "summary": self.summary,
                "importance": self.importance,
                "tags": self.tags or [],
                "metadata": self.extra_data or {},  # 映射回 metadata
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
    LongTermMemoryModel = None


class LongTermMemory:
    """
    长期记忆系统

    提供记忆的持久化存储、检索和管理功能。
    """

    # 默认配置
    DEFAULT_DB_URL = "sqlite:///./data/memory/long_term.db"
    MAX_MEMORIES_PER_QUERY = 100
    DECAY_THRESHOLD = 0.1  # 衰减阈值，低于此值的记忆会被清理

    def __init__(
        self,
        db_url: str = DEFAULT_DB_URL,
        auto_create_tables: bool = True,
        rag_store=None,
        **kwargs,
    ):
        """
        初始化长期记忆系统

        Args:
            db_url: 数据库连接 URL
            auto_create_tables: 是否自动创建表
            rag_store: RAG 存储实例（用于语义检索）
            **kwargs: 其他配置参数
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "SQLAlchemy is required. Install with: pip install sqlalchemy"
            )

        self.db_url = db_url
        self.rag_store = rag_store

        # 初始化数据库
        self.engine = create_engine(db_url, echo=False)
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

        self.logger = logger.bind(
            component="long_term_memory",
            db_url=db_url,
        )

        self.logger.info(
            "LongTermMemory initialized",
            db_url=db_url,
        )

    def _get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

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
        """
        import uuid

        memory_id = str(uuid.uuid4())

        with self._get_session() as session:
            memory = LongTermMemoryModel(
                memory_id=memory_id,
                memory_type=memory_type.value,
                content=content,
                summary=summary,
                importance=importance.value,
                tags=tags or [],
                extra_data=metadata or {},  # 参数名 metadata 映射到 extra_data 列
                agent_id=agent_id,
                session_id=session_id,
                task_id=task_id,
                decay_factor=self.importance_boost.get(importance.value, 1.0),
            )

            session.add(memory)
            session.commit()

            # 同步到 RAG 存储
            if self.rag_store:
                try:
                    vector_id = await self.rag_store.add_memory(
                        content=content,
                        metadata={
                            "memory_id": memory_id,
                            "memory_type": memory_type.value,
                            "importance": importance.value,
                            "tags": tags or [],
                        },
                    )
                    memory.vector_id = vector_id
                    session.commit()
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

    async def retrieve(
        self,
        memory_id: str,
        update_access: bool = True,
    ) -> dict[str, Any] | None:
        """
        检索记忆

        Args:
            memory_id: 记忆 ID
            update_access: 是否更新访问时间

        Returns:
            记忆数据，不存在则返回 None
        """
        with self._get_session() as session:
            memory = session.query(LongTermMemoryModel).filter(
                LongTermMemoryModel.memory_id == memory_id
            ).first()

            if not memory:
                return None

            if update_access:
                memory.last_accessed_at = datetime.utcnow()
                memory.access_count += 1
                session.commit()

            return memory.to_dict()

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
        # 如果有语义搜索需求且有 RAG 存储
        if query and self.rag_store:
            return await self._semantic_search(
                query=query,
                memory_type=memory_type,
                limit=limit,
            )

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
                # JSON 标签过滤（SQLite 不完全支持）
                for tag in tags:
                    q = q.filter(LongTermMemoryModel.tags.contains(tag))
            if query:
                # 简单的全文搜索
                q = q.filter(LongTermMemoryModel.content.contains(query))

            # 排序
            order_column = getattr(LongTermMemoryModel, order_by, LongTermMemoryModel.created_at)
            if descending:
                q = q.order_by(desc(order_column))
            else:
                q = q.order_by(order_column)

            # 分页
            q = q.offset(offset).limit(limit)

            memories = q.all()

            return [m.to_dict() for m in memories]

    async def _semantic_search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """语义搜索（通过 RAG 存储）"""
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

            # 获取完整记忆
            memories = []
            for result in results:
                memory_id = result.get("metadata", {}).get("memory_id")
                if memory_id:
                    memory = await self.retrieve(memory_id)
                    if memory:
                        memory["similarity_score"] = result.get("distance", 0)
                        memories.append(memory)

            return memories
        except Exception as e:
            self.logger.error(
                "Semantic search failed",
                error=str(e),
            )
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
        with self._get_session() as session:
            memory = session.query(LongTermMemoryModel).filter(
                LongTermMemoryModel.memory_id == memory_id
            ).first()

            if not memory:
                return False

            if content is not None:
                memory.content = content
            if summary is not None:
                memory.summary = summary
            if importance is not None:
                memory.importance = importance.value
                memory.decay_factor = self.importance_boost.get(importance.value, memory.decay_factor)
            if tags is not None:
                memory.tags = tags
            if metadata is not None:
                memory.extra_data = {**(memory.extra_data or {}), **metadata}

            memory.updated_at = datetime.utcnow()
            session.commit()

            self.logger.debug("Memory updated", memory_id=memory_id)
            return True

    async def delete(self, memory_id: str) -> bool:
        """
        删除记忆

        Args:
            memory_id: 记忆 ID

        Returns:
            是否成功
        """
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
            session.commit()

            self.logger.info("Memory deleted", memory_id=memory_id)
            return True

    async def apply_decay(self, days: int = 1) -> int:
        """
        应用记忆衰减

        Args:
            days: 衰减天数

        Returns:
            清理的记忆数量
        """
        decay_amount = self.decay_rate * days
        cleaned_count = 0

        with self._get_session() as session:
            # 更新所有记忆的衰减因子
            memories = session.query(LongTermMemoryModel).all()

            for memory in memories:
                memory.decay_factor *= (1 - decay_amount)

                # 检查是否需要清理
                if memory.decay_factor < self.DECAY_THRESHOLD:
                    session.delete(memory)
                    cleaned_count += 1

            session.commit()

        self.logger.info(
            "Decay applied",
            days=days,
            cleaned_count=cleaned_count,
        )

        return cleaned_count

    async def get_important_memories(
        self,
        limit: int = 10,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取重要记忆

        Args:
            limit: 返回数量
            agent_id: Agent ID 过滤

        Returns:
            重要记忆列表
        """
        with self._get_session() as session:
            q = session.query(LongTermMemoryModel).filter(
                LongTermMemoryModel.importance.in_([
                    MemoryImportance.HIGH.value,
                    MemoryImportance.CRITICAL.value,
                ])
            )

            if agent_id:
                q = q.filter(LongTermMemoryModel.agent_id == agent_id)

            # 按重要性和访问次数排序
            importance_order = {
                MemoryImportance.CRITICAL.value: 0,
                MemoryImportance.HIGH.value: 1,
            }

            memories = q.order_by(
                desc(LongTermMemoryModel.access_count)
            ).limit(limit).all()

            return [m.to_dict() for m in memories]

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

    async def get_stats(self) -> dict[str, Any]:
        """
        获取记忆统计信息

        Returns:
            统计信息
        """
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


# 便捷函数
def create_long_term_memory(
    db_url: str = LongTermMemory.DEFAULT_DB_URL,
    **kwargs,
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