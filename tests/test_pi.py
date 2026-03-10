"""
Pi 系统测试

测试智能 Agent 协作系统的核心功能
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pi.agent_manager import AgentManager, get_agent_manager
from src.pi.communication import (
    CommunicationHub,
    EventBus,
    MessageBus,
    get_communication_hub,
)
from src.pi.result_aggregator import (
    ConflictResolver,
    ResultAggregator,
    ResultEvaluator,
    get_result_aggregator,
)
from src.pi.task_scheduler import TaskScheduler, get_task_scheduler
from src.pi.types import (
    AgentCapability,
    MessageType,
    PiAgentConfig,
    PiAgentInfo,
    PiAgentStatus,
    PiMessage,
    PiTaskConfig,
    PiTaskInfo,
    PiTaskPriority,
    PiTaskStatus,
    TaskAssignmentStrategy,
)


# ===========================================
# Fixtures
# ===========================================


@pytest.fixture
def agent_manager():
    """创建 Agent 管理器"""
    manager = AgentManager()
    yield manager
    # 清理
    manager._agents.clear()


@pytest.fixture
def task_scheduler(agent_manager):
    """创建任务调度器"""
    scheduler = TaskScheduler(agent_manager=agent_manager)
    yield scheduler
    # 清理
    scheduler._tasks.clear()
    scheduler._pending_queue.clear()


@pytest.fixture
def event_bus():
    """创建事件总线"""
    return EventBus()


@pytest.fixture
def message_bus():
    """创建消息总线"""
    return MessageBus()


@pytest.fixture
def communication_hub():
    """创建通信中心"""
    return CommunicationHub()


@pytest.fixture
def result_evaluator():
    """创建结果评估器"""
    return ResultEvaluator()


@pytest.fixture
def conflict_resolver():
    """创建冲突解决器"""
    return ConflictResolver()


@pytest.fixture
def result_aggregator():
    """创建结果聚合器"""
    return ResultAggregator()


@pytest.fixture
def sample_agent_config():
    """示例 Agent 配置"""
    return PiAgentConfig(
        name="TestAgent",
        role="coder",
        capabilities=["code_generation", "testing"],
        max_concurrent_tasks=3,
        timeout_seconds=300,
    )


@pytest.fixture
def sample_task_config():
    """示例任务配置"""
    return PiTaskConfig(
        title="Test Task",
        description="A test task",
        priority=PiTaskPriority.NORMAL,
        required_capabilities=["code_generation"],
        input_data={"requirements": "Write a function"},
    )


# ===========================================
# Types Tests
# ===========================================


class TestTypes:
    """类型定义测试"""

    def test_pi_agent_status_values(self):
        """测试 Agent 状态枚举值"""
        assert PiAgentStatus.IDLE.value == "idle"
        assert PiAgentStatus.BUSY.value == "busy"
        assert PiAgentStatus.ERROR.value == "error"
        assert PiAgentStatus.OFFLINE.value == "offline"
        assert PiAgentStatus.INITIALIZING.value == "initializing"

    def test_pi_task_status_values(self):
        """测试任务状态枚举值"""
        assert PiTaskStatus.PENDING.value == "pending"
        assert PiTaskStatus.QUEUED.value == "queued"
        assert PiTaskStatus.ASSIGNED.value == "assigned"
        assert PiTaskStatus.COMPLETED.value == "completed"
        assert PiTaskStatus.FAILED.value == "failed"

    def test_pi_task_priority_values(self):
        """测试任务优先级枚举值"""
        assert PiTaskPriority.LOW.value == "low"
        assert PiTaskPriority.NORMAL.value == "normal"
        assert PiTaskPriority.HIGH.value == "high"
        assert PiTaskPriority.CRITICAL.value == "critical"

    def test_pi_agent_info_is_available(self):
        """测试 Agent 可用性检查"""
        agent = PiAgentInfo(
            name="TestAgent",
            role="coder",
            status=PiAgentStatus.IDLE,
        )
        assert agent.is_available() is True

        agent.status = PiAgentStatus.BUSY
        assert agent.is_available() is False

    def test_pi_agent_info_get_load(self):
        """测试 Agent 负载计算"""
        agent = PiAgentInfo(
            name="TestAgent",
            role="coder",
            status=PiAgentStatus.IDLE,
            max_concurrent_tasks=3,
        )
        assert agent.get_load() == 0.0

        agent.current_tasks = ["task-1"]
        assert agent.get_load() == 1 / 3

        agent.current_tasks = ["task-1", "task-2", "task-3"]
        assert agent.get_load() == 1.0

    def test_pi_task_info_is_high_priority(self):
        """测试任务高优先级检查"""
        task = PiTaskInfo(
            title="Test Task",
            priority=PiTaskPriority.NORMAL,
        )
        assert task.is_high_priority() is False

        task.priority = PiTaskPriority.HIGH
        assert task.is_high_priority() is True

        task.priority = PiTaskPriority.CRITICAL
        assert task.is_high_priority() is True


# ===========================================
# AgentManager Tests
# ===========================================


class TestAgentManager:
    """Agent 管理器测试"""

    @pytest.mark.asyncio
    async def test_create_agent(self, agent_manager, sample_agent_config):
        """测试创建 Agent"""
        agent = await agent_manager.create_agent(sample_agent_config)

        assert agent.id is not None
        assert agent.name == sample_agent_config.name
        assert agent.role == sample_agent_config.role
        assert agent.capabilities == sample_agent_config.capabilities
        assert agent.status == PiAgentStatus.IDLE

    @pytest.mark.asyncio
    async def test_create_agent_without_name(self, agent_manager):
        """测试创建没有名称的 Agent"""
        config = PiAgentConfig(name="", role="coder")
        with pytest.raises(ValueError, match="name is required"):
            await agent_manager.create_agent(config)

    @pytest.mark.asyncio
    async def test_start_agent(self, agent_manager, sample_agent_config):
        """测试启动 Agent"""
        agent = await agent_manager.create_agent(sample_agent_config)

        success = await agent_manager.start_agent(agent.id)
        assert success is True

        agent_info = agent_manager.get_agent(agent.id)
        assert agent_info.status == PiAgentStatus.IDLE

    @pytest.mark.asyncio
    async def test_stop_agent(self, agent_manager, sample_agent_config):
        """测试停止 Agent"""
        agent = await agent_manager.create_agent(sample_agent_config)
        await agent_manager.start_agent(agent.id)

        success = await agent_manager.stop_agent(agent.id)
        assert success is True

        agent_info = agent_manager.get_agent(agent.id)
        assert agent_info.status == PiAgentStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_destroy_agent(self, agent_manager, sample_agent_config):
        """测试销毁 Agent"""
        agent = await agent_manager.create_agent(sample_agent_config)

        success = await agent_manager.destroy_agent(agent.id)
        assert success is True

        assert agent_manager.get_agent(agent.id) is None

    @pytest.mark.asyncio
    async def test_set_agent_busy(self, agent_manager, sample_agent_config):
        """测试设置 Agent 忙碌状态"""
        agent = await agent_manager.create_agent(sample_agent_config)

        success = agent_manager.set_agent_busy(agent.id, "task-1")
        assert success is True

        agent_info = agent_manager.get_agent(agent.id)
        assert agent_info.status == PiAgentStatus.BUSY
        assert "task-1" in agent_info.current_tasks

    @pytest.mark.asyncio
    async def test_set_agent_idle(self, agent_manager, sample_agent_config):
        """测试设置 Agent 空闲状态"""
        agent = await agent_manager.create_agent(sample_agent_config)
        agent_manager.set_agent_busy(agent.id, "task-1")

        success = agent_manager.set_agent_idle(agent.id, "task-1")
        assert success is True

        agent_info = agent_manager.get_agent(agent.id)
        assert agent_info.status == PiAgentStatus.IDLE
        assert "task-1" not in agent_info.current_tasks

    @pytest.mark.asyncio
    async def test_list_agents(self, agent_manager):
        """测试列出 Agents"""
        config1 = PiAgentConfig(name="Agent1", role="coder")
        config2 = PiAgentConfig(name="Agent2", role="tester")

        await agent_manager.create_agent(config1)
        await agent_manager.create_agent(config2)

        agents = agent_manager.list_agents()
        assert len(agents) == 2

        # 按角色过滤
        coders = agent_manager.list_agents(role="coder")
        assert len(coders) == 1

    @pytest.mark.asyncio
    async def test_get_available_agents(self, agent_manager):
        """测试获取可用 Agents"""
        config = PiAgentConfig(
            name="TestAgent",
            role="coder",
            capabilities=["code_generation", "testing"],
        )
        agent = await agent_manager.create_agent(config)

        # 初始状态可用
        available = agent_manager.get_available_agents()
        assert len(available) == 1

        # 设置忙碌
        agent_manager.set_agent_busy(agent.id, "task-1")
        available = agent_manager.get_available_agents()
        assert len(available) == 0

    @pytest.mark.asyncio
    async def test_get_available_agents_with_capabilities(self, agent_manager):
        """测试按能力获取可用 Agents"""
        config1 = PiAgentConfig(
            name="Agent1",
            role="coder",
            capabilities=["code_generation"],
        )
        config2 = PiAgentConfig(
            name="Agent2",
            role="tester",
            capabilities=["testing"],
        )

        await agent_manager.create_agent(config1)
        await agent_manager.create_agent(config2)

        # 按能力过滤
        available = agent_manager.get_available_agents(
            capabilities=["code_generation"]
        )
        assert len(available) == 1
        assert available[0].name == "Agent1"


# ===========================================
# TaskScheduler Tests
# ===========================================


class TestTaskScheduler:
    """任务调度器测试"""

    @pytest.mark.asyncio
    async def test_submit_task(self, task_scheduler, sample_task_config):
        """测试提交任务"""
        task = await task_scheduler.submit_task(sample_task_config)

        assert task.id is not None
        assert task.title == sample_task_config.title
        assert task.status == PiTaskStatus.QUEUED
        assert task.priority == sample_task_config.priority

    @pytest.mark.asyncio
    async def test_cancel_task(self, task_scheduler, sample_task_config):
        """测试取消任务"""
        task = await task_scheduler.submit_task(sample_task_config)

        success = await task_scheduler.cancel_task(task.id)
        assert success is True

        task_info = task_scheduler.get_task(task.id)
        assert task_info.status == PiTaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_assign_task(self, task_scheduler, agent_manager, sample_task_config, sample_agent_config):
        """测试分配任务"""
        # 创建 Agent
        agent = await agent_manager.create_agent(sample_agent_config)
        await agent_manager.start_agent(agent.id)

        # 提交任务
        task = await task_scheduler.submit_task(sample_task_config)

        # 分配任务
        assignment = await task_scheduler.assign_task(task.id)

        assert assignment is not None
        assert assignment.task_id == task.id
        assert assignment.agent_id == agent.id

    @pytest.mark.asyncio
    async def test_assign_task_no_available_agent(self, task_scheduler, agent_manager, sample_task_config):
        """测试无可用 Agent 时分配任务"""
        # 提交任务（不创建 Agent）
        task = await task_scheduler.submit_task(sample_task_config)

        # 尝试分配
        assignment = await task_scheduler.assign_task(task.id)
        assert assignment is None

    @pytest.mark.asyncio
    async def test_complete_task(self, task_scheduler, agent_manager, sample_task_config, sample_agent_config):
        """测试完成任务"""
        # 创建 Agent 和任务
        agent = await agent_manager.create_agent(sample_agent_config)
        task = await task_scheduler.submit_task(sample_task_config)
        await task_scheduler.assign_task(task.id)

        # 开始并完成任务
        await task_scheduler.start_task(task.id)
        success = await task_scheduler.complete_task(
            task.id,
            {"output": "done"},
            success=True
        )

        assert success is True

        task_info = task_scheduler.get_task(task.id)
        assert task_info.status == PiTaskStatus.COMPLETED
        assert task_info.output_data == {"output": "done"}

    @pytest.mark.asyncio
    async def test_fail_task_with_retry(self, task_scheduler, sample_task_config):
        """测试任务失败重试"""
        task = await task_scheduler.submit_task(sample_task_config)

        # 第一次失败
        await task_scheduler.fail_task(task.id, "Error 1")
        task_info = task_scheduler.get_task(task.id)
        assert task_info.status == PiTaskStatus.PENDING
        assert task_info.retry_count == 1

    @pytest.mark.asyncio
    async def test_fail_task_max_retries(self, task_scheduler):
        """测试任务超过最大重试次数"""
        config = PiTaskConfig(
            title="Test Task",
            max_retries=2,
        )
        task = await task_scheduler.submit_task(config)

        # 多次失败
        await task_scheduler.fail_task(task.id, "Error 1")
        await task_scheduler.fail_task(task.id, "Error 2")
        await task_scheduler.fail_task(task.id, "Error 3")

        task_info = task_scheduler.get_task(task.id)
        assert task_info.status == PiTaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_get_stats(self, task_scheduler, sample_task_config):
        """测试获取统计信息"""
        await task_scheduler.submit_task(sample_task_config)

        stats = task_scheduler.get_stats()
        assert stats["total_submitted"] == 1
        assert stats["pending_tasks"] == 1


# ===========================================
# EventBus Tests
# ===========================================


class TestEventBus:
    """事件总线测试"""

    def test_subscribe(self, event_bus):
        """测试订阅事件"""
        def callback():
            pass
        event_bus.subscribe("test_event", callback)

        assert "test_event" in event_bus._subscribers
        assert callback in event_bus._subscribers["test_event"]

    def test_unsubscribe(self, event_bus):
        """测试取消订阅"""
        def callback():
            pass
        event_bus.subscribe("test_event", callback)

        success = event_bus.unsubscribe("test_event", callback)
        assert success is True
        assert callback not in event_bus._subscribers["test_event"]

    @pytest.mark.asyncio
    async def test_publish(self, event_bus):
        """测试发布事件"""
        callback = AsyncMock()
        event_bus.subscribe("test_event", callback)

        await event_bus.publish("test_event", {"data": "test"})

        callback.assert_called_once()
        message = callback.call_args[0][0]
        assert message.subject == "test_event"
        assert message.content == {"data": "test"}

    @pytest.mark.asyncio
    async def test_publish_to_multiple_subscribers(self, event_bus):
        """测试发布到多个订阅者"""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        event_bus.subscribe("test_event", callback1)
        event_bus.subscribe("test_event", callback2)

        await event_bus.publish("test_event", {"data": "test"})

        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_get_history(self, event_bus):
        """测试获取历史消息"""
        import asyncio

        # 发布一些事件
        asyncio.run(event_bus.publish("event1", {"data": 1}))
        asyncio.run(event_bus.publish("event2", {"data": 2}))
        asyncio.run(event_bus.publish("event1", {"data": 3}))

        # 获取历史
        history = event_bus.get_history()
        assert len(history) == 3

        # 按类型过滤
        history = event_bus.get_history(event_type="event1")
        assert len(history) == 2


# ===========================================
# MessageBus Tests
# ===========================================


class TestMessageBus:
    """消息总线测试"""

    def test_register_agent(self, message_bus):
        """测试注册 Agent"""
        success = message_bus.register_agent("agent-1")
        assert success is True
        assert "agent-1" in message_bus._agent_queues

    def test_unregister_agent(self, message_bus):
        """测试注销 Agent"""
        message_bus.register_agent("agent-1")
        success = message_bus.unregister_agent("agent-1")
        assert success is True
        assert "agent-1" not in message_bus._agent_queues

    @pytest.mark.asyncio
    async def test_send_to(self, message_bus):
        """测试发送点对点消息"""
        message_bus.register_agent("agent-1")

        message = PiMessage(
            sender_id="agent-2",
            receiver_id="agent-1",
            subject="test",
            content={"data": "test"},
        )

        success = await message_bus.send_to("agent-1", message)
        assert success is True

        # 接收消息
        received = await message_bus.receive("agent-1", timeout=0.1)
        assert received is not None
        assert received.subject == "test"

    @pytest.mark.asyncio
    async def test_broadcast(self, message_bus):
        """测试广播消息"""
        message_bus.register_agent("agent-1")
        message_bus.register_agent("agent-2")
        message_bus.register_agent("agent-3")

        message = PiMessage(
            sender_id="agent-0",
            subject="broadcast",
            content={"data": "test"},
        )

        sent_count = await message_bus.broadcast(message)
        assert sent_count == 3

    @pytest.mark.asyncio
    async def test_broadcast_with_exclude(self, message_bus):
        """测试广播消息（排除部分）"""
        message_bus.register_agent("agent-1")
        message_bus.register_agent("agent-2")
        message_bus.register_agent("agent-3")

        message = PiMessage(
            sender_id="agent-0",
            subject="broadcast",
            content={"data": "test"},
        )

        sent_count = await message_bus.broadcast(message, exclude_ids=["agent-1"])
        assert sent_count == 2


# ===========================================
# CommunicationHub Tests
# ===========================================


class TestCommunicationHub:
    """通信中心测试"""

    def test_register_agent(self, communication_hub):
        """测试注册 Agent"""
        success = communication_hub.register_agent("agent-1")
        assert success is True

    @pytest.mark.asyncio
    async def test_send_message(self, communication_hub):
        """测试发送消息"""
        communication_hub.register_agent("agent-1")
        communication_hub.register_agent("agent-2")

        success = await communication_hub.send_message(
            "agent-1",
            "agent-2",
            "test",
            {"data": "test"},
        )
        assert success is True

    @pytest.mark.asyncio
    async def test_broadcast(self, communication_hub):
        """测试广播"""
        communication_hub.register_agent("agent-1")
        communication_hub.register_agent("agent-2")

        sent_count = await communication_hub.broadcast(
            "agent-1",
            "announcement",
            {"data": "test"},
        )
        assert sent_count == 2

    def test_get_stats(self, communication_hub):
        """测试获取统计信息"""
        communication_hub.register_agent("agent-1")

        stats = communication_hub.get_stats()
        assert stats["registered_agents"] == 1


# ===========================================
# ResultEvaluator Tests
# ===========================================


class TestResultEvaluator:
    """结果评估器测试"""

    @pytest.mark.asyncio
    async def test_evaluate_good_result(self, result_evaluator):
        """测试评估好的结果"""
        task = PiTaskInfo(title="Test Task")
        result = {
            "status": "success",
            "output": {"data": "test result"},
        }

        evaluation = await result_evaluator.evaluate(task, result, "agent-1")

        assert evaluation.task_id == task.id
        assert evaluation.agent_id == "agent-1"
        assert evaluation.quality_score > 50
        assert len(evaluation.issues) == 0

    @pytest.mark.asyncio
    async def test_evaluate_empty_result(self, result_evaluator):
        """测试评估空结果"""
        task = PiTaskInfo(title="Test Task")
        result = {}

        evaluation = await result_evaluator.evaluate(task, result, "agent-1")

        assert evaluation.quality_score < 50
        assert len(evaluation.issues) > 0

    @pytest.mark.asyncio
    async def test_evaluate_error_result(self, result_evaluator):
        """测试评估错误结果"""
        task = PiTaskInfo(title="Test Task")
        result = {
            "status": "error",
            "error": "Something went wrong",
        }

        evaluation = await result_evaluator.evaluate(task, result, "agent-1")

        assert "Error" in str(evaluation.issues)


# ===========================================
# ConflictResolver Tests
# ===========================================


class TestConflictResolver:
    """冲突解决器测试"""

    @pytest.mark.asyncio
    async def test_resolve_by_majority(self, conflict_resolver):
        """测试多数投票解决"""
        results = [
            {"status": "success", "data": 1},
            {"status": "success", "data": 1},
            {"status": "success", "data": 2},
        ]

        resolution = await conflict_resolver.resolve(
            "task-1",
            results,
            strategy="majority",
        )

        assert resolution.task_id == "task-1"
        assert resolution.resolution_strategy == "majority"
        assert resolution.final_result["data"] == 1

    @pytest.mark.asyncio
    async def test_resolve_by_quality(self, conflict_resolver):
        """测试质量优先解决"""
        results = [
            {"status": "error", "error": "failed"},
            {"status": "success", "output": "good result"},
        ]

        resolution = await conflict_resolver.resolve(
            "task-1",
            results,
            strategy="best_quality",
        )

        assert resolution.final_result["status"] == "success"

    @pytest.mark.asyncio
    async def test_resolve_by_merge(self, conflict_resolver):
        """测试合并解决"""
        results = [
            {"status": "success", "data1": "value1"},
            {"status": "success", "data2": "value2"},
        ]

        resolution = await conflict_resolver.resolve(
            "task-1",
            results,
            strategy="merge",
        )

        assert "data1" in resolution.final_result
        assert "data2" in resolution.final_result


# ===========================================
# ResultAggregator Tests
# ===========================================


class TestResultAggregator:
    """结果聚合器测试"""

    def test_collect(self, result_aggregator):
        """测试收集结果"""
        result_aggregator.collect("task-1", "agent-1", {"output": "result1"})
        result_aggregator.collect("task-1", "agent-2", {"output": "result2"})

        results = result_aggregator.get_collected_results("task-1")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_aggregate_single_result(self, result_aggregator):
        """测试聚合单个结果"""
        result_aggregator.collect("task-1", "agent-1", {"output": "result"})

        task = PiTaskInfo(id="task-1", title="Test")
        final = await result_aggregator.aggregate(task)

        assert final["output"] == "result"

    @pytest.mark.asyncio
    async def test_aggregate_multiple_results(self, result_aggregator):
        """测试聚合多个结果"""
        result_aggregator.collect("task-1", "agent-1", {"output": "result1"})
        result_aggregator.collect("task-1", "agent-2", {"output": "result2"})

        task = PiTaskInfo(id="task-1", title="Test")
        final = await result_aggregator.aggregate(task, strategy="best_quality")

        assert "_aggregation" in final
        assert final["_aggregation"]["total_results"] == 2

    def test_get_stats(self, result_aggregator):
        """测试获取统计信息"""
        result_aggregator.collect("task-1", "agent-1", {"output": "result"})

        stats = result_aggregator.get_stats()
        assert stats["total_tasks"] == 1
        assert stats["total_results"] == 1


# ===========================================
# Integration Tests
# ===========================================


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流"""
        # 1. 创建管理器
        agent_manager = AgentManager()
        task_scheduler = TaskScheduler(agent_manager=agent_manager)
        result_aggregator = ResultAggregator()

        # 2. 创建 Agent
        agent_config = PiAgentConfig(
            name="TestAgent",
            role="coder",
            capabilities=["code_generation"],
        )
        agent = await agent_manager.create_agent(agent_config)
        await agent_manager.start_agent(agent.id)

        # 3. 提交任务
        task_config = PiTaskConfig(
            title="Write a function",
            required_capabilities=["code_generation"],
        )
        task = await task_scheduler.submit_task(task_config)

        # 4. 分配任务
        assignment = await task_scheduler.assign_task(task.id)
        assert assignment is not None

        # 5. 执行任务
        await task_scheduler.start_task(task.id)
        result = {"output": "def hello(): pass"}
        await task_scheduler.complete_task(task.id, result, success=True)

        # 6. 收集和评估结果
        result_aggregator.collect(task.id, agent.id, result)
        final = await result_aggregator.aggregate(task)

        assert "output" in final

        # 7. 清理
        await agent_manager.destroy_agent(agent.id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])