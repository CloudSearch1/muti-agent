"""
会话管理器

职责：管理 Agent 会话生命周期

特性：
- 会话创建和管理
- 会话消息存储
- TTL 自动过期
- 统计信息
"""

import uuid
from datetime import datetime
from typing import Any, Optional

import structlog
from pydantic import BaseModel, Field, field_serializer

from .exceptions import MemoryNotFoundError, SessionError
from .short_term import ShortTermMemory

logger = structlog.get_logger(__name__)

# 默认配置
DEFAULT_SESSION_TTL = 1800  # 30 分钟
MAX_MESSAGES_PER_SESSION = 1000
MAX_MESSAGE_SIZE = 100000  # 100 KB


class SessionInfo(BaseModel):
    """会话信息"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = Field(..., description="Agent ID")
    user_id: Optional[str] = Field(default=None, description="用户 ID")

    # 会话状态
    active: bool = Field(default=True, description="是否活跃")
    created_at: datetime = Field(default_factory=datetime.now)
    last_active_at: datetime = Field(default_factory=datetime.now)

    # 会话数据
    message_count: int = Field(default=0, description="消息数量")
    context_size: int = Field(default=0, description="上下文大小")

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer('created_at', 'last_active_at')
    def serialize_datetime(self, dt: datetime | None, _info) -> str | None:
        return dt.isoformat() if dt else None


class SessionManager:
    """
    会话管理器

    管理多个 Agent 会话的生命周期。

    Attributes:
        memory: 短期记忆实例
        session_ttl: 会话 TTL（秒）
        _sessions: 内存中的会话缓存

    Example:
        >>> memory = ShortTermMemory()
        >>> manager = SessionManager(memory)
        >>> session = await manager.create_session("agent-001")
        >>> await manager.add_message(session.id, {"role": "user", "content": "Hello"})
    """

    def __init__(
        self,
        memory: ShortTermMemory,
        session_ttl: int = DEFAULT_SESSION_TTL,
        max_sessions: int = 1000,
        **kwargs: Any,
    ) -> None:
        """
        初始化会话管理器

        Args:
            memory: 短期记忆实例
            session_ttl: 会话 TTL（秒）
            max_sessions: 最大会话数
            **kwargs: 额外配置
        """
        self.memory = memory
        self.session_ttl = session_ttl
        self.max_sessions = max_sessions

        # 内存中的会话缓存
        self._sessions: dict[str, SessionInfo] = {}

        self.logger = logger.bind(component="session_manager")
        self.logger.info(
            "SessionManager initialized",
            session_ttl=session_ttl,
            max_sessions=max_sessions,
        )

    def _make_session_key(self, session_id: str) -> str:
        """生成会话存储键"""
        return f"session:{session_id}"

    def _make_messages_key(self, session_id: str) -> str:
        """生成消息存储键"""
        return f"messages:{session_id}"

    async def create_session(
        self,
        agent_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> SessionInfo:
        """
        创建新会话

        Args:
            agent_id: Agent ID
            user_id: 用户 ID
            metadata: 元数据

        Returns:
            新创建的会话信息

        Raises:
            SessionError: 创建失败时
        """
        # 检查最大会话数
        if len(self._sessions) >= self.max_sessions:
            # 尝试清理过期会话
            await self.cleanup_expired()

            if len(self._sessions) >= self.max_sessions:
                raise SessionError(
                    message=f"Maximum sessions reached: {self.max_sessions}",
                )

        session = SessionInfo(
            agent_id=agent_id,
            user_id=user_id,
            metadata=metadata or {},
        )

        # 保存到缓存
        self._sessions[session.id] = session

        # 持久化到 Redis
        try:
            await self.memory.set(
                self._make_session_key(session.id),
                session.model_dump(),
                ttl=self.session_ttl,
            )
        except Exception as e:
            del self._sessions[session.id]
            raise SessionError(
                message=f"Failed to persist session: {e}",
                session_id=session.id,
            ) from e

        self.logger.info(
            "Session created",
            session_id=session.id,
            agent_id=agent_id,
            user_id=user_id,
        )

        return session

    async def get_session(
        self,
        session_id: str,
    ) -> Optional[SessionInfo]:
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
            if session.active:
                return session

        # 从 Redis 获取
        try:
            data = await self.memory.get(self._make_session_key(session_id))
            if not data:
                return None

            session = SessionInfo(**data)
            self._sessions[session_id] = session
            return session

        except Exception as e:
            self.logger.error(
                "Failed to get session",
                session_id=session_id,
                error=str(e),
            )
            return None

    async def update_session(
        self,
        session_id: str,
        **updates: Any,
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
        try:
            await self.memory.set(
                self._make_session_key(session_id),
                session.model_dump(),
                ttl=self.session_ttl,
            )
        except Exception as e:
            self.logger.error(
                "Failed to update session",
                session_id=session_id,
                error=str(e),
            )
            return False

        self.logger.debug("Session updated", session_id=session_id)
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
        try:
            await self.memory.delete(self._make_session_key(session_id))
            await self.memory.delete(self._make_messages_key(session_id))
        except Exception as e:
            self.logger.warning(
                "Failed to delete session from Redis",
                session_id=session_id,
                error=str(e),
            )

        duration_minutes = (datetime.now() - session.created_at).total_seconds() / 60

        self.logger.info(
            "Session ended",
            session_id=session_id,
            duration_minutes=round(duration_minutes, 2),
            message_count=session.message_count,
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

        # 验证消息大小
        message_str = str(message)
        if len(message_str) > MAX_MESSAGE_SIZE:
            self.logger.warning(
                "Message too large, truncating",
                session_id=session_id,
                size=len(message_str),
            )
            # 截断处理
            message = {
                "role": message.get("role", "unknown"),
                "content": message.get("content", "")[:MAX_MESSAGE_SIZE // 2],
                "truncated": True,
            }

        # 追加消息
        messages_key = self._make_messages_key(session_id)

        try:
            messages = await self.memory.get(messages_key, [])

            # 限制消息数量
            if len(messages) >= MAX_MESSAGES_PER_SESSION:
                # 移除旧消息
                messages = messages[-(MAX_MESSAGES_PER_SESSION - 1):]

            messages.append({
                **message,
                "timestamp": datetime.now().isoformat(),
            })

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

        except Exception as e:
            self.logger.error(
                "Failed to add message",
                session_id=session_id,
                error=str(e),
            )
            return False

    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        获取会话消息

        Args:
            session_id: 会话 ID
            limit: 最大消息数
            offset: 偏移量

        Returns:
            消息列表
        """
        try:
            messages = await self.memory.get(
                self._make_messages_key(session_id),
                [],
            )

            # 应用偏移和限制
            if offset > 0:
                messages = messages[offset:]

            return messages[-limit:] if limit > 0 else messages

        except Exception as e:
            self.logger.error(
                "Failed to get messages",
                session_id=session_id,
                error=str(e),
            )
            return []

    async def clear_messages(self, session_id: str) -> bool:
        """
        清空会话消息

        Args:
            session_id: 会话 ID

        Returns:
            是否成功
        """
        try:
            await self.memory.delete(self._make_messages_key(session_id))
            await self.update_session(session_id, message_count=0)
            return True
        except Exception as e:
            self.logger.error(
                "Failed to clear messages",
                session_id=session_id,
                error=str(e),
            )
            return False

    async def get_active_sessions(
        self,
        agent_id: Optional[str] = None,
    ) -> list[SessionInfo]:
        """
        获取活跃会话

        Args:
            agent_id: Agent ID 过滤

        Returns:
            活跃会话列表
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
        """
        清理过期会话

        Returns:
            清理的会话数量
        """
        expired_count = 0

        for session_id in list(self._sessions.keys()):
            session = await self.get_session(session_id)

            if not session or not session.active:
                if session_id in self._sessions:
                    del self._sessions[session_id]
                expired_count += 1

        if expired_count > 0:
            self.logger.info(
                "Session cleanup complete",
                expired_sessions=expired_count,
                remaining_sessions=len(self._sessions),
            )

        return expired_count

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        active_count = sum(1 for s in self._sessions.values() if s.active)
        total_messages = sum(s.message_count for s in self._sessions.values())

        return {
            "total_sessions": len(self._sessions),
            "active_sessions": active_count,
            "total_messages": total_messages,
            "session_ttl": self.session_ttl,
            "max_sessions": self.max_sessions,
        }

    async def get_or_create_session(
        self,
        session_id: Optional[str],
        agent_id: str,
        user_id: Optional[str] = None,
    ) -> SessionInfo:
        """
        获取或创建会话

        Args:
            session_id: 会话 ID（可选）
            agent_id: Agent ID
            user_id: 用户 ID

        Returns:
            会话信息
        """
        if session_id:
            session = await self.get_session(session_id)
            if session:
                return session

        return await self.create_session(agent_id, user_id)