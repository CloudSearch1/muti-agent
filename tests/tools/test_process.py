"""
Process 工具单元测试

测试 ProcessTool 的所有动作。
"""

import pytest
import asyncio

from src.tools.builtin.process import (
    ProcessListRequest,
    ProcessListResponse,
    ProcessLogRequest,
    ProcessPollRequest,
    ProcessSessionInfo,
    ProcessTool,
    create_process_tool,
)
from src.tools.base import ToolResult


class TestProcessTool:
    """Process 工具测试"""

    def test_create_process_tool(self):
        """测试创建工具实例"""
        tool = create_process_tool(agent_id="test-agent")
        assert tool.NAME == "process"
        assert tool.agent_id == "test-agent"
        assert len(tool.ACTIONS) == 7

    def test_parameters(self):
        """测试参数定义"""
        tool = ProcessTool(agent_id="test-agent")
        params = tool.parameters

        # 检查必需参数
        action_param = next(p for p in params if p.name == "action")
        assert action_param.required is True
        assert action_param.enum == tool.ACTIONS

    def test_missing_action(self):
        """测试缺少 action 参数"""
        tool = ProcessTool(agent_id="test-agent")
        result = asyncio.run(tool(session_id="test"))

        assert result.success is False
        assert "action" in str(result.error).lower()

    def test_invalid_action(self):
        """测试无效的 action"""
        tool = ProcessTool(agent_id="test-agent")
        result = asyncio.run(tool(action="invalid"))

        assert result.success is False
        assert "Invalid action" in str(result.error) or "must be one of" in str(result.error)

    def test_missing_session_id(self):
        """测试缺少 session_id"""
        tool = ProcessTool(agent_id="test-agent")
        result = asyncio.run(tool(action="poll"))

        assert result.success is False
        assert "session_id" in str(result.error).lower()


class TestProcessModels:
    """Process 数据模型测试"""

    def test_list_request_defaults(self):
        """测试 list 请求默认值"""
        req = ProcessListRequest()
        assert req.cursor is None
        assert req.limit == 20

    def test_poll_request_defaults(self):
        """测试 poll 请求默认值"""
        req = ProcessPollRequest(session_id="test-123")
        assert req.session_id == "test-123"
        assert req.wait_ms == 1000

    def test_log_request_defaults(self):
        """测试 log 请求默认值"""
        req = ProcessLogRequest(session_id="test-123")
        assert req.stream == "stdout"
        assert req.offset == 0
        assert req.max_bytes == 65536


class TestProcessSessionInfo:
    """会话信息模型测试"""

    def test_session_info_creation(self):
        """测试创建会话信息"""
        from datetime import datetime

        info = ProcessSessionInfo(
            session_id="sess-123",
            agent_id="agent-001",
            status="running",
            command="ls -la",
            cwd="/home/user",
            created_at=datetime.now(),
        )

        assert info.session_id == "sess-123"
        assert info.agent_id == "agent-001"
        assert info.status == "running"
        assert info.command == "ls -la"
        assert info.exit_code is None
