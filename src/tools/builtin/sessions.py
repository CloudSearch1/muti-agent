"""
会话工具族

职责：提供会话管理和消息交互能力

工具列表：
- SessionsListTool: 列出会话
- SessionsHistoryTool: 获取会话历史消息
- SessionsSendTool: 向指定会话发送消息
- SessionsSpawnTool: 创建新会话
- SessionStatusTool: 查询会话状态
- AgentsListTool: 列出可用 agents

特性：
- 支持分页查询（cursor-based）
- 会话可见性约束（沙箱场景）
- allowAgents 限制
- 统一的 SessionToolManager 接口
- 使用标准错误模型 (ErrorCode, StandardError)
"""

import uuid
from datetime import datetime
from typing import Any, Optional

import structlog
from pydantic import BaseModel, Field

from ..base import BaseTool, OutputField, OutputSchema, ToolParameter, ToolResult
from ..errors import ErrorCode, StandardError

logger = structlog.get_logger(__name__)


# ============ 数据模型 ============


class PageResponse(BaseModel):
    """分页响应"""

    items: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: Optional[str] = Field(default=None)
    has_more: bool = Field(default=False)


class SessionSummary(BaseModel):
    """会话摘要"""

    session_id: str
    agent_id: str
    title: str
    updated_at: str


class MessageItem(BaseModel):
    """消息项"""

    message_id: str
    role: str
    content: str
    created_at: str


class SessionStatus(BaseModel):
    """会话状态"""

    session_id: str
    state: str  # idle, running, waiting, completed
    running_tools: list[str] = Field(default_factory=list)
    updated_at: str


class AgentInfo(BaseModel):
    """Agent 信息"""

    agent_id: str
    name: str
    description: str
    visible: bool = True


# ============ SessionToolManager 接口 ============


class SessionToolManager:
    """
    会话工具管理器

    统一管理会话相关的操作，提供与底层 SessionManager 的集成。
    处理分页、可见性约束等逻辑。

    Attributes:
        session_manager: 底层会话管理器实例
        allow_agents: 允许的 agent ID 列表（用于沙箱约束）
    """

    def __init__(
        self,
        session_manager: Any = None,
        allow_agents: Optional[list[str]] = None,
        current_session_id: Optional[str] = None,
        current_user_id: Optional[str] = None,
    ):
        """
        初始化会话工具管理器

        Args:
            session_manager: 底层 SessionManager 实例
            allow_agents: 允许访问的 agent ID 列表
            current_session_id: 当前会话 ID（用于会话可见性约束）
            current_user_id: 当前用户 ID
        """
        self._session_manager = session_manager
        self._allow_agents = set(allow_agents) if allow_agents else None
        self._current_session_id = current_session_id
        self._current_user_id = current_user_id

        # 内存存储（当无外部 session_manager 时使用）
        self._sessions: dict[str, dict[str, Any]] = {}
        self._messages: dict[str, list[dict[str, Any]]] = {}
        self._agents: dict[str, dict[str, Any]] = {}
        self._session_agents: dict[str, str] = {}  # session_id -> agent_id

        self.logger = logger.bind(component="session_tool_manager")
        self.logger.info(
            "SessionToolManager initialized",
            allow_agents=allow_agents,
            current_session_id=current_session_id,
        )

    def _check_agent_allowed(self, agent_id: str) -> bool:
        """检查 agent 是否被允许访问"""
        if self._allow_agents is None:
            return True
        return agent_id in self._allow_agents

    def _check_session_visible(self, session_id: str) -> bool:
        """
        检查会话可见性

        沙箱场景下，只能访问当前会话相关的资源
        """
        if self._current_session_id is None:
            # 非沙箱模式，全部可见
            return True
        # 沙箱模式：只允许访问当前会话
        return session_id == self._current_session_id

    async def list_sessions(
        self,
        agent_id: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> PageResponse:
        """
        列出会话

        Args:
            agent_id: Agent ID 过滤
            cursor: 分页游标
            limit: 每页数量

        Returns:
            分页响应
        """
        items = []

        if self._session_manager is not None:
            # 使用外部 SessionManager
            sessions = await self._session_manager.get_active_sessions(agent_id)
            for session in sessions:
                if not self._check_session_visible(session.id):
                    continue
                if agent_id and session.agent_id != agent_id:
                    continue

                items.append({
                    "sessionId": session.id,
                    "agentId": session.agent_id,
                    "title": session.metadata.get("title", "Untitled"),
                    "updatedAt": session.last_active_at.isoformat() if session.last_active_at else datetime.now().isoformat(),
                })
        else:
            # 使用内存存储
            for session_id, session_data in self._sessions.items():
                if not self._check_session_visible(session_id):
                    continue
                if agent_id and session_data.get("agent_id") != agent_id:
                    continue

                items.append({
                    "sessionId": session_id,
                    "agentId": session_data.get("agent_id", ""),
                    "title": session_data.get("title", "Untitled"),
                    "updatedAt": session_data.get("updated_at", datetime.now().isoformat()),
                })

        # 排序（按更新时间降序）
        items.sort(key=lambda x: x["updatedAt"], reverse=True)

        # 处理分页
        start_idx = 0
        if cursor:
            try:
                start_idx = int(cursor)
            except ValueError:
                start_idx = 0

        end_idx = start_idx + limit
        page_items = items[start_idx:end_idx]
        has_more = end_idx < len(items)
        next_cursor = str(end_idx) if has_more else None

        return PageResponse(
            items=page_items,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def get_history(
        self,
        session_id: str,
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> PageResponse:
        """
        获取会话历史消息

        Args:
            session_id: 会话 ID
            cursor: 分页游标
            limit: 每页数量

        Returns:
            分页响应
        """
        if not self._check_session_visible(session_id):
            self.logger.warning(
                "Session not visible",
                session_id=session_id,
                current_session=self._current_session_id,
            )
            return PageResponse(items=[], has_more=False)

        items = []

        if self._session_manager is not None:
            # 使用外部 SessionManager
            messages = await self._session_manager.get_messages(session_id, limit=limit * 2)
            for msg in messages:
                items.append({
                    "messageId": msg.get("id", str(uuid.uuid4())),
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                    "createdAt": msg.get("timestamp", datetime.now().isoformat()),
                })
        else:
            # 使用内存存储
            session_messages = self._messages.get(session_id, [])
            for msg in session_messages:
                items.append({
                    "messageId": msg.get("id", str(uuid.uuid4())),
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                    "createdAt": msg.get("created_at", datetime.now().isoformat()),
                })

        # 处理分页
        start_idx = 0
        if cursor:
            try:
                start_idx = int(cursor)
            except ValueError:
                start_idx = 0

        end_idx = start_idx + limit
        page_items = items[start_idx:end_idx]
        has_more = end_idx < len(items)
        next_cursor = str(end_idx) if has_more else None

        return PageResponse(
            items=page_items,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def send_message(
        self,
        session_id: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[bool, str]:
        """
        向指定会话发送消息

        Args:
            session_id: 会话 ID
            content: 消息内容
            metadata: 消息元数据

        Returns:
            (是否成功, 消息ID或错误信息)
        """
        if not self._check_session_visible(session_id):
            return False, "Session not visible"

        message_id = str(uuid.uuid4())
        message = {
            "id": message_id,
            "role": "user",
            "content": content,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        if self._session_manager is not None:
            # 使用外部 SessionManager
            success = await self._session_manager.add_message(session_id, message)
            if not success:
                return False, "Failed to add message"
        else:
            # 使用内存存储
            if session_id not in self._messages:
                self._messages[session_id] = []
            self._messages[session_id].append(message)

            # 更新会话时间
            if session_id in self._sessions:
                self._sessions[session_id]["updated_at"] = datetime.now().isoformat()

        self.logger.info(
            "Message sent",
            session_id=session_id,
            message_id=message_id,
        )

        return True, message_id

    async def spawn_session(
        self,
        agent_id: str,
        title: str,
        initial_prompt: str,
        inherit_policy_from_session_id: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        创建新会话

        Args:
            agent_id: Agent ID
            title: 会话标题
            initial_prompt: 初始提示
            inherit_policy_from_session_id: 继承策略的源会话 ID

        Returns:
            (会话ID, AgentID) 或 (None, None) 表示失败
        """
        # 检查 agent 是否被允许
        if not self._check_agent_allowed(agent_id):
            self.logger.warning(
                "Agent not allowed",
                agent_id=agent_id,
                allow_agents=self._allow_agents,
            )
            return None, None

        session_id = str(uuid.uuid4())

        if self._session_manager is not None:
            # 使用外部 SessionManager
            metadata = {
                "title": title,
                "inherit_from": inherit_policy_from_session_id,
            }
            try:
                session = await self._session_manager.create_session(
                    agent_id=agent_id,
                    user_id=self._current_user_id,
                    metadata=metadata,
                )
                session_id = session.id
            except Exception as e:
                self.logger.error(
                    "Failed to create session",
                    error=str(e),
                    agent_id=agent_id,
                )
                return None, None
        else:
            # 使用内存存储
            self._sessions[session_id] = {
                "id": session_id,
                "agent_id": agent_id,
                "title": title,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "state": "idle",
                "inherit_from": inherit_policy_from_session_id,
            }
            self._session_agents[session_id] = agent_id

            # 如果有初始提示，添加为第一条消息
            if initial_prompt:
                await self.send_message(session_id, initial_prompt)

        self.logger.info(
            "Session spawned",
            session_id=session_id,
            agent_id=agent_id,
            title=title,
        )

        return session_id, agent_id

    async def get_status(self, session_id: str) -> Optional[SessionStatus]:
        """
        查询会话状态

        Args:
            session_id: 会话 ID

        Returns:
            会话状态，不存在则返回 None
        """
        if not self._check_session_visible(session_id):
            self.logger.warning(
                "Session not visible for status query",
                session_id=session_id,
            )
            return None

        if self._session_manager is not None:
            # 使用外部 SessionManager
            session = await self._session_manager.get_session(session_id)
            if not session:
                return None

            return SessionStatus(
                session_id=session_id,
                state="idle" if session.active else "completed",
                running_tools=[],  # TODO: 从实际执行上下文获取
                updated_at=session.last_active_at.isoformat() if session.last_active_at else datetime.now().isoformat(),
            )
        else:
            # 使用内存存储
            session_data = self._sessions.get(session_id)
            if not session_data:
                return None

            return SessionStatus(
                session_id=session_id,
                state=session_data.get("state", "idle"),
                running_tools=session_data.get("running_tools", []),
                updated_at=session_data.get("updated_at", datetime.now().isoformat()),
            )

    async def list_agents(
        self,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> PageResponse:
        """
        列出可用 agents

        受 allowAgents 限制

        Args:
            cursor: 分页游标
            limit: 每页数量

        Returns:
            分页响应
        """
        items = []

        # 获取所有 agents
        if self._session_manager is not None and hasattr(self._session_manager, "list_agents"):
            agents = await self._session_manager.list_agents()
            for agent in agents:
                agent_id = agent.get("id") or agent.get("agent_id") or agent.get("name")
                # 应用 allowAgents 过滤
                if self._allow_agents is not None and agent_id not in self._allow_agents:
                    continue

                items.append({
                    "agentId": agent_id,
                    "name": agent.get("name", "Unknown"),
                    "description": agent.get("description", ""),
                    "visible": agent.get("visible", True),
                })
        else:
            # 使用内存存储或默认 agents
            for agent_id, agent_data in self._agents.items():
                if self._allow_agents is not None and agent_id not in self._allow_agents:
                    continue

                items.append({
                    "agentId": agent_id,
                    "name": agent_data.get("name", agent_id),
                    "description": agent_data.get("description", ""),
                    "visible": agent_data.get("visible", True),
                })

        # 如果没有 agents，返回一些默认的
        if not items and self._allow_agents is None:
            default_agents = [
                {"agentId": "planner", "name": "Planner", "description": "任务规划师", "visible": True},
                {"agentId": "coder", "name": "Coder", "description": "代码工程师", "visible": True},
                {"agentId": "architect", "name": "Architect", "description": "系统架构师", "visible": True},
                {"agentId": "tester", "name": "Tester", "description": "测试工程师", "visible": True},
            ]
            items = default_agents

        # 处理分页
        start_idx = 0
        if cursor:
            try:
                start_idx = int(cursor)
            except ValueError:
                start_idx = 0

        end_idx = start_idx + limit
        page_items = items[start_idx:end_idx]
        has_more = end_idx < len(items)
        next_cursor = str(end_idx) if has_more else None

        return PageResponse(
            items=page_items,
            next_cursor=next_cursor,
            has_more=has_more,
        )


# ============ 工具实现 ============


class SessionsListTool(BaseTool):
    """
    列出会话工具

    列出当前用户可访问的会话列表，支持分页和按 agent 过滤。
    """

    NAME = "sessions_list"
    DESCRIPTION = "列出会话"
    SCHEMA_VERSION = "1.0.0"

    def __init__(self, manager: Optional[SessionToolManager] = None, **kwargs):
        super().__init__(**kwargs)
        self._manager = manager or SessionToolManager()

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="cursor",
                description="分页游标",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="limit",
                description="每页数量，默认 20",
                type="integer",
                required=False,
                default=20,
            ),
            ToolParameter(
                name="agentId",
                description="Agent ID 过滤",
                type="string",
                required=False,
            ),
        ]

    @property
    def output_schema(self) -> OutputSchema:
        """获取工具输出模式定义"""
        return OutputSchema(
            description="Session list result",
            fields=[
                OutputField(name="items", type="array", description="List of sessions", required=True),
                OutputField(name="nextCursor", type="string", description="Next page cursor", required=False),
                OutputField(name="hasMore", type="boolean", description="Whether more results exist", required=True),
            ],
        )

    async def execute(self, **kwargs) -> ToolResult:
        cursor = kwargs.get("cursor")
        limit = kwargs.get("limit", 20)
        agent_id = kwargs.get("agentId")

        response = await self._manager.list_sessions(
            agent_id=agent_id,
            cursor=cursor,
            limit=limit,
        )

        return ToolResult.ok(
            data={
                "items": response.items,
                "nextCursor": response.next_cursor,
                "hasMore": response.has_more,
            },
        )


class SessionsHistoryTool(BaseTool):
    """
    获取会话历史消息工具

    获取指定会话的历史消息列表，支持分页。
    """

    NAME = "sessions_history"
    DESCRIPTION = "获取会话历史消息"
    SCHEMA_VERSION = "1.0.0"

    def __init__(self, manager: Optional[SessionToolManager] = None, **kwargs):
        super().__init__(**kwargs)
        self._manager = manager or SessionToolManager()

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="sessionId",
                description="会话 ID",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="cursor",
                description="分页游标",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="limit",
                description="每页数量，默认 50",
                type="integer",
                required=False,
                default=50,
            ),
        ]

    @property
    def output_schema(self) -> OutputSchema:
        """获取工具输出模式定义"""
        return OutputSchema(
            description="Session history messages",
            fields=[
                OutputField(name="items", type="array", description="List of messages", required=True),
                OutputField(name="nextCursor", type="string", description="Next page cursor", required=False),
            ],
        )

    async def execute(self, **kwargs) -> ToolResult:
        session_id = kwargs.get("sessionId")
        cursor = kwargs.get("cursor")
        limit = kwargs.get("limit", 50)

        if not session_id:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message="sessionId is required",
                hint="请提供要查询的会话 ID",
            )

        response = await self._manager.get_history(
            session_id=session_id,
            cursor=cursor,
            limit=limit,
        )

        return ToolResult.ok(
            data={
                "items": response.items,
                "nextCursor": response.next_cursor,
            },
        )


class SessionsSendTool(BaseTool):
    """
    向会话发送消息工具

    向指定会话发送消息，返回消息 ID。
    """

    NAME = "sessions_send"
    DESCRIPTION = "向指定会话发送消息"
    SCHEMA_VERSION = "1.0.0"

    def __init__(self, manager: Optional[SessionToolManager] = None, **kwargs):
        super().__init__(**kwargs)
        self._manager = manager or SessionToolManager()

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="sessionId",
                description="会话 ID",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="content",
                description="消息内容",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="metadata",
                description="消息元数据",
                type="object",
                required=False,
            ),
        ]

    @property
    def output_schema(self) -> OutputSchema:
        """获取工具输出模式定义"""
        return OutputSchema(
            description="Message send result",
            fields=[
                OutputField(name="accepted", type="boolean", description="Whether message was accepted", required=True),
                OutputField(name="messageId", type="string", description="Message ID", required=False),
            ],
        )

    async def execute(self, **kwargs) -> ToolResult:
        session_id = kwargs.get("sessionId")
        content = kwargs.get("content")
        metadata = kwargs.get("metadata")

        if not session_id:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message="sessionId is required",
                hint="请提供目标会话 ID",
            )

        if not content:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message="content is required",
                hint="请提供要发送的消息内容",
            )

        success, result = await self._manager.send_message(
            session_id=session_id,
            content=content,
            metadata=metadata,
        )

        if not success:
            return ToolResult.error(
                code=ErrorCode.FORBIDDEN,
                message=result,
                hint="会话可能不存在或不可访问",
            )

        return ToolResult.ok(
            data={
                "accepted": True,
                "messageId": result,
            },
        )


class SessionsSpawnTool(BaseTool):
    """
    创建新会话工具

    创建新的会话并可选地发送初始提示。
    """

    NAME = "sessions_spawn"
    DESCRIPTION = "创建新会话"
    SCHEMA_VERSION = "1.0.0"

    def __init__(self, manager: Optional[SessionToolManager] = None, **kwargs):
        super().__init__(**kwargs)
        self._manager = manager or SessionToolManager()

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="agentId",
                description="Agent ID",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="title",
                description="会话标题",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="initialPrompt",
                description="初始提示",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="inheritPolicyFromSessionId",
                description="继承策略的源会话 ID",
                type="string",
                required=False,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        agent_id = kwargs.get("agentId")
        title = kwargs.get("title")
        initial_prompt = kwargs.get("initialPrompt")
        inherit_policy_from_session_id = kwargs.get("inheritPolicyFromSessionId")

        if not agent_id:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message="agentId is required",
                hint="请指定要创建会话的 Agent ID",
            )

        if not title:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message="title is required",
                hint="请提供会话标题",
            )

        session_id, returned_agent_id = await self._manager.spawn_session(
            agent_id=agent_id,
            title=title,
            initial_prompt=initial_prompt or "",
            inherit_policy_from_session_id=inherit_policy_from_session_id,
        )

        if not session_id:
            return ToolResult.error(
                code=ErrorCode.FORBIDDEN,
                message="Failed to spawn session. Agent may not be allowed.",
                hint="Agent 可能不在允许列表中，请检查 allowAgents 配置",
                details={"agentId": agent_id},
            )

        return ToolResult.ok(
            data={
                "sessionId": session_id,
                "agentId": returned_agent_id,
            },
        )


class SessionStatusTool(BaseTool):
    """
    查询会话状态工具

    查询指定会话的当前状态，包括正在执行的工具等信息。
    """

    NAME = "session_status"
    DESCRIPTION = "查询会话状态"
    SCHEMA_VERSION = "1.0.0"

    def __init__(self, manager: Optional[SessionToolManager] = None, **kwargs):
        super().__init__(**kwargs)
        self._manager = manager or SessionToolManager()

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="sessionId",
                description="会话 ID",
                type="string",
                required=True,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        session_id = kwargs.get("sessionId")

        if not session_id:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message="sessionId is required",
                hint="请提供要查询状态的会话 ID",
            )

        status = await self._manager.get_status(session_id)

        if not status:
            return ToolResult.error(
                code=ErrorCode.NOT_FOUND,
                message=f"Session not found: {session_id}",
                hint="会话可能已过期或不存在",
                details={"sessionId": session_id},
            )

        return ToolResult.ok(
            data={
                "sessionId": status.session_id,
                "state": status.state,
                "runningTools": status.running_tools,
                "updatedAt": status.updated_at,
            },
        )


class AgentsListTool(BaseTool):
    """
    列出可用 agents 工具

    列出所有可用的 agents，受 allowAgents 策略约束。
    """

    NAME = "agents_list"
    DESCRIPTION = "列出可用 agents"
    SCHEMA_VERSION = "1.0.0"

    def __init__(self, manager: Optional[SessionToolManager] = None, **kwargs):
        super().__init__(**kwargs)
        self._manager = manager or SessionToolManager()

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="cursor",
                description="分页游标",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="limit",
                description="每页数量，默认 20",
                type="integer",
                required=False,
                default=20,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        cursor = kwargs.get("cursor")
        limit = kwargs.get("limit", 20)

        response = await self._manager.list_agents(
            cursor=cursor,
            limit=limit,
        )

        return ToolResult.ok(
            data={
                "items": response.items,
                "nextCursor": response.next_cursor,
            },
        )


# ============ 便捷函数 ============


def create_session_tools(
    session_manager: Any = None,
    allow_agents: Optional[list[str]] = None,
    current_session_id: Optional[str] = None,
    current_user_id: Optional[str] = None,
) -> tuple[
    SessionsListTool,
    SessionsHistoryTool,
    SessionsSendTool,
    SessionsSpawnTool,
    SessionStatusTool,
    AgentsListTool,
]:
    """
    创建会话工具族实例

    Args:
        session_manager: 底层 SessionManager 实例
        allow_agents: 允许访问的 agent ID 列表
        current_session_id: 当前会话 ID
        current_user_id: 当前用户 ID

    Returns:
        工具实例元组
    """
    manager = SessionToolManager(
        session_manager=session_manager,
        allow_agents=allow_agents,
        current_session_id=current_session_id,
        current_user_id=current_user_id,
    )

    return (
        SessionsListTool(manager=manager),
        SessionsHistoryTool(manager=manager),
        SessionsSendTool(manager=manager),
        SessionsSpawnTool(manager=manager),
        SessionStatusTool(manager=manager),
        AgentsListTool(manager=manager),
    )
