"""
Git 工具集

提供 Git 操作功能，包含命令安全验证。
"""

import asyncio
import subprocess
from pathlib import Path

import structlog

from .base import BaseTool, ToolParameter, ToolResult
from .security import ToolSecurity, SecurityError

logger = structlog.get_logger(__name__)


class GitTools(BaseTool):
    """
    Git 工具集

    提供：
    - Git 状态查询
    - 提交历史
    - 分支管理
    - 代码差异

    安全特性：
    - 命令注入防护
    - 敏感操作限制
    - 执行超时控制
    """

    NAME = "git_tools"
    DESCRIPTION = "Git 操作工具集合"

    # 允许的 Git 操作
    ALLOWED_ACTIONS = ["status", "log", "diff", "branch", "checkout", "pull", "push"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.repo_path = Path(kwargs.get("repo_path", ".")).resolve()
        self.security = ToolSecurity(root_dir=self.repo_path)
        self.timeout = kwargs.get("timeout", 30)

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                description="操作类型",
                type="string",
                required=True,
                enum=["status", "log", "diff", "branch", "checkout", "pull", "push"],
            ),
            ToolParameter(
                name="args",
                description="额外参数",
                type="string",
                required=False,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """执行 Git 工具"""
        action = kwargs.get("action")
        args = kwargs.get("args", "")

        # 安全检查：验证操作类型
        if action not in self.ALLOWED_ACTIONS:
            return ToolResult(
                success=False,
                error=f"Action not allowed: {action}. Allowed: {self.ALLOWED_ACTIONS}",
            )

        # 安全检查：验证参数
        if args:
            try:
                self.security.validate_command(["git", action, args])
            except SecurityError as e:
                return ToolResult(
                    success=False,
                    error=f"Security violation: {str(e)}",
                )

        try:
            if action == "status":
                return self._run_git(["status"])
            elif action == "log":
                return self._run_git(["log", "--oneline", "-10"])
            elif action == "diff":
                return self._run_git(["diff"])
            elif action == "branch":
                return self._run_git(["branch"])
            elif action == "checkout":
                if not args:
                    return ToolResult(
                        success=False,
                        error="Branch name required for checkout",
                    )
                return self._run_git(["checkout", args])
            elif action == "pull":
                return self._run_git(["pull"])
            elif action == "push":
                return self._run_git(["push"])
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}",
                )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def _run_git(self, args: list[str]) -> ToolResult:
        """运行 Git 命令（带安全检查）"""
        try:
            # 构建完整命令
            cmd = ["git"] + args

            # 安全检查
            try:
                self.security.validate_command(cmd)
            except SecurityError as e:
                return ToolResult(
                    success=False,
                    error=f"Security violation: {str(e)}",
                )

            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    data={
                        "command": " ".join(cmd),
                        "output": result.stdout,
                    },
                )
            else:
                return ToolResult(
                    success=False,
                    error=result.stderr,
                )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error="Git command timed out",
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                error="Git not found. Please install Git.",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
