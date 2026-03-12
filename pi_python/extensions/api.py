"""
PI-Python 扩展 API

提供扩展的编程接口
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..agent import Agent
from ..agent.session import Session
from ..agent.tools import AgentTool

__all__ = [
    "ExtensionContext",
    "ExtensionAPI",
]


@dataclass
class ExtensionContext:
    """
    扩展上下文数据类。

    包含扩展运行时需要的上下文信息。

    Attributes:
        ui: UI 接口对象
        agent: Agent 实例
        session: 当前会话实例
    """
    ui: Any  # UI 接口
    agent: Agent
    session: Session


class ExtensionAPI:
    """
    扩展 API 类。

    提供扩展访问 Agent 核心功能的能力，包括事件处理、工具注册、命令注册等。

    Attributes:
        _agent: 关联的 Agent 实例
        _context: 扩展上下文
        _event_handlers: 事件处理器字典
        _commands: 命令字典
        _tools: 工具列表
    """

    def __init__(self, agent: Agent, context: ExtensionContext | None = None):
        """
        初始化扩展 API。

        Args:
            agent: Agent 实例
            context: 扩展上下文（可选）
        """
        self._agent = agent
        self._context = context
        self._event_handlers: dict[str, list[Callable]] = {}
        self._commands: dict[str, Callable] = {}
        self._tools: list[AgentTool] = []

    def on(
        self,
        event: str,
        handler: Callable | None = None
    ) -> Callable:
        """
        注册事件处理器装饰器。

        可以作为装饰器使用，也可以直接传入处理器函数。

        Args:
            event: 事件名称
            handler: 事件处理函数（可选）

        Returns:
            Callable: 装饰器函数

        Example:
            @pi.on("tool_call")
            async def on_tool_call(event, ctx):
                ...

            # 或直接调用
            pi.on("tool_call", handler)
        """
        def decorator(func: Callable) -> Callable:
            if event not in self._event_handlers:
                self._event_handlers[event] = []
            self._event_handlers[event].append(func)
            return func

        if handler:
            return decorator(handler)
        return decorator

    def off(self, event: str, handler: Callable) -> None:
        """
        移除事件处理器。

        Args:
            event: 事件名称
            handler: 要移除的处理函数
        """
        if event in self._event_handlers:
            if handler in self._event_handlers[event]:
                self._event_handlers[event].remove(handler)

    async def emit(
        self,
        event: str,
        data: Any
    ) -> list[Any]:
        """
        发射事件。

        调用所有注册的处理器，并收集返回值。

        Args:
            event: 事件名称
            data: 事件数据

        Returns:
            list[Any]: 所有处理器的返回值列表
        """
        results = []

        for handler in self._event_handlers.get(event, []):
            try:
                result = await handler(data, self._context)
                results.append(result)
            except Exception:
                pass

        return results

    def register_tool(self, tool: AgentTool) -> None:
        """
        注册工具到 Agent。

        Args:
            tool: 要注册的工具实例
        """
        self._tools.append(tool)
        self._agent.add_tool(tool)

    def tool(
        self,
        name: str,
        description: str,
        parameters: dict | None = None,
        required: list[str] | None = None,
    ) -> Callable:
        """
        装饰器：将函数注册为工具。

        Args:
            name: 工具名称
            description: 工具描述
            parameters: 参数定义字典
            required: 必需参数列表

        Returns:
            Callable: 装饰器函数

        Example:
            @pi.tool("greet", "Greet someone", {"name": {"type": "string"}})
            async def greet(tool_call_id, params, **kwargs):
                return f"Hello, {params['name']}!"
        """
        from ..agent.tools import tool as tool_decorator

        def decorator(func: Callable) -> AgentTool:
            t = tool_decorator(name, description, parameters, required)(func)
            self.register_tool(t)
            return t

        return decorator

    def register_command(self, name: str, handler: Callable) -> None:
        """
        注册命令处理器。

        Args:
            name: 命令名称
            handler: 命令处理函数
        """
        self._commands[name] = handler

    def command(self, name: str) -> Callable:
        """
        装饰器：将函数注册为命令。

        Args:
            name: 命令名称

        Returns:
            Callable: 装饰器函数

        Example:
            @pi.command("hello")
            async def hello(args, ctx):
                print(f"Hello, {args}!")
        """
        def decorator(func: Callable) -> Callable:
            self.register_command(name, func)
            return func

        return decorator

    async def execute_command(self, name: str, args: str = "") -> Any:
        """
        执行已注册的命令。

        Args:
            name: 命令名称
            args: 命令参数

        Returns:
            Any: 命令执行结果

        Raises:
            ValueError: 当命令未注册时
        """
        handler = self._commands.get(name)
        if handler:
            return await handler(args, self._context)
        raise ValueError(f"Unknown command: {name}")

    def list_commands(self) -> list[str]:
        """
        列出所有已注册的命令。

        Returns:
            list[str]: 命令名称列表
        """
        return list(self._commands.keys())

    def list_tools(self) -> list[AgentTool]:
        """
        列出所有已注册的工具。

        Returns:
            list[AgentTool]: 工具实例列表的副本
        """
        return self._tools.copy()

    def get_agent(self) -> Agent:
        """
        获取关联的 Agent 实例。

        Returns:
            Agent: Agent 实例
        """
        return self._agent

    def get_context(self) -> ExtensionContext | None:
        """
        获取扩展上下文。

        Returns:
            ExtensionContext | None: 扩展上下文对象，可能为 None
        """
        return self._context
