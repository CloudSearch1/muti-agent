"""
会话管理器

职责：管理 Agent 会话生命周期
"""

import uuid
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from .short_term import ShortTermMemory

logger = structlog.get_logger(__name__)


class SessionInfo(BaseModel):
    """会话信息"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = Field(..., description="Agent ID")
    user_id: str | None = Field(default=None, description="用户 ID")

    # 会话状态
    active: bool = Field(default=True, description="是否活跃")
    created_at: datetime = Field(default_factory=datetime.now)
    last_active_at: datetime = Field(default_factory=datetime.now)

    # 会话数据
    message_count: int = Field(default=0, description="消息数量")
    context_size: int = Field(default=0, description="上下文大小")

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionManager:
    """
    会话管理器

    管理多个 Agent 会话的生命周期
    """

    def __init__(
        self,
        memory: ShortTermMemory,
        session_ttl: int = 1800,  # 30 分钟
        **kwargs,
    ):
        """
        初始化会话管理器

        Args:
            memory: 短期记忆实例
            session_ttl: 会话 TTL (秒)
        """
        self.memory = memory
        self.session_ttl = session_ttl

        # 内存中的会话缓存
        self._sessions: dict[str, SessionInfo] = {}

        self.logger = logger.bind(component="session_manager")
        self.logger.info(
            "SessionManager initialized",
            session_ttl=session_ttl,
        )

    async def create_session(
        self,
        agent_id: str,
        user_id: str | None = None,
        metadata: dict | None = None,
    ) -> SessionInfo:
        """
        创建新会话

        Args:
            agent_id: Agent ID
            user_id: 用户 ID
            metadata: 元数据

        Returns:
            会话信息
        """
        session = SessionInfo(
            agent_id=agent_id,
            user_id=user_id,
            metadata=metadata or {},
        )

        # 保存到缓存
        self._sessions[session.id] = session

        # 持久化到 Redis
        await self.memory.set(
            f"session:{session.id}",
            session.dict(),
            ttl=self.session_ttl,
        )

        self.logger.info(
            "Session created",
            session_id=session.id,
            agent_id=agent_id,
        )

        return session

    async def get_session(
        self,
        session_id: str,
    ) -> SessionInfo | None:
        """
        获取会话

        Args:
            session_id: 会话 ID

        Returns:
            会话信息，不存在则返回 None
        """
        # 先查缓存
        if session_id in self._sessions:
            session = self._sessions[session_id]

            # 检查是否过期
            if session.active:
                return session

        # 从 Redis 获取
        data = await self.memory.get(f"session:{session_id}")

        if not data:
            return None

        session = SessionInfo(**data)
        self._sessions[session_id] = session

        return session

    async def update_session(
        self,
        session_id: str,
        **updates,
    ) -> bool:
        """
        更新会话

        Args:
            session_id: 会话 ID
            **updates: 更新字段

        Returns:
            是否成功
        """
        session = await self.get_session(session_id)

        if not session:
            return False

        # 更新字段
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)

        session.last_active_at = datetime.now()

        # 更新缓存
        self._sessions[session_id] = session

        # 持久化
        await self.memory.set(
            f"session:{session_id}",
            session.dict(),
            ttl=self.session_ttl,
        )

        self.logger.debug(
            "Session updated",
            session_id=session_id,
        )

        return True

    async def end_session(self, session_id: str) -> bool:
        """
        结束会话

        Args:
            session_id: 会话 ID

        Returns:
            是否成功
        """
        session = await self.get_session(session_id)

        if not session:
            return False

        # 标记为非活跃
        session.active = False

        # 从缓存移除
        if session_id in self._sessions:
            del self._sessions[session_id]

        # 从 Redis 删除
        await self.memory.delete(f"session:{session_id}")

        self.logger.info(
            "Session ended",
            session_id=session_id,
            duration_minutes=(datetime.now() - session.created_at).total_seconds() / 60,
        )

        return True

    async def add_message(
        self,
        session_id: str,
        message: dict[str, Any],
    ) -> bool:
        """
        添加消息到会话

        Args:
            session_id: 会话 ID
            message: 消息内容

        Returns:
            是否成功
        """
        session = await self.get_session(session_id)

        if not session:
            return False

        # 追加消息到记忆
        messages_key = f"messages:{session_id}"
        messages = await self.memory.get(messages_key, [])
        messages.append(
            {
                **message,
                "timestamp": datetime.now().isoformat(),
            }
        )

        await self.memory.set(
            messages_key,
            messages,
            ttl=self.session_ttl,
        )

        # 更新会话统计
        await self.update_session(
            session_id,
            message_count=session.message_count + 1,
        )

        return True

    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        获取会话消息

        Args:
            session_id: 会话 ID
            limit: 最大消息数

        Returns:
            消息列表
        """
        messages = await self.memory.get(
            f"messages:{session_id}",
            [],
        )

        # 返回最新的 N 条
        return messages[-limit:]

    async def clear_messages(self, session_id: str) -> bool:
        """清空会话消息"""
        await self.memory.delete(f"messages:{session_id}")
        return True

    async def get_active_sessions(
        self,
        agent_id: str | None = None,
    ) -> list[SessionInfo]:
        """
        获取活跃会话

        Args:
            agent_id: Agent ID 过滤

        Returns:
            会话列表
        """
        active = []

        for session in self._sessions.values():
            if not session.active:
                continue

            if agent_id and session.agent_id != agent_id:
                continue

            active.append(session)

        return active

    async def cleanup_expired(self) -> int:
        """清理过期会话"""
        expired_count = 0

        for session_id in list(self._sessions.keys()):
            session = await self.get_session(session_id)

            if not session or not session.active:
                expired_count += 1

        self.logger.info(
            "Cleanup complete",
            expired_sessions=expired_count,
        )

        return expired_count

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": sum(1 for s in self._sessions.values() if s.active),
            "session_ttl": self.session_ttl,
        }
