"""
工具注册中心

职责：管理所有可用工具的注册、查找和执行

架构:
┌─────────────────────────────────────────────────────────────┐
│                       ToolRegistry                           │
│  (注册、发现、执行工具)                                       │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ToolPolicyEngine      ToolPresenter       LoopDetector
   (策略裁剪)            (双通道呈现)        (循环检测)

使用示例:
    # 获取注册中心
    registry = get_registry()
    
    # 注册工具
    registry.register(ExecTool())
    
    # 执行工具
    result = await registry.execute("exec", cmd="ls -la")
    
    # 获取有效工具（经策略过滤）
    tools = registry.get_effective_tools("agent-001", "openai", "gpt-4")
    
    # 获取工具呈现
    presentation = registry.get_presentation("agent-001", "openai", "gpt-4")
"""

from typing import Any, Optional, Set

import structlog
from pydantic import BaseModel, ConfigDict

from .base import BaseTool, ToolResult
from .errors import ErrorCode, StandardError, ToolError
from .policy import (
    AgentToolsConfig,
    ToolPolicyEngine,
    ToolsConfig,
    merge_policies,
)

logger = structlog.get_logger(__name__)


# Forward declarations for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .presenter import ToolPresentation, ToolPresenter
    from .guardrails import LoopDetector, LoopDetectionConfig, LoopSignal


class ToolRegistry(BaseModel):
    """
    工具注册中心

    单例模式，管理所有可用工具。
    支持策略引擎集成、双通道呈现和循环检测。

    Attributes:
        tools: 已注册的工具字典
        policy_engine: 策略引擎实例（可选）
        loop_detector: 循环检测器实例（可选）
        enabled: 是否启用注册中心
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tools: dict[str, BaseTool] = {}
    policy_engine: Optional[Any] = None  # ToolPolicyEngine 类型，避免循环导入
    loop_detector: Optional[Any] = None  # LoopDetector 类型
    enabled: bool = True

    # Agent 级配置缓存
    _agent_configs: dict[str, AgentToolsConfig] = {}

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

    def get_effective_tools(
        self,
        agent_id: str,
        provider: str = "default",
        model: str = "default",
    ) -> Set[str]:
        """
        获取经过策略裁剪的有效工具集

        Args:
            agent_id: Agent ID
            provider: Provider 名称
            model: 模型名称

        Returns:
            有效工具名集合
        """
        if self.policy_engine is None:
            # 无策略引擎，返回所有工具
            return set(self.tools.keys())

        # 获取 Agent 级配置（如果有）
        agent_config = self._agent_configs.get(agent_id)

        # 调用策略引擎进行过滤
        from .policy import ToolsConfig

        if isinstance(self.policy_engine, ToolsConfig):
            # policy_engine 是 ToolsConfig 实例
            return merge_policies(
                global_config=self.policy_engine,
                agent_config=agent_config,
                provider=provider,
                model=model,
                registry=self,
            )

        # 兼容旧的策略引擎接口
        if hasattr(self.policy_engine, "filter_tools"):
            return self.policy_engine.filter_tools(
                set(self.tools.keys()), agent_id, provider, model
            )

        return set(self.tools.keys())

    def get_presentation(
        self,
        agent_id: str,
        provider: str = "default",
        model: str = "default",
    ) -> "ToolPresentation":
        """
        获取双通道工具呈现

        Args:
            agent_id: Agent ID
            provider: Provider 名称
            model: 模型名称

        Returns:
            ToolPresentation 包含系统提示和 API schemas
        """
        from .presenter import ToolPresenter

        # 获取有效工具集
        effective_tools = self.get_effective_tools(agent_id, provider, model)

        # 创建呈现器
        presenter = ToolPresenter(self)

        return presenter.present(effective_tools)

    def register_builtin_tools(self) -> None:
        """
        注册所有内置工具

        自动导入并注册 builtin 模块中的所有工具。
        """
        from .builtin import (
            ExecTool,
            ProcessTool,
            WebFetchTool,
            WebSearchTool,
            MemorySearchTool,
            MemoryGetTool,
            SessionsListTool,
            SessionsHistoryTool,
            SessionsSendTool,
            SessionsSpawnTool,
            SessionStatusTool,
            AgentsListTool,
            BrowserTool,
        )

        # 注册基础工具（不需要特殊参数）
        tools_to_register = [
            ExecTool(),
            WebFetchTool(),
            WebSearchTool(),
            MemorySearchTool(),
            MemoryGetTool(),
            SessionsListTool(),
            SessionsHistoryTool(),
            SessionsSendTool(),
            SessionsSpawnTool(),
            SessionStatusTool(),
            AgentsListTool(),
            BrowserTool(),
        ]

        for tool in tools_to_register:
            self.register(tool)

        # 注意：ProcessTool 需要 agent_id 参数，不在此自动注册
        # 需要在运行时根据具体 agent 创建实例

        logger.info(
            "Builtin tools registered",
            tool_count=len(tools_to_register),
        )

    def set_agent_config(
        self,
        agent_id: str,
        config: AgentToolsConfig,
    ) -> None:
        """
        设置 Agent 级工具配置

        Args:
            agent_id: Agent ID
            config: Agent 工具配置
        """
        self._agent_configs[agent_id] = config
        logger.debug(
            "Agent config set",
            agent_id=agent_id,
        )

    def get_agent_config(self, agent_id: str) -> Optional[AgentToolsConfig]:
        """
        获取 Agent 级工具配置

        Args:
            agent_id: Agent ID

        Returns:
            Agent 工具配置，未设置返回 None
        """
        return self._agent_configs.get(agent_id)

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

        # 循环检测检查（如果启用）
        if self.loop_detector:
            from .guardrails import ToolCall, ToolResult as GuardrailsToolResult

            # 在执行前检查循环
            signal = self.loop_detector.check(kwargs.get("agent_id", "default"))
            if signal and signal.suggested_action == "stop":
                logger.warning(
                    "Tool execution blocked by loop detector",
                    tool_name=tool_name,
                    signal_level=signal.level.value,
                )
                return ToolResult(
                    success=False,
                    error=f"Loop detected: {signal.reason}",
                )

        logger.info(
            "Executing tool",
            tool_name=tool_name,
            params=kwargs,
        )

        # 执行工具
        result = await tool(**kwargs)

        # 记录到循环检测器
        if self.loop_detector:
            from .guardrails import ToolCall, ToolResult as GuardrailsToolResult

            call = ToolCall(
                tool_name=tool_name,
                action=kwargs.get("action"),
                arguments=kwargs,
            )
            guardrails_result = GuardrailsToolResult(
                success=result.success,
                data=result.data,
                error=result.error,
                metadata=result.metadata,
            )
            self.loop_detector.record_call(
                agent_id=kwargs.get("agent_id", "default"),
                call=call,
                result=guardrails_result,
            )

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
        self._agent_configs = {}
        logger.info("Tool registry cleared")

    def set_policy_engine(self, engine: Any) -> None:
        """
        设置策略引擎

        Args:
            engine: 策略引擎实例（ToolsConfig 或 ToolPolicyEngine）
        """
        self.policy_engine = engine
        logger.info("Policy engine set", engine_type=type(engine).__name__)

    def set_loop_detector(self, detector: Any) -> None:
        """
        设置循环检测器

        Args:
            detector: 循环检测器实例
        """
        self.loop_detector = detector
        logger.info("Loop detector set")


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


def get_effective_tools(
    agent_id: str,
    provider: str = "default",
    model: str = "default",
) -> Set[str]:
    """便捷函数：获取有效工具集"""
    return get_registry().get_effective_tools(agent_id, provider, model)


def get_presentation(
    agent_id: str,
    provider: str = "default",
    model: str = "default",
) -> "ToolPresentation":
    """便捷函数：获取工具呈现"""
    return get_registry().get_presentation(agent_id, provider, model)
