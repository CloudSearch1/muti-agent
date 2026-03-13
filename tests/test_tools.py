"""
工具测试

测试工具系统相关功能
"""

import pytest

from src.tools.base import BaseTool, ToolParameter, ToolResult
from src.tools.code_tools import CodeTools
from src.tools.registry import ToolRegistry, get_registry
from src.tools.test_tools import TestingTools


class TestBaseTool:
    """测试工具基类"""

    def test_tool_result_creation(self):
        """测试工具结果创建"""
        result = ToolResult(
            success=True,
            data={"key": "value"},
        )

        assert result.success is True
        assert result.data == {"key": "value"}

    def test_tool_result_failure(self):
        """测试工具失败结果"""
        result = ToolResult(
            success=False,
            error="Test error",
        )

        assert result.success is False
        assert "Test error" in str(result.error)
        assert result.data is None


class TestToolRegistry:
    """测试工具注册中心"""

    def test_registry_creation(self):
        """测试注册中心创建"""
        registry = ToolRegistry()
        assert registry is not None
        assert len(registry.tools) == 0

    def test_registry_register(self):
        """测试注册工具"""
        registry = ToolRegistry()
        tool = CodeTools()
        registry.register(tool)
        assert tool.NAME in registry.tools

    def test_registry_get(self):
        """测试获取工具"""
        registry = ToolRegistry()
        tool = CodeTools()
        registry.register(tool)
        retrieved = registry.get(tool.NAME)
        assert retrieved is tool

    def test_registry_list_tools(self):
        """测试列出工具"""
        registry = ToolRegistry()
        tool = CodeTools()
        registry.register(tool)
        tools = registry.list_tools()
        assert len(tools) > 0

    def test_registry_execute(self):
        """测试执行工具"""
        registry = ToolRegistry()
        tool = CodeTools()
        registry.register(tool)
        assert hasattr(registry, 'execute')


class TestCodeTools:
    """测试代码工具"""

    def test_code_tools_creation(self):
        """测试代码工具创建"""
        tool = CodeTools()
        assert tool.NAME == "code_tools"

    def test_code_tools_parameters(self):
        """测试代码工具参数"""
        tool = CodeTools()
        params = tool.parameters
        assert len(params) > 0


class TestTestTools:
    """测试测试工具"""

    def test_test_tools_creation(self):
        """测试测试工具创建"""
        tool = TestingTools()
        assert tool.NAME == "testing_tools"


class TestGlobalRegistry:
    """测试全局注册表"""

    def test_get_registry_singleton(self):
        """测试注册表单例"""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_register_tool_convenience(self):
        """测试便捷注册"""
        from src.tools import register_tool
        tool = CodeTools()
        assert callable(register_tool)
