"""
Agent 测试

测试 Agent 相关功能
"""

import pytest
from datetime import datetime

from src.core.models import (
    Agent,
    AgentRole,
    AgentState,
    Task,
    TaskStatus,
)
from src.agents.base import BaseAgent
from src.agents.planner import PlannerAgent
from src.agents.coder import CoderAgent


# ===========================================
# Agent 模型测试
# ===========================================

class TestAgentModel:
    """测试 Agent 数据模型"""
    
    def test_agent_creation(self):
        """测试 Agent 创建"""
        agent = Agent(
            name="TestAgent",
            role=AgentRole.CODER,
        )
        
        assert agent.name == "TestAgent"
        assert agent.role == AgentRole.CODER
        assert agent.state == AgentState.IDLE
        assert agent.enabled is True
        assert agent.id is not None
    
    def test_agent_is_available(self):
        """测试 Agent 可用性检查"""
        agent = Agent(
            name="TestAgent",
            role=AgentRole.CODER,
            state=AgentState.IDLE,
            enabled=True,
        )
        
        assert agent.is_available() is True
        
        # 忙碌状态
        agent.state = AgentState.BUSY
        assert agent.is_available() is False
        
        # 禁用状态
        agent.enabled = False
        agent.state = AgentState.IDLE
        assert agent.is_available() is False
    
    def test_agent_assign_task(self):
        """测试 Agent 分配任务"""
        agent = Agent(
            name="TestAgent",
            role=AgentRole.CODER,
        )
        
        task_id = "task-001"
        agent.assign_task(task_id)
        
        assert agent.current_task_id == task_id
        assert agent.state == AgentState.BUSY
    
    def test_agent_complete_task(self):
        """测试 Agent 完成任务"""
        agent = Agent(
            name="TestAgent",
            role=AgentRole.CODER,
        )
        
        # 分配任务
        agent.assign_task("task-001")
        
        # 完成任务
        agent.complete_task(success=True, execution_time=10.5)
        
        assert agent.current_task_id is None
        assert agent.state == AgentState.IDLE
        assert agent.tasks_completed == 1
    
    def test_agent_statistics(self):
        """测试 Agent 统计"""
        agent = Agent(
            name="TestAgent",
            role=AgentRole.CODER,
        )
        
        # 模拟完成任务
        agent.complete_task(success=True, execution_time=10.0)
        agent.complete_task(success=True, execution_time=20.0)
        agent.complete_task(success=False, execution_time=5.0)
        
        stats = agent.get_statistics()
        
        assert stats["tasks_completed"] == 2
        assert stats["tasks_failed"] == 1
        assert "success_rate" in stats


# ===========================================
# PlannerAgent 测试
# ===========================================

class TestPlannerAgent:
    """测试 PlannerAgent"""
    
    @pytest.mark.asyncio
    async def test_planner_creation(self):
        """测试 PlannerAgent 创建"""
        agent = PlannerAgent(name="TestPlanner")
        
        assert agent.agent.name == "TestPlanner"
        assert agent.ROLE == AgentRole.PLANNER
        assert agent.is_available() is True
    
    @pytest.mark.asyncio
    async def test_planner_execute(self, sample_task):
        """测试 PlannerAgent 执行"""
        agent = PlannerAgent()
        
        # 设置任务输入
        sample_task.input_data = {
            "goal": "创建一个简单的 API 接口",
            "context": {},
        }
        
        # 执行任务
        result = await agent.execute(sample_task)
        
        assert result["status"] == "planning_complete"
        assert "subtasks" in result
        assert len(result["subtasks"]) > 0
    
    @pytest.mark.asyncio
    async def test_planner_think(self):
        """测试 PlannerAgent 思考"""
        agent = PlannerAgent()
        
        context = {
            "goal": "构建一个 Web 应用",
            "constraints": ["使用 Python", "使用 FastAPI"],
        }
        
        result = await agent.think(context)
        
        assert "subtasks" in result
        assert isinstance(result["subtasks"], list)


# ===========================================
# CoderAgent 测试
# ===========================================

class TestCoderAgent:
    """测试 CoderAgent"""
    
    @pytest.mark.asyncio
    async def test_coder_creation(self):
        """测试 CoderAgent 创建"""
        agent = CoderAgent(name="TestCoder")
        
        assert agent.agent.name == "TestCoder"
        assert agent.ROLE == AgentRole.CODER
    
    @pytest.mark.asyncio
    async def test_coder_execute(self, sample_task):
        """测试 CoderAgent 执行"""
        agent = CoderAgent()
        
        # 设置任务输入
        sample_task.input_data = {
            "requirements": "创建一个 Hello World 函数",
            "architecture": {},
        }
        
        # 执行任务
        result = await agent.execute(sample_task)
        
        assert result["status"] == "coding_complete"
        assert "code_files" in result


# ===========================================
# Task 模型测试
# ===========================================

class TestTaskModel:
    """测试 Task 数据模型"""
    
    def test_task_creation(self):
        """测试任务创建"""
        task = Task(
            title="Test Task",
            description="A test task",
        )
        
        assert task.title == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.id is not None
    
    def test_task_lifecycle(self):
        """测试任务生命周期"""
        task = Task(title="Test Task")
        
        # 开始任务
        task.start()
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None
        
        # 完成任务
        task.complete(output_data={"result": "success"})
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.output_data == {"result": "success"}
    
    def test_task_fail(self):
        """测试任务失败"""
        task = Task(title="Test Task")
        task.start()
        
        task.fail(error_message="Test error")
        
        assert task.status == TaskStatus.FAILED
        assert task.error_message == "Test error"
    
    def test_task_retry(self):
        """测试任务重试"""
        task = Task(title="Test Task")
        task.start()
        task.fail(error_message="Test error")
        
        # 重试
        task.retry()
        
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 1
        assert task.error_message is None
    
    def test_task_is_terminal(self):
        """测试终端状态检查"""
        task = Task(title="Test Task")
        
        assert task.is_terminal() is False
        
        task.complete()
        assert task.is_terminal() is True
