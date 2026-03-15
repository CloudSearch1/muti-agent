"""
命令执行工具

提供安全、可控的命令执行能力，支持前台和后台模式。

功能特性:
- 同步/异步命令执行
- 后台进程管理
- 权限提升审计
- 命令安全检查
- Agent 隔离的会话管理

使用示例:
    exec_tool = ExecTool()
    
    # 同步执行
    result = await exec_tool(cmd="ls -la", cwd="/project")
    
    # 后台执行
    result = await exec_tool(cmd="npm start", background=True)
    session_id = result.data["session_id"]
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog
from pydantic import BaseModel, Field

from ..base import BaseTool, OutputField, OutputSchema, ToolParameter, ToolResult, ToolStatus
from ..errors import ErrorCode, StandardError, ToolError
from ..security import SecurityError, ToolSecurity

logger = structlog.get_logger(__name__)


# =============================================================================
# 数据模型
# =============================================================================


class NodeTarget(BaseModel):
    """节点目标配置"""

    id: str = Field(..., description="节点 ID")


class ExecRequest(BaseModel):
    """命令执行请求"""

    cmd: str = Field(..., description="要执行的命令")
    cwd: Optional[str] = Field(None, description="工作目录")
    env: dict[str, str] = Field(default_factory=dict, description="环境变量")
    yield_ms: int = Field(1000, description="返回前等待时间(毫秒)")
    timeout_ms: int = Field(120000, description="超时时间(毫秒)")
    background: bool = Field(False, description="是否后台运行")
    pty: bool = Field(False, description="是否使用 PTY")
    elevated: bool = Field(False, description="是否提升权限")
    host: str = Field("local", description="执行主机")
    node: Optional[NodeTarget] = Field(None, description="节点目标")
    shell: bool = Field(True, description="是否使用 shell 执行（默认 True，设置为 False 可提高安全性）")


class ExecResponse(BaseModel):
    """命令执行响应"""

    exit_code: int = Field(..., description="退出码")
    stdout: str = Field("", description="标准输出")
    stderr: str = Field("", description="标准错误")
    session_id: Optional[str] = Field(None, description="后台运行时的会话 ID")


class ProcessSession(BaseModel):
    """进程会话"""

    session_id: str = Field(..., description="会话 ID")
    agent_id: str = Field(..., description="所属 Agent ID")
    cmd: str = Field(..., description="执行的命令")
    cwd: str = Field(..., description="工作目录")
    status: str = Field("running", description="进程状态")
    exit_code: Optional[int] = Field(None, description="退出码")
    stdout: str = Field("", description="标准输出")
    stderr: str = Field("", description="标准错误")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    finished_at: Optional[datetime] = Field(None, description="结束时间")
    process: Any = Field(None, description="进程对象", exclude=True)


# =============================================================================
# 会话管理器
# =============================================================================


class ProcessSessionManager:
    """
    进程会话管理器（单例）

    管理所有后台运行的进程会话，提供 Agent 隔离。

    功能:
    - 创建和销毁会话
    - Agent 级别的会话隔离
    - 进程状态跟踪
    - 资源清理
    - 自动过期清理
    """

    _instance: Optional["ProcessSessionManager"] = None

    # 会话配置
    MAX_SESSIONS = 100  # 最大会话数
    MAX_SESSION_AGE = 3600  # 会话最大存活时间（秒）
    CLEANUP_INTERVAL = 60  # 清理间隔（秒）

    def __new__(cls) -> "ProcessSessionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 实例级别的会话存储
            cls._instance._sessions: dict[str, ProcessSession] = {}
            cls._instance._session_timestamps: dict[str, float] = {}
            cls._instance._last_cleanup: float = 0
        return cls._instance

    def _should_cleanup(self) -> bool:
        """检查是否需要清理"""
        import time
        now = time.time()
        if now - self._last_cleanup > self.CLEANUP_INTERVAL:
            self._last_cleanup = now
            return True
        return False

    async def _auto_cleanup(self) -> int:
        """
        自动清理过期和已完成的会话

        Returns:
            清理的会话数量
        """
        import time
        now = time.time()
        cleaned = 0

        # 找出需要清理的会话
        to_remove = []
        for session_id, timestamp in list(self._session_timestamps.items()):
            session = self._sessions.get(session_id)

            # 清理条件：过期、已完成或超过最大数量
            should_remove = (
                now - timestamp > self.MAX_SESSION_AGE or
                (session and session.status in ("completed", "error", "killed")) or
                len(self._sessions) > self.MAX_SESSIONS
            )

            if should_remove:
                to_remove.append(session_id)

        # 执行清理
        for session_id in to_remove:
            await self.remove_session(session_id)
            cleaned += 1

        if cleaned > 0:
            logger.info(
                "Auto cleanup completed",
                cleaned_sessions=cleaned,
                remaining_sessions=len(self._sessions),
            )

        return cleaned

    async def create_session(
        self,
        cmd: str,
        cwd: str,
        agent_id: str,
        env: dict[str, str] = None,
    ) -> str:
        """
        创建后台进程会话

        Args:
            cmd: 要执行的命令
            cwd: 工作目录
            agent_id: 所属 Agent ID
            env: 环境变量

        Returns:
            session_id: 会话 ID
        """
        session_id = str(uuid.uuid4())

        import time

        # 检查是否需要清理
        if self._should_cleanup():
            await self._auto_cleanup()

        # 检查最大会话数
        if len(self._sessions) >= self.MAX_SESSIONS:
            # 强制清理最旧的会话
            oldest = min(self._session_timestamps.items(), key=lambda x: x[1])
            await self.remove_session(oldest[0])
            logger.warning(
                "Max sessions reached, removed oldest session",
                removed_session=oldest[0],
            )

        session = ProcessSession(
            session_id=session_id,
            agent_id=agent_id,
            cmd=cmd,
            cwd=cwd,
            status="running",
        )

        self._sessions[session_id] = session
        self._session_timestamps[session_id] = time.time()

        logger.info(
            "Process session created",
            session_id=session_id,
            agent_id=agent_id,
            cmd=cmd,
            total_sessions=len(self._sessions),
        )

        return session_id

    async def get_session(
        self,
        session_id: str,
        agent_id: str,
    ) -> Optional[ProcessSession]:
        """
        获取会话（带 Agent 隔离）

        Args:
            session_id: 会话 ID
            agent_id: Agent ID

        Returns:
            会话对象，不存在或不属于该 Agent 则返回 None
        """
        session = self._sessions.get(session_id)

        if session and session.agent_id == agent_id:
            return session

        return None

    async def update_session(
        self,
        session_id: str,
        **updates,
    ) -> bool:
        """
        更新会话状态

        Args:
            session_id: 会话 ID
            **updates: 要更新的字段

        Returns:
            是否更新成功
        """
        session = self._sessions.get(session_id)

        if not session:
            return False

        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)

        logger.debug(
            "Process session updated",
            session_id=session_id,
            updates=list(updates.keys()),
        )

        return True

    async def remove_session(self, session_id: str) -> bool:
        """
        移除会话

        Args:
            session_id: 会话 ID

        Returns:
            是否移除成功
        """
        if session_id in self._sessions:
            session = self._sessions[session_id]

            # 如果进程还在运行，尝试终止
            if session.status == "running" and session.process:
                try:
                    session.process.terminate()
                    logger.info(
                        "Terminated running process",
                        session_id=session_id,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to terminate process",
                        session_id=session_id,
                        error=str(e),
                    )

            del self._sessions[session_id]
            self._session_timestamps.pop(session_id, None)

            logger.info(
                "Process session removed",
                session_id=session_id,
                remaining_sessions=len(self._sessions),
            )

            return True

        return False

    async def list_sessions(
        self,
        agent_id: Optional[str] = None,
    ) -> list[ProcessSession]:
        """
        列出会话

        Args:
            agent_id: 可选的 Agent ID 过滤

        Returns:
            会话列表
        """
        if agent_id:
            return [
                s for s in self._sessions.values()
                if s.agent_id == agent_id
            ]

        return list(self._sessions.values())

    async def clear_agent_sessions(self, agent_id: str) -> int:
        """
        清理指定 Agent 的所有会话

        Args:
            agent_id: Agent ID

        Returns:
            清理的会话数量
        """
        sessions_to_remove = [
            s.session_id for s in self._sessions.values()
            if s.agent_id == agent_id
        ]

        for session_id in sessions_to_remove:
            await self.remove_session(session_id)

        logger.info(
            "Cleared agent sessions",
            agent_id=agent_id,
            count=len(sessions_to_remove),
        )

        return len(sessions_to_remove)


# 全局会话管理器实例
_session_manager: Optional[ProcessSessionManager] = None


def get_session_manager() -> ProcessSessionManager:
    """获取全局会话管理器单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = ProcessSessionManager()
    return _session_manager


# =============================================================================
# Exec 工具
# =============================================================================


class ExecTool(BaseTool):
    """
    命令执行工具

    提供:
    - 同步命令执行
    - 后台命令执行
    - 权限提升支持
    - 安全命令检查
    """

    NAME = "exec"
    DESCRIPTION = "Execute a command, optionally in background mode"
    SCHEMA_VERSION = "1.0.0"

    # 命令长度限制
    MAX_CMD_LENGTH = 10000

    # 最大输出长度
    MAX_OUTPUT_LENGTH = 1024 * 1024  # 1MB

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 工作目录
        self.root_dir = Path(kwargs.get("root_dir", ".")).resolve()

        # 安全检查器
        self.security = ToolSecurity(root_dir=self.root_dir)

        # 会话管理器
        self.session_manager = get_session_manager()

        # 默认 Agent ID（可从配置或环境获取）
        self.default_agent_id = kwargs.get(
            "agent_id",
            os.getenv("AGENT_ID", "default"),
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        """定义工具参数"""
        return [
            ToolParameter(
                name="cmd",
                description="Command to execute",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="cwd",
                description="Working directory",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="env",
                description="Environment variables",
                type="object",
                required=False,
                default={},
            ),
            ToolParameter(
                name="yield_ms",
                description="Time to wait before returning (milliseconds)",
                type="integer",
                required=False,
                default=1000,
            ),
            ToolParameter(
                name="timeout_ms",
                description="Command timeout (milliseconds)",
                type="integer",
                required=False,
                default=120000,
            ),
            ToolParameter(
                name="background",
                description="Run in background mode",
                type="boolean",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="pty",
                description="Use PTY for command execution",
                type="boolean",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="elevated",
                description="Run with elevated privileges",
                type="boolean",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="host",
                description="Target host for execution",
                type="string",
                required=False,
                default="local",
            ),
            ToolParameter(
                name="node",
                description="Node target configuration",
                type="object",
                required=False,
            ),
            ToolParameter(
                name="shell",
                description="Use shell for command execution (default True, set False for safer execution without shell features like pipes/redirections)",
                type="boolean",
                required=False,
                default=True,
            ),
        ]

    @property
    def output_schema(self) -> OutputSchema:
        """
        获取工具输出模式定义

        Returns:
            Exec 工具的输出模式
        """
        return OutputSchema(
            description="Command execution result",
            fields=[
                OutputField(
                    name="exitCode",
                    type="integer",
                    description="Command exit code (0 for success)",
                    required=True,
                ),
                OutputField(
                    name="stdout",
                    type="string",
                    description="Standard output from the command",
                    required=True,
                ),
                OutputField(
                    name="stderr",
                    type="string",
                    description="Standard error from the command",
                    required=True,
                ),
                OutputField(
                    name="sessionId",
                    type="string",
                    description="Session ID for background processes (only when background=true)",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs) -> ToolResult:
        """
        执行命令

        根据 background 参数决定同步或异步执行
        """
        # 兼容 AI 模型可能使用的 'command' 参数
        if 'command' in kwargs and 'cmd' not in kwargs:
            kwargs['cmd'] = kwargs.pop('command')
            self.logger.debug(f"Converted 'command' parameter to 'cmd': {kwargs['cmd']}")

        # 解析请求
        try:
            request = ExecRequest(**kwargs)
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Invalid request parameters: {e}",
                hint="Check that all parameters have correct types",
            )

        # 安全检查
        try:
            self._validate_request(request)
        except SecurityError as e:
            return ToolResult.error(
                code=ErrorCode.SECURITY_BLOCKED,
                message=f"Security check failed: {e}",
                retryable=False,
                hint="The command may contain dangerous patterns or access restricted paths",
            )

        # 权限提升审计
        if request.elevated:
            self._audit_elevated_request(request)

        # 检查 process 工具是否可用
        # 如果不可用，强制同步执行
        background = request.background
        if background and not self._is_process_tool_available():
            logger.warning(
                "Process tool not available, forcing synchronous execution"
            )
            background = False

        # 执行命令
        try:
            if background:
                response = await self._execute_background(request)
                # 后台任务返回 RUNNING 状态
                return ToolResult.running(
                    session_id=response.session_id,
                    data=response.model_dump(exclude_none=True),
                )
            else:
                response = await self._execute_sync(request)
                return ToolResult.ok(data=response.model_dump(exclude_none=True))

        except asyncio.TimeoutError:
            return ToolResult.error(
                code=ErrorCode.TIMEOUT,
                message=f"Command timed out after {request.timeout_ms}ms",
                retryable=True,
                details={"timeout_ms": request.timeout_ms, "cmd": request.cmd[:100]},
                hint="Try increasing timeout_ms or optimizing the command",
            )
        except Exception as e:
            logger.error(
                "Command execution failed",
                cmd=request.cmd[:100],
                error=str(e),
            )
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Execution failed: {e}",
                details={"cmd": request.cmd[:100]},
            )

    def _validate_request(self, request: ExecRequest) -> None:
        """
        验证请求安全性

        Args:
            request: 执行请求

        Raises:
            SecurityError: 安全检查失败
        """
        # 检查命令长度
        if len(request.cmd) > self.MAX_CMD_LENGTH:
            raise SecurityError(
                f"Command exceeds maximum length: {len(request.cmd)} > {self.MAX_CMD_LENGTH}"
            )

        # 检查命令安全性
        self.security.validate_command(request.cmd)

        # 检查工作目录
        if request.cwd:
            cwd_path = Path(request.cwd)
            if not cwd_path.is_absolute():
                cwd_path = self.root_dir / cwd_path

            # 验证目录存在
            if not cwd_path.exists():
                raise SecurityError(f"Working directory does not exist: {cwd_path}")

            # 验证目录在允许范围内
            self.security.validate_path(cwd_path, operation="read")

    def _audit_elevated_request(self, request: ExecRequest) -> None:
        """
        记录权限提升请求的审计日志

        Args:
            request: 执行请求
        """
        logger.warning(
            "Elevated command execution requested",
            cmd=request.cmd[:100],
            cwd=request.cwd,
            agent_id=self.default_agent_id,
            timestamp=datetime.now().isoformat(),
        )

        # TODO: 发送到审计系统
        # audit_log.record({
        #     "type": "elevated_exec",
        #     "cmd": request.cmd,
        #     "agent_id": self.default_agent_id,
        # })

    def _is_process_tool_available(self) -> bool:
        """
        检查 process 工具是否可用

        Returns:
            process 工具是否可用
        """
        # 从注册中心检查
        from ..registry import get_registry

        registry = get_registry()
        return registry.has_tool("process") and registry.get("process").enabled

    async def _execute_sync(self, request: ExecRequest) -> ExecResponse:
        """
        同步执行命令

        Args:
            request: 执行请求

        Returns:
            执行响应
        """
        # 准备环境变量
        env = os.environ.copy()
        env.update(request.env)

        # 准备工作目录
        cwd = request.cwd
        if cwd:
            cwd_path = Path(cwd)
            if not cwd_path.is_absolute():
                cwd_path = self.root_dir / cwd_path
            cwd = str(cwd_path)
        else:
            cwd = str(self.root_dir)

        # 构建命令
        cmd = request.cmd

        # 安全警告：shell=True 可能导致命令注入风险
        # 建议在生产环境中使用 shell=False 并传递参数列表
        if request.shell:
            # 使用 shell 执行（支持管道、重定向等 shell 特性）
            # ⚠️ 警告：shell=True 存在命令注入风险，请确保输入可信
            if sys.platform == "win32":
                create_process = asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                )
            else:
                create_process = asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                )
            logger.debug(
                "Executing command with shell=True",
                cmd=cmd[:100],
                warning="shell mode enabled - potential command injection risk",
            )
        else:
            # 安全模式：不使用 shell 执行
            # 命令将被解析为参数列表，避免 shell 注入
            cmd_args = self._parse_command(cmd)
            if sys.platform == "win32":
                # Windows 需要指定 shell=False 并使用列表参数
                create_process = asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                )
            else:
                create_process = asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                )
            logger.debug(
                "Executing command with shell=False (safer mode)",
                cmd_args=cmd_args[:5],  # 只记录前5个参数
            )

        # 创建进程
        process = await create_process

        # 等待执行完成（带超时）
        timeout_sec = request.timeout_ms / 1000
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_sec,
        )

        # 解码输出
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        # 截断过长的输出
        if len(stdout_str) > self.MAX_OUTPUT_LENGTH:
            stdout_str = stdout_str[:self.MAX_OUTPUT_LENGTH] + "\n... (truncated)"
        if len(stderr_str) > self.MAX_OUTPUT_LENGTH:
            stderr_str = stderr_str[:self.MAX_OUTPUT_LENGTH] + "\n... (truncated)"

        return ExecResponse(
            exit_code=process.returncode or 0,
            stdout=stdout_str,
            stderr=stderr_str,
        )

    async def _execute_background(self, request: ExecRequest) -> ExecResponse:
        """
        后台执行命令

        Args:
            request: 执行请求

        Returns:
            执行响应（包含 session_id）
        """
        # 准备工作目录
        cwd = request.cwd
        if cwd:
            cwd_path = Path(cwd)
            if not cwd_path.is_absolute():
                cwd_path = self.root_dir / cwd_path
            cwd = str(cwd_path)
        else:
            cwd = str(self.root_dir)

        # 创建会话
        session_id = await self.session_manager.create_session(
            cmd=request.cmd,
            cwd=cwd,
            agent_id=self.default_agent_id,
            env=request.env,
        )

        # 获取会话
        session = await self.session_manager.get_session(
            session_id,
            self.default_agent_id,
        )

        # 启动后台进程
        env = os.environ.copy()
        env.update(request.env)

        # 安全执行：支持 shell=False 模式
        if request.shell:
            if sys.platform == "win32":
                process = await asyncio.create_subprocess_shell(
                    request.cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                )
            else:
                process = await asyncio.create_subprocess_shell(
                    request.cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                )
        else:
            cmd_args = self._parse_command(request.cmd)
            if sys.platform == "win32":
                process = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                )

        # 更新会话的进程对象
        session.process = process

        # 等待 yield_ms
        await asyncio.sleep(request.yield_ms / 1000)

        # 检查进程是否已结束
        if process.returncode is not None:
            # 进程已结束，收集输出
            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # 更新会话状态
            await self.session_manager.update_session(
                session_id,
                status="completed",
                exit_code=process.returncode,
                stdout=stdout_str,
                stderr=stderr_str,
                finished_at=datetime.now(),
            )

            return ExecResponse(
                exit_code=process.returncode,
                stdout=stdout_str,
                stderr=stderr_str,
                session_id=session_id,
            )
        else:
            # 进程仍在运行
            return ExecResponse(
                exit_code=-1,  # -1 表示仍在运行
                stdout="",
                stderr="",
                session_id=session_id,
            )

    def _parse_command(self, cmd: str) -> list[str]:
        """
        解析命令字符串为参数列表

        使用 shlex 安全地解析命令，正确处理引号和转义。

        Args:
            cmd: 命令字符串

        Returns:
            参数列表
        """
        import shlex

        try:
            # shlex.split 可以正确处理引号和转义
            return shlex.split(cmd)
        except ValueError as e:
            # 如果解析失败，回退到简单分割
            logger.warning(
                "Failed to parse command with shlex, using simple split",
                error=str(e),
                cmd=cmd[:100],
            )
            return cmd.split()


# =============================================================================
# 便捷函数
# =============================================================================


async def exec_command(
    cmd: str,
    cwd: Optional[str] = None,
    **kwargs,
) -> ToolResult:
    """
    便捷函数：执行命令

    Args:
        cmd: 要执行的命令
        cwd: 工作目录
        **kwargs: 其他参数

    Returns:
        执行结果
    """
    tool = ExecTool()
    return await tool(cmd=cmd, cwd=cwd, **kwargs)
