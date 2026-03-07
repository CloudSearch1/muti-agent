"""
核心数据模型

定义 Agent、Task、Workflow 等核心实体
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ============ 枚举类型 ============


class AgentRole(StrEnum):
    """Agent 角色枚举"""

    PLANNER = "planner"
    ARCHITECT = "architect"
    CODER = "coder"
    TESTER = "tester"
    DOC_WRITER = "doc_writer"
    RESEARCHER = "researcher"
    SENIOR_ARCHITECT = "senior_architect"


class AgentState(StrEnum):
    """Agent 状态枚举"""

    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class TaskStatus(StrEnum):
    """任务状态枚举"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    """任务优先级枚举"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowStatus(StrEnum):
    """工作流状态枚举"""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


# ============ Agent 模型 ============


class Agent(BaseModel):
    """Agent 数据模型"""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Agent ID")
    name: str = Field(..., description="Agent 名称")
    role: AgentRole = Field(..., description="Agent 角色")
    state: AgentState = Field(default=AgentState.IDLE, description="Agent 状态")
    enabled: bool = Field(default=True, description="是否启用")
    description: str = Field(default="", description="描述")

    # 当前任务
    current_task_id: str | None = Field(default=None, description="当前任务 ID")

    # 超时设置
    timeout_seconds: int = Field(default=300, ge=1, le=3600, description="任务超时时间(秒)")

    # 最后活跃时间
    last_active_at: datetime | None = Field(default=None, description="最后活跃时间")

    # 统计信息
    tasks_completed: int = Field(default=0, ge=0, description="完成任务数")
    tasks_failed: int = Field(default=0, ge=0, description="失败任务数")
    total_execution_time: float = Field(default=0.0, ge=0.0, description="总执行时间")
    avg_execution_time: float = Field(default=0.0, ge=0.0, description="平均执行时间")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def is_available(self) -> bool:
        """检查 Agent 是否可用"""
        return self.enabled and self.state == AgentState.IDLE

    def assign_task(self, task_id: str) -> None:
        """分配任务"""
        self.current_task_id = task_id
        self.state = AgentState.BUSY
        self.updated_at = datetime.now()

    def complete_task(self, success: bool = True, execution_time: float = 0.0) -> None:
        """完成任务"""
        if success:
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1

        self.total_execution_time += execution_time
        total_tasks = self.tasks_completed + self.tasks_failed
        self.avg_execution_time = (
            self.total_execution_time / total_tasks if total_tasks > 0 else 0.0
        )

        self.current_task_id = None
        self.state = AgentState.IDLE
        self.updated_at = datetime.now()

    def fail_task(self) -> None:
        """任务失败"""
        self.tasks_failed += 1
        self.current_task_id = None
        self.state = AgentState.IDLE
        self.updated_at = datetime.now()

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        total = self.tasks_completed + self.tasks_failed
        success_rate = (self.tasks_completed / total * 100) if total > 0 else 0.0

        return {
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "success_rate": round(success_rate, 2),
            "avg_execution_time": round(self.avg_execution_time, 2),
            "total_execution_time": round(self.total_execution_time, 2),
        }


# ============ Task 模型 ============


class Task(BaseModel):
    """任务数据模型"""

    id: str = Field(default_factory=lambda: str(uuid4()), description="任务 ID")
    title: str = Field(..., description="任务标题")
    description: str = Field(default="", description="任务描述")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="任务优先级")

    # 分配信息
    assignee: str | None = Field(default=None, description="分配给谁")
    assigned_to: str | None = Field(default=None, description="分配给的 Agent ID")
    agent_role: AgentRole | None = Field(default=None, description="负责的 Agent 角色")

    # 输入输出
    input_data: dict[str, Any] = Field(default_factory=dict, description="输入数据")
    output_data: dict[str, Any] = Field(default_factory=dict, description="输出数据")

    # 执行信息
    error_message: str | None = Field(default=None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")

    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")

    # 依赖关系
    dependencies: list[str] = Field(default_factory=list, description="依赖的任务 ID")

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def start(self) -> None:
        """开始任务"""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def complete(self, output_data: dict[str, Any] = None) -> None:
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        if output_data:
            self.output_data = output_data

    def fail(self, error_message: str = None) -> None:
        """任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        if error_message:
            self.error_message = error_message

    def retry(self) -> bool:
        """重试任务"""
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            self.status = TaskStatus.PENDING
            self.error_message = None
            self.started_at = None
            self.completed_at = None
            return True
        return False

    def is_terminal(self) -> bool:
        """检查是否为终端状态"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]

    def get_priority_level(self) -> int:
        """获取优先级数值（用于排序，数值越大优先级越高）"""
        priority_map = {
            TaskPriority.LOW: 1,
            TaskPriority.NORMAL: 2,
            TaskPriority.HIGH: 3,
            TaskPriority.CRITICAL: 4,
        }
        return priority_map.get(self.priority, 2)

    def is_high_priority(self) -> bool:
        """检查是否为高优先级任务"""
        return self.priority in [TaskPriority.HIGH, TaskPriority.CRITICAL]

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return self.model_dump()


# ============ Workflow 模型 ============


class Workflow(BaseModel):
    """工作流数据模型"""

    id: str = Field(default_factory=lambda: str(uuid4()), description="工作流 ID")
    name: str = Field(..., description="工作流名称")
    description: str = Field(default="", description="工作流描述")
    status: WorkflowStatus = Field(default=WorkflowStatus.CREATED, description="工作流状态")

    # 任务列表
    task_ids: list[str] = Field(default_factory=list, description="任务 ID 列表")

    # 输入输出
    input_data: dict[str, Any] = Field(default_factory=dict, description="输入数据")
    output_data: dict[str, Any] = Field(default_factory=dict, description="输出数据")

    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def start(self) -> None:
        """开始工作流"""
        self.status = WorkflowStatus.RUNNING
        self.started_at = datetime.now()

    def complete(self, output_data: dict[str, Any] = None) -> None:
        """完成工作流"""
        self.status = WorkflowStatus.COMPLETED
        self.completed_at = datetime.now()
        if output_data:
            self.output_data = output_data

    def fail(self) -> None:
        """工作流失败"""
        self.status = WorkflowStatus.FAILED
        self.completed_at = datetime.now()

    def add_task(self, task_id: str) -> None:
        """添加任务"""
        if task_id not in self.task_ids:
            self.task_ids.append(task_id)


# ============ Blackboard 模型 ============


class BlackboardEntry(BaseModel):
    """黑板条目模型"""

    id: str = Field(default_factory=lambda: str(uuid4()), description="条目 ID")
    key: str = Field(..., description="键")
    value: Any = Field(..., description="值")
    entry_type: str = Field(default="generic", description="条目类型")

    # 来源信息
    source_agent: str | None = Field(default=None, description="来源 Agent")
    source_task: str | None = Field(default=None, description="来源任务")

    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    expires_at: datetime | None = Field(default=None, description="过期时间")

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class BlackboardMessage(BaseModel):
    """黑板消息模型"""

    id: str = Field(default_factory=lambda: str(uuid4()), description="消息 ID")
    sender: str = Field(..., description="发送者")
    receiver: str | None = Field(default=None, description="接收者（None 表示广播）")
    content: str = Field(..., description="消息内容")
    message_type: str = Field(default="info", description="消息类型")

    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class MessageType(StrEnum):
    """消息类型枚举"""

    NOTIFICATION = "notification"
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    STATUS = "status"
    TASK = "task"
    INFO = "info"


class Message(BaseModel):
    """消息模型"""

    id: str = Field(default_factory=lambda: str(uuid4()), description="消息 ID")
    type: MessageType = Field(default=MessageType.NOTIFICATION, description="消息类型")
    priority: str = Field(default="normal", description="优先级")
    subject: str = Field(default="", description="主题")
    content: Any = Field(..., description="内容")

    # 发送者信息
    sender_id: str | None = Field(default=None, description="发送者 ID")
    sender_role: str | None = Field(default=None, description="发送者角色")

    # 接收者信息
    recipient_id: str | None = Field(default=None, description="接收者 ID")
    recipient_role: str | None = Field(default=None, description="接收者角色")

    # 关联信息
    task_id: str | None = Field(default=None, description="关联任务 ID")

    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    read_at: datetime | None = Field(default=None, description="阅读时间")

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class Blackboard(BaseModel):
    """黑板系统 - 用于 Agent 间通信和共享状态"""

    id: str = Field(default_factory=lambda: str(uuid4()), description="黑板 ID")
    name: str = Field(default="default", description="黑板名称")
    description: str | None = Field(default=None, description="黑板描述")
    entries: dict[str, BlackboardEntry] = Field(default_factory=dict, description="条目字典")
    messages: list[Message] = Field(default_factory=list, description="消息列表")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    def put(self, key: str, value: Any, owner_id: str | None = None, **kwargs) -> BlackboardEntry:
        """写入数据"""
        entry = BlackboardEntry(key=key, value=value, source_agent=owner_id, **kwargs)
        self.entries[key] = entry
        self.updated_at = datetime.now()
        return entry

    def get(self, key: str, default: Any = None) -> Any:
        """读取数据"""
        entry = self.entries.get(key)
        return entry.value if entry else default

    def post_message(self, message: Message) -> None:
        """发布消息"""
        self.messages.append(message)
        self.updated_at = datetime.now()

    def get_messages(
        self,
        recipient_id: str | None = None,
        recipient_role: str | None = None,
        message_type: MessageType | None = None,
        unread_only: bool = False,
    ) -> list[Message]:
        """获取消息"""
        result = []
        for msg in self.messages:
            if recipient_id and msg.recipient_id and msg.recipient_id != recipient_id:
                continue
            if recipient_role and msg.recipient_role and msg.recipient_role != recipient_role:
                continue
            if message_type and msg.type != message_type:
                continue
            if unread_only and msg.read_at:
                continue
            result.append(msg)
        return result

    def mark_message_read(self, message_id: str, reader_id: str) -> None:
        """标记消息已读"""
        for msg in self.messages:
            if msg.id == message_id:
                msg.read_at = datetime.now()
                break


# ============ 导出 ============

__all__ = [
    # 枚举
    "AgentRole",
    "AgentState",
    "TaskStatus",
    "TaskPriority",
    "WorkflowStatus",
    "MessageType",
    # 模型
    "Agent",
    "Task",
    "Workflow",
    "BlackboardEntry",
    "BlackboardMessage",
    "Message",
    "Blackboard",
]
