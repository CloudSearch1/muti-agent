"""异常模块测试"""
import pytest
from src.core.exceptions import (
    IntelliTeamError,
    AgentError,
    AgentNotFoundError,
    AgentTimeoutError,
    AgentExecutionError,
    TaskError,
    TaskNotFoundError,
    TaskValidationError,
    TaskExecutionError,
    WorkflowError,
    ToolError,
    ToolNotFoundError,
    ToolExecutionError,
    ConfigurationError,
)


class TestExceptions:
    """异常测试类"""

    def test_intelliteam_error_creation(self):
        """测试基础异常创建"""
        error = IntelliTeamError("测试错误")
        assert str(error) == "测试错误"
        assert error.code == "UNKNOWN_ERROR"

    def test_intelliteam_error_to_dict(self):
        """测试异常转换为字典"""
        error = IntelliTeamError("测试错误", code="TEST_ERROR", details={"key": "value"})
        result = error.to_dict()
        assert result["error"] == "TEST_ERROR"
        assert result["message"] == "测试错误"
        assert result["details"]["key"] == "value"

    def test_agent_not_found_error(self):
        """测试 Agent 不存在错误"""
        error = AgentNotFoundError("test-agent")
        assert "test-agent" in str(error)
        assert error.code == "AGENT_NOT_FOUND"

    def test_agent_timeout_error(self):
        """测试 Agent 超时错误"""
        error = AgentTimeoutError("test-agent", 30)
        assert "test-agent" in str(error)
        assert "30" in str(error)
        assert error.code == "AGENT_TIMEOUT"

    def test_agent_execution_error(self):
        """测试 Agent 执行错误"""
        error = AgentExecutionError("test-agent", "执行失败")
        assert "test-agent" in str(error)
        assert "执行失败" in str(error)

    def test_task_not_found_error(self):
        """测试任务不存在错误"""
        error = TaskNotFoundError("task-123")
        assert "task-123" in str(error)
        assert error.code == "TASK_NOT_FOUND"

    def test_task_validation_error(self):
        """测试任务验证错误"""
        error = TaskValidationError("task-123", ["字段不能为空", "格式错误"])
        assert "task-123" in str(error)
        assert error.code == "TASK_VALIDATION_ERROR"

    def test_task_execution_error(self):
        """测试任务执行错误"""
        error = TaskExecutionError("task-123", "执行失败")
        assert "task-123" in str(error)
        assert "执行失败" in str(error)

    def test_tool_not_found_error(self):
        """测试工具不存在错误"""
        error = ToolNotFoundError("test-tool")
        assert "test-tool" in str(error)
        assert error.code == "TOOL_NOT_FOUND"

    def test_configuration_error(self):
        """测试配置错误"""
        error = ConfigurationError("DATABASE_URL", "无效的 URL")
        assert "DATABASE_URL" in str(error)
        assert error.code == "CONFIGURATION_ERROR"

    def test_exception_inheritance(self):
        """测试异常继承关系"""
        assert issubclass(AgentError, IntelliTeamError)
        assert issubclass(TaskError, IntelliTeamError)
        assert issubclass(WorkflowError, IntelliTeamError)
        assert issubclass(ToolError, IntelliTeamError)

    def test_raise_agent_error(self):
        """测试抛出 Agent 错误"""
        with pytest.raises(AgentError):
            raise AgentNotFoundError("test-agent")

    def test_raise_task_error(self):
        """测试抛出任务错误"""
        with pytest.raises(TaskError):
            raise TaskNotFoundError("task-123")
