"""
工作流状态定义

职责：定义 LangGraph 工作流的状态结构
"""

from typing import Any

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    LangGraph 工作流状态

    在节点之间传递的状态对象
    """

    # 任务信息
    task_id: str = Field(..., description="任务 ID")
    task_title: str = Field(default="", description="任务标题")
    task_description: str = Field(default="", description="任务描述")

    # 输入输出
    input_data: dict[str, Any] = Field(default_factory=dict, description="输入数据")
    output_data: dict[str, Any] = Field(default_factory=dict, description="输出数据")

    # 消息历史
    messages: list[dict[str, str]] = Field(default_factory=list, description="消息历史")

    # 当前步骤
    current_step: str = Field(default="start", description="当前步骤")

    # Agent 执行结果
    agent_results: dict[str, Any] = Field(default_factory=dict, description="Agent 执行结果")

    # 错误信息
    error: str | None = Field(default=None, description="错误信息")

    # 控制标志
    should_continue: bool = Field(default=True, description="是否继续")
    retry_count: int = Field(default=0, description="重试次数")

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def add_message(self, role: str, content: str) -> None:
        """添加消息"""
        self.messages.append({"role": role, "content": content})

    def add_agent_result(self, agent_name: str, result: Any) -> None:
        """添加 Agent 执行结果"""
        self.agent_results[agent_name] = result

    def has_error(self) -> bool:
        """检查是否有错误"""
        return self.error is not None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return self.dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentState":
        """从字典创建"""
        return cls(**data)


class WorkflowState(BaseModel):
    """
    工作流级别的状态

    用于管理多个并行或顺序的任务
    """

    # 工作流信息
    workflow_id: str = Field(..., description="工作流 ID")
    workflow_name: str = Field(default="", description="工作流名称")

    # 任务状态列表
    task_states: list[AgentState] = Field(default_factory=list, description="任务状态列表")

    # 当前活跃任务
    active_task_id: str | None = Field(default=None, description="当前活跃任务 ID")

    # 工作流状态
    status: str = Field(default="running", description="工作流状态")

    # 结果汇总
    results: dict[str, Any] = Field(default_factory=dict, description="结果汇总")

    def add_task_state(self, state: AgentState) -> None:
        """添加任务状态"""
        self.task_states.append(state)

    def get_task_state(self, task_id: str) -> AgentState | None:
        """获取任务状态"""
        for state in self.task_states:
            if state.task_id == task_id:
                return state
        return None

    def update_task_state(self, task_id: str, state: AgentState) -> None:
        """更新任务状态"""
        for i, s in enumerate(self.task_states):
            if s.task_id == task_id:
                self.task_states[i] = state
                return
        self.task_states.append(state)
