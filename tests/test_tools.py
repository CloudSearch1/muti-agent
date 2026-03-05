"""
工具测试

测试工具系统相关功能
"""

import pytest

from src.tools.base import BaseTool, ToolParameter, ToolResult
from src.tools.code_tools import CodeTools
from src.tools.registry import ToolRegistry, get_registry
from src.tools.test_tools import TestTools

# ===========================================
# BaseTool 测试
# ===========================================


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
        assert result.error is None

    def test_tool_result_failure(self):
        """测试工具失败结果"""
        result = ToolResult(
            success=False,
            error="Test error",
        )

        assert result.success is False
        assert result.error == "Test error"
        assert result.data is None


# ===========================================
# ToolRegistry 测试
# ===========================================


class TestToolRegistry:
    """测试工具注册中心"""

    def test_registry_creation(self):
        """测试注册中心创建"""
        registry = ToolRegistry()

        assert registry.tools == {}
        assert registry.enabled is True

    def test_registry_register(self):
        """测试工具注册"""
        registry = ToolRegistry()

        # 创建测试工具
        class TestTool(BaseTool):
            NAME = "test_tool"
            DESCRIPTION = "Test tool"

            @property
            def parameters(self):
                return []

            async def execute(self, **kwargs):
                return ToolResult(success=True, data={})

        tool = TestTool()
        result = registry.register(tool)

        assert result is True
        assert "test_tool" in registry.tools

    def test_registry_get(self):
        """测试获取工具"""
        registry = ToolRegistry()

        class TestTool(BaseTool):
            NAME = "test_tool"
            DESCRIPTION = "Test tool"

            @property
            def parameters(self):
                return []

            async def execute(self, **kwargs):
                return ToolResult(success=True, data={})

        tool = TestTool()
        registry.register(tool)

        retrieved = registry.get("test_tool")

        assert retrieved is not None
        assert retrieved.NAME == "test_tool"

    def test_registry_list_tools(self):
        """测试列出工具"""
        registry = ToolRegistry()

        # 注册两个工具
        class Tool1(BaseTool):
            NAME = "tool1"
            DESCRIPTION = "Tool 1"

            @property
            def parameters(self):
                return []

            async def execute(self, **kwargs):
                return ToolResult(success=True)

        class Tool2(BaseTool):
            NAME = "tool2"
            DESCRIPTION = "Tool 2"

            @property
            def parameters(self):
                return []

            async def execute(self, **kwargs):
                return ToolResult(success=True)

        registry.register(Tool1())
        registry.register(Tool2())

        tools = registry.list_tools()

        assert len(tools) == 2
        assert any(t["name"] == "tool1" for t in tools)
        assert any(t["name"] == "tool2" for t in tools)

    @pytest.mark.asyncio
    async def test_registry_execute(self):
        """测试执行工具"""
        registry = ToolRegistry()

        class TestTool(BaseTool):
            NAME = "test_tool"
            DESCRIPTION = "Test tool"

            @property
            def parameters(self):
                return [
                    ToolParameter(
                        name="input",
                        description="Input value",
                        type="string",
                        required=True,
                    )
                ]

            async def execute(self, **kwargs):
                return ToolResult(
                    success=True,
                    data={"echo": kwargs.get("input")},
                )

        registry.register(TestTool())

        result = await registry.execute("test_tool", input="hello")

        assert result.success is True
        assert result.data["echo"] == "hello"


# ===========================================
# CodeTools 测试
# ===========================================


class TestCodeTools:
    """测试代码工具"""

    def test_code_tools_creation(self):
        """测试代码工具创建"""
        tools = CodeTools()

        assert tools.NAME == "code_tools"
        assert tools.enabled is True

    def test_code_tools_parameters(self):
        """测试代码工具参数"""
        tools = CodeTools()

        params = tools.parameters

        assert len(params) == 4

        # 检查 action 参数
        action_param = next(p for p in params if p.name == "action")
        assert action_param.required is True
        assert action_param.enum == ["format", "analyze", "convert", "generate"]

    @pytest.mark.asyncio
    async def test_code_tools_format(self):
        """测试代码格式化"""
        tools = CodeTools()

        code = "def hello( ): print('hello')"

        result = await tools.execute(
            action="format",
            code=code,
            language="python",
        )

        assert result.success is True
        assert "formatted_code" in result.data

    @pytest.mark.asyncio
    async def test_code_tools_analyze(self):
        """测试代码分析"""
        tools = CodeTools()

        code = """
def hello():
    print('hello')

class MyClass:
    pass
"""

        result = await tools.execute(
            action="analyze",
            code=code,
            language="python",
        )

        assert result.success is True
        assert "lines_of_code" in result.data


# ===========================================
# TestTools 测试
# ===========================================


class TestTestTools:
    """测试测试工具"""

    def test_test_tools_creation(self):
        """测试测试工具创建"""
        tools = TestTools()

        assert tools.NAME == "test_tools"
        assert tools.test_framework == "pytest"

    @pytest.mark.asyncio
    async def test_test_tools_run(self):
        """测试运行测试"""
        tools = TestTools()

        result = await tools.execute(
            action="run",
            test_path="tests",
            options={"verbose": False},
        )

        # 由于是模拟实现，应该返回成功
        assert result.success is True


# ===========================================
# 全局注册中心测试
# ===========================================


class TestGlobalRegistry:
    """测试全局注册中心函数"""

    def test_get_registry_singleton(self):
        """测试注册中心单例"""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_register_tool_convenience(self):
        """测试便捷注册函数"""
        from src.tools.registry import register_tool

        class TestTool(BaseTool):
            NAME = "convenience_test"
            DESCRIPTION = "Test"

            @property
            def parameters(self):
                return []

            async def execute(self, **kwargs):
                return ToolResult(success=True)

        result = register_tool(TestTool())

        assert result is True
        assert get_registry().has_tool("convenience_test")
