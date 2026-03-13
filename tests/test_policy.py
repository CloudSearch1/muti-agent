"""
策略引擎单元测试
"""

import pytest

from src.tools.policy import (
    ToolsConfig,
    AgentToolsConfig,
    ProviderScopedPolicy,
    merge_policies,
    get_profile_tools,
    expand_patterns,
    expand_group,
    get_effective_tools,
    is_tool_allowed,
)


class TestToolsConfig:
    """测试 ToolsConfig 模型"""

    def test_default_profile(self):
        """测试默认 profile 为 coding"""
        config = ToolsConfig()
        assert config.profile == "coding"

    def test_profile_only(self):
        """测试仅 profile"""
        config = ToolsConfig(profile="minimal")
        assert config.profile == "minimal"


class TestAgentToolsConfig:
    """测试 AgentToolsConfig 模型"""

    def test_default_values(self):
        """测试默认值"""
        config = AgentToolsConfig()
        assert config.profile is None
        assert config.allow is None
        assert config.deny is None


class TestProviderScopedPolicy:
    """测试 ProviderScopedPolicy 模型"""

    def test_default_values(self):
        """测试默认值"""
        policy = ProviderScopedPolicy()
        assert policy.profile is None
        assert policy.allow is None
        assert policy.deny is None


class TestMergePolicies:
    """测试 merge_policies 函数"""

    def test_default_config(self):
        """测试默认配置"""
        config = ToolsConfig()  # 默认 profile="coding"
        tools = merge_policies(config)
        assert len(tools) > 0
        assert "read" in tools

    def test_minimal_profile(self):
        """测试 minimal profile"""
        config = ToolsConfig(profile="minimal")
        tools = merge_policies(config)
        assert "session_status" in tools

    def test_deny_exec(self):
        """测试 deny exec"""
        config = ToolsConfig(profile="coding", deny=["exec"])
        tools = merge_policies(config)
        assert "exec" not in tools
        assert "read" in tools


class TestHelperFunctions:
    """测试辅助函数"""

    def test_get_profile_tools_coding(self):
        """测试获取 coding profile 工具"""
        tools = get_profile_tools("coding")
        assert len(tools) > 0
        assert "read" in tools

    def test_get_profile_tools_minimal(self):
        """测试获取 minimal profile 工具"""
        tools = get_profile_tools("minimal")
        assert "session_status" in tools

    def test_expand_group(self):
        """测试组展开"""
        expanded = expand_group("group:fs")
        assert len(expanded) > 0


class TestAdvancedAPI:
    """测试高级 API"""

    def test_get_effective_tools(self):
        """测试 get_effective_tools"""
        config = ToolsConfig(profile="coding")
        tools = get_effective_tools(config)
        assert len(tools) > 0

    def test_is_tool_allowed(self):
        """测试 is_tool_allowed"""
        config = ToolsConfig(profile="coding")
        assert is_tool_allowed("read", config) is True
