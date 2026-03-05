"""核心模型测试"""

from src.core.models import (
    Agent,
    AgentRole,
    AgentState,
    Task,
    TaskPriority,
    TaskStatus,
    WorkflowStatus,
)


class TestModels:
    """模型测试类"""

    def test_agent_role_values(self):
        """测试 Agent 枚举值"""
        assert AgentRole.PLANNER.value == "planner"
        assert AgentRole.CODER.value == "coder"
        assert AgentRole.TESTER.value == "tester"
        assert AgentRole.ARCHITECT.value == "architect"
        assert AgentRole.DOC_WRITER.value == "doc_writer"

    def test_task_priority_values(self):
        """测试任务优先级枚举"""
        assert TaskPriority.LOW.value == "low"
        assert TaskPriority.NORMAL.value == "normal"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.CRITICAL.value == "critical"

    def test_task_status_values(self):
        """测试任务状态枚举"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_agent_state_values(self):
        """测试 Agent 状态枚举"""
        assert AgentState.IDLE.value == "idle"
        assert AgentState.BUSY.value == "busy"
        assert AgentState.ERROR.value == "error"
        assert AgentState.OFFLINE.value == "offline"

    def test_workflow_status_values(self):
        """测试工作流状态枚举"""
        assert WorkflowStatus.CREATED.value == "created"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.COMPLETED.value == "completed"

    def test_agent_creation(self):
        """测试 Agent 创建"""
        agent = Agent(
            name="测试 Agent",
            role=AgentRole.CODER,
        )
        assert agent.name == "测试 Agent"
        assert agent.role == AgentRole.CODER
        assert agent.state == AgentState.IDLE
        assert agent.enabled is True

    def test_agent_is_available(self):
        """测试 Agent 可用性"""
        agent = Agent(name="测试 Agent", role=AgentRole.CODER)
        assert agent.is_available() is True

        agent.state = AgentState.BUSY
        assert agent.is_available() is False

    def test_agent_assign_task(self):
        """测试 Agent 分配任务"""
        agent = Agent(name="测试 Agent", role=AgentRole.CODER)
        agent.assign_task("task-123")
        assert agent.current_task_id == "task-123"
        assert agent.state == AgentState.BUSY

    def test_agent_complete_task(self):
        """测试 Agent 完成任务"""
        agent = Agent(name="测试 Agent", role=AgentRole.CODER)
        agent.assign_task("task-123")
        agent.complete_task(success=True, execution_time=10.0)
        assert agent.tasks_completed == 1
        assert agent.state == AgentState.IDLE
        assert agent.current_task_id is None

    def test_task_creation(self):
        """测试任务创建"""
        task = Task(
            title="测试任务",
            description="这是一个测试任务",
            priority=TaskPriority.HIGH,
        )
        assert task.title == "测试任务"
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.PENDING

    def test_task_with_input_data(self):
        """测试带输入数据的任务"""
        task = Task(
            title="数据处理",
            description="处理输入数据",
            input_data={"key": "value", "count": 100},
        )
        assert task.input_data["key"] == "value"
        assert task.input_data["count"] == 100

    def test_task_output_data(self):
        """测试任务输出数据"""
        task = Task(
            title="输出测试",
            output_data={"result": "success", "score": 95},
        )
        assert task.output_data["result"] == "success"
        assert task.output_data["score"] == 95

    def test_agent_statistics(self):
        """测试 Agent 统计"""
        agent = Agent(name="测试 Agent", role=AgentRole.CODER)
        stats = agent.get_statistics()
        assert "tasks_completed" in stats
        assert "tasks_failed" in stats
        assert "avg_execution_time" in stats
