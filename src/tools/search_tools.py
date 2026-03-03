"""
搜索工具集

提供代码搜索、文件搜索等功能
"""

import re
from pathlib import Path

import structlog

from .base import BaseTool, ToolParameter, ToolResult

logger = structlog.get_logger(__name__)


class SearchTools(BaseTool):
    """
    搜索工具集
    
    提供：
    - 文件内容搜索
    - 文件名搜索
    - 正则表达式搜索
    """

    NAME = "search_tools"
    DESCRIPTION = "搜索工具集合"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.root_dir = Path(kwargs.get("root_dir", ".")).resolve()
        self.max_results = kwargs.get("max_results", 100)

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                description="操作类型",
                type="string",
                required=True,
                enum=["content", "filename", "regex"],
            ),
            ToolParameter(
                name="query",
                description="搜索关键词/正则",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="path",
                description="搜索路径",
                type="string",
                required=False,
                default=".",
            ),
            ToolParameter(
                name="pattern",
                description="文件匹配模式",
                type="string",
                required=False,
                default="*",
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """执行搜索工具"""
        action = kwargs.get("action")
        query = kwargs.get("query")
        path = kwargs.get("path", ".")
        pattern = kwargs.get("pattern", "*")

        search_path = (self.root_dir / path).resolve()

        if action == "content":
            return self._search_content(search_path, query, pattern)
        elif action == "filename":
            return self._search_filename(search_path, query)
        elif action == "regex":
            return self._search_regex(search_path, query, pattern)
        else:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    def _search_content(
        self,
        path: Path,
        query: str,
        pattern: str,
    ) -> ToolResult:
        """搜索文件内容"""
        try:
            results = []

            for file_path in path.glob(f"**/{pattern}"):
                if not file_path.is_file():
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")

                    if query.lower() in content.lower():
                        # 找到匹配行
                        lines = content.splitlines()
                        matching_lines = []

                        for i, line in enumerate(lines, 1):
                            if query.lower() in line.lower():
                                matching_lines.append({
                                    "line": i,
                                    "content": line.strip()[:200],
                                })

                        results.append({
                            "file": str(file_path.relative_to(self.root_dir)),
                            "matches": matching_lines[:10],  # 限制每文件显示行数
                            "total_matches": len(matching_lines),
                        })

                        if len(results) >= self.max_results:
                            break

                except (UnicodeDecodeError, PermissionError):
                    continue

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results,
                    "total_files": len(results),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def _search_filename(self, path: Path, query: str) -> ToolResult:
        """搜索文件名"""
        try:
            results = []

            for file_path in path.glob(f"**/*{query}*"):
                rel_path = file_path.relative_to(self.root_dir)
                results.append({
                    "path": str(rel_path),
                    "is_file": file_path.is_file(),
                    "size": file_path.stat().st_size if file_path.is_file() else 0,
                })

                if len(results) >= self.max_results:
                    break

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results,
                    "count": len(results),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )

    def _search_regex(
        self,
        path: Path,
        pattern: str,
        file_pattern: str,
    ) -> ToolResult:
        """正则表达式搜索"""
        try:
            regex = re.compile(pattern)
            results = []

            for file_path in path.glob(f"**/{file_pattern}"):
                if not file_path.is_file():
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    lines = content.splitlines()

                    file_matches = []
                    for i, line in enumerate(lines, 1):
                        matches = regex.findall(line)
                        if matches:
                            file_matches.append({
                                "line": i,
                                "matches": matches,
                                "content": line.strip()[:200],
                            })

                    if file_matches:
                        results.append({
                            "file": str(file_path.relative_to(self.root_dir)),
                            "matches": file_matches[:10],
                            "total_matches": sum(len(m["matches"]) for m in file_matches),
                        })

                        if len(results) >= self.max_results:
                            break

                except (UnicodeDecodeError, PermissionError):
                    continue

            return ToolResult(
                success=True,
                data={
                    "pattern": pattern,
                    "results": results,
                    "total_files": len(results),
                },
            )
        except re.error as e:
            return ToolResult(
                success=False,
                error=f"Invalid regex pattern: {str(e)}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
