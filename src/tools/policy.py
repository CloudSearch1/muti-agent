"""
工具策略引擎模块

职责：
1. 定义 Profile 预设配置
2. 实现 Tool Group 展开机制
3. 策略合并逻辑（profile -> byProvider -> allow/deny）
4. 支持通配符匹配和大小写不敏感

策略优先级：
1. profile（基础白名单）
2. byProvider（provider 定向策略，只能缩小工具集）
3. deny（黑名单，最高优先级）
4. allow（白名单）

合并规则：
- deny 优先于 allow
- agent 级配置覆盖全局配置
- byProvider 只能缩小工具集，不能扩大

使用示例：
    from src.tools.policy import (
        ToolsConfig,
        AgentToolsConfig,
        merge_policies,
        get_effective_tools,
    )

    # 创建全局配置
    global_config = ToolsConfig(profile="coding")

    # 创建 agent 级配置
    agent_config = AgentToolsConfig(deny=["exec"])

    # 获取有效工具集
    effective_tools = merge_policies(
        global_config=global_config,
        agent_config=agent_config,
        provider="openai",
        model="gpt-4",
    )
"""

from __future__ import annotations

import fnmatch
import re
from enum import Enum
from typing import TYPE_CHECKING, Optional

import structlog
from pydantic import BaseModel, Field, field_validator, model_validator

if TYPE_CHECKING:
    from .registry import ToolRegistry

logger = structlog.get_logger(__name__)


# =============================================================================
# Tool Groups 定义
# =============================================================================

TOOL_GROUPS: dict[str, list[str]] = {
    "group:runtime": ["exec", "bash", "process"],
    "group:fs": ["read", "write", "edit", "apply_patch"],
    "group:sessions": [
        "sessions_list",
        "sessions_history",
        "sessions_send",
        "sessions_spawn",
        "session_status",
    ],
    "group:memory": ["memory_search", "memory_get"],
    "group:web": ["web_search", "web_fetch"],
    "group:ui": ["browser", "canvas"],
    "group:automation": ["cron", "gateway"],
    "group:messaging": ["message"],
    "group:nodes": ["nodes"],
    "group:openclaw": [
        # 所有内置工具（不含 provider 插件工具）
        "exec",
        "bash",
        "process",
        "read",
        "write",
        "edit",
        "apply_patch",
        "sessions_list",
        "sessions_history",
        "sessions_send",
        "sessions_spawn",
        "session_status",
        "memory_search",
        "memory_get",
        "web_search",
        "web_fetch",
        "browser",
        "canvas",
        "cron",
        "gateway",
        "message",
        "nodes",
        "image",
    ],
}

# 所有已知工具名称集合（用于验证）
ALL_KNOWN_TOOLS: set[str] = set()
for tools in TOOL_GROUPS.values():
    ALL_KNOWN_TOOLS.update(tools)
# 添加 session_status（minimal profile 需要）
ALL_KNOWN_TOOLS.add("session_status")


# =============================================================================
# Profile 预设配置
# =============================================================================

class ProfileType(str, Enum):
    """工具 Profile 类型"""
    MINIMAL = "minimal"
    CODING = "coding"
    MESSAGING = "messaging"
    FULL = "full"


# Profile 预设工具集
PROFILE_TOOLS: dict[str, list[str]] = {
    ProfileType.MINIMAL: ["session_status"],
    ProfileType.CODING: [
        # group:fs
        "read", "write", "edit", "apply_patch",
        # group:runtime
        "exec", "bash", "process",
        # group:sessions
        "sessions_list", "sessions_history", "sessions_send", "sessions_spawn", "session_status",
        # group:memory
        "memory_search", "memory_get",
        # image
        "image",
    ],
    ProfileType.MESSAGING: [
        # group:messaging
        "message",
        # 特定 sessions 工具
        "sessions_list", "sessions_history", "sessions_send", "session_status",
    ],
    ProfileType.FULL: [],  # 空列表表示不限制
}


# =============================================================================
# 循环检测配置
# =============================================================================

class LoopDetectionConfig(BaseModel):
    """循环检测配置"""
    
    enabled: bool = Field(default=False, description="是否启用循环检测")
    warning_threshold: int = Field(default=3, description="警告阈值")
    critical_threshold: int = Field(default=5, description="严重阈值")
    global_circuit_breaker_threshold: int = Field(
        default=10, 
        description="全局熔断阈值"
    )
    history_size: int = Field(default=50, description="历史记录大小")
    detectors: list[str] = Field(
        default=["genericRepeat", "knownPollNoProgress", "pingPong"],
        description="启用的检测器列表",
    )


# =============================================================================
# 策略配置模型
# =============================================================================

class ProviderScopedPolicy(BaseModel):
    """
    Provider 定向策略
    
    只能缩小工具集，不能扩大。
    key 支持 provider 或 provider/model。
    """
    
    profile: Optional[str] = Field(
        default=None,
        description="Profile 名称（minimal/coding/messaging/full）",
    )
    allow: Optional[list[str]] = Field(
        default=None,
        description="允许的工具列表",
    )
    deny: Optional[list[str]] = Field(
        default=None,
        description="禁止的工具列表",
    )
    
    @field_validator("profile")
    @classmethod
    def validate_profile(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in [p.value for p in ProfileType]:
            raise ValueError(f"Invalid profile: {v}. Must be one of: {[p.value for p in ProfileType]}")
        return v


class AgentToolsConfig(BaseModel):
    """
    Agent 级工具配置
    
    仅覆盖，不反向污染全局配置。
    所有字段都是可选的，未设置的字段继承全局配置。
    """
    
    profile: Optional[str] = Field(
        default=None,
        description="Profile 名称（minimal/coding/messaging/full）",
    )
    allow: Optional[list[str]] = Field(
        default=None,
        description="允许的工具列表",
    )
    deny: Optional[list[str]] = Field(
        default=None,
        description="禁止的工具列表",
    )
    byProvider: Optional[dict[str, ProviderScopedPolicy]] = Field(
        default=None,
        description="Provider 定向策略",
    )
    
    @field_validator("profile")
    @classmethod
    def validate_profile(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in [p.value for p in ProfileType]:
            raise ValueError(f"Invalid profile: {v}. Must be one of: {[p.value for p in ProfileType]}")
        return v


class ToolsConfig(BaseModel):
    """
    全局工具配置
    
    定义工具策略的顶层配置。
    """
    
    profile: str = Field(
        default="coding",
        description="默认 Profile",
    )
    allow: list[str] = Field(
        default_factory=list,
        description="全局允许的工具列表",
    )
    deny: list[str] = Field(
        default_factory=list,
        description="全局禁止的工具列表（最高优先级）",
    )
    byProvider: dict[str, ProviderScopedPolicy] = Field(
        default_factory=dict,
        description="Provider 定向策略",
    )
    loopDetection: Optional[LoopDetectionConfig] = Field(
        default=None,
        description="循环检测配置",
    )
    
    @field_validator("profile")
    @classmethod
    def validate_profile(cls, v: str) -> str:
        if v not in [p.value for p in ProfileType]:
            raise ValueError(f"Invalid profile: {v}. Must be one of: {[p.value for p in ProfileType]}")
        return v


# =============================================================================
# 核心函数
# =============================================================================

def expand_group(pattern: str) -> list[str]:
    """
    展开工具组名
    
    如果 pattern 是 group:xxx 格式，返回对应的工具列表。
    否则返回单元素列表 [pattern]。
    
    Args:
        pattern: 工具名或组名（如 "group:fs" 或 "read"）
        
    Returns:
        展开后的工具名列表
        
    Examples:
        >>> expand_group("group:fs")
        ['read', 'write', 'edit', 'apply_patch']
        >>> expand_group("read")
        ['read']
        >>> expand_group("unknown_group")
        ['unknown_group']
    """
    if pattern.startswith("group:"):
        group_name = pattern
        if group_name in TOOL_GROUPS:
            return TOOL_GROUPS[group_name].copy()
        else:
            logger.warning(
                "Unknown tool group",
                group=group_name,
            )
            return [pattern]
    return [pattern]


def expand_patterns(patterns: list[str]) -> set[str]:
    """
    展开多个模式（包含组名和工具名）
    
    Args:
        patterns: 模式列表
        
    Returns:
        展开后的工具名集合
    """
    result: set[str] = set()
    for pattern in patterns:
        expanded = expand_group(pattern)
        result.update(expanded)
    return result


def match_pattern(name: str, pattern: str) -> bool:
    """
    检查工具名是否匹配模式
    
    支持：
    - 精确匹配（大小写不敏感）
    - 通配符匹配（使用 * 通配符）
    
    Args:
        name: 工具名
        pattern: 匹配模式（支持 * 通配符）
        
    Returns:
        是否匹配
        
    Examples:
        >>> match_pattern("read", "read")
        True
        >>> match_pattern("read", "READ")
        True
        >>> match_pattern("read", "r*")
        True
        >>> match_pattern("read", "w*")
        False
        >>> match_pattern("sessions_list", "sessions_*")
        True
    """
    # 大小写不敏感
    name_lower = name.lower()
    pattern_lower = pattern.lower()
    
    # 精确匹配
    if name_lower == pattern_lower:
        return True
    
    # 通配符匹配
    if "*" in pattern_lower:
        # 使用 fnmatch 进行通配符匹配
        return fnmatch.fnmatch(name_lower, pattern_lower)
    
    return False


def match_any_pattern(name: str, patterns: list[str]) -> bool:
    """
    检查工具名是否匹配任一模式
    
    Args:
        name: 工具名
        patterns: 模式列表
        
    Returns:
        是否匹配任一模式
    """
    return any(match_pattern(name, p) for p in patterns)


def get_profile_tools(profile: str) -> set[str]:
    """
    获取 Profile 对应的工具集
    
    Args:
        profile: Profile 名称
        
    Returns:
        工具名集合。full profile 返回空集合（表示不限制）。
        
    Raises:
        ValueError: 如果 profile 无效
    """
    if profile not in PROFILE_TOOLS:
        raise ValueError(f"Invalid profile: {profile}")
    
    tools = PROFILE_TOOLS[profile]
    return set(tools)  # full profile 返回空集合


def find_provider_policy(
    byProvider: dict[str, ProviderScopedPolicy],
    provider: str,
    model: Optional[str] = None,
) -> Optional[ProviderScopedPolicy]:
    """
    查找匹配的 Provider 策略
    
    匹配优先级：
    1. provider/model（精确匹配）
    2. provider（仅 provider 匹配）
    
    Args:
        byProvider: Provider 策略字典
        provider: Provider 名称
        model: 模型名称（可选）
        
    Returns:
        匹配的策略，未找到返回 None
    """
    # 优先匹配 provider/model
    if model:
        key = f"{provider}/{model}"
        if key in byProvider:
            return byProvider[key]
    
    # 匹配仅 provider
    if provider in byProvider:
        return byProvider[provider]
    
    return None


def merge_policies(
    global_config: ToolsConfig,
    agent_config: Optional[AgentToolsConfig] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    registry: Optional[ToolRegistry] = None,
) -> set[str]:
    """
    合并策略，返回有效工具集
    
    合并顺序（按优先级从低到高）：
    1. Profile 基础白名单
    2. Provider 定向策略（byProvider，只能缩小）
    3. Allow 白名单
    4. Deny 黑名单（最高优先级）
    
    Args:
        global_config: 全局工具配置
        agent_config: Agent 级配置（可选，覆盖全局配置）
        provider: Provider 名称（用于 byProvider 匹配）
        model: 模型名称（用于精确 byProvider 匹配）
        registry: 工具注册中心（用于验证工具是否存在）
        
    Returns:
        有效工具名集合
        
    Examples:
        >>> config = ToolsConfig(profile="coding")
        >>> tools = merge_policies(config)
        >>> "read" in tools
        True
    """
    # Step 1: 确定使用的 profile
    profile = global_config.profile
    if agent_config and agent_config.profile is not None:
        profile = agent_config.profile
    
    # Step 2: 从 profile 获取基础工具集
    if profile == ProfileType.FULL:
        # full profile 不限制，从注册中心获取所有工具
        if registry:
            effective_tools = set(registry.tools.keys())
        else:
            # 无注册中心时使用所有已知工具
            effective_tools = ALL_KNOWN_TOOLS.copy()
    else:
        effective_tools = get_profile_tools(profile)
    
    logger.debug(
        "Initial tools from profile",
        profile=profile,
        tool_count=len(effective_tools),
    )
    
    # Step 3: 应用全局 byProvider 策略
    if provider and global_config.byProvider:
        provider_policy = find_provider_policy(
            global_config.byProvider, provider, model
        )
        if provider_policy:
            effective_tools = _apply_provider_policy(
                effective_tools, provider_policy
            )
            logger.debug(
                "Applied global byProvider policy",
                provider=provider,
                model=model,
                tool_count=len(effective_tools),
            )
    
    # Step 4: 应用 agent 级 byProvider 策略
    if provider and agent_config and agent_config.byProvider:
        agent_provider_policy = find_provider_policy(
            agent_config.byProvider, provider, model
        )
        if agent_provider_policy:
            effective_tools = _apply_provider_policy(
                effective_tools, agent_provider_policy
            )
            logger.debug(
                "Applied agent byProvider policy",
                provider=provider,
                model=model,
                tool_count=len(effective_tools),
            )
    
    # Step 5: 合并 allow 列表
    allow_patterns = list(global_config.allow)
    if agent_config and agent_config.allow is not None:
        allow_patterns = agent_config.allow
    
    if allow_patterns:
        allow_tools = expand_patterns(allow_patterns)
        # 验证 allow 列表中的工具
        if registry:
            unknown_tools = allow_tools - set(registry.tools.keys())
            if unknown_tools and not allow_tools.isdisjoint(effective_tools):
                # 如果 allow 包含未知工具但仍有已知工具，记录警告
                logger.warning(
                    "Allow list contains unknown tools",
                    unknown_tools=list(unknown_tools),
                )
        
        # allow 扩展工具集（但不能超过 profile 限制）
        effective_tools = effective_tools.union(allow_tools)
    
    # Step 6: 合并 deny 列表（最高优先级）
    deny_patterns = list(global_config.deny)
    if agent_config and agent_config.deny is not None:
        deny_patterns = agent_config.deny
    
    if deny_patterns:
        # 展开并过滤 deny 工具
        for pattern in deny_patterns:
            expanded = expand_group(pattern)
            for tool in expanded:
                if match_any_pattern(tool, [pattern]):
                    effective_tools.discard(tool)
                else:
                    # 直接匹配
                    effective_tools.discard(tool)
        
        logger.debug(
            "Applied deny list",
            deny_patterns=deny_patterns,
            tool_count=len(effective_tools),
        )
    
    logger.info(
        "Policy merge complete",
        profile=profile,
        provider=provider,
        model=model,
        effective_tool_count=len(effective_tools),
    )
    
    return effective_tools


def _apply_provider_policy(
    current_tools: set[str],
    policy: ProviderScopedPolicy,
) -> set[str]:
    """
    应用 Provider 定向策略
    
    Provider 策略只能缩小工具集，不能扩大。
    
    Args:
        current_tools: 当前工具集
        policy: Provider 策略
        
    Returns:
        应用策略后的工具集
    """
    result = current_tools.copy()
    
    # 如果 policy 定义了 profile，使用 profile 的工具集作为基础
    if policy.profile:
        profile_tools = get_profile_tools(policy.profile)
        result = result.intersection(profile_tools)
    
    # 应用 allow（在当前范围内）
    if policy.allow:
        allow_tools = expand_patterns(policy.allow)
        result = result.intersection(allow_tools)
    
    # 应用 deny
    if policy.deny:
        for pattern in policy.deny:
            expanded = expand_group(pattern)
            for tool in expanded:
                result.discard(tool)
    
    return result


def get_effective_tools(
    global_config: ToolsConfig,
    agent_config: Optional[AgentToolsConfig] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    registry: Optional[ToolRegistry] = None,
) -> set[str]:
    """
    获取有效工具集（merge_policies 的别名，提供更语义化的接口）
    
    Args:
        global_config: 全局工具配置
        agent_config: Agent 级配置
        provider: Provider 名称
        model: 模型名称
        registry: 工具注册中心
        
    Returns:
        有效工具名集合
    """
    return merge_policies(
        global_config=global_config,
        agent_config=agent_config,
        provider=provider,
        model=model,
        registry=registry,
    )


def is_tool_allowed(
    tool_name: str,
    global_config: ToolsConfig,
    agent_config: Optional[AgentToolsConfig] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    registry: Optional[ToolRegistry] = None,
) -> bool:
    """
    检查指定工具是否被允许使用
    
    Args:
        tool_name: 工具名称
        global_config: 全局工具配置
        agent_config: Agent 级配置
        provider: Provider 名称
        model: 模型名称
        registry: 工具注册中心
        
    Returns:
        工具是否被允许
    """
    effective_tools = get_effective_tools(
        global_config=global_config,
        agent_config=agent_config,
        provider=provider,
        model=model,
        registry=registry,
    )
    
    return tool_name.lower() in {t.lower() for t in effective_tools}


def validate_config(config: ToolsConfig) -> tuple[bool, list[str]]:
    """
    验证配置的有效性
    
    Args:
        config: 工具配置
        
    Returns:
        (是否有效，错误信息列表)
    """
    errors: list[str] = []
    
    # 验证 profile
    if config.profile not in [p.value for p in ProfileType]:
        errors.append(f"Invalid profile: {config.profile}")
    
    # 验证 byProvider 中的 profile
    for provider_key, policy in config.byProvider.items():
        if policy.profile and policy.profile not in [p.value for p in ProfileType]:
            errors.append(
                f"Invalid profile in byProvider['{provider_key}']: {policy.profile}"
            )
    
    # 警告：如果 allow 只包含未知工具
    if config.allow:
        allow_tools = expand_patterns(config.allow)
        unknown = allow_tools - ALL_KNOWN_TOOLS
        if unknown and not allow_tools.intersection(ALL_KNOWN_TOOLS):
            errors.append(
                f"Allow list only contains unknown tools: {unknown}. "
                "This may result in empty tool set."
            )
    
    return len(errors) == 0, errors


# =============================================================================
# 策略引擎类
# =============================================================================

class ToolPolicyEngine:
    """
    工具策略引擎

    封装策略配置和工具过滤逻辑，提供简洁的接口。

    使用示例:
        engine = ToolPolicyEngine(ToolsConfig(profile="coding"))
        tools = engine.filter_tools(all_tools, agent_id, provider, model)
    """

    def __init__(self, config: Optional[ToolsConfig] = None):
        """
        初始化策略引擎

        Args:
            config: 工具配置，默认使用 coding profile
        """
        self.config = config or ToolsConfig(profile=ProfileType.CODING)
        self._agent_configs: dict[str, AgentToolsConfig] = {}
        self.logger = logger.bind(component="ToolPolicyEngine")

    def set_agent_config(self, agent_id: str, config: AgentToolsConfig) -> None:
        """设置 Agent 级配置"""
        self._agent_configs[agent_id] = config
        self.logger.debug("Agent config set", agent_id=agent_id)

    def get_agent_config(self, agent_id: str) -> Optional[AgentToolsConfig]:
        """获取 Agent 级配置"""
        return self._agent_configs.get(agent_id)

    def filter_tools(
        self,
        all_tools: set[str],
        agent_id: str,
        provider: str = "default",
        model: str = "default",
    ) -> set[str]:
        """
        过滤工具集

        Args:
            all_tools: 所有可用工具
            agent_id: Agent ID
            provider: Provider 名称
            model: 模型名称

        Returns:
            过滤后的工具集
        """
        agent_config = self._agent_configs.get(agent_id)

        effective_tools = merge_policies(
            global_config=self.config,
            agent_config=agent_config,
            provider=provider,
            model=model,
        )

        # 确保只返回实际存在的工具
        return effective_tools.intersection(all_tools)

    def is_tool_allowed(
        self,
        tool_name: str,
        agent_id: str,
        provider: str = "default",
        model: str = "default",
    ) -> bool:
        """检查工具是否被允许"""
        effective_tools = self.filter_tools(
            set([tool_name]), agent_id, provider, model
        )
        return tool_name in effective_tools


# =============================================================================
# 全局策略引擎实例
# =============================================================================

_policy_engine: Optional[ToolPolicyEngine] = None


def get_policy_engine() -> ToolPolicyEngine:
    """获取全局策略引擎实例"""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = ToolPolicyEngine()
    return _policy_engine


def create_policy_engine(config: Optional[ToolsConfig] = None) -> ToolPolicyEngine:
    """
    创建策略引擎实例

    Args:
        config: 工具配置

    Returns:
        策略引擎实例
    """
    return ToolPolicyEngine(config)


# =============================================================================
# 便捷函数
# =============================================================================

def create_minimal_config() -> ToolsConfig:
    """创建 minimal profile 配置"""
    return ToolsConfig(profile=ProfileType.MINIMAL)


def create_coding_config() -> ToolsConfig:
    """创建 coding profile 配置"""
    return ToolsConfig(profile=ProfileType.CODING)


def create_messaging_config() -> ToolsConfig:
    """创建 messaging profile 配置"""
    return ToolsConfig(profile=ProfileType.MESSAGING)


def create_full_config() -> ToolsConfig:
    """创建 full profile 配置"""
    return ToolsConfig(profile=ProfileType.FULL)
