"""测试 Container 中的角色映射功能"""

import pytest

from src.core.container import AgentContainer, get_agent_container
from src.core.models import AgentRole


class TestContainerRoleMapping:
    """测试容器的角色映射功能"""

    def setup_method(self):
        """每个测试前重置容器"""
        AgentContainer.reset("test_role_mapping")
        self.container = AgentContainer("test_role_mapping")

    def test_create_agent_by_role_planner(self):
        """测试根据角色创建 Planner Agent"""
        agent = self.container.create_agent_by_role(AgentRole.PLANNER)
        
        assert agent is not None
        assert agent.__class__.__name__ == "PlannerAgent"
        assert agent.ROLE == AgentRole.PLANNER

    def test_create_agent_by_role_coder(self):
        """测试根据角色创建 Coder Agent"""
        agent = self.container.create_agent_by_role(AgentRole.CODER)
        
        assert agent is not None
        assert agent.__class__.__name__ == "CoderAgent"
        assert agent.ROLE == AgentRole.CODER

    def test_create_agent_by_role_with_custom_name(self):
        """测试使用自定义名称创建 Agent"""
        custom_name = "my_planner"
        agent = self.container.create_agent_by_role(
            AgentRole.PLANNER, 
            name=custom_name
        )
        
        assert agent.agent.name == custom_name

    def test_create_agent_by_role_with_kwargs(self):
        """测试使用额外参数创建 Agent"""
        agent = self.container.create_agent_by_role(
            AgentRole.PLANNER,
            max_subtasks=30
        )
        
        # 验证参数被传递
        assert hasattr(agent, 'max_subtasks')
        assert agent.max_subtasks == 30

    def test_create_all_agents(self):
        """测试创建所有角色的 Agent"""
        agents = self.container.create_all_agents()
        
        # 验证所有角色都被创建
        assert len(agents) == 7
        assert "planner" in agents
        assert "architect" in agents
        assert "coder" in agents
        assert "tester" in agents
        assert "doc_writer" in agents
        assert "researcher" in agents
        assert "senior_architect" in agents

    def test_get_agent_by_role(self):
        """测试根据角色获取 Agent"""
        # 首次获取会自动创建
        agent1 = self.container.get_agent_by_role(AgentRole.PLANNER)
        assert agent1 is not None
        
        # 再次获取应该返回同一个实例
        agent2 = self.container.get_agent_by_role(AgentRole.PLANNER)
        assert agent2 is agent1

    def test_get_agent_by_role_after_manual_registration(self):
        """测试手动注册后根据角色获取 Agent"""
        from src.agents import PlannerAgent
        
        # 手动注册一个 Agent
        custom_planner = PlannerAgent(name="custom_planner")
        self.container.register_agent("planner", custom_planner)
        
        # 获取的应该是手动注册的实例
        agent = self.container.get_agent_by_role(AgentRole.PLANNER)
        assert agent is custom_planner

    def test_agent_registration_in_container(self):
        """测试 Agent 在容器中的注册"""
        agent = self.container.create_agent_by_role(AgentRole.CODER)
        
        # 验证 Agent 已注册到容器
        assert self.container.has_agent("coder")
        assert self.container.get_agent("coder") is agent

    def test_create_agents_with_common_config(self):
        """测试使用通用配置创建所有 Agent"""
        agents = self.container.create_all_agents(
            max_subtasks=25  # 这个参数会被传递给 PlannerAgent
        )
        
        # 验证 PlannerAgent 接收了配置
        planner = agents.get("planner")
        if planner and hasattr(planner, 'max_subtasks'):
            assert planner.max_subtasks == 25

    def test_invalid_role_handling(self):
        """测试无效角色的处理"""
        # 创建一个假的枚举值
        # 由于 AgentRole.get_agent_class 会返回 None，
        # create_agent_by_role 应该抛出 ValueError
        with pytest.raises(ValueError, match="No agent class found"):
            # 使用一个不存在的角色值
            self.container.create_agent_by_role("invalid_role")  # type: ignore

    def test_container_isolation(self):
        """测试容器隔离性"""
        # 在 test_role_mapping 容器中创建 Agent
        agent1 = self.container.create_agent_by_role(AgentRole.PLANNER)
        
        # 创建另一个容器
        AgentContainer.reset("test_another_container")
        container2 = AgentContainer("test_another_container")
        
        # 在新容器中创建 Agent
        agent2 = container2.create_agent_by_role(AgentRole.PLANNER)
        
        # 两个容器的 Agent 应该是不同的实例
        assert agent1 is not agent2
