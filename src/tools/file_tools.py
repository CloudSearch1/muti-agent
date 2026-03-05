"""
文件操作工具集

提供文件读写、目录管理等功能
"""

import shutil
from pathlib import Path

import structlog

from .base import BaseTool, ToolParameter, ToolResult

logger = structlog.get_logger(__name__)


class FileTools(BaseTool):
    """
    文件工具集

    提供：
    - 文件读写
    - 目录管理
    - 文件操作（复制、移动、删除）
    """

    NAME = "file_tools"
    DESCRIPTION = "文件操作工具集合"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 根目录限制（安全考虑）
        self.root_dir = Path(kwargs.get("root_dir", ".")).resolve()

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                description="操作类型",
                type="string",
                required=True,
                enum=["read", "write", "list", "create_dir", "delete", "copy", "move"],
            ),
            ToolParameter(
                name="path",
                description="文件/目录路径",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="content",
                description="文件内容（写入时使用）",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="destination",
                description="目标路径（复制/移动时使用）",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="recursive",
                description="是否递归（目录操作）",
                type="boolean",
                required=False,
                default=False,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """执行文件工具"""
        action = kwargs.get("action")
        path = kwargs.get("path")
        content = kwargs.get("content")
        destination = kwargs.get("destination")
        recursive = kwargs.get("recursive", False)

        # 安全检查
        safe_path = self._safe_path(path)
        if not safe_path:
            return ToolResult(
                success=False,
                error=f"Path '{path}' is outside root directory",
            )

        if action == "read":
            return self._read_file(safe_path)
        elif action == "write":
            return self._write_file(safe_path, content)
        elif action == "list":
            return self._list_directory(safe_path, recursive)
        elif action == "create_dir":
            return self._create_directory(safe_path)
        elif action == "delete":
            return self._delete(safe_path, recursive)
        elif action == "copy":
            if not destination:
                return ToolResult(
                    success=False,
                    error="Destination path required for copy",
                )
            safe_dest = self._safe_path(destination)
            if not safe_dest:
                return ToolResult(
                    success=False,
                    error=f"Destination path '{destination}' is outside root directory",
                )
            return self._copy_file(safe_path, safe_dest)
        elif action == "move":
            if not destination:
                return ToolResult(
                    success=False,
                    error="Destination path required for move",
                )
            safe_dest = self._safe_path(destination)
            if not safe_dest:
                return ToolResult(
                    success=False,
                    error=f"Destination path '{destination}' is outside root directory",
                )
            return self._move_file(safe_path, safe_dest)
        else:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    def _safe_path(self, path: str) -> Path | None:
        """安全检查：确保路径在根目录内"""
        try:
            full_path = (self.root_dir / path).resolve()

            # 检查是否在根目录内
            if not str(full_path).startswith(str(self.root_dir)):
                return None

            return full_path
        except Exception:
            return None

    def _read_file(self, path: Path) -> ToolResult:
        """读取文件"""
        try:
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {path}",
                )

            if not path.is_file():
                return ToolResult(
                    success=False,
                    error=f"Not a file: {path}",
                )

            content = path.read_text(encoding="utf-8")

            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "content": content,
                    "size": len(content),
                    "lines": len(content.splitlines()),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def _write_file(self, path: Path, content: str) -> ToolResult:
        """写入文件"""
        try:
            # 创建父目录
            path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            path.write_text(content, encoding="utf-8")

            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "size": len(content),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def _list_directory(self, path: Path, recursive: bool) -> ToolResult:
        """列出目录"""
        try:
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {path}",
                )

            if not path.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Not a directory: {path}",
                )

            items = []

            if recursive:
                for item in path.rglob("*"):
                    rel_path = item.relative_to(path)
                    items.append(
                        {
                            "path": str(rel_path),
                            "is_file": item.is_file(),
                            "size": item.stat().st_size if item.is_file() else 0,
                        }
                    )
            else:
                for item in path.iterdir():
                    items.append(
                        {
                            "name": item.name,
                            "is_file": item.is_file(),
                            "size": item.stat().st_size if item.is_file() else 0,
                        }
                    )

            return ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "items": items,
                    "count": len(items),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def _create_directory(self, path: Path) -> ToolResult:
        """创建目录"""
        try:
            path.mkdir(parents=True, exist_ok=True)

            return ToolResult(
                success=True,
                data={"path": str(path)},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def _delete(self, path: Path, recursive: bool) -> ToolResult:
        """删除文件/目录"""
        try:
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"Path not found: {path}",
                )

            if path.is_file():
                path.unlink()
            elif path.is_dir():
                if recursive:
                    shutil.rmtree(path)
                else:
                    path.rmdir()

            return ToolResult(
                success=True,
                data={"deleted": str(path)},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def _copy_file(self, src: Path, dest: Path) -> ToolResult:
        """复制文件"""
        try:
            if src.is_file():
                shutil.copy2(src, dest)
            else:
                shutil.copytree(src, dest)

            return ToolResult(
                success=True,
                data={
                    "source": str(src),
                    "destination": str(dest),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def _move_file(self, src: Path, dest: Path) -> ToolResult:
        """移动文件"""
        try:
            shutil.move(str(src), str(dest))

            return ToolResult(
                success=True,
                data={
                    "source": str(src),
                    "destination": str(dest),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
