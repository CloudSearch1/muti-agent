"""
工具策略引擎单元测试

测试覆盖：
1. Profile 预设配置验证
2. Tool Group 展开机制
3. 模式匹配（通配符、大小写不敏感）
4. 策略合并逻辑
5. Provider 定向策略
6. Agent 级配置覆盖
"""

import pytest
from pydantic import ValidationError

from src.tools.policy import (
    TOOL_GROUPS,
    PROFILE_TOOLS,
    ALL_KNOWN_TOOLS,
    ProfileType,
    ToolsConfig,
    AgentToolsConfig,
    ProviderScopedPolicy,
    LoopDetectionConfig,
    expand_group,
    expand_patterns,
    match_pattern,
    match_any_pattern,
    get_profile_tools,
    find_provider_policy,
    merge_policies,
    get_effective_tools,
    is_tool_allowed,
    validate_config,
    create_minimal_config,
    create_coding_config,
    create_messaging_config,
    create_full_config,
    _apply_provider_policy,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def basic_config():
    """基础配置"""
    return ToolsConfig(profile="coding")


@pytest.fixture
def full_config():
    """Full profile 配置"""
    return ToolsConfig(profile="full")


@pytest.fixture
def config_with_deny():
    """带 deny 的配置"""
    return ToolsConfig(
        profile="coding",
        deny=["exec"],
    )


@pytest.fixture
def config_with_by_provider():
    """带 byProvider 的配置"""
    return ToolsConfig(
        profile="coding",
        byProvider={
            "openai": ProviderScopedPolicy(deny=["exec"]),
            "anthropic/claude-opus": ProviderScopedPolicy(allow=["read", "write"]),
        },
    )


# =============================================================================
# Tool Groups 测试
# =============================================================================

class TestToolGroups:
    """测试 Tool Group 定义"""
    
    def test_group_runtime(self):
        """测试 group:runtime"""
        assert "group:runtime" in TOOL_GROUPS
        assert set(TOOL_GROUPS["group:runtime"]) == {"exec", "bash", "process"}
    
    def test_group_fs(self):
        """测试 group:fs"""
        assert "group:fs" in TOOL_GROUPS
        assert set(TOOL_GROUPS["group:fs"]) == {"read", "write", "edit", "apply_patch"}
    
    def test_group_sessions(self):
        """测试 group:sessions"""
        assert "group:sessions" in TOOL_GROUPS
        expected = {"sessions_list", "sessions_history", "sessions_send", "sessions_spawn", "session_status"}
        assert set(TOOL_GROUPS["group:sessions"]) == expected
    
    def test_group_memory(self):
        """测试 group:memory"""
        assert "group:memory" in TOOL_GROUPS
        assert set(TOOL_GROUPS["group:memory"]) == {"memory_search", "memory_get"}
    
    def test_group_web(self):
        """测试 group:web"""
        assert "group:web" in TOOL_GROUPS
        assert set(TOOL_GROUPS["group:web"]) == {"web_search", "web_fetch"}
    
    def test_group_openclaw(self):
        """测试 group:openclaw"""
        assert "group:openclaw" in TOOL_GROUPS
        # 应该包含大部分内置工具
        assert "exec" in TOOL_GROUPS["group:openclaw"]
        assert "read" in TOOL_GROUPS["group:openclaw"]
        assert "browser" in TOOL_GROUPS["group:openclaw"]


# =============================================================================
# expand_group 测试
# =============================================================================

class TestExpandGroup:
    """测试 expand_group 函数"""
    
    def test_expand_group_fs(self):
        """测试展开 group:fs"""
        result = expand_group("group:fs")
        assert set(result) == {"read", "write", "edit", "apply_patch"}
    
    def test_expand_group_runtime(self):
        """测试展开 group:runtime"""
        result = expand_group("group:runtime")
        assert set(result) == {"exec", "bash", "process"}
    
    def test_expand_single_tool(self):
        """测试单个工具名不展开"""
        result = expand_group("read")
        assert result == ["read"]
    
    def test_expand_unknown_group(self):
        """测试未知组名返回原值"""
        result = expand_group("group:unknown")
        assert result == ["group:unknown"]
    
    def test_expand_patterns_multiple(self):
        """测试展开多个模式"""
        result = expand_patterns(["read", "group:fs"])
        assert "read" in result
        assert "write" in result
        assert "edit" in result
        assert "apply_patch" in result


# =============================================================================
# match_pattern 测试
# =============================================================================

class TestMatchPattern:
    """测试 match_pattern 函数"""
    
    def test_exact_match(self):
        """测试精确匹配"""
        assert match_pattern("read", "read") is True
        assert match_pattern("write", "write") is True
    
    def test_case_insensitive(self):
        """测试大小写不敏感"""
        assert match_pattern("read", "READ") is True
        assert match_pattern("READ", "read") is True
        assert match_pattern("Read", "READ") is True
    
    def test_wildcard_prefix(self):
        """测试前缀通配符"""
        assert match_pattern("read", "r*") is True
        assert match_pattern("write", "w*") is True
        assert match_pattern("read", "x*") is False
    
    def test_wildcard_suffix(self):
        """测试后缀通配符"""
        assert match_pattern("sessions_list", "*_list") is True
        assert match_pattern("sessions_history", "*_list") is False
    
    def test_wildcard_middle(self):
        """测试中间通配符"""
        assert match_pattern("sessions_list", "sessions_*") is True
        assert match_pattern("session_status", "session_*") is True
        assert match_pattern("exec", "ex*") is True
    
    def test_wildcard_all(self):
        """测试全匹配通配符"""
        assert match_pattern("anything", "*") is True
        assert match_pattern("read", "*") is True
    
    def test_match_any_pattern(self):
        """测试匹配任一模式"""
        assert match_any_pattern("read", ["w*", "r*"]) is True
        assert match_any_pattern("exec", ["x*", "y*"]) is False
        assert match_any_pattern("sessions_list", ["sessions_*", "exec"]) is True


# =============================================================================
# Profile 测试
# =============================================================================

class TestProfiles:
    """测试 Profile 配置"""
    
    def test_profile_types(self):
        """测试 Profile 枚举值"""
        assert ProfileType.MINIMAL.value == "minimal"
        assert ProfileType.CODING.value == "coding"
        assert ProfileType.MESSAGING.value == "messaging"
        assert ProfileType.FULL.value == "full"
    
    def test_minimal_profile_tools(self):
        """测试 minimal profile 工具集"""
        tools = get_profile_tools("minimal")
        assert tools == {"session_status"}
    
    def test_coding_profile_tools(self):
        """测试 coding profile 工具集"""
        tools = get_profile_tools("coding")
        # 应包含 fs 工具
        assert "read" in tools
        assert "write" in tools
        assert "edit" in tools
        # 应包含 runtime 工具
        assert "exec" in tools
        assert "bash" in tools
        assert "process" in tools
        # 应包含 sessions 工具
        assert "sessions_list" in tools
        assert "session_status" in tools
        # 应包含 memory 工具
        assert "memory_search" in tools
        # 应包含 image
        assert "image" in tools
        # 不应包含 web 工具
        assert "web_search" not in tools
        assert "browser" not in tools
    
    def test_messaging_profile_tools(self):
        """测试 messaging profile 工具集"""
        tools = get_profile_tools("messaging")
        # 应包含 message
        assert "message" in tools
        # 应包含特定 sessions 工具
        assert "sessions_list" in tools
        assert "sessions_send" in tools
        assert "session_status" in tools
        # 不应包含 fs 或 runtime
        assert "read" not in tools
        assert "exec" not in tools
    
    def test_full_profile_tools(self):
        """测试 full profile 工具集"""
        tools = get_profile_tools("full")
        # full profile 返回空集合（表示不限制）
        assert tools == set()
    
    def test_invalid_profile(self):
        """测试无效 profile"""
        with pytest.raises(ValueError):
            get_profile_tools("invalid")


# =============================================================================
# 配置模型验证测试
# =============================================================================

class TestConfigModels:
    """测试配置模型"""
    
    def test_tools_config_default(self):
        """测试默认配置"""
        config = ToolsConfig()
        assert config.profile == "coding"
        assert config.allow == []
        assert config.deny == []
        assert config.byProvider == {}
    
    def test_tools_config_invalid_profile(self):
        """测试无效 profile"""
        with pytest.raises(ValidationError):
            ToolsConfig(profile="invalid")
    
    def test_provider_scoped_policy(self):
        """测试 Provider 策略"""
        policy = ProviderScopedPolicy(deny=["exec"])
        assert policy.deny == ["exec"]
        assert policy.allow is None
        assert policy.profile is None
    
    def test_provider_scoped_policy_invalid_profile(self):
        """测试 Provider 策略无效 profile"""
        with pytest.raises(ValidationError):
            ProviderScopedPolicy(profile="invalid")
    
    def test_agent_tools_config(self):
        """测试 Agent 配置"""
        config = AgentToolsConfig(deny=["exec"])
        assert config.deny == ["exec"]
        assert config.profile is None
        assert config.allow is None
    
    def test_loop_detection_config(self):
        """测试循环检测配置"""
        config = LoopDetectionConfig(
            enabled=True,
            warning_threshold=5,
            critical_threshold=10,
        )
        assert config.enabled is True
        assert config.warning_threshold == 5
        assert config.critical_threshold == 10
        assert "genericRepeat" in config.detectors
    
    def test_tools_config_with_loop_detection(self):
        """测试带循环检测的配置"""
        config = ToolsConfig(
            loopDetection=LoopDetectionConfig(enabled=True)
        )
        assert config.loopDetection is not None
        assert config.loopDetection.enabled is True


# =============================================================================
# find_provider_policy 测试
# =============================================================================

class TestFindProviderPolicy:
    """测试 find_provider_policy 函数"""
    
    def test_find_provider_only(self):
        """测试仅 provider 匹配"""
        byProvider = {
            "openai": ProviderScopedPolicy(deny=["exec"]),
        }
        policy = find_provider_policy(byProvider, "openai")
        assert policy is not None
        assert policy.deny == ["exec"]
    
    def test_find_provider_model(self):
        """测试 provider/model 精确匹配"""
        byProvider = {
            "openai": ProviderScopedPolicy(deny=["exec"]),
            "openai/gpt-4": ProviderScopedPolicy(deny=["bash"]),
        }
        # 应匹配 provider/model
        policy = find_provider_policy(byProvider, "openai", "gpt-4")
        assert policy is not None
        assert policy.deny == ["bash"]
    
    def test_find_provider_fallback(self):
        """测试 provider/model 未匹配时回退到 provider"""
        byProvider = {
            "openai": ProviderScopedPolicy(deny=["exec"]),
        }
        # gpt-4 未定义，应回退到 openai
        policy = find_provider_policy(byProvider, "openai", "gpt-4")
        assert policy is not None
        assert policy.deny == ["exec"]
    
    def test_find_provider_not_found(self):
        """测试未找到匹配"""
        byProvider = {
            "openai": ProviderScopedPolicy(deny=["exec"]),
        }
        policy = find_provider_policy(byProvider, "anthropic")
        assert policy is None


# =============================================================================
# merge_policies 测试
# =============================================================================

class TestMergePolicies:
    """测试策略合并"""
    
    def test_merge_basic(self, basic_config):
        """测试基本合并"""
        tools = merge_policies(basic_config)
        # 应包含 coding profile 的工具
        assert "read" in tools
        assert "exec" in tools
        # 不应包含 web 工具
        assert "web_search" not in tools
    
    def test_merge_with_deny(self, config_with_deny):
        """测试 deny 列表"""
        tools = merge_policies(config_with_deny)
        # exec 应被排除
        assert "exec" not in tools
        # 其他工具应保留
        assert "read" in tools
        assert "bash" in tools
    
    def test_merge_deny_priority(self):
        """测试 deny 优先于 allow"""
        config = ToolsConfig(
            profile="coding",
            allow=["exec"],
            deny=["exec"],
        )
        tools = merge_policies(config)
        # deny 应优先，exec 不应存在
        assert "exec" not in tools
    
    def test_merge_with_agent_config(self, basic_config):
        """测试 agent 级配置覆盖"""
        agent_config = AgentToolsConfig(deny=["exec"])
        tools = merge_policies(basic_config, agent_config=agent_config)
        assert "exec" not in tools
    
    def test_merge_agent_profile_override(self):
        """测试 agent profile 覆盖全局"""
        global_config = ToolsConfig(profile="coding")
        agent_config = AgentToolsConfig(profile="minimal")
        tools = merge_policies(global_config, agent_config=agent_config)
        # 应只有 minimal 的工具
        assert tools == {"session_status"}
    
    def test_merge_with_by_provider(self, config_with_by_provider):
        """测试 byProvider 策略"""
        # 测试 openai provider
        tools = merge_policies(config_with_by_provider, provider="openai")
        assert "exec" not in tools  # 被 byProvider 禁止
        
        # 测试 anthropic/claude-opus provider/model
        tools = merge_policies(
            config_with_by_provider, 
            provider="anthropic", 
            model="claude-opus"
        )
        # 应只有 allow 中的工具
        assert "read" in tools
        assert "write" in tools
    
    def test_merge_by_provider_shrink_only(self):
        """测试 byProvider 只能缩小工具集"""
        # byProvider 中的 allow 应限制工具集
        config = ToolsConfig(
            profile="coding",
            byProvider={
                "openai": ProviderScopedPolicy(allow=["read"]),
            },
        )
        tools = merge_policies(config, provider="openai")
        # 应只有 read（byProvider 限制了范围）
        assert "read" in tools
    
    def test_merge_full_profile(self, full_config):
        """测试 full profile"""
        tools = merge_policies(full_config)
        # full profile 不限制，应包含所有已知工具
        # 由于没有 registry，使用 ALL_KNOWN_TOOLS
        assert len(tools) > 0
    
    def test_merge_wildcard_deny(self):
        """测试通配符 deny"""
        config = ToolsConfig(
            profile="coding",
            deny=["sessions_*"],
        )
        tools = merge_policies(config)
        # 所有 sessions_ 开头的工具应被排除
        assert "sessions_list" not in tools
        assert "sessions_send" not in tools
        assert "session_status" not in tools
        # 其他工具应保留
        assert "read" in tools
    
    def test_merge_wildcard_allow(self):
        """测试通配符 allow"""
        config = ToolsConfig(
            profile="minimal",
            allow=["r*"],
        )
        tools = merge_policies(config)
        # 应包含 r* 匹配的工具
        assert "read" in tools


# =============================================================================
# is_tool_allowed 测试
# =============================================================================

class TestIsToolAllowed:
    """测试 is_tool_allowed 函数"""
    
    def test_allowed_tool(self, basic_config):
        """测试允许的工具"""
        assert is_tool_allowed("read", basic_config) is True
        assert is_tool_allowed("exec", basic_config) is True
    
    def test_denied_tool(self, config_with_deny):
        """测试禁止的工具"""
        assert is_tool_allowed("exec", config_with_deny) is False
        assert is_tool_allowed("read", config_with_deny) is True
    
    def test_case_insensitive(self, basic_config):
        """测试大小写不敏感"""
        assert is_tool_allowed("READ", basic_config) is True
        assert is_tool_allowed("Read", basic_config) is True


# =============================================================================
# validate_config 测试
# =============================================================================

class TestValidateConfig:
    """测试配置验证"""
    
    def test_valid_config(self, basic_config):
        """测试有效配置"""
        valid, errors = validate_config(basic_config)
        assert valid is True
        assert errors == []
    
    def test_invalid_profile_in_by_provider(self):
        """测试 byProvider 中无效的 profile"""
        config = ToolsConfig(
            profile="coding",
            byProvider={
                "openai": ProviderScopedPolicy(profile="invalid"),
            },
        )
        # ProviderScopedPolicy 应该在构造时验证失败
        with pytest.raises(ValidationError):
            config = ToolsConfig(
                profile="coding",
                byProvider={
                    "openai": ProviderScopedPolicy(profile="invalid"),
                },
            )


# =============================================================================
# 便捷函数测试
# =============================================================================

class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def test_create_minimal_config(self):
        """测试创建 minimal 配置"""
        config = create_minimal_config()
        assert config.profile == "minimal"
    
    def test_create_coding_config(self):
        """测试创建 coding 配置"""
        config = create_coding_config()
        assert config.profile == "coding"
    
    def test_create_messaging_config(self):
        """测试创建 messaging 配置"""
        config = create_messaging_config()
        assert config.profile == "messaging"
    
    def test_create_full_config(self):
        """测试创建 full 配置"""
        config = create_full_config()
        assert config.profile == "full"


# =============================================================================
# _apply_provider_policy 测试
# =============================================================================

class TestApplyProviderPolicy:
    """测试 _apply_provider_policy 函数"""
    
    def test_apply_deny(self):
        """测试应用 deny"""
        current = {"read", "write", "exec"}
        policy = ProviderScopedPolicy(deny=["exec"])
        result = _apply_provider_policy(current, policy)
        assert "exec" not in result
        assert "read" in result
        assert "write" in result
    
    def test_apply_allow_shrink(self):
        """测试应用 allow 缩小范围"""
        current = {"read", "write", "exec", "bash"}
        policy = ProviderScopedPolicy(allow=["read", "write"])
        result = _apply_provider_policy(current, policy)
        assert result == {"read", "write"}
    
    def test_apply_profile(self):
        """测试应用 profile"""
        current = {"read", "write", "exec", "web_search", "browser"}
        policy = ProviderScopedPolicy(profile="minimal")
        result = _apply_provider_policy(current, policy)
        assert result == {"session_status"}
    
    def test_cannot_expand(self):
        """测试不能扩大工具集"""
        current = {"read", "write"}
        policy = ProviderScopedPolicy(allow=["read", "write", "exec"])
        result = _apply_provider_policy(current, policy)
        # 不应添加 exec（不能扩大）
        assert result == {"read", "write"}


# =============================================================================
# 边界情况测试
# =============================================================================

class TestEdgeCases:
    """测试边界情况"""
    
    def test_empty_allow_deny(self):
        """测试空的 allow/deny"""
        config = ToolsConfig(profile="coding", allow=[], deny=[])
        tools = merge_policies(config)
        # 应等同于基本 coding profile
        assert "read" in tools
        assert "exec" in tools
    
    def test_all_tools_denied(self):
        """测试禁止所有工具"""
        config = ToolsConfig(profile="coding", deny=["*"])
        tools = merge_policies(config)
        # 应为空集
        assert len(tools) == 0
    
    def test_agent_config_none(self, basic_config):
        """测试 agent_config 为 None"""
        tools = merge_policies(basic_config, agent_config=None)
        assert "read" in tools
    
    def test_provider_none(self, basic_config):
        """测试 provider 为 None"""
        tools = merge_policies(basic_config, provider=None)
        assert "read" in tools
    
    def test_get_effective_tools_alias(self, basic_config):
        """测试 get_effective_tools 是 merge_policies 的别名"""
        tools1 = merge_policies(basic_config)
        tools2 = get_effective_tools(basic_config)
        assert tools1 == tools2


# =============================================================================
# 集成测试
# =============================================================================

class TestIntegration:
    """集成测试"""
    
    def test_complete_scenario(self):
        """测试完整场景"""
        # 创建全局配置
        global_config = ToolsConfig(
            profile="coding",
            deny=["bash"],  # 全局禁止 bash
            byProvider={
                "openai": ProviderScopedPolicy(deny=["exec"]),
            },
        )
        
        # 创建 agent 配置
        agent_config = AgentToolsConfig(
            allow=["web_search"],  # agent 需要 web_search
        )
        
        # 合并策略
        tools = merge_policies(
            global_config,
            agent_config=agent_config,
            provider="openai",
        )
        
        # 验证结果
        assert "bash" not in tools  # 全局 deny
        assert "exec" not in tools  # provider deny
        assert "read" in tools  # coding profile
        assert "web_search" in tools  # agent allow
    
    def test_messaging_with_sessions(self):
        """测试 messaging profile 配合 sessions"""
        config = ToolsConfig(
            profile="messaging",
            allow=["sessions_spawn"],
        )
        tools = merge_policies(config)
        
        # messaging profile 的工具
        assert "message" in tools
        assert "sessions_list" in tools
        # allow 添加的
        assert "sessions_spawn" in tools
        # 不应有 fs/runtime
        assert "read" not in tools
        assert "exec" not in tools


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
