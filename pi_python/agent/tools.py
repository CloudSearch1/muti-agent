"""
PI-Python Agent 工具系统
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from ..ai import Content, TextContent, Tool

__all__ = [
    "ToolResult",
    "AgentTool",
    "tool",
    "BashTool",
    "ReadFileTool",
    "WriteFileTool",
    "HTTPTool",
    "BUILTIN_TOOLS",
]


class ToolResult:
    """
    工具执行结果类。

    封装工具执行的返回结果，支持文本内容或结构化内容。

    Attributes:
        content: 结果内容，可以是字符串或 Content 对象列表
        details: 附加详情字典
    """

    def __init__(
        self,
        content: str | list[Content] = "",
        details: dict[str, Any] | None = None
    ):
        """
        初始化工具结果。

        Args:
            content: 结果内容，字符串会自动转换为 TextContent 列表
            details: 附加详情字典
        """
        if isinstance(content, str):
            content = [TextContent(text=content)]
        self.content = content
        self.details = details or {}

    @classmethod
    def text(cls, text: str, **details) -> ToolResult:
        """
        创建文本结果的类方法。

        Args:
            text: 文本内容
            **details: 附加详情键值对

        Returns:
            ToolResult: 包含文本内容的结果实例
        """
        return cls(content=text, details=details)

    @classmethod
    def error(cls, error: str) -> ToolResult:
        """
        创建错误结果的类方法。

        Args:
            error: 错误信息

        Returns:
            ToolResult: 包含错误信息的结果实例
        """
        return cls(content=f"Error: {error}", details={"error": True})


class AgentTool(ABC):
    """
    Agent 工具基类

    所有工具必须实现 execute 方法
    """

    name: str = ""
    label: str = ""
    description: str = ""
    parameters: dict[str, dict[str, Any]] = {}
    required: list[str] = []

    @abstractmethod
    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.CancelledError | None = None,
        on_update: Callable[[ToolResult], Awaitable[None]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """
        执行工具

        Args:
            tool_call_id: 工具调用 ID
            params: 参数
            signal: 取消信号
            on_update: 进度更新回调
            context: 执行上下文

        Returns:
            ToolResult: 执行结果
        """
        pass

    def to_tool(self) -> Tool:
        """
        将工具转换为 LLM 可识别的工具定义。

        Returns:
            Tool: LLM 工具定义对象
        """
        from ..ai import ToolParameter

        parameters = {}
        for name, param in self.parameters.items():
            parameters[name] = ToolParameter(
                type=param.get("type", "string"),
                description=param.get("description"),
                enum=param.get("enum"),
                default=param.get("default"),
            )

        return Tool(
            name=self.name,
            description=self.description,
            parameters=parameters,
            required=self.required
        )


def tool(
    name: str,
    description: str,
    parameters: dict[str, dict[str, Any]] | None = None,
    required: list[str] | None = None,
):
    """
    装饰器：将函数转换为 AgentTool 实例。

    用于快速创建工具，无需继承 AgentTool 类。

    Args:
        name: 工具名称
        description: 工具描述
        parameters: 参数定义字典，每个参数包含 type、description 等
        required: 必需参数名称列表

    Returns:
        Callable: 返回一个装饰器函数

    Example:
        @tool("greet", "Greet someone", {"name": {"type": "string"}})
        async def greet(tool_call_id, params, **kwargs):
            return f"Hello, {params['name']}!"
    """
    def decorator(func: Callable[..., Awaitable[str | ToolResult]]) -> AgentTool:
        class FunctionTool(AgentTool):
            def __init__(self):
                self.name = name
                self.label = name
                self.description = description
                self.parameters = parameters or {}
                self.required = required or []

            async def execute(
                self,
                tool_call_id: str,
                params: dict[str, Any],
                signal: asyncio.CancelledError | None = None,
                on_update: Callable[[ToolResult], Awaitable[None]] | None = None,
                context: dict[str, Any] | None = None,
            ) -> ToolResult:
                result = await func(tool_call_id, params, signal=signal, context=context)

                if isinstance(result, ToolResult):
                    return result
                if isinstance(result, str):
                    return ToolResult.text(result)

                return ToolResult.text(str(result))

        return FunctionTool()
    return decorator


# ============ 内置工具 ============

class BashTool(AgentTool):
    """Bash 命令执行工具"""

    name = "bash"
    label = "Bash"
    description = "Execute a bash command and return the output"
    parameters = {
        "command": {
            "type": "string",
            "description": "The bash command to execute"
        },
        "timeout": {
            "type": "integer",
            "description": "Timeout in seconds",
            "default": 30
        }
    }
    required = ["command"]

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.CancelledError | None = None,
        on_update: Callable[[ToolResult], Awaitable[None]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        command = params["command"]
        timeout = params.get("timeout", 30)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )

            output = stdout.decode() + stderr.decode()

            return ToolResult.text(
                output,
                exit_code=proc.returncode,
                command=command
            )

        except TimeoutError:
            proc.kill()
            return ToolResult.error(f"Command timed out after {timeout}s")

        except Exception as e:
            return ToolResult.error(str(e))


class ReadFileTool(AgentTool):
    """文件读取工具"""

    name = "read_file"
    label = "Read File"
    description = "Read the contents of a file"
    parameters = {
        "path": {
            "type": "string",
            "description": "The path to the file to read"
        }
    }
    required = ["path"]

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.CancelledError | None = None,
        on_update: Callable[[ToolResult], Awaitable[None]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        import aiofiles

        path = params["path"]

        try:
            async with aiofiles.open(path) as f:
                content = await f.read()

            return ToolResult.text(
                content,
                path=path,
                size=len(content)
            )

        except FileNotFoundError:
            return ToolResult.error(f"File not found: {path}")
        except Exception as e:
            return ToolResult.error(str(e))


class WriteFileTool(AgentTool):
    """文件写入工具"""

    name = "write_file"
    label = "Write File"
    description = "Write content to a file"
    parameters = {
        "path": {
            "type": "string",
            "description": "The path to the file to write"
        },
        "content": {
            "type": "string",
            "description": "The content to write"
        }
    }
    required = ["path", "content"]

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.CancelledError | None = None,
        on_update: Callable[[ToolResult], Awaitable[None]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        import aiofiles

        path = params["path"]
        content = params["content"]

        try:
            async with aiofiles.open(path, "w") as f:
                await f.write(content)

            return ToolResult.text(
                f"Successfully wrote {len(content)} bytes to {path}",
                path=path,
                size=len(content)
            )

        except Exception as e:
            return ToolResult.error(str(e))


class HTTPTool(AgentTool):
    """HTTP 请求工具"""

    name = "http_request"
    label = "HTTP Request"
    description = "Make an HTTP request"
    parameters = {
        "url": {
            "type": "string",
            "description": "The URL to request"
        },
        "method": {
            "type": "string",
            "description": "HTTP method",
            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
        },
        "headers": {
            "type": "object",
            "description": "Request headers"
        },
        "body": {
            "type": "string",
            "description": "Request body"
        }
    }
    required = ["url"]

    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.CancelledError | None = None,
        on_update: Callable[[ToolResult], Awaitable[None]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        import httpx

        url = params["url"]
        method = params.get("method", "GET")
        headers = params.get("headers", {})
        body = params.get("body")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    content=body,
                    timeout=30
                )

                return ToolResult.text(
                    response.text,
                    status_code=response.status_code,
                    url=url
                )

        except Exception as e:
            return ToolResult.error(str(e))


# 内置工具列表
BUILTIN_TOOLS = [
    BashTool(),
    ReadFileTool(),
    WriteFileTool(),
    HTTPTool(),
]
