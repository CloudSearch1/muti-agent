"""
文件操作工具集

提供独立的文件操作工具，适配 OpenAI function calling 格式
"""

import json
from pathlib import Path

from ..base import BaseTool, ToolResult, ToolParameter
from ..errors import StandardError, ErrorCode
from ..security import ToolSecurity, SecurityError
from ..file_tools import FileTools


class ReadTool(BaseTool):
    """读取文件工具"""
    
    NAME = "read"
    DESCRIPTION = "读取文件内容"
    
    def __init__(self):
        super().__init__()
        self.file_tools = FileTools()
    
    @property
    def parameters(self) -> list[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="path",
                type="string",
                description="文件路径",
                required=True
            )
        ]
    
    async def execute(self, path: str, **kwargs) -> ToolResult:
        """读取文件"""
        return await self.file_tools.execute(action="read", path=path)


class WriteTool(BaseTool):
    """写入文件工具"""
    
    NAME = "write"
    DESCRIPTION = "写入文件内容（会覆盖）"
    
    def __init__(self):
        super().__init__()
        self.file_tools = FileTools()
    
    @property
    def parameters(self) -> list[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="path",
                type="string",
                description="文件路径",
                required=True
            ),
            ToolParameter(
                name="content",
                type="string",
                description="文件内容",
                required=True
            )
        ]
    
    async def execute(self, path: str, content: str, **kwargs) -> ToolResult:
        """写入文件"""
        return await self.file_tools.execute(action="write", path=path, content=content)


class EditTool(BaseTool):
    """编辑文件工具"""
    
    NAME = "edit"
    DESCRIPTION = "编辑文件内容（查找并替换）"
    
    def __init__(self):
        super().__init__()
        self.file_tools = FileTools()
    
    @property
    def parameters(self) -> list[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="path",
                type="string",
                description="文件路径",
                required=True
            ),
            ToolParameter(
                name="old_str",
                type="string",
                description="要替换的旧内容",
                required=True
            ),
            ToolParameter(
                name="new_str",
                type="string",
                description="新内容",
                required=True
            )
        ]
    
    async def execute(self, path: str, old_str: str, new_str: str, **kwargs) -> ToolResult:
        """编辑文件"""
        # 先读取文件
        read_result = await self.file_tools.execute(action="read", path=path)
        if not read_result.success:
            return read_result
        
        # 替换内容
        content = read_result.data
        if old_str not in content:
            return ToolResult(
                success=False,
                error=f"未找到要替换的内容: {old_str[:50]}..."
            )
        
        new_content = content.replace(old_str, new_str)
        
        # 写回文件
        return await self.file_tools.execute(action="write", path=path, content=new_content)


class ApplyPatchTool(BaseTool):
    """应用补丁工具"""
    
    NAME = "apply_patch"
    DESCRIPTION = "应用补丁到文件"
    
    def __init__(self):
        super().__init__()
        self.file_tools = FileTools()
    
    @property
    def parameters(self) -> list[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="path",
                type="string",
                description="文件路径",
                required=True
            ),
            ToolParameter(
                name="patch",
                type="string",
                description="补丁内容",
                required=True
            )
        ]
    
    async def execute(self, path: str, patch: str, **kwargs) -> ToolResult:
        """应用补丁"""
        # 简化的补丁应用（实际应该使用更复杂的解析）
        # 这里假设 patch 是完整的文件内容
        return await self.file_tools.execute(action="write", path=path, content=patch)


# 会话工具（简化版本）
class SessionsListTool(BaseTool):
    """列出会话工具"""
    
    NAME = "sessions_list"
    DESCRIPTION = "列出所有会话"
    
    @property
    def parameters(self) -> list[ToolParameter]:
        """获取工具参数定义"""
        return []
    
    async def execute(self, **kwargs) -> ToolResult:
        """列出会话"""
        # 这是一个占位实现
        return ToolResult(
            success=True,
            data="会话列表功能未完全实现"
        )


class SessionsHistoryTool(BaseTool):
    """获取会话历史工具"""
    
    NAME = "sessions_history"
    DESCRIPTION = "获取会话历史"
    
    @property
    def parameters(self) -> list[ToolParameter]:
        """获取工具参数定义"""
        return [
            ToolParameter(
                name="session_id",
                type="string",
                description="会话ID",
                required=True
            )
        ]
    
    async def execute(self, session_id: str, **kwargs) -> ToolResult:
        """获取会话历史"""
        # 这是一个占位实现
        return ToolResult(
            success=True,
            data=f"会话 {session_id} 的历史"
        )
