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

    def test_agent_role_get_agent_class(self):
        """测试 AgentRole 到 Agent 类的映射"""
        # 测试所有角色的映射
        assert AgentRole.get_agent_class(AgentRole.PLANNER).__name__ == "PlannerAgent"
        assert AgentRole.get_agent_class(AgentRole.ARCHITECT).__name__ == "ArchitectAgent"
        assert AgentRole.get_agent_class(AgentRole.CODER).__name__ == "CoderAgent"
        assert AgentRole.get_agent_class(AgentRole.TESTER).__name__ == "TesterAgent"
        assert AgentRole.get_agent_class(AgentRole.DOC_WRITER).__name__ == "DocWriterAgent"
        assert AgentRole.get_agent_class(AgentRole.RESEARCHER).__name__ == "ResearchAgent"
        assert AgentRole.get_agent_class(AgentRole.SENIOR_ARCHITECT).__name__ == "SeniorArchitectAgent"

    def test_agent_role_get_all_roles(self):
        """测试获取所有角色列表"""
        roles = AgentRole.get_all_roles()
        assert len(roles) == 7
        assert AgentRole.PLANNER in roles
        assert AgentRole.ARCHITECT in roles
        assert AgentRole.CODER in roles
        assert AgentRole.TESTER in roles
        assert AgentRole.DOC_WRITER in roles
        assert AgentRole.RESEARCHER in roles
        assert AgentRole.SENIOR_ARCHITECT in roles

    def test_agent_role_from_string(self):
        """测试从字符串创建角色枚举"""
        assert AgentRole.from_string("planner") == AgentRole.PLANNER
        assert AgentRole.from_string("PLANNER") == AgentRole.PLANNER  # 大小写不敏感
        assert AgentRole.from_string("Architect") == AgentRole.ARCHITECT
        assert AgentRole.from_string("invalid_role") is None
