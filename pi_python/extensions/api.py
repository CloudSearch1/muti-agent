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


@dataclass
class ExtensionContext:
    """扩展上下文"""
    ui: Any  # UI 接口
    agent: Agent
    session: Session


class ExtensionAPI:
    """
    扩展 API

    提供扩展访问 Agent 核心功能的能力
    """

    def __init__(self, agent: Agent, context: ExtensionContext | None = None):
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
        注册事件处理器

        Usage:
            @pi.on("tool_call")
            async def on_tool_call(event, ctx):
                ...

            # 或
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
        """移除事件处理器"""
        if event in self._event_handlers:
            if handler in self._event_handlers[event]:
                self._event_handlers[event].remove(handler)

    async def emit(
        self,
        event: str,
        data: Any
    ) -> list[Any]:
        """
        发射事件

        Returns:
            所有处理器的返回值列表
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
        """注册工具"""
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
        装饰器：注册工具

        Usage:
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
        """注册命令"""
        self._commands[name] = handler

    def command(self, name: str) -> Callable:
        """
        装饰器：注册命令

        Usage:
            @pi.command("hello")
            async def hello(args, ctx):
                print(f"Hello, {args}!")
        """
        def decorator(func: Callable) -> Callable:
            self.register_command(name, func)
            return func

        return decorator

    async def execute_command(self, name: str, args: str = "") -> Any:
        """执行命令"""
        handler = self._commands.get(name)
        if handler:
            return await handler(args, self._context)
        raise ValueError(f"Unknown command: {name}")

    def list_commands(self) -> list[str]:
        """列出所有命令"""
        return list(self._commands.keys())

    def list_tools(self) -> list[AgentTool]:
        """列出所有工具"""
        return self._tools.copy()

    def get_agent(self) -> Agent:
        """获取 Agent 实例"""
        return self._agent

    def get_context(self) -> ExtensionContext | None:
        """获取扩展上下文"""
        return self._context
