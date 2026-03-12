"""
PI-Python 扩展测试

测试 extensions 模块的扩展加载和 API 注册
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from pi_python.extensions.loader import ExtensionLoader, create_builtin_extensions
from pi_python.extensions.api import ExtensionAPI, ExtensionContext
from pi_python.agent import Agent


def create_mock_agent() -> Agent:
    """创建模拟 Agent"""
    agent = MagicMock(spec=Agent)
    agent.add_tool = MagicMock()
    return agent


def create_mock_context() -> ExtensionContext:
    """创建模拟上下文"""
    return ExtensionContext(
        ui=MagicMock(),
        agent=MagicMock(),
        session=MagicMock()
    )


class TestExtensionLoader:
    """扩展加载器测试"""

    def test_loader_creation(self, tmp_path: Path):
        """测试加载器创建"""
        loader = ExtensionLoader(tmp_path)
        assert loader.extensions_dir == tmp_path
        assert loader._loaded == {}

    def test_discover_no_directory(self, tmp_path: Path):
        """测试发现扩展 - 目录不存在"""
        non_existent = tmp_path / "non_existent"
        loader = ExtensionLoader(non_existent)

        files = loader.discover()
        assert files == []

    def test_discover_empty_directory(self, tmp_path: Path):
        """测试发现扩展 - 空目录"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        loader = ExtensionLoader(extensions_dir)
        files = loader.discover()
        assert files == []

    def test_discover_python_files(self, tmp_path: Path):
        """测试发现扩展 - Python 文件"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        # 创建测试扩展文件
        (extensions_dir / "test_ext.py").write_text("# test extension")
        (extensions_dir / "another.py").write_text("# another extension")
        (extensions_dir / "not_py.txt").write_text("not a python file")

        loader = ExtensionLoader(extensions_dir)
        files = loader.discover()

        assert len(files) == 2
        names = [f.stem for f in files]
        assert "test_ext" in names
        assert "another" in names

    def test_load_extension_with_extension_entry(self, tmp_path: Path):
        """测试加载扩展 - extension 入口"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        # 创建扩展文件
        ext_file = extensions_dir / "test_ext.py"
        ext_file.write_text("""
def extension(api, context=None):
    api.test_loaded = True
""")

        loader = ExtensionLoader(extensions_dir)
        api = MagicMock(spec=ExtensionAPI)

        result = loader.load(ext_file, api)
        assert result is True
        assert loader.is_loaded("test_ext")
        assert api.test_loaded is True

    def test_load_extension_with_setup_entry(self, tmp_path: Path):
        """测试加载扩展 - setup 入口"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        ext_file = extensions_dir / "setup_ext.py"
        ext_file.write_text("""
def setup(api, context=None):
    api.setup_called = True
""")

        loader = ExtensionLoader(extensions_dir)
        api = MagicMock(spec=ExtensionAPI)

        result = loader.load(ext_file, api)
        assert result is True
        assert api.setup_called is True

    def test_load_extension_with_init_entry(self, tmp_path: Path):
        """测试加载扩展 - init 入口"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        ext_file = extensions_dir / "init_ext.py"
        ext_file.write_text("""
def init(api, context=None):
    api.init_called = True
""")

        loader = ExtensionLoader(extensions_dir)
        api = MagicMock(spec=ExtensionAPI)

        result = loader.load(ext_file, api)
        assert result is True
        assert api.init_called is True

    def test_load_extension_with_context(self, tmp_path: Path):
        """测试加载扩展 - 带上下文"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        ext_file = extensions_dir / "context_ext.py"
        ext_file.write_text("""
def extension(api, context):
    api.context_received = context is not None
""")

        loader = ExtensionLoader(extensions_dir)
        api = MagicMock(spec=ExtensionAPI)
        context = create_mock_context()

        result = loader.load(ext_file, api, context)
        assert result is True
        assert api.context_received is True

    def test_load_extension_already_loaded(self, tmp_path: Path):
        """测试加载扩展 - 已加载"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        ext_file = extensions_dir / "loaded_ext.py"
        ext_file.write_text("pass")

        loader = ExtensionLoader(extensions_dir)
        loader._loaded["loaded_ext"] = True

        # 再次加载应该返回 True 且不执行
        result = loader.load(ext_file, MagicMock())
        assert result is True

    def test_load_extension_with_error(self, tmp_path: Path):
        """测试加载扩展 - 有错误"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        ext_file = extensions_dir / "error_ext.py"
        ext_file.write_text("raise RuntimeError('Extension error')")

        loader = ExtensionLoader(extensions_dir)
        api = MagicMock(spec=ExtensionAPI)

        result = loader.load(ext_file, api)
        assert result is False
        assert not loader.is_loaded("error_ext")

    def test_load_extension_invalid_spec(self, tmp_path: Path):
        """测试加载扩展 - 无效 spec"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        # 创建一个目录伪装成文件
        ext_file = extensions_dir / "invalid"
        ext_file.mkdir()

        loader = ExtensionLoader(extensions_dir)
        result = loader.load(ext_file, MagicMock())
        assert result is False

    def test_load_all(self, tmp_path: Path):
        """测试加载所有扩展"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        # 创建多个扩展文件
        (extensions_dir / "ext1.py").write_text("def extension(api): api.ext1 = True")
        (extensions_dir / "ext2.py").write_text("def extension(api): api.ext2 = True")
        (extensions_dir / "ext3.py").write_text("raise RuntimeError()")

        loader = ExtensionLoader(extensions_dir)
        api = MagicMock(spec=ExtensionAPI)

        count = loader.load_all(api)
        assert count == 2  # 两个成功
        assert loader.is_loaded("ext1")
        assert loader.is_loaded("ext2")
        assert not loader.is_loaded("ext3")

    def test_unload(self, tmp_path: Path):
        """测试卸载扩展"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        loader = ExtensionLoader(extensions_dir)
        loader._loaded["test"] = True

        result = loader.unload("test")
        assert result is True
        assert not loader.is_loaded("test")

    def test_unload_not_loaded(self, tmp_path: Path):
        """测试卸载未加载的扩展"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        loader = ExtensionLoader(extensions_dir)
        result = loader.unload("not_loaded")
        assert result is False

    def test_list_loaded(self, tmp_path: Path):
        """测试列出已加载扩展"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        loader = ExtensionLoader(extensions_dir)
        loader._loaded["ext1"] = True
        loader._loaded["ext2"] = True

        loaded = loader.list_loaded()
        assert "ext1" in loaded
        assert "ext2" in loaded
        assert len(loaded) == 2


class TestExtensionAPI:
    """扩展 API 测试"""

    def test_api_creation(self):
        """测试 API 创建"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        assert api._agent == agent
        assert api._event_handlers == {}
        assert api._commands == {}
        assert api._tools == []

    def test_api_creation_with_context(self):
        """测试带上下文的 API 创建"""
        agent = create_mock_agent()
        context = create_mock_context()
        api = ExtensionAPI(agent, context)

        assert api._context == context

    def test_on_decorator(self):
        """测试事件注册装饰器"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        @api.on("test_event")
        async def handler(event, ctx):
            pass

        assert "test_event" in api._event_handlers
        assert handler in api._event_handlers["test_event"]

    def test_on_direct(self):
        """测试直接注册事件处理器"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        async def handler(event, ctx):
            pass

        api.on("test_event", handler)

        assert "test_event" in api._event_handlers
        assert handler in api._event_handlers["test_event"]

    def test_off(self):
        """测试移除事件处理器"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        async def handler(event, ctx):
            pass

        api.on("test_event", handler)
        api.off("test_event", handler)

        assert handler not in api._event_handlers.get("test_event", [])

    def test_off_not_registered(self):
        """测试移除未注册的处理器"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        async def handler(event, ctx):
            pass

        # 不应该抛出异常
        api.off("non_existent", handler)

    @pytest.mark.asyncio
    async def test_emit(self):
        """测试发射事件"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        results = []

        @api.on("test_event")
        async def handler1(event, ctx):
            results.append(("handler1", event))
            return "result1"

        @api.on("test_event")
        async def handler2(event, ctx):
            results.append(("handler2", event))
            return "result2"

        returned = await api.emit("test_event", {"data": "test"})

        assert len(results) == 2
        assert "result1" in returned
        assert "result2" in returned

    @pytest.mark.asyncio
    async def test_emit_with_exception(self):
        """测试发射事件 - 处理器异常"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        @api.on("test_event")
        async def handler_with_error(event, ctx):
            raise RuntimeError("Handler error")

        @api.on("test_event")
        async def handler_ok(event, ctx):
            return "ok"

        # 不应该抛出异常
        results = await api.emit("test_event", {})
        assert "ok" in results

    def test_register_tool(self):
        """测试注册工具"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"

        api.register_tool(mock_tool)

        assert mock_tool in api._tools
        agent.add_tool.assert_called_once_with(mock_tool)

    def test_tool_decorator(self):
        """测试工具装饰器"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        @api.tool("greet", "Greet someone", {"name": {"type": "string"}}, ["name"])
        async def greet(tool_call_id, params, **kwargs):
            return f"Hello, {params['name']}!"

        assert len(api._tools) == 1
        agent.add_tool.assert_called_once()

    def test_register_command(self):
        """测试注册命令"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        async def cmd_handler(args, ctx):
            return f"executed: {args}"

        api.register_command("test_cmd", cmd_handler)

        assert "test_cmd" in api._commands
        assert api._commands["test_cmd"] == cmd_handler

    def test_command_decorator(self):
        """测试命令装饰器"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        @api.command("hello")
        async def hello(args, ctx):
            return f"Hello, {args}!"

        assert "hello" in api._commands

    @pytest.mark.asyncio
    async def test_execute_command(self):
        """测试执行命令"""
        agent = create_mock_agent()
        context = create_mock_context()
        api = ExtensionAPI(agent, context)

        @api.command("echo")
        async def echo(args, ctx):
            return f"echo: {args}"

        result = await api.execute_command("echo", "test")
        assert result == "echo: test"

    @pytest.mark.asyncio
    async def test_execute_command_unknown(self):
        """测试执行未知命令"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        with pytest.raises(ValueError, match="Unknown command"):
            await api.execute_command("unknown")

    def test_list_commands(self):
        """测试列出命令"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        api.register_command("cmd1", lambda a, c: None)
        api.register_command("cmd2", lambda a, c: None)

        commands = api.list_commands()
        assert "cmd1" in commands
        assert "cmd2" in commands

    def test_list_tools(self):
        """测试列出工具"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        tool1 = MagicMock()
        tool1.name = "tool1"
        tool2 = MagicMock()
        tool2.name = "tool2"

        api.register_tool(tool1)
        api.register_tool(tool2)

        tools = api.list_tools()
        assert len(tools) == 2
        # 返回副本，不应影响原列表
        tools.clear()
        assert len(api._tools) == 2

    def test_get_agent(self):
        """测试获取 Agent"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        assert api.get_agent() == agent

    def test_get_context(self):
        """测试获取上下文"""
        agent = create_mock_agent()
        context = create_mock_context()
        api = ExtensionAPI(agent, context)

        assert api.get_context() == context

    def test_get_context_none(self):
        """测试获取空上下文"""
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        assert api.get_context() is None


class TestExtensionContext:
    """扩展上下文测试"""

    def test_context_creation(self):
        """测试上下文创建"""
        ui = MagicMock()
        agent = MagicMock()
        session = MagicMock()

        context = ExtensionContext(ui=ui, agent=agent, session=session)

        assert context.ui == ui
        assert context.agent == agent
        assert context.session == session


class TestBuiltinExtensions:
    """内置扩展测试"""

    def test_create_builtin_extensions(self):
        """测试创建内置扩展"""
        extensions = create_builtin_extensions()

        assert isinstance(extensions, dict)
        assert "permission" in extensions
        assert "logging" in extensions

    def test_permission_extension(self):
        """测试权限扩展"""
        extensions = create_builtin_extensions()
        permission_ext = extensions["permission"]

        api = MagicMock(spec=ExtensionAPI)
        api.on = MagicMock(return_value=lambda f: f)

        permission_ext(api)

        # 应该注册事件处理器
        api.on.assert_called()

    def test_logging_extension(self):
        """测试日志扩展"""
        extensions = create_builtin_extensions()
        logging_ext = extensions["logging"]

        api = MagicMock(spec=ExtensionAPI)
        api.on = MagicMock(return_value=lambda f: f)

        logging_ext(api)

        # 应该注册两个事件处理器
        assert api.on.call_count == 2


class TestExtensionIntegration:
    """扩展集成测试"""

    def test_full_extension_lifecycle(self, tmp_path: Path):
        """测试完整扩展生命周期"""
        extensions_dir = tmp_path / "extensions"
        extensions_dir.mkdir()

        # 创建一个完整的扩展
        ext_file = extensions_dir / "full_ext.py"
        ext_file.write_text("""
# 完整扩展示例

def extension(api, context=None):
    # 注册事件处理器
    @api.on("tool_execution_start")
    async def on_tool_start(event, ctx):
        pass

    # 注册命令
    @api.command("my_command")
    async def my_command(args, ctx):
        return f"Executed: {args}"

    # 标记已加载
    api.full_ext_loaded = True
""")

        loader = ExtensionLoader(extensions_dir)
        agent = create_mock_agent()
        api = ExtensionAPI(agent)

        # 加载扩展
        result = loader.load(ext_file, api)
        assert result is True
        assert api.full_ext_loaded is True

        # 验证事件和命令已注册
        assert "tool_execution_start" in api._event_handlers
        assert "my_command" in api._commands

        # 卸载扩展
        result = loader.unload("full_ext")
        assert result is True
        assert not loader.is_loaded("full_ext")