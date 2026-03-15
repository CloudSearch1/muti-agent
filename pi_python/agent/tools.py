"""
PI-Python Agent 工具系统

提供工具定义、执行和结果处理功能。
支持大输出截断、错误处理和进度回调。
"""

from __future__ import annotations

import asyncio
import logging
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

# 大输出阈值配置
MAX_OUTPUT_SIZE = 100000  # 100KB
TRUNCATION_WARNING_TEMPLATE = (
    "\n\n[WARNING] Output truncated. Original size: {size} bytes. "
    "Only first {max_size} bytes shown. "
    "Consider using pagination or filtering to reduce output size."
)

_logger = logging.getLogger(__name__)


def _truncate_if_needed(text: str, max_size: int = MAX_OUTPUT_SIZE) -> tuple[str, bool]:
    """
    如果文本超过阈值，进行截断并返回警告

    Args:
        text: 原始文本
        max_size: 最大允许大小（字节）

    Returns:
        元组：(处理后的文本, 是否被截断)
    """
    if len(text) <= max_size:
        return text, False

    truncated = text[:max_size]
    warning = TRUNCATION_WARNING_TEMPLATE.format(
        size=len(text),
        max_size=max_size
    )
    return truncated + warning, True


class ToolResult:
    """
    工具执行结果类。

    封装工具执行的返回结果，支持文本内容或结构化内容。
    自动处理大输出截断，防止内存溢出和上下文过大。

    Attributes:
        content: 结果内容，可以是字符串或 Content 对象列表
        details: 附加详情字典
        truncated: 是否被截断
    """

    def __init__(
        self,
        content: str | list[Content] = "",
        details: dict[str, Any] | None = None,
        truncated: bool = False
    ):
        """
        初始化工具结果。

        Args:
            content: 结果内容，字符串会自动转换为 TextContent 列表
            details: 附加详情字典
            truncated: 内容是否被截断
        """
        if isinstance(content, str):
            # 检查并处理大输出
            if len(content) > MAX_OUTPUT_SIZE:
                content, was_truncated = _truncate_if_needed(content)
                if was_truncated:
                    truncated = True
                    _logger.warning(
                        "Large output detected and truncated",
                        original_size=len(content),
                        max_size=MAX_OUTPUT_SIZE
                    )
            content = [TextContent(text=content)]
        self.content = content
        self.details = details or {}
        self.truncated = truncated

    @classmethod
    def text(cls, text: str, **details) -> ToolResult:
        """
        创建文本结果的类方法。

        自动处理大输出截断。

        Args:
            text: 文本内容
            **details: 附加详情键值对

        Returns:
            ToolResult: 包含文本内容的结果实例
        """
        truncated = False
        if len(text) > MAX_OUTPUT_SIZE:
            text, truncated = _truncate_if_needed(text)
            _logger.info(
                "Large output truncated",
                original_size=len(text),
                truncated=truncated
            )
        return cls(content=text, details=details, truncated=truncated)

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

    @classmethod
    def truncated_result(
        cls,
        text: str,
        original_size: int,
        max_size: int = MAX_OUTPUT_SIZE
    ) -> ToolResult:
        """
        创建已截断结果的类方法。

        Args:
            text: 截断后的文本
            original_size: 原始大小
            max_size: 最大允许大小

        Returns:
            ToolResult: 包含截断信息的结果实例
        """
        warning = TRUNCATION_WARNING_TEMPLATE.format(
            size=original_size,
            max_size=max_size
        )
        return cls(
            content=text + warning,
            details={"truncated": True, "original_size": original_size},
            truncated=True
        )


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
        """
        执行 Bash 命令

        自动处理大输出截断，防止返回过大内容。

        Args:
            tool_call_id: 工具调用 ID
            params: 参数字典，包含 command 和可选的 timeout
            signal: 取消信号
            on_update: 进度更新回调
            context: 执行上下文

        Returns:
            ToolResult: 执行结果，包含命令输出
        """
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

            # 使用 text() 方法自动处理大输出
            return ToolResult.text(
                output,
                exit_code=proc.returncode,
                command=command
            )

        except TimeoutError:
            proc.kill()
            return ToolResult.error(
                f"Command timed out after {timeout}s. "
                f"Consider increasing timeout parameter for long-running commands."
            )

        except Exception as e:
            return ToolResult.error(
                f"Command execution failed: {e}. "
                f"Please check command syntax and permissions."
            )


class ReadFileTool(AgentTool):
    """文件读取工具"""

    name = "read_file"
    label = "Read File"
    description = "Read the contents of a file"
    parameters = {
        "path": {
            "type": "string",
            "description": "The path to the file to read"
        },
        "max_size": {
            "type": "integer",
            "description": "Maximum bytes to read (default: 100KB)",
            "default": MAX_OUTPUT_SIZE
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
        """
        读取文件内容

        自动处理大文件截断，提供友好的错误消息。

        Args:
            tool_call_id: 工具调用 ID
            params: 参数字典，包含 path 和可选的 max_size
            signal: 取消信号
            on_update: 进度更新回调
            context: 执行上下文

        Returns:
            ToolResult: 文件内容结果
        """
        import aiofiles

        path = params["path"]
        max_size = params.get("max_size", MAX_OUTPUT_SIZE)

        try:
            async with aiofiles.open(path) as f:
                content = await f.read()

            # 检查文件大小并处理
            if len(content) > max_size:
                original_size = len(content)
                content = content[:max_size]
                _logger.info(
                    "Large file truncated",
                    path=path,
                    original_size=original_size,
                    max_size=max_size
                )
                return ToolResult.truncated_result(
                    content,
                    original_size=original_size,
                    max_size=max_size
                )

            return ToolResult.text(
                content,
                path=path,
                size=len(content)
            )

        except FileNotFoundError:
            return ToolResult.error(
                f"File not found: '{path}'. "
                f"Please verify the file path exists and check for typos."
            )
        except PermissionError:
            return ToolResult.error(
                f"Permission denied: '{path}'. "
                f"Please check file permissions or run with appropriate privileges."
            )
        except IsADirectoryError:
            return ToolResult.error(
                f"Path is a directory, not a file: '{path}'. "
                f"Use list command to see directory contents."
            )
        except UnicodeDecodeError:
            return ToolResult.error(
                f"Cannot read file as text: '{path}'. "
                f"The file may be binary. Use a binary read tool instead."
            )
        except Exception as e:
            return ToolResult.error(
                f"Failed to read file '{path}': {e}. "
                f"Please check the file path and permissions."
            )


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
        """
        写入文件内容

        Args:
            tool_call_id: 工具调用 ID
            params: 参数字典，包含 path 和 content
            signal: 取消信号
            on_update: 进度更新回调
            context: 执行上下文

        Returns:
            ToolResult: 写入结果
        """
        import aiofiles
        import os

        path = params["path"]
        content = params["content"]

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

            async with aiofiles.open(path, "w") as f:
                await f.write(content)

            return ToolResult.text(
                f"Successfully wrote {len(content)} bytes to '{path}'",
                path=path,
                size=len(content)
            )

        except PermissionError:
            return ToolResult.error(
                f"Permission denied: '{path}'. "
                f"Please check file permissions or run with appropriate privileges."
            )
        except OSError as e:
            return ToolResult.error(
                f"Failed to write file '{path}': {e}. "
                f"Please check disk space and file path."
            )
        except Exception as e:
            return ToolResult.error(
                f"Failed to write file '{path}': {e}. "
                f"Please check the file path and permissions."
            )


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
        """
        发送 HTTP 请求

        自动处理大响应截断。

        Args:
            tool_call_id: 工具调用 ID
            params: 参数字典，包含 url 和可选的 method、headers、body
            signal: 取消信号
            on_update: 进度更新回调
            context: 执行上下文

        Returns:
            ToolResult: HTTP 响应结果
        """
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

                # 使用 text() 方法自动处理大响应
                return ToolResult.text(
                    response.text,
                    status_code=response.status_code,
                    url=url
                )

        except httpx.TimeoutException:
            return ToolResult.error(
                f"HTTP request timed out: {method} {url}. "
                f"Consider using a longer timeout or check server availability."
            )
        except httpx.ConnectError:
            return ToolResult.error(
                f"Connection failed: {method} {url}. "
                f"Please check the URL and network connectivity."
            )
        except httpx.HTTPStatusError as e:
            return ToolResult.error(
                f"HTTP error {e.response.status_code}: {method} {url}. "
                f"Please check the request parameters and endpoint."
            )
        except Exception as e:
            return ToolResult.error(
                f"HTTP request failed: {method} {url} - {e}. "
                f"Please check the URL and network connectivity."
            )


# 内置工具列表
BUILTIN_TOOLS = [
    BashTool(),
    ReadFileTool(),
    WriteFileTool(),
    HTTPTool(),
]
