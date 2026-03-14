"""
Memory 工具族

提供记忆搜索和检索功能，支持 Agent 隔离的记忆访问。

工具：
- MemorySearchTool: 搜索 agent 的记忆
- MemoryGetTool: 根据 ID 获取特定记忆

后端：
- MemoryBackend: 抽象后端接口
- InMemoryBackend: 内存存储后端（开发/测试用）
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from ..base import BaseTool, OutputField, OutputSchema, ToolParameter, ToolResult
from ..errors import ErrorCode

logger = structlog.get_logger(__name__)


# ==========================================
# 数据模型
# ==========================================


class MemoryEntry(BaseModel):
    """记忆条目模型"""

    id: str = Field(..., description="记忆 ID")
    agent_id: str = Field(..., description="所属 Agent ID")
    content: str = Field(..., description="记忆内容")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")
    namespace: str = Field(default="default", description="命名空间")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    score: float | None = Field(default=None, description="搜索相关性分数")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


# ==========================================
# 后端接口
# ==========================================


class MemoryBackend(ABC):
    """
    记忆存储后端抽象接口

    所有记忆后端必须实现此接口。
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        agent_id: str,
        limit: int = 10,
        namespace: str | None = None,
    ) -> list[MemoryEntry]:
        """
        搜索记忆

        Args:
            query: 搜索查询
            agent_id: Agent ID（用于隔离）
            limit: 最大返回数量
            namespace: 命名空间过滤

        Returns:
            记忆条目列表
        """
        pass

    @abstractmethod
    async def get(
        self,
        memory_id: str,
        agent_id: str,
    ) -> MemoryEntry | None:
        """
        获取特定记忆

        Args:
            memory_id: 记忆 ID
            agent_id: Agent ID（用于权限验证）

        Returns:
            记忆条目，不存在则返回 None
        """
        pass

    @abstractmethod
    async def store(
        self,
        agent_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        namespace: str = "default",
    ) -> str:
        """
        存储记忆

        Args:
            agent_id: Agent ID
            content: 记忆内容
            metadata: 元数据
            namespace: 命名空间

        Returns:
            记忆 ID
        """
        pass


class InMemoryBackend(MemoryBackend):
    """
    内存存储后端

    适用于开发、测试场景。数据保存在内存中，进程重启后丢失。

    Attributes:
        _memories: 内存存储字典 {memory_id: MemoryEntry}

    Example:
        >>> backend = InMemoryBackend()
        >>> memory_id = await backend.store("agent-001", "重要记忆")
        >>> memories = await backend.search("重要", "agent-001")
    """

    def __init__(self) -> None:
        """初始化内存后端"""
        self._memories: dict[str, MemoryEntry] = {}
        self._agent_index: dict[str, list[str]] = {}  # agent_id -> [memory_ids]
        self.logger = logger.bind(backend="in_memory")

    async def search(
        self,
        query: str,
        agent_id: str,
        limit: int = 10,
        namespace: str | None = None,
    ) -> list[MemoryEntry]:
        """
        搜索记忆（简单文本匹配）

        Args:
            query: 搜索查询
            agent_id: Agent ID
            limit: 最大返回数量
            namespace: 命名空间过滤

        Returns:
            匹配的记忆列表
        """
        results = []

        # 获取该 agent 的所有记忆 ID
        memory_ids = self._agent_index.get(agent_id, [])

        for memory_id in memory_ids:
            memory = self._memories.get(memory_id)
            if not memory:
                continue

            # 命名空间过滤
            if namespace and memory.namespace != namespace:
                continue

            # 简单文本匹配
            if query.lower() in memory.content.lower():
                # 计算简单的相关性分数
                score = memory.content.lower().count(query.lower()) / len(
                    memory.content.split()
                )
                memory_copy = MemoryEntry(
                    id=memory.id,
                    agent_id=memory.agent_id,
                    content=memory.content,
                    metadata=memory.metadata,
                    namespace=memory.namespace,
                    created_at=memory.created_at,
                    score=score,
                )
                results.append(memory_copy)

        # 按分数排序并限制数量
        results.sort(key=lambda x: x.score or 0, reverse=True)
        return results[:limit]

    async def get(
        self,
        memory_id: str,
        agent_id: str,
    ) -> MemoryEntry | None:
        """
        获取特定记忆

        Args:
            memory_id: 记忆 ID
            agent_id: Agent ID

        Returns:
            记忆条目，不存在或不属于该 agent 则返回 None
        """
        memory = self._memories.get(memory_id)

        # Agent 隔离检查
        if memory and memory.agent_id == agent_id:
            return memory

        return None

    async def store(
        self,
        agent_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        namespace: str = "default",
    ) -> str:
        """
        存储记忆

        Args:
            agent_id: Agent ID
            content: 记忆内容
            metadata: 元数据
            namespace: 命名空间

        Returns:
            记忆 ID
        """
        import uuid

        memory_id = str(uuid.uuid4())

        memory = MemoryEntry(
            id=memory_id,
            agent_id=agent_id,
            content=content,
            metadata=metadata or {},
            namespace=namespace,
        )

        self._memories[memory_id] = memory

        # 更新 agent 索引
        if agent_id not in self._agent_index:
            self._agent_index[agent_id] = []
        self._agent_index[agent_id].append(memory_id)

        self.logger.debug(
            "Memory stored",
            memory_id=memory_id,
            agent_id=agent_id,
            namespace=namespace,
        )

        return memory_id


# ==========================================
# 工具实现
# ==========================================


class MemorySearchTool(BaseTool):
    """
    记忆搜索工具

    搜索 agent 的记忆以获取相关信息。

    Attributes:
        NAME: 工具名称
        DESCRIPTION: 工具描述
        backend: 记忆后端实例

    Example:
        >>> backend = InMemoryBackend()
        >>> tool = MemorySearchTool(backend=backend)
        >>> result = await tool(
        ...     query="项目需求",
        ...     agent_id="agent-001",
        ...     limit=5
        ... )
    """

    NAME = "memory_search"
    DESCRIPTION = "Search agent's memory for relevant information"
    SCHEMA_VERSION = "1.0.0"

    def __init__(
        self,
        backend: MemoryBackend | None = None,
        **kwargs: Any,
    ) -> None:
        """
        初始化记忆搜索工具

        Args:
            backend: 记忆后端实例（默认使用 InMemoryBackend）
            **kwargs: 其他配置
        """
        super().__init__(**kwargs)
        self.backend = backend or InMemoryBackend()
        self.logger = logger.bind(tool="memory_search")

    @property
    def parameters(self) -> list[ToolParameter]:
        """获取参数定义"""
        return [
            ToolParameter(
                name="query",
                type="string",
                required=True,
                description="Search query to find relevant memories",
            ),
            ToolParameter(
                name="agent_id",
                type="string",
                required=True,
                description="Agent ID to search memories for",
            ),
            ToolParameter(
                name="limit",
                type="integer",
                required=False,
                default=10,
                description="Maximum number of results to return",
            ),
            ToolParameter(
                name="namespace",
                type="string",
                required=False,
                default=None,
                description="Memory namespace to search within",
            ),
        ]

    @property
    def output_schema(self) -> OutputSchema:
        """
        获取工具输出模式定义

        Returns:
            MemorySearchTool 的输出模式
        """
        return OutputSchema(
            description="Memory search results",
            fields=[
                OutputField(
                    name="memories",
                    type="array",
                    description="List of matching memory entries",
                    required=True,
                ),
                OutputField(
                    name="count",
                    type="integer",
                    description="Number of results returned",
                    required=True,
                ),
            ],
            nested_schemas={
                "memory_entry": OutputSchema(
                    description="Memory entry",
                    fields=[
                        OutputField(name="id", type="string", description="Memory ID", required=True),
                        OutputField(name="agent_id", type="string", description="Agent ID", required=True),
                        OutputField(name="content", type="string", description="Memory content", required=True),
                        OutputField(name="namespace", type="string", description="Namespace", required=True),
                        OutputField(name="created_at", type="string", description="Creation time (ISO 8601)", required=True),
                        OutputField(name="score", type="number", description="Relevance score", required=False),
                    ],
                ),
            },
        )

    async def execute(
        self,
        query: str,
        agent_id: str,
        limit: int = 10,
        namespace: str | None = None,
    ) -> ToolResult:
        """
        执行记忆搜索

        Args:
            query: 搜索查询
            agent_id: Agent ID
            limit: 最大结果数
            namespace: 命名空间

        Returns:
            搜索结果
        """
        try:
            memories = await self.backend.search(
                query=query,
                agent_id=agent_id,
                limit=limit,
                namespace=namespace,
            )

            results = [memory.model_dump() for memory in memories]

            self.logger.info(
                "Memory search completed",
                query=query,
                agent_id=agent_id,
                results_count=len(results),
            )

            return ToolResult.ok(
                data={
                    "query": query,
                    "agent_id": agent_id,
                    "count": len(results),
                    "memories": results,
                },
                limit=limit,
                namespace=namespace,
            )

        except Exception as e:
            self.logger.error(
                "Memory search failed",
                query=query,
                agent_id=agent_id,
                error=str(e),
            )
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to search memories: {e}",
                retryable=True,
                details={"query": query, "agent_id": agent_id},
            )


class MemoryGetTool(BaseTool):
    """
    记忆获取工具

    根据 ID 检索特定的记忆条目。

    Attributes:
        NAME: 工具名称
        DESCRIPTION: 工具描述
        backend: 记忆后端实例

    Example:
        >>> backend = InMemoryBackend()
        >>> tool = MemoryGetTool(backend=backend)
        >>> result = await tool(
        ...     memory_id="mem-123",
        ...     agent_id="agent-001"
        ... )
    """

    NAME = "memory_get"
    DESCRIPTION = "Retrieve specific memory entry by ID"
    SCHEMA_VERSION = "1.0.0"

    def __init__(
        self,
        backend: MemoryBackend | None = None,
        **kwargs: Any,
    ) -> None:
        """
        初始化记忆获取工具

        Args:
            backend: 记忆后端实例（默认使用 InMemoryBackend）
            **kwargs: 其他配置
        """
        super().__init__(**kwargs)
        self.backend = backend or InMemoryBackend()
        self.logger = logger.bind(tool="memory_get")

    @property
    def parameters(self) -> list[ToolParameter]:
        """获取参数定义"""
        return [
            ToolParameter(
                name="memory_id",
                type="string",
                required=True,
                description="Memory entry ID to retrieve",
            ),
            ToolParameter(
                name="agent_id",
                type="string",
                required=True,
                description="Agent ID for access control",
            ),
        ]

    @property
    def output_schema(self) -> OutputSchema:
        """
        获取工具输出模式定义

        Returns:
            MemoryGetTool 的输出模式
        """
        return OutputSchema(
            description="Memory entry data",
            fields=[
                OutputField(name="id", type="string", description="Memory ID", required=True),
                OutputField(name="agent_id", type="string", description="Agent ID", required=True),
                OutputField(name="content", type="string", description="Memory content", required=True),
                OutputField(name="namespace", type="string", description="Namespace", required=True),
                OutputField(name="created_at", type="string", description="Creation time (ISO 8601)", required=True),
                OutputField(name="metadata", type="object", description="Additional metadata", required=False),
            ],
        )

    async def execute(
        self,
        memory_id: str,
        agent_id: str,
    ) -> ToolResult:
        """
        执行记忆获取

        Args:
            memory_id: 记忆 ID
            agent_id: Agent ID（用于权限验证）

        Returns:
            记忆数据
        """
        try:
            memory = await self.backend.get(
                memory_id=memory_id,
                agent_id=agent_id,
            )

            if not memory:
                return ToolResult.error(
                    code=ErrorCode.NOT_FOUND,
                    message=f"Memory not found: {memory_id}",
                    retryable=False,
                    details={"memory_id": memory_id, "agent_id": agent_id},
                    hint="Verify the memory ID and agent ID are correct",
                )

            self.logger.info(
                "Memory retrieved",
                memory_id=memory_id,
                agent_id=agent_id,
            )

            return ToolResult.ok(
                data=memory.model_dump(),
                memory_id=memory_id,
                agent_id=agent_id,
            )

        except Exception as e:
            self.logger.error(
                "Memory retrieval failed",
                memory_id=memory_id,
                agent_id=agent_id,
                error=str(e),
            )
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to retrieve memory: {e}",
                retryable=True,
                details={"memory_id": memory_id, "agent_id": agent_id},
            )


# ==========================================
# 便捷函数
# ==========================================


def create_memory_tools(
    backend: MemoryBackend | None = None,
) -> tuple[MemorySearchTool, MemoryGetTool]:
    """
    创建记忆工具实例

    Args:
        backend: 记忆后端实例

    Returns:
        (MemorySearchTool, MemoryGetTool) 元组

    Example:
        >>> backend = InMemoryBackend()
        >>> search_tool, get_tool = create_memory_tools(backend)
    """
    search_tool = MemorySearchTool(backend=backend)
    get_tool = MemoryGetTool(backend=backend)

    return search_tool, get_tool
