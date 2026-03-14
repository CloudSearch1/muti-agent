"""
工具适配器模块

将 src.tools.base.BaseTool 适配为 pi_python.agent.tools.AgentTool
使得 Agent 框架可以使用系统注册的所有工具。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from ..tools.base import BaseTool, ToolResult as BaseToolResult
from ..tools.registry import get_registry

if TYPE_CHECKING:
    from pi_python.agent.tools import ToolResult as AgentToolResult


class BaseToolAdapter:
    """
    将 BaseTool 适配为 AgentTool 接口
    
    使 Agent 框架能够调用 ToolRegistry 中注册的所有工具。
    """
    
    def __init__(self, tool: BaseTool):
        """
        初始化适配器
        
        Args:
            tool: BaseTool 实例
        """
        self._tool = tool
        self.name = tool.NAME
        self.label = tool.NAME
        self.description = tool.DESCRIPTION
        self.parameters = self._convert_parameters(tool)
        self.required = self._get_required_parameters(tool)
    
    def _convert_parameters(self, tool: BaseTool) -> dict[str, dict[str, Any]]:
        """
        将 BaseTool 参数转换为 AgentTool 参数格式
        
        Args:
            tool: BaseTool 实例
            
        Returns:
            参数定义字典
        """
        parameters = {}
        if hasattr(tool, 'PARAMETERS') and tool.PARAMETERS:
            for param in tool.PARAMETERS:
                param_def = {
                    "type": param.get("type", "string"),
                    "description": param.get("description", ""),
                }
                if param.get("enum"):
                    param_def["enum"] = param["enum"]
                if param.get("default") is not None:
                    param_def["default"] = param["default"]
                parameters[param["name"]] = param_def
        return parameters
    
    def _get_required_parameters(self, tool: BaseTool) -> list[str]:
        """
        获取必需参数列表
        
        Args:
            tool: BaseTool 实例
            
        Returns:
            必需参数名称列表
        """
        required = []
        if hasattr(tool, 'PARAMETERS') and tool.PARAMETERS:
            for param in tool.PARAMETERS:
                if param.get("required", False):
                    required.append(param["name"])
        return required
    
    async def execute(
        self,
        tool_call_id: str,
        params: dict[str, Any],
        signal: asyncio.CancelledError | None = None,
        on_update: Callable[[Any], Awaitable[None]] | None = None,
        context: dict[str, Any] | None = None,
    ):
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
        from pi_python.agent.tools import ToolResult
        from pi_python.ai import TextContent
        
        try:
            # 调用 BaseTool 的异步执行方法
            result = await self._tool.execute(**params)
            
            # 转换结果
            if isinstance(result, BaseToolResult):
                if result.success:
                    # 成功结果
                    if isinstance(result.data, str):
                        content = result.data
                    elif isinstance(result.data, dict):
                        import json
                        content = json.dumps(result.data, ensure_ascii=False, indent=2)
                    else:
                        content = str(result.data)
                    
                    return ToolResult(
                        content=[TextContent(text=content)],
                        details={"success": True, "data": result.data}
                    )
                else:
                    # 失败结果
                    return ToolResult(
                        content=[TextContent(text=f"Error: {result.error}")],
                        details={"success": False, "error": result.error}
                    )
            else:
                # 直接返回字符串或其他类型
                if isinstance(result, str):
                    return ToolResult.text(result)
                else:
                    import json
                    return ToolResult.text(json.dumps(result, ensure_ascii=False))
                    
        except Exception as e:
            return ToolResult.error(str(e))
    
    def to_tool(self):
        """
        将工具转换为 LLM 可识别的工具定义
        
        Returns:
            Tool: LLM 工具定义对象
        """
        from pi_python.ai import Tool, ToolParameter
        
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


def create_agent_tools(
    profile: str = "coding",
    allow: list[str] | None = None,
    deny: list[str] | None = None,
) -> list[BaseToolAdapter]:
    """
    创建 Agent 工具列表
    
    根据策略配置从 ToolRegistry 中获取工具并转换为 AgentTool。
    
    Args:
        profile: 工具策略 profile (minimal/coding/messaging/full)
        allow: 额外允许的工具列表
        deny: 禁止的工具列表
        
    Returns:
        AgentTool 适配器列表
    """
    from ..tools.policy import ToolsConfig, get_effective_tools
    
    registry = get_registry()
    
    # 获取有效工具集
    config = ToolsConfig(profile=profile)
    if allow:
        config.allow = allow
    if deny:
        config.deny = deny
    
    effective_tools = get_effective_tools(
        global_config=config,
        registry=registry
    )
    
    # 转换为 AgentTool
    agent_tools = []
    for tool_name in effective_tools:
        tool = registry.get(tool_name)
        if tool and tool.enabled:
            agent_tools.append(BaseToolAdapter(tool))
    
    return agent_tools


def get_agent_tool(tool_name: str) -> BaseToolAdapter | None:
    """
    获取单个工具的适配器
    
    Args:
        tool_name: 工具名称
        
    Returns:
        工具适配器，不存在则返回 None
    """
    registry = get_registry()
    tool = registry.get(tool_name)
    if tool:
        return BaseToolAdapter(tool)
    return None
