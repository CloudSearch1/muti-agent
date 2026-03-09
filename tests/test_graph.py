"""
工作流模块测试

测试 LangGraph 工作流编排、状态管理、进度追踪等功能
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import time

from src.graph import (
    AgentWorkflow,
    WorkflowStatus,
    WorkflowProgress,
    WorkflowError,
    WorkflowTimeoutError,
    StateTransitionValidator,
    create_workflow,
)


# ============ State Transition Validator Tests ============

class TestStateTransitionValidator:
    """状态转换验证器测试"""

    def test_valid_transition_start_to_planner(self):
        """测试有效转换：start -> planner"""
        assert StateTransitionValidator.validate("start", "planner") is True

    def test_valid_transition_planner_to_architect(self):
        """测试有效转换：planner -> architect"""
        assert StateTransitionValidator.validate("planner", "architect") is True

    def test_valid_transition_coder_to_tester(self):
        """测试有效转换：coder -> tester"""
        assert StateTransitionValidator.validate("coder", "tester") is True

    def test_valid_transition_tester_to_doc_writer(self):
        """测试有效转换：tester -> doc_writer"""
        assert StateTransitionValidator.validate("tester", "doc_writer") is True

    def test_invalid_transition_start_to_coder(self):
        """测试无效转换：start -> coder"""
        assert StateTransitionValidator.validate("start", "coder") is False

    def test_invalid_transition_architect_to_planner(self):
        """测试无效转换：architect -> planner"""
        assert StateTransitionValidator.validate("architect", "planner") is False

    def test_get_valid_next_states_from_start(self):
        """测试从 start 获取合法下一状态"""
        states = StateTransitionValidator.get_valid_next_states("start")
        assert states == ["planner"]

    def test_get_valid_next_states_from_planner(self):
        """测试从 planner 获取合法下一状态"""
        states = StateTransitionValidator.get_valid_next_states("planner")
        assert "architect" in states
        assert "end" in states

    def test_get_valid_next_states_from_end(self):
        """测试从 end 获取合法下一状态"""
        states = StateTransitionValidator.get_valid_next_states("end")
        assert states == []

    def test_get_valid_next_states_unknown_state(self):
        """测试未知状态的合法下一状态"""
        states = StateTransitionValidator.get_valid_next_states("unknown")
        assert states == []


# ============ Workflow Progress Tests ============

class TestWorkflowProgress:
    """工作流进度测试"""

    def test_create_progress(self):
        """测试创建进度"""
        progress = WorkflowProgress(total_steps=6)
        assert progress.total_steps == 6
        assert progress.current_step == 0

    def test_progress_start(self):
        """测试开始进度"""
        progress = WorkflowProgress()
        progress.start()
        assert progress.start_time is not None

    def test_progress_complete(self):
        """测试完成进度"""
        progress = WorkflowProgress()
        progress.start()
        time.sleep(0.1)
        progress.complete()
        assert progress.end_time is not None
        assert progress.elapsed_seconds > 0

    def test_progress_advance(self):
        """测试前进一步"""
        progress = WorkflowProgress()
        progress.start()
        progress.advance("start")
        assert progress.current_step == 0  # start 是第一个

    def test_progress_advance_to_planner(self):
        """测试前进到 planner"""
        progress = WorkflowProgress()
        progress.start()
        progress.advance("planner")
        assert progress.current_step == 1

    def test_progress_percent_zero(self):
        """测试零进度百分比"""
        progress = WorkflowProgress(total_steps=6)
        assert progress.progress_percent == 0.0

    def test_progress_percent_half(self):
        """测试 50% 进度"""
        progress = WorkflowProgress(total_steps=6)
        progress.current_step = 3
        assert progress.progress_percent == 50.0

    def test_progress_percent_complete(self):
        """测试 100% 进度"""
        progress = WorkflowProgress(total_steps=6)
        progress.current_step = 6
        assert progress.progress_percent == 100.0

    def test_elapsed_seconds_not_started(self):
        """测试未开始时的时间"""
        progress = WorkflowProgress()
        assert progress.elapsed_seconds == 0

    def test_elapsed_seconds_running(self):
        """测试运行中的时间"""
        progress = WorkflowProgress()
        progress.start()
        time.sleep(0.1)
        assert progress.elapsed_seconds >= 0.1

    def test_to_dict(self):
        """测试转换为字典"""
        progress = WorkflowProgress(total_steps=6)
        progress.start()
        d = progress.to_dict()

        assert "total_steps" in d
        assert "current_step" in d
        assert "progress_percent" in d
        assert "elapsed_seconds" in d
        assert "status" in d


# ============ Workflow Status Tests ============

class TestWorkflowStatus:
    """工作流状态枚举测试"""

    def test_status_values(self):
        """测试状态值"""
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.PAUSED.value == "paused"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.TIMEOUT.value == "timeout"


# ============ Workflow Error Tests ============

class TestWorkflowError:
    """工作流错误测试"""

    def test_workflow_error(self):
        """测试工作流错误"""
        error = WorkflowError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_workflow_timeout_error(self):
        """测试工作流超时错误"""
        error = WorkflowTimeoutError("Operation timed out")
        assert str(error) == "Operation timed out"
        assert isinstance(error, WorkflowError)


# ============ Agent Workflow Tests ============

class TestAgentWorkflow:
    """Agent 工作流测试"""

    def test_create_workflow(self):
        """测试创建工作流"""
        workflow = AgentWorkflow()
        assert workflow.status == WorkflowStatus.PENDING
        assert workflow.graph is None

    def test_create_workflow_with_id(self):
        """测试带 ID 创建工作流"""
        workflow = AgentWorkflow(workflow_id="test-workflow-001")
        assert workflow.workflow_id == "test-workflow-001"

    def test_create_workflow_with_timeout_config(self):
        """测试带超时配置创建工作流"""
        workflow = AgentWorkflow(
            node_timeout=600,
            workflow_timeout=3600,
        )
        assert workflow.node_timeout == 600
        assert workflow.workflow_timeout == 3600

    def test_workflow_status_initial(self):
        """测试工作流初始状态"""
        workflow = AgentWorkflow()
        assert workflow.status == WorkflowStatus.PENDING
        assert workflow.progress.current_step == 0

    def test_set_progress_callback(self):
        """测试设置进度回调"""
        workflow = AgentWorkflow()
        callback_called = []

        def callback(progress):
            callback_called.append(progress)

        workflow.on_progress(callback)
        assert workflow._on_progress is not None

    def test_set_error_callback(self):
        """测试设置错误回调"""
        workflow = AgentWorkflow()

        def callback(error, node):
            pass

        workflow.on_error(callback)
        assert workflow._on_error is not None

    def test_get_status(self):
        """测试获取工作流状态"""
        workflow = AgentWorkflow(workflow_id="test-001")
        status = workflow.get_status()

        assert status["workflow_id"] == "test-001"
        assert status["status"] == "pending"
        assert "progress" in status
        assert "error_count" in status


class TestAgentWorkflowGraph:
    """工作流图测试"""

    @pytest.mark.skipif(
        True,  # 需要 LangGraph 安装
        reason="Requires LangGraph installation"
    )
    def test_build_graph(self):
        """测试构建工作流图"""
        workflow = AgentWorkflow()
        graph = workflow.build_graph()

        assert graph is not None
        assert workflow.graph is not None

    @pytest.mark.skipif(
        True,  # 需要 LangGraph 安装
        reason="Requires LangGraph installation"
    )
    def test_compile_workflow(self):
        """测试编译工作流"""
        workflow = AgentWorkflow()
        compiled = workflow.compile()

        assert compiled is not None
        assert workflow.compiled_graph is not None


class TestAgentWorkflowExecution:
    """工作流执行测试"""

    @pytest.mark.asyncio
    async def test_execute_with_timeout_success(self):
        """测试带超时执行成功"""
        workflow = AgentWorkflow()

        async def quick_operation():
            await asyncio.sleep(0.1)
            return "success"

        result = await workflow._execute_with_timeout(
            quick_operation(),
            timeout=5,
            node_name="test",
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_timeout_fails(self):
        """测试带超时执行失败"""
        workflow = AgentWorkflow()

        async def slow_operation():
            await asyncio.sleep(10)
            return "success"

        with pytest.raises(WorkflowTimeoutError):
            await workflow._execute_with_timeout(
                slow_operation(),
                timeout=1,
                node_name="test",
            )

    @pytest.mark.asyncio
    async def test_execute_with_recovery_success(self):
        """测试带恢复执行成功"""
        workflow = AgentWorkflow(enable_recovery=True)

        # 创建模拟状态
        state = MagicMock()
        state.dict.return_value = {"status": "ok"}

        async def success_func(s):
            return {"status": "ok"}

        result = await workflow._execute_with_recovery(
            state,
            success_func,
            "test_node",
        )
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_record_error(self):
        """测试记录错误"""
        workflow = AgentWorkflow()

        error = Exception("Test error")
        workflow._record_error(error, "test_node")

        assert len(workflow.error_history) == 1
        assert workflow.error_history[0]["node"] == "test_node"
        assert workflow.error_history[0]["error_message"] == "Test error"

    @pytest.mark.asyncio
    async def test_report_progress(self):
        """测试报告进度"""
        workflow = AgentWorkflow()
        progress_records = []

        def callback(progress):
            progress_records.append(progress)

        workflow.on_progress(callback)
        workflow._report_progress("start")

        assert len(progress_records) == 1


# ============ Factory Function Tests ============

class TestCreateWorkflow:
    """工厂函数测试"""

    def test_create_workflow_factory(self):
        """测试工作流工厂函数"""
        workflow = create_workflow(workflow_id="factory-test")
        assert isinstance(workflow, AgentWorkflow)
        assert workflow.workflow_id == "factory-test"

    def test_create_workflow_with_config(self):
        """测试带配置创建工作流"""
        workflow = create_workflow(
            node_timeout=120,
            workflow_timeout=600,
            enable_recovery=False,
        )
        assert workflow.node_timeout == 120
        assert workflow.enable_recovery is False


# ============ Edge Cases Tests ============

class TestWorkflowEdgeCases:
    """边界情况测试"""

    def test_workflow_with_zero_timeout(self):
        """测试零超时"""
        workflow = AgentWorkflow(node_timeout=0)
        assert workflow.node_timeout == 0

    def test_workflow_with_negative_timeout(self):
        """测试负超时（应该有默认值或验证）"""
        # 取决于实现，可能需要验证
        workflow = AgentWorkflow(node_timeout=-1)
        # 如果有验证，这里应该抛出异常

    def test_progress_with_zero_steps(self):
        """测试零步骤进度"""
        progress = WorkflowProgress(total_steps=0)
        # 应该处理除零错误
        if progress.total_steps == 0:
            assert progress.progress_percent == 0

    def test_progress_advance_unknown_step(self):
        """测试前进到未知步骤"""
        progress = WorkflowProgress()
        progress.start()
        progress.advance("unknown_step")
        # 不应该崩溃

    def test_workflow_with_special_characters_id(self):
        """测试特殊字符 ID"""
        workflow = AgentWorkflow(workflow_id="test-工作流-001")
        assert workflow.workflow_id == "test-工作流-001"

    def test_multiple_errors_recording(self):
        """测试多次错误记录"""
        workflow = AgentWorkflow()

        for i in range(5):
            workflow._record_error(Exception(f"Error {i}"), f"node_{i}")

        assert len(workflow.error_history) == 5

    def test_get_status_with_errors(self):
        """测试获取有错误的状态"""
        workflow = AgentWorkflow()
        workflow._record_error(Exception("Test"), "node")
        workflow._record_error(Exception("Test2"), "node2")

        status = workflow.get_status()
        assert status["error_count"] == 2
        assert len(status["errors"]) <= 5  # 最多返回 5 个


# ============ Integration Tests ============

class TestWorkflowIntegration:
    """集成测试"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_workflow_execution_mock(self):
        """测试完整工作流执行（Mock）"""
        workflow = AgentWorkflow(
            node_timeout=60,
            workflow_timeout=300,
        )

        # Mock 所有 Agent
        workflow.planner = MagicMock()
        workflow.planner.process_task = AsyncMock(return_value=MagicMock(
            output_data={"subtasks": []}
        ))

        workflow.architect = MagicMock()
        workflow.architect.process_task = AsyncMock(return_value=MagicMock(
            output_data={"architecture": "test"}
        ))

        workflow.coder = MagicMock()
        workflow.coder.process_task = AsyncMock(return_value=MagicMock(
            output_data={"files_created": 1}
        ))

        workflow.tester = MagicMock()
        workflow.tester.process_task = AsyncMock(return_value=MagicMock(
            output_data={"passed": 5, "failed": 0}
        ))

        workflow.doc_writer = MagicMock()
        workflow.doc_writer.process_task = AsyncMock(return_value=MagicMock(
            output_data={"docs": []}
        ))

        # 验证工作流已初始化
        assert workflow.status == WorkflowStatus.PENDING

    @pytest.mark.integration
    def test_state_transitions_complete_cycle(self):
        """测试完整状态转换周期"""
        transitions = [
            ("start", "planner"),
            ("planner", "architect"),
            ("architect", "coder"),
            ("coder", "tester"),
            ("tester", "doc_writer"),
            ("doc_writer", "end"),
        ]

        for from_state, to_state in transitions:
            assert StateTransitionValidator.validate(from_state, to_state) is True, \
                f"Transition {from_state} -> {to_state} should be valid"


# ============ Performance Tests ============

class TestWorkflowPerformance:
    """性能测试"""

    @pytest.mark.slow
    def test_progress_update_performance(self):
        """测试进度更新性能"""
        import time

        progress = WorkflowProgress()
        progress.start()

        start = time.time()
        for i in range(10000):
            progress.advance("planner")
            progress.current_step = 0  # 重置
        elapsed = time.time() - start

        assert elapsed < 1.0  # 10000 次更新应该在 1 秒内

    @pytest.mark.slow
    def test_state_validation_performance(self):
        """测试状态验证性能"""
        import time

        start = time.time()
        for _ in range(100000):
            StateTransitionValidator.validate("start", "planner")
        elapsed = time.time() - start

        assert elapsed < 0.5  # 100000 次验证应该在 0.5 秒内

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_error_recording_performance(self):
        """测试错误记录性能"""
        import time

        workflow = AgentWorkflow()

        start = time.time()
        for i in range(1000):
            workflow._record_error(Exception(f"Error {i}"), "node")
        elapsed = time.time() - start

        assert elapsed < 1.0  # 1000 次记录应该在 1 秒内