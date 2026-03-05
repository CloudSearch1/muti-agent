"""
工具注册中心

职责：管理所有可用工具的注册、查找和执行
"""

from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from .base import BaseTool, ToolResult

logger = structlog.get_logger(__name__)


class ToolRegistry(BaseModel):
    """
    工具注册中心

    单例模式，管理所有可用工具
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tools: dict[str, BaseTool] = {}
    enabled: bool = True

    def register(self, tool: BaseTool) -> bool:
        """
        注册工具

        Args:
            tool: 工具实例

        Returns:
            是否注册成功
        """
        if not tool.NAME:
            logger.error("Cannot register tool without NAME")
            return False

        if tool.NAME in self.tools:
            logger.warning(
                "Tool already registered, replacing",
                tool_name=tool.NAME,
            )

        self.tools[tool.NAME] = tool

        logger.info(
            "Tool registered",
            tool_name=tool.NAME,
            tool_description=tool.DESCRIPTION,
        )

        return True

    def unregister(self, tool_name: str) -> bool:
        """
        注销工具

        Args:
            tool_name: 工具名称

        Returns:
            是否注销成功
        """
        if tool_name not in self.tools:
            logger.warning(
                "Tool not found",
                tool_name=tool_name,
            )
            return False

        del self.tools[tool_name]

        logger.info(
            "Tool unregistered",
            tool_name=tool_name,
        )

        return True

    def get(self, tool_name: str) -> BaseTool | None:
        """
        获取工具

        Args:
            tool_name: 工具名称

        Returns:
            工具实例，不存在则返回 None
        """
        return self.tools.get(tool_name)

    def list_tools(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        """
        列出所有工具

        Args:
            enabled_only: 是否只列出启用的工具

        Returns:
            工具信息列表
        """
        tools = []

        for tool in self.tools.values():
            if enabled_only and not tool.enabled:
                continue

            tools.append(tool.to_dict())

        return tools

    async def execute(
        self,
        tool_name: str,
        **kwargs,
    ) -> ToolResult:
        """
        执行工具

        Args:
            tool_name: 工具名称
            **kwargs: 工具参数

        Returns:
            执行结果
        """
        if not self.enabled:
            return ToolResult(
                success=False,
                error="Tool registry is disabled",
            )

        tool = self.get(tool_name)

        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}",
            )

        if not tool.enabled:
            return ToolResult(
                success=False,
                error=f"Tool is disabled: {tool_name}",
            )

        logger.info(
            "Executing tool",
            tool_name=tool_name,
            params=kwargs,
        )

        # 执行工具
        result = await tool(**kwargs)

        logger.debug(
            "Tool execution complete",
            tool_name=tool_name,
            success=result.success,
        )

        return result

    def has_tool(self, tool_name: str) -> bool:
        """检查工具是否存在"""
        return tool_name in self.tools

    def enable_tool(self, tool_name: str) -> bool:
        """启用工具"""
        tool = self.get(tool_name)
        if tool:
            tool.enabled = True
            logger.info("Tool enabled", tool_name=tool_name)
            return True
        return False

    def disable_tool(self, tool_name: str) -> bool:
        """禁用工具"""
        tool = self.get(tool_name)
        if tool:
            tool.enabled = False
            logger.info("Tool disabled", tool_name=tool_name)
            return True
        return False

    def clear(self) -> None:
        """清空所有工具"""
        self.tools = {}
        logger.info("Tool registry cleared")


# 全局单例
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """获取全局工具注册中心单例"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(tool: BaseTool) -> bool:
    """便捷函数：注册工具到全局注册中心"""
    return get_registry().register(tool)


async def execute_tool(tool_name: str, **kwargs) -> ToolResult:
    """便捷函数：执行全局注册中心的工具"""
    return await get_registry().execute(tool_name, **kwargs)
