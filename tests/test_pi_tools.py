"""
PI-Python Tools 测试

测试 AgentTool 和内置工具
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pi_python.agent.tools import (
    AgentTool,
    BashTool,
    ReadFileTool,
    WriteFileTool,
    HTTPTool,
    ToolResult,
    tool,
    BUILTIN_TOOLS,
)
from pi_python.ai import TextContent


# ===========================================
# ToolResult Tests
# ===========================================


class TestToolResult:
    """ToolResult 测试"""

    def test_init_with_string(self):
        """测试用字符串初始化"""
        result = ToolResult(content="Test content")

        assert len(result.content) == 1
        assert isinstance(result.content[0], TextContent)
        assert result.content[0].text == "Test content"
        assert result.details == {}

    def test_init_with_list(self):
        """测试用列表初始化"""
        content = [TextContent(text="Test")]
        result = ToolResult(content=content)

        assert result.content == content

    def test_init_with_details(self):
        """测试带详情初始化"""
        result = ToolResult(content="Test", details={"key": "value"})

        assert result.details == {"key": "value"}

    def test_text_classmethod(self):
        """测试 text 类方法"""
        result = ToolResult.text("Test", key="value")

        assert len(result.content) == 1
        assert result.content[0].text == "Test"
        assert result.details == {"key": "value"}

    def test_error_classmethod(self):
        """测试 error 类方法"""
        result = ToolResult.error("Something went wrong")

        assert "Error:" in result.content[0].text
        assert result.details.get("error") is True


# ===========================================
# tool Decorator Tests
# ===========================================


class TestToolDecorator:
    """tool 装饰器测试"""

    @pytest.mark.asyncio
    async def test_tool_decorator_string_return(self):
        """测试返回字符串的工具"""
        @tool("greet", "Greet someone", {"name": {"type": "string"}})
        async def greet(tool_call_id, params, **kwargs):
            return f"Hello, {params['name']}!"

        assert greet.name == "greet"
        assert greet.description == "Greet someone"

        result = await greet.execute("call-1", {"name": "World"})

        assert isinstance(result, ToolResult)
        assert "Hello, World!" in result.content[0].text

    @pytest.mark.asyncio
    async def test_tool_decorator_tool_result_return(self):
        """测试返回 ToolResult 的工具"""
        @tool("calc", "Calculate", {"x": {"type": "integer"}})
        async def calc(tool_call_id, params, **kwargs):
            return ToolResult.text(f"Result: {params['x'] * 2}")

        result = await calc.execute("call-1", {"x": 5})

        assert "Result: 10" in result.content[0].text

    @pytest.mark.asyncio
    async def test_tool_decorator_to_tool(self):
        """测试 to_tool 方法"""
        @tool("test", "Test tool", {"arg": {"type": "string", "description": "A string arg"}})
        async def test_tool(tool_call_id, params, **kwargs):
            return "ok"

        tool_def = test_tool.to_tool()

        assert tool_def.name == "test"
        assert tool_def.description == "Test tool"
        assert "arg" in tool_def.parameters

    @pytest.mark.asyncio
    async def test_tool_decorator_other_return_type(self):
        """测试返回其他类型的工具（非字符串、非 ToolResult）"""
        @tool("dict_tool", "Returns a dict", {})
        async def dict_tool(tool_call_id, params, **kwargs):
            return {"result": "value"}  # 返回字典而非字符串

        result = await dict_tool.execute("call-1", {})

        # 应该转换为字符串
        assert isinstance(result, ToolResult)
        assert "result" in result.content[0].text or "value" in result.content[0].text

    @pytest.mark.asyncio
    async def test_tool_decorator_with_enum_parameter(self):
        """测试带 enum 参数的工具"""
        @tool("select", "Select option", {
            "option": {"type": "string", "enum": ["a", "b", "c"]}
        })
        async def select_tool(tool_call_id, params, **kwargs):
            return f"Selected: {params.get('option')}"

        tool_def = select_tool.to_tool()
        assert tool_def.parameters["option"].enum == ["a", "b", "c"]


# ===========================================
# BashTool Tests
# ===========================================


class TestBashTool:
    """BashTool 测试"""

    def test_properties(self):
        """测试属性"""
        bash_tool = BashTool()

        assert bash_tool.name == "bash"
        assert bash_tool.label == "Bash"
        assert "command" in bash_tool.parameters
        assert "command" in bash_tool.required

    def test_to_tool(self):
        """测试 to_tool 方法"""
        bash_tool = BashTool()

        tool_def = bash_tool.to_tool()

        assert tool_def.name == "bash"
        assert "command" in tool_def.parameters

    @pytest.mark.asyncio
    async def test_execute_simple_command(self):
        """测试执行简单命令"""
        bash_tool = BashTool()

        result = await bash_tool.execute("call-1", {"command": "echo 'Hello'"})

        assert "Hello" in result.content[0].text
        assert result.details.get("exit_code") == 0

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """测试带超时的命令"""
        bash_tool = BashTool()

        result = await bash_tool.execute("call-1", {"command": "sleep 0.1", "timeout": 5})

        assert result.details.get("exit_code") == 0

    @pytest.mark.asyncio
    async def test_execute_error_command(self):
        """测试错误命令"""
        bash_tool = BashTool()

        result = await bash_tool.execute("call-1", {"command": "ls /nonexistent_directory_12345"})

        # 命令执行但返回非零退出码
        assert result.details.get("exit_code") != 0 or result.details.get("error")

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """测试命令超时"""
        bash_tool = BashTool()

        # 使用非常短的超时时间
        result = await bash_tool.execute("call-1", {"command": "sleep 10", "timeout": 0.1})

        # 应该返回超时错误
        assert result.details.get("error") is True

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        """测试命令执行异常"""
        bash_tool = BashTool()

        # 模拟异常
        with patch("asyncio.create_subprocess_shell", side_effect=OSError("Mock error")):
            result = await bash_tool.execute("call-1", {"command": "echo test"})

            assert result.details.get("error") is True


# ===========================================
# ReadFileTool Tests
# ===========================================


class TestReadFileTool:
    """ReadFileTool 测试"""

    def test_properties(self):
        """测试属性"""
        tool = ReadFileTool()

        assert tool.name == "read_file"
        assert "path" in tool.parameters
        assert "path" in tool.required

    def test_to_tool(self):
        """测试 to_tool 方法"""
        tool = ReadFileTool()

        tool_def = tool.to_tool()

        assert tool_def.name == "read_file"
        assert "path" in tool_def.parameters

    @pytest.mark.asyncio
    async def test_read_file(self):
        """测试读取文件"""
        tool = ReadFileTool()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            # 使用 importlib 在函数内部 mock
            import importlib
            import pi_python.agent.tools as tools_module

            # 创建 mock aiofiles
            mock_aiofiles = MagicMock()
            mock_file = AsyncMock()
            mock_file.read = AsyncMock(return_value="Test content")
            mock_file.__aenter__ = AsyncMock(return_value=mock_file)
            mock_file.__aexit__ = AsyncMock(return_value=None)
            mock_aiofiles.open = MagicMock(return_value=mock_file)

            # 临时替换模块的导入
            with patch.dict('sys.modules', {'aiofiles': mock_aiofiles}):
                # 重新加载模块以使用 mock
                importlib.reload(tools_module)
                tool = tools_module.ReadFileTool()

                result = await tool.execute("call-1", {"path": temp_path})

                assert "Test content" in result.content[0].text

            # 恢复原始模块
            importlib.reload(tools_module)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """测试读取不存在的文件"""
        tool = ReadFileTool()

        import importlib
        import pi_python.agent.tools as tools_module

        mock_aiofiles = MagicMock()
        mock_aiofiles.open = MagicMock(side_effect=FileNotFoundError("File not found"))

        with patch.dict('sys.modules', {'aiofiles': mock_aiofiles}):
            importlib.reload(tools_module)
            tool = tools_module.ReadFileTool()

            result = await tool.execute("call-1", {"path": "/nonexistent/file.txt"})

            assert result.details.get("error") is True

        importlib.reload(tools_module)

    @pytest.mark.asyncio
    async def test_read_file_general_exception(self):
        """测试读取文件时的一般异常"""
        import importlib
        import pi_python.agent.tools as tools_module

        mock_aiofiles = MagicMock()
        mock_aiofiles.open = MagicMock(side_effect=PermissionError("Permission denied"))

        with patch.dict('sys.modules', {'aiofiles': mock_aiofiles}):
            importlib.reload(tools_module)
            tool = tools_module.ReadFileTool()

            result = await tool.execute("call-1", {"path": "/some/file.txt"})

            assert result.details.get("error") is True

        importlib.reload(tools_module)


# ===========================================
# WriteFileTool Tests
# ===========================================


class TestWriteFileTool:
    """WriteFileTool 测试"""

    def test_properties(self):
        """测试属性"""
        tool = WriteFileTool()

        assert tool.name == "write_file"
        assert "path" in tool.parameters
        assert "content" in tool.parameters
        assert "path" in tool.required
        assert "content" in tool.required

    def test_to_tool(self):
        """测试 to_tool 方法"""
        tool = WriteFileTool()

        tool_def = tool.to_tool()

        assert tool_def.name == "write_file"
        assert "path" in tool_def.parameters

    @pytest.mark.asyncio
    async def test_write_file(self):
        """测试写入文件"""
        tool = WriteFileTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "test.txt"

            import importlib
            import pi_python.agent.tools as tools_module

            mock_aiofiles = MagicMock()
            mock_file = AsyncMock()
            mock_file.write = AsyncMock()
            mock_file.__aenter__ = AsyncMock(return_value=mock_file)
            mock_file.__aexit__ = AsyncMock(return_value=None)
            mock_aiofiles.open = MagicMock(return_value=mock_file)

            with patch.dict('sys.modules', {'aiofiles': mock_aiofiles}):
                importlib.reload(tools_module)
                tool = tools_module.WriteFileTool()

                result = await tool.execute("call-1", {"path": str(temp_path), "content": "Hello World"})

                assert "Successfully" in result.content[0].text

            importlib.reload(tools_module)

    @pytest.mark.asyncio
    async def test_write_file_exception(self):
        """测试写入文件异常"""
        import importlib
        import pi_python.agent.tools as tools_module

        mock_aiofiles = MagicMock()
        mock_aiofiles.open = MagicMock(side_effect=PermissionError("Permission denied"))

        with patch.dict('sys.modules', {'aiofiles': mock_aiofiles}):
            importlib.reload(tools_module)
            tool = tools_module.WriteFileTool()

            result = await tool.execute("call-1", {"path": "/root/test.txt", "content": "test"})

            assert result.details.get("error") is True

        importlib.reload(tools_module)


# ===========================================
# HTTPTool Tests
# ===========================================


class TestHTTPTool:
    """HTTPTool 测试"""

    def test_properties(self):
        """测试属性"""
        tool = HTTPTool()

        assert tool.name == "http_request"
        assert "url" in tool.parameters
        assert "method" in tool.parameters
        assert "url" in tool.required

    @pytest.mark.asyncio
    async def test_http_get(self):
        """测试 HTTP GET 请求"""
        tool = HTTPTool()

        # 使用 httpbin 测试服务
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.text = '{"status": "ok"}'
            mock_response.status_code = 200

            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_context.request = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            result = await tool.execute("call-1", {"url": "https://httpbin.org/get"})

            assert result.details.get("status_code") == 200

    @pytest.mark.asyncio
    async def test_http_with_method(self):
        """测试带方法的 HTTP 请求"""
        tool = HTTPTool()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.text = "Created"
            mock_response.status_code = 201

            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_context.request = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            result = await tool.execute("call-1", {
                "url": "https://httpbin.org/post",
                "method": "POST",
                "body": '{"data": "test"}'
            })

            assert result.details.get("status_code") == 201

    @pytest.mark.asyncio
    async def test_http_exception(self):
        """测试 HTTP 请求异常"""
        tool = HTTPTool()

        with patch("httpx.AsyncClient") as mock_client:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_context.request = AsyncMock(side_effect=Exception("Connection error"))
            mock_client.return_value = mock_context

            result = await tool.execute("call-1", {"url": "https://invalid.url"})

            assert result.details.get("error") is True


# ===========================================
# BUILTIN_TOOLS Tests
# ===========================================


class TestBuiltinTools:
    """内置工具测试"""

    def test_builtin_tools_list(self):
        """测试内置工具列表"""
        assert len(BUILTIN_TOOLS) == 4

        names = [t.name for t in BUILTIN_TOOLS]
        assert "bash" in names
        assert "read_file" in names
        assert "write_file" in names
        assert "http_request" in names

    def test_all_tools_have_names(self):
        """测试所有工具都有名称"""
        for t in BUILTIN_TOOLS:
            assert t.name
            assert t.label
            assert t.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])