"""
PI-Python 测试夹具

提供 Agent 测试的工具和辅助函数
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncGenerator

import pytest

from ...agent import Agent
from ...agent.tools import AgentTool, ToolResult
from ...ai.types import TextContent

if TYPE_CHECKING:
    from ...agent.events import AgentEvent


class MockTool(AgentTool):
    """Mock 工具，用于测试"""
    
    def __init__(self, name: str = "mock_tool", return_value: str = "mock result"):
        self.name = name
        self.label = name
        self.description = f"A mock tool named {name}"
        self.parameters = {
            "input": {"type": "string", "description": "Input parameter"}
        }
        self.return_value = return_value
    
    async def execute(self, tool_call_id: str, params: dict, **kwargs) -> ToolResult:
        """执行 Mock 工具"""
        return ToolResult(
            content=[TextContent(text=self.return_value)],
            details={"mock": True, "params": params}
        )


class AgentTestFixture:
    """Agent 测试夹具
    
    提供便捷的 Agent 测试功能
    """
    
    def __init__(self, model: str = "openai/gpt-4o"):
        """
        初始化测试夹具
        
        Args:
            model: 模型名称 (格式: provider/model-id)
        """
        from ...ai import get_model
        
        try:
            provider, model_id = model.split("/", 1)
            self.model = get_model(provider, model_id)
        except Exception as e:
            raise ValueError(f"模型格式不正确: {e}")
        
        self.events: list[AgentEvent] = []
        self.captured_output: list[str] = []
    
    def create_agent(
        self,
        system_prompt: str = "You are a test assistant.",
        tools: list[AgentTool] | None = None,
        use_mock_tools: bool = True
    ) -> Agent:
        """
        创建测试 Agent
        
        Args:
            system_prompt: 系统提示词
            tools: 工具列表（如果为 None 且 use_mock_tools=True，则使用 Mock 工具）
            use_mock_tools: 是否使用 Mock 工具
            
        Returns:
            Agent 实例
        """
        from ...agent import AgentState
        
        if tools is None and use_mock_tools:
            tools = [MockTool()]
        elif tools is None:
            tools = []
        
        agent = Agent(
            initial_state=AgentState(
                system_prompt=system_prompt,
                model=self.model,
                tools=tools,
                messages=[]
            )
        )
        
        # 捕获事件
        agent.subscribe(self._capture_event)
        
        return agent
    
    def _capture_event(self, event: AgentEvent) -> None:
        """捕获 Agent 事件"""
        self.events.append(event)
        
        # 捕获输出
        if hasattr(event, 'type') and event.type == "message_update":
            if hasattr(event, 'delta') and event.delta:
                self.captured_output.append(event.delta)
    
    def get_events(self, event_type: str | None = None) -> list[AgentEvent]:
        """
        获取捕获的事件
        
        Args:
            event_type: 事件类型过滤（如果为 None，返回所有事件）
            
        Returns:
            事件列表
        """
        if event_type is None:
            return self.events
        
        return [
            event for event in self.events
            if hasattr(event, 'type') and event.type == event_type
        ]
    
    def get_output(self) -> str:
        """
        获取捕获的输出
        
        Returns:
            合并后的输出字符串
        """
        return "".join(self.captured_output)
    
    def clear_events(self) -> None:
        """清除捕获的事件"""
        self.events.clear()
        self.captured_output.clear()
    
    def assert_tool_called(self, tool_name: str) -> None:
        """
        断言工具被调用
        
        Args:
            tool_name: 工具名称
        
        Raises:
            AssertionError: 如果工具未被调用
        """
        tool_events = self.get_events("tool_execution_start")
        
        assert any(
            hasattr(event, 'tool_name') and event.tool_name == tool_name
            for event in tool_events
        ), f"工具 '{tool_name}' 未被调用"
    
    def assert_tool_not_called(self, tool_name: str) -> None:
        """
        断言工具未被调用
        
        Args:
            tool_name: 工具名称
        
        Raises:
            AssertionError: 如果工具被调用
        """
        tool_events = self.get_events("tool_execution_start")
        
        assert not any(
            hasattr(event, 'tool_name') and event.tool_name == tool_name
            for event in tool_events
        ), f"工具 '{tool_name}' 被调用了"
    
    def assert_no_errors(self) -> None:
        """
        断言没有错误
        
        Raises:
            AssertionError: 如果发生错误
        """
        error_events = self.get_events("error")
        
        assert len(error_events) == 0, (
            f"发生 {len(error_events)} 个错误: "
            + ", ".join([
                getattr(event, 'error', '未知错误')
                for event in error_events
            ])
        )
    
    def assert_output_contains(self, text: str) -> None:
        """
        断言输出包含指定文本
        
        Args:
            text: 要检查的文本
        
        Raises:
            AssertionError: 如果输出不包含指定文本
        """
        output = self.get_output()
        
        assert text in output, (
            f"输出中不包含 '{text}'\n"
            f"实际输出: {output[:200]}..."
        )
    
    def assert_event_fired(self, event_type: str) -> None:
        """
        断言事件被触发
        
        Args:
            event_type: 事件类型
        
        Raises:
            AssertionError: 如果事件未触发
        """
        events = self.get_events(event_type)
        
        assert len(events) > 0, f"事件 '{event_type}' 未被触发"
    
    async def run_prompt(
        self,
        agent: Agent,
        prompt: str,
        clear_events: bool = True
    ) -> str:
        """
        运行提示并返回输出
        
        Args:
            agent: Agent 实例
            prompt: 提示文本
            clear_events: 运行前是否清除事件
            
        Returns:
            Agent 输出字符串
        """
        if clear_events:
            self.clear_events()
        
        await agent.prompt(prompt)
        
        # 等待所有事件处理完成
        await asyncio.sleep(0.1)
        
        return self.get_output()
    
    @staticmethod
       def create_mock_tool(name: str = "mock_tool", return_value: str = "mock result") -> MockTool:
        """
        创建 Mock 工具
        
        Args:
            name: 工具名称
            return_value: 返回值
            
        Returns:
            MockTool 实例
        """
        return MockTool(name, return_value)


# pytest fixtures
@pytest.fixture
def agent_fixture() -> AgentTestFixture:
    """pytest 夹具 - 创建测试夹具"""
    return AgentTestFixture()


@pytest.fixture
async def mock_agent(agent_fixture) -> AsyncGenerator[Agent, None]:
    """pytest 夹具 - 创建带有 Mock 工具的 Agent"""
    agent = agent_fixture.create_agent()
    yield agent
    # 清理
    agent_fixture.clear_events()
