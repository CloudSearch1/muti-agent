"""
Pi 系统 - 类型定义

定义智能 Agent 协作系统的核心类型

版本: 1.0.0
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class PiAgentStatus(str, Enum):
    """Pi Agent 状态"""

    IDLE = "idle"  # 空闲
    BUSY = "busy"  # 忙碌
    ERROR = "error"  # 错误
    OFFLINE = "offline"  # 离线
    INITIALIZING = "initializing"  # 初始化中


class PiTaskStatus(str, Enum):
    """Pi 任务状态"""

    PENDING = "pending"  # 待处理
    QUEUED = "queued"  # 已入队
    ASSIGNED = "assigned"  # 已分配
    IN_PROGRESS = "in_progress"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class PiTaskPriority(str, Enum):
    """Pi 任务优先级"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class MessageType(str, Enum):
    """消息类型"""

    TASK = "task"  # 任务消息
    STATUS = "status"  # 状态消息
    RESULT = "result"  # 结果消息
    ERROR = "error"  # 错误消息
    CONTROL = "control"  # 控制消息
    BROADCAST = "broadcast"  # 广播消息


class AgentCapability(str, Enum):
    """Agent 能力"""

    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    RESEARCH = "research"
    PLANNING = "planning"
    ANALYSIS = "analysis"


class TaskAssignmentStrategy(str, Enum):
    """任务分配策略"""

    ROUND_ROBIN = "round_robin"  # 轮询
    LEAST_LOADED = "least_loaded"  # 最少负载
    CAPABILITY_MATCH = "capability_match"  # 能力匹配
    PRIORITY_FIRST = "priority_first"  # 优先级优先
    SMART = "smart"  # 智能分配


# ===========================================
# 请求/响应模型
# ===========================================


class PiAgentConfig(BaseModel):
    """Pi Agent 配置"""

    name: str = Field(..., description="Agent 名称")
    role: str = Field(..., description="Agent 角色")
    capabilities: list[str] = Field(default_factory=list, description="能力列表")
    max_concurrent_tasks: int = Field(default=3, ge=1, le=10, description="最大并发任务数")
    timeout_seconds: int = Field(default=300, ge=30, le=3600, description="任务超时时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class PiAgentInfo(BaseModel):
    """Pi Agent 信息"""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Agent ID")
    name: str = Field(..., description="Agent 名称")
    role: str = Field(..., description="Agent 角色")
    status: PiAgentStatus = Field(default=PiAgentStatus.IDLE, description="状态")
    capabilities: list[str] = Field(default_factory=list, description="能力列表")
    current_tasks: list[str] = Field(default_factory=list, description="当前任务列表")
    completed_tasks: int = Field(default=0, description="完成任务数")
    failed_tasks: int = Field(default=0, description="失败任务数")
    avg_execution_time: float = Field(default=0.0, description="平均执行时间")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    last_active_at: datetime | None = Field(default=None, description="最后活跃时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def is_available(self) -> bool:
        """检查 Agent 是否可用"""
        return self.status == PiAgentStatus.IDLE

    def get_load(self) -> float:
        """获取负载比例"""
        return len(self.current_tasks) / max(1, self.max_concurrent_tasks)

    max_concurrent_tasks: int = Field(default=3, description="最大并发任务数")


class PiTaskConfig(BaseModel):
    """Pi 任务配置"""

    title: str = Field(..., description="任务标题")
    description: str = Field(default="", description="任务描述")
    priority: PiTaskPriority = Field(default=PiTaskPriority.NORMAL, description="优先级")
    required_capabilities: list[str] = Field(default_factory=list, description="所需能力")
    input_data: dict[str, Any] = Field(default_factory=dict, description="输入数据")
    dependencies: list[str] = Field(default_factory=list, description="依赖任务 ID")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    timeout_seconds: int = Field(default=300, ge=30, le=3600, description="超时时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class PiTaskInfo(BaseModel):
    """Pi 任务信息"""

    id: str = Field(default_factory=lambda: str(uuid4()), description="任务 ID")
    title: str = Field(..., description="任务标题")
    description: str = Field(default="", description="任务描述")
    status: PiTaskStatus = Field(default=PiTaskStatus.PENDING, description="状态")
    priority: PiTaskPriority = Field(default=PiTaskPriority.NORMAL, description="优先级")
    required_capabilities: list[str] = Field(default_factory=list, description="所需能力")
    input_data: dict[str, Any] = Field(default_factory=dict, description="输入数据")
    output_data: dict[str, Any] = Field(default_factory=dict, description="输出数据")
    assigned_agent_id: str | None = Field(default=None, description="分配的 Agent ID")
    dependencies: list[str] = Field(default_factory=list, description="依赖任务 ID")
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    error_message: str | None = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def is_high_priority(self) -> bool:
        """检查是否高优先级"""
        return self.priority in [PiTaskPriority.HIGH, PiTaskPriority.CRITICAL]


class PiMessage(BaseModel):
    """Pi 消息"""

    id: str = Field(default_factory=lambda: str(uuid4()), description="消息 ID")
    type: MessageType = Field(default=MessageType.STATUS, description="消息类型")
    sender_id: str | None = Field(default=None, description="发送者 ID")
    receiver_id: str | None = Field(default=None, description="接收者 ID (None 为广播)")
    subject: str = Field(default="", description="主题")
    content: Any = Field(default=None, description="内容")
    task_id: str | None = Field(default=None, description="关联任务 ID")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class PiWorkflowConfig(BaseModel):
    """Pi 工作流配置"""

    name: str = Field(..., description="工作流名称")
    description: str = Field(default="", description="工作流描述")
    tasks: list[PiTaskConfig] = Field(default_factory=list, description="任务列表")
    assignment_strategy: TaskAssignmentStrategy = Field(
        default=TaskAssignmentStrategy.SMART, description="分配策略"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class PiWorkflowResult(BaseModel):
    """Pi 工作流结果"""

    workflow_id: str = Field(default_factory=lambda: str(uuid4()), description="工作流 ID")
    name: str = Field(..., description="工作流名称")
    status: str = Field(default="pending", description="状态")
    task_results: dict[str, PiTaskInfo] = Field(default_factory=dict, description="任务结果")
    total_tasks: int = Field(default=0, description="总任务数")
    completed_tasks: int = Field(default=0, description="完成任务数")
    failed_tasks: int = Field(default=0, description="失败任务数")
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")
    output_data: dict[str, Any] = Field(default_factory=dict, description="输出数据")


class PiSystemStats(BaseModel):
    """Pi 系统统计"""

    total_agents: int = Field(default=0, description="总 Agent 数")
    active_agents: int = Field(default=0, description="活跃 Agent 数")
    total_tasks: int = Field(default=0, description="总任务数")
    pending_tasks: int = Field(default=0, description="待处理任务数")
    completed_tasks: int = Field(default=0, description="完成任务数")
    failed_tasks: int = Field(default=0, description="失败任务数")
    avg_task_duration: float = Field(default=0.0, description="平均任务时长")
    system_load: float = Field(default=0.0, description="系统负载")
    uptime_seconds: float = Field(default=0.0, description="运行时长")


class TaskAssignment(BaseModel):
    """任务分配记录"""

    task_id: str = Field(..., description="任务 ID")
    agent_id: str = Field(..., description="Agent ID")
    assigned_at: datetime = Field(default_factory=datetime.now, description="分配时间")
    reason: str = Field(default="", description="分配原因")
    score: float = Field(default=0.0, description="匹配得分")


class AgentLoadInfo(BaseModel):
    """Agent 负载信息"""

    agent_id: str = Field(..., description="Agent ID")
    current_tasks: int = Field(default=0, description="当前任务数")
    max_tasks: int = Field(default=3, description="最大任务数")
    load_ratio: float = Field(default=0.0, description="负载比例")
    recent_success_rate: float = Field(default=1.0, description="近期成功率")
    avg_response_time: float = Field(default=0.0, description="平均响应时间")


class ResultEvaluation(BaseModel):
    """结果评估"""

    task_id: str = Field(..., description="任务 ID")
    agent_id: str = Field(..., description="Agent ID")
    quality_score: float = Field(default=0.0, ge=0.0, le=100.0, description="质量分数")
    completeness: float = Field(default=0.0, ge=0.0, le=1.0, description="完整度")
    accuracy: float = Field(default=0.0, ge=0.0, le=1.0, description="准确度")
    issues: list[str] = Field(default_factory=list, description="问题列表")
    suggestions: list[str] = Field(default_factory=list, description="改进建议")
    evaluated_at: datetime = Field(default_factory=datetime.now, description="评估时间")


class ConflictResolution(BaseModel):
    """冲突解决"""

    conflict_id: str = Field(default_factory=lambda: str(uuid4()), description="冲突 ID")
    task_id: str = Field(..., description="任务 ID")
    conflicting_results: list[dict[str, Any]] = Field(default_factory=list, description="冲突结果")
    resolution_strategy: str = Field(default="majority", description="解决策略")
    final_result: dict[str, Any] = Field(default_factory=dict, description="最终结果")
    resolved_at: datetime = Field(default_factory=datetime.now, description="解决时间")


# ===========================================
# API 请求/响应模型
# ===========================================


class CreateAgentRequest(BaseModel):
    """创建 Agent 请求"""

    name: str
    role: str
    capabilities: list[str] = []
    max_concurrent_tasks: int = 3
    timeout_seconds: int = 300
    metadata: dict[str, Any] = {}


class CreateTaskRequest(BaseModel):
    """创建任务请求"""

    title: str
    description: str = ""
    priority: str = "normal"
    required_capabilities: list[str] = []
    input_data: dict[str, Any] = {}
    dependencies: list[str] = []
    max_retries: int = 3
    timeout_seconds: int = 300


class ExecuteWorkflowRequest(BaseModel):
    """执行工作流请求"""

    name: str
    description: str = ""
    tasks: list[CreateTaskRequest]
    assignment_strategy: str = "smart"


class AgentListResponse(BaseModel):
    """Agent 列表响应"""

    agents: list[PiAgentInfo]
    total: int


class TaskListResponse(BaseModel):
    """任务列表响应"""

    tasks: list[PiTaskInfo]
    total: int


__all__ = [
    # 枚举
    "PiAgentStatus",
    "PiTaskStatus",
    "PiTaskPriority",
    "MessageType",
    "AgentCapability",
    "TaskAssignmentStrategy",
    # 模型
    "PiAgentConfig",
    "PiAgentInfo",
    "PiTaskConfig",
    "PiTaskInfo",
    "PiMessage",
    "PiWorkflowConfig",
    "PiWorkflowResult",
    "PiSystemStats",
    "TaskAssignment",
    "AgentLoadInfo",
    "ResultEvaluation",
    "ConflictResolution",
    # API 模型
    "CreateAgentRequest",
    "CreateTaskRequest",
    "ExecuteWorkflowRequest",
    "AgentListResponse",
    "TaskListResponse",
]