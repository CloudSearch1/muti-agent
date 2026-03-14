"""
Process 工具 - 管理后台进程会话

职责：管理由 exec 工具创建的后台进程会话

功能：
- list: 列出后台会话
- poll: 轮询会话状态
- log: 获取会话日志
- write: 向会话写入输入
- kill: 终止会话
- clear: 清理会话
- remove: 删除会话

与 exec 工具集成：
- 共享 ProcessSessionManager（从 exec 模块导入）
- exec 创建会话，process 管理会话
- 所有操作都验证 agent_id 进行作用域隔离
"""

import asyncio
import base64
from datetime import datetime
from typing import Any, Optional

import structlog
from pydantic import BaseModel, Field

from ..base import BaseTool, OutputField, OutputSchema, ToolParameter, ToolResult

logger = structlog.get_logger(__name__)


# ============ 请求/响应模型 ============


class ProcessListRequest(BaseModel):
    """列出会话请求"""

    cursor: Optional[str] = Field(None, description="分页游标")
    limit: int = Field(20, ge=1, le=100, description="返回数量限制")


class ProcessPollRequest(BaseModel):
    """轮询会话请求"""

    session_id: str = Field(..., description="会话ID")
    wait_ms: int = Field(1000, ge=0, le=30000, description="等待时间（毫秒）")


class ProcessLogRequest(BaseModel):
    """获取日志请求"""

    session_id: str = Field(..., description="会话ID")
    stream: str = Field("stdout", description="日志流: stdout | stderr | both")
    offset: int = Field(0, ge=0, description="字节偏移量")
    max_bytes: int = Field(65536, ge=1, le=1048576, description="最大字节数")


class ProcessWriteRequest(BaseModel):
    """写入输入请求"""

    session_id: str = Field(..., description="会话ID")
    input: str = Field(..., description="输入内容")


class ProcessSessionInfo(BaseModel):
    """会话信息（从 ProcessSession 转换）"""

    session_id: str = Field(..., description="会话ID")
    agent_id: str = Field(..., description="创建者Agent ID")
    status: str = Field(..., description="会话状态")
    command: str = Field(..., description="执行的命令")
    cwd: Optional[str] = Field(None, description="工作目录")
    created_at: datetime = Field(..., description="创建时间")
    exit_code: Optional[int] = Field(None, description="退出码")
    pid: Optional[int] = Field(None, description="进程ID")
    stdout_bytes: int = Field(0, description="stdout字节数")
    stderr_bytes: int = Field(0, description="stderr字节数")


class ProcessListResponse(BaseModel):
    """列出会话响应"""

    items: list[ProcessSessionInfo] = Field(default_factory=list, description="会话列表")
    next_cursor: Optional[str] = Field(None, description="下一页游标")
    has_more: bool = Field(False, description="是否有更多")


class ProcessPollResponse(BaseModel):
    """轮询会话响应"""

    session_id: str = Field(..., description="会话ID")
    status: str = Field(..., description="会话状态")
    exit_code: Optional[int] = Field(None, description="退出码")
    stdout_bytes: int = Field(0, description="stdout字节数")
    stderr_bytes: int = Field(0, description="stderr字节数")


class ProcessLogResponse(BaseModel):
    """获取日志响应"""

    session_id: str = Field(..., description="会话ID")
    stream: str = Field(..., description="日志流")
    data: str = Field(..., description="日志内容（base64编码）")
    offset: int = Field(..., description="字节偏移量")
    bytes_read: int = Field(..., description="读取字节数")
    eof: bool = Field(False, description="是否到达末尾")


# ============ Process 工具实现 ============


class ProcessTool(BaseTool):
    """
    Process 工具 - 管理后台进程会话

    支持动作：
    - list: 列出后台会话
    - poll: 轮询会话状态
    - log: 获取会话日志
    - write: 向会话写入输入
    - kill: 终止会话
    - clear: 清理会话
    - remove: 删除会话

    所有操作都进行 agent 作用域隔离
    """

    NAME = "process"
    DESCRIPTION = "Manage background process sessions"
    SCHEMA_VERSION = "1.0.0"
    ACTIONS = ["list", "poll", "log", "write", "kill", "clear", "remove"]

    def __init__(self, agent_id: str, **kwargs):
        """
        初始化 Process 工具

        Args:
            agent_id: 当前 Agent ID（用于作用域隔离）
            **kwargs: 其他配置
        """
        super().__init__(**kwargs)
        self.agent_id = agent_id

    @property
    def parameters(self) -> list[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="action",
                description="操作类型",
                type="string",
                required=True,
                enum=self.ACTIONS,
            ),
            ToolParameter(
                name="session_id",
                description="会话ID（list 之外的动作需要）",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="cursor",
                description="分页游标（list 动作）",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="limit",
                description="返回数量限制（list 动作，默认20）",
                type="integer",
                required=False,
                default=20,
            ),
            ToolParameter(
                name="wait_ms",
                description="等待时间毫秒（poll 动作，默认1000）",
                type="integer",
                required=False,
                default=1000,
            ),
            ToolParameter(
                name="stream",
                description="日志流类型（log 动作：stdout/stderr/both）",
                type="string",
                required=False,
                default="stdout",
            ),
            ToolParameter(
                name="offset",
                description="字节偏移量（log 动作）",
                type="integer",
                required=False,
                default=0,
            ),
            ToolParameter(
                name="max_bytes",
                description="最大读取字节数（log 动作，默认65536）",
                type="integer",
                required=False,
                default=65536,
            ),
            ToolParameter(
                name="input",
                description="输入内容（write 动作）",
                type="string",
                required=False,
            ),
        ]

    @property
    def output_schema(self) -> OutputSchema:
        """
        获取工具输出模式定义

        Returns:
            Process 工具的输出模式（根据 action 不同而变化）
        """
        return OutputSchema(
            description="Process session management result",
            fields=[
                OutputField(
                    name="sessions",
                    type="array",
                    description="List of sessions (for list action)",
                    required=False,
                ),
                OutputField(
                    name="sessionId",
                    type="string",
                    description="Session ID",
                    required=False,
                ),
                OutputField(
                    name="status",
                    type="string",
                    description="Session status (running/finished/error)",
                    required=False,
                ),
                OutputField(
                    name="exitCode",
                    type="integer",
                    description="Exit code (when finished)",
                    required=False,
                ),
                OutputField(
                    name="stdout",
                    type="string",
                    description="Standard output (for log action)",
                    required=False,
                ),
                OutputField(
                    name="stderr",
                    type="string",
                    description="Standard error (for log action)",
                    required=False,
                ),
                OutputField(
                    name="hasMore",
                    type="boolean",
                    description="Whether more logs are available",
                    required=False,
                ),
                OutputField(
                    name="bytesRead",
                    type="integer",
                    description="Number of bytes read (for log action)",
                    required=False,
                ),
                OutputField(
                    name="success",
                    type="boolean",
                    description="Operation success status",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs) -> ToolResult:
        """
        执行 Process 工具

        Args:
            action: 操作类型
            **kwargs: 操作参数

        Returns:
            执行结果
        """
        action = kwargs.get("action")
        if not action:
            return ToolResult(success=False, error="Missing required parameter: action")

        if action not in self.ACTIONS:
            return ToolResult(success=False, error=f"Invalid action: {action}. Must be one of {self.ACTIONS}")

        try:
            # 导入会话管理器（延迟导入以避免循环依赖）
            from .exec import get_session_manager

            manager = get_session_manager()

            if action == "list":
                return await self._list(manager, kwargs)
            elif action == "poll":
                return await self._poll(manager, kwargs)
            elif action == "log":
                return await self._log(manager, kwargs)
            elif action == "write":
                return await self._write(manager, kwargs)
            elif action == "kill":
                return await self._kill(manager, kwargs)
            elif action == "clear":
                return await self._clear(manager, kwargs)
            elif action == "remove":
                return await self._remove(manager, kwargs)
            else:
                return ToolResult(success=False, error=f"Unsupported action: {action}")

        except ImportError as e:
            return ToolResult(success=False, error=f"Failed to import session manager: {str(e)}")
        except RuntimeError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            self.logger.error("Process tool execution failed", action=action, error=str(e))
            return ToolResult(success=False, error=f"Execution failed: {str(e)}")

    async def _list(self, manager, kwargs: dict[str, Any]) -> ToolResult:
        """列出会话"""
        request = ProcessListRequest(
            cursor=kwargs.get("cursor"),
            limit=kwargs.get("limit", 20),
        )

        # 从会话管理器获取会话列表
        sessions = await manager.list_sessions(agent_id=self.agent_id)

        # 转换为响应格式
        items = []
        for session in sessions[: request.limit]:
            info = ProcessSessionInfo(
                session_id=session.session_id,
                agent_id=session.agent_id,
                status=session.status,
                command=session.cmd,
                cwd=session.cwd,
                created_at=session.created_at,
                exit_code=session.exit_code,
                pid=session.process.pid if session.process else None,
                stdout_bytes=len(session.stdout),
                stderr_bytes=len(session.stderr),
            )
            items.append(info)

        return ToolResult(
            success=True,
            data={
                "items": [item.model_dump() for item in items],
                "next_cursor": None,  # 简单实现，暂不支持分页
                "has_more": len(sessions) > request.limit,
            },
        )

    async def _poll(self, manager, kwargs: dict[str, Any]) -> ToolResult:
        """轮询会话状态"""
        session_id = kwargs.get("session_id")
        if not session_id:
            return ToolResult(success=False, error="Missing required parameter: session_id")

        request = ProcessPollRequest(
            session_id=session_id,
            wait_ms=kwargs.get("wait_ms", 1000),
        )

        # 获取会话（已包含 agent 隔离检查）
        session = await manager.get_session(request.session_id, self.agent_id)

        if not session:
            return ToolResult(
                success=False,
                error=f"Session not found: {request.session_id}",
                metadata={"error_code": "NOT_FOUND"},
            )

        # 如果会话正在运行，等待指定时间
        if session.status == "running" and request.wait_ms > 0:
            await asyncio.sleep(request.wait_ms / 1000)

        # 返回会话状态
        return ToolResult(
            success=True,
            data={
                "session_id": session.session_id,
                "status": session.status,
                "exit_code": session.exit_code,
                "stdout_bytes": len(session.stdout),
                "stderr_bytes": len(session.stderr),
            },
        )

    async def _log(self, manager, kwargs: dict[str, Any]) -> ToolResult:
        """获取会话日志"""
        session_id = kwargs.get("session_id")
        if not session_id:
            return ToolResult(success=False, error="Missing required parameter: session_id")

        request = ProcessLogRequest(
            session_id=session_id,
            stream=kwargs.get("stream", "stdout"),
            offset=kwargs.get("offset", 0),
            max_bytes=kwargs.get("max_bytes", 65536),
        )

        # 获取会话
        session = await manager.get_session(request.session_id, self.agent_id)

        if not session:
            return ToolResult(
                success=False,
                error=f"Session not found: {request.session_id}",
                metadata={"error_code": "NOT_FOUND"},
            )

        # 获取日志内容
        if request.stream == "stdout":
            log_content = session.stdout
        elif request.stream == "stderr":
            log_content = session.stderr
        elif request.stream == "both":
            log_content = session.stdout + session.stderr
        else:
            return ToolResult(success=False, error=f"Invalid stream type: {request.stream}")

        # 应用偏移量和限制
        log_bytes = log_content.encode("utf-8")
        sliced = log_bytes[request.offset : request.offset + request.max_bytes]

        # 转换为 base64
        data_b64 = base64.b64encode(sliced).decode("ascii")

        return ToolResult(
            success=True,
            data={
                "session_id": session.session_id,
                "stream": request.stream,
                "data": data_b64,
                "offset": request.offset,
                "bytes_read": len(sliced),
                "eof": request.offset + len(sliced) >= len(log_bytes),
            },
        )

    async def _write(self, manager, kwargs: dict[str, Any]) -> ToolResult:
        """向会话写入输入"""
        session_id = kwargs.get("session_id")
        input_data = kwargs.get("input")

        if not session_id:
            return ToolResult(success=False, error="Missing required parameter: session_id")
        if input_data is None:
            return ToolResult(success=False, error="Missing required parameter: input")

        request = ProcessWriteRequest(
            session_id=session_id,
            input=input_data,
        )

        # 获取会话
        session = await manager.get_session(request.session_id, self.agent_id)

        if not session:
            return ToolResult(
                success=False,
                error=f"Session not found: {request.session_id}",
                metadata={"error_code": "NOT_FOUND"},
            )

        # 检查会话状态
        if session.status != "running":
            return ToolResult(
                success=False,
                error=f"Session is not running: {session.status}",
            )

        # 检查进程是否有 stdin
        if not session.process or not session.process.stdin:
            return ToolResult(
                success=False,
                error="Session does not support input",
            )

        try:
            # 写入输入
            session.process.stdin.write(request.input.encode("utf-8"))
            await session.process.stdin.drain()

            return ToolResult(
                success=True,
                data={"session_id": request.session_id, "written": True},
            )

        except Exception as e:
            self.logger.error("Failed to write to session", session_id=request.session_id, error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to write to session: {str(e)}",
            )

    async def _kill(self, manager, kwargs: dict[str, Any]) -> ToolResult:
        """终止会话"""
        session_id = kwargs.get("session_id")
        if not session_id:
            return ToolResult(success=False, error="Missing required parameter: session_id")

        # 获取会话
        session = await manager.get_session(session_id, self.agent_id)

        if not session:
            return ToolResult(
                success=False,
                error=f"Session not found: {session_id}",
                metadata={"error_code": "NOT_FOUND"},
            )

        # 检查会话状态
        if session.status != "running":
            return ToolResult(
                success=False,
                error=f"Session is not running: {session.status}",
            )

        # 终止进程
        try:
            if session.process:
                session.process.terminate()
                try:
                    await asyncio.wait_for(session.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # 如果进程没有响应 terminate，使用 kill
                    session.process.kill()
                    await session.process.wait()

            # 更新会话状态
            await manager.update_session(
                session_id,
                status="killed",
                finished_at=datetime.now(),
            )

            return ToolResult(
                success=True,
                data={"session_id": session_id, "killed": True},
            )

        except Exception as e:
            self.logger.error("Failed to kill session", session_id=session_id, error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to kill session: {str(e)}",
            )

    async def _clear(self, manager, kwargs: dict[str, Any]) -> ToolResult:
        """清理会话资源"""
        session_id = kwargs.get("session_id")
        if not session_id:
            return ToolResult(success=False, error="Missing required parameter: session_id")

        # 获取会话
        session = await manager.get_session(session_id, self.agent_id)

        if not session:
            return ToolResult(
                success=False,
                error=f"Session not found: {session_id}",
                metadata={"error_code": "NOT_FOUND"},
            )

        # 清理 stdout/stderr 缓冲区
        try:
            await manager.update_session(
                session_id,
                stdout="",
                stderr="",
            )

            return ToolResult(
                success=True,
                data={"session_id": session_id, "cleared": True},
            )

        except Exception as e:
            self.logger.error("Failed to clear session", session_id=session_id, error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to clear session: {str(e)}",
            )

    async def _remove(self, manager, kwargs: dict[str, Any]) -> ToolResult:
        """删除会话记录"""
        session_id = kwargs.get("session_id")
        if not session_id:
            return ToolResult(success=False, error="Missing required parameter: session_id")

        # 先检查会话是否存在且属于当前 agent
        session = await manager.get_session(session_id, self.agent_id)

        if not session:
            return ToolResult(
                success=False,
                error=f"Session not found: {session_id}",
                metadata={"error_code": "NOT_FOUND"},
            )

        # 如果会话还在运行，先终止
        if session.status == "running" and session.process:
            try:
                session.process.terminate()
                await asyncio.wait_for(session.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                session.process.kill()
                await session.process.wait()
            except Exception:
                pass  # 忽略终止失败

        # 删除会话
        success = await manager.remove_session(session_id)

        return ToolResult(
            success=success,
            data={"session_id": session_id, "removed": True},
            error=None if success else "Failed to remove session",
        )


# ============ 便捷函数 ============


def create_process_tool(agent_id: str, **kwargs) -> ProcessTool:
    """创建 Process 工具实例"""
    return ProcessTool(agent_id=agent_id, **kwargs)
