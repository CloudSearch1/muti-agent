"""
自动化测试配置

pytest 配置和测试工具
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============ pytest 配置 ============

def pytest_configure(config):
    """pytest 配置"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


# ============ 测试夹具 ============

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_llm():
    """Mock LLM 提供商"""
    llm = MagicMock()
    llm.generate = AsyncMock(return_value="mock response")
    llm.generate_json = AsyncMock(return_value={"status": "success"})
    return llm


@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_cache():
    """Mock 缓存"""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    return cache


@pytest.fixture
def sample_task():
    """示例任务"""
    from src.core.models import Task
    return Task(
        id="test-001",
        title="Test Task",
        description="Test Description",
        input_data={"requirements": ["test"]},
    )


@pytest.fixture
def sample_agent_config():
    """示例 Agent 配置"""
    return {
        "preferred_language": "python",
        "code_style": "pep8",
        "timeout_seconds": 60,
    }


# ============ Mock LLM Helper ============

@pytest.fixture
def mock_llm_helper():
    """
    Mock AgentLLMHelper for testing
    
    提供统一的 mock LLM helper，避免测试时调用真实 LLM API
    
    使用示例:
        async def test_planner_with_mock(mock_llm_helper):
            agent = PlannerAgent(llm_helper=mock_llm_helper)
            result = await agent.execute(task)
    
    默认行为:
        - is_available() 返回 False（触发 fallback 逻辑）
        - 所有 LLM 方法都有 mock 实现
    """
    helper = MagicMock()
    
    # Mock is_available - 默认返回 False，避免调用真实 LLM
    helper.is_available = MagicMock(return_value=False)
    
    # Mock generate 方法
    helper.generate = AsyncMock(return_value="Mock LLM response")
    
    # Mock generate_json 方法 - 返回合理的测试数据
    helper.generate_json = AsyncMock(return_value={
        "reasoning": "Mock reasoning for testing",
        "subtasks": [
            {
                "title": "Mock Subtask 1",
                "description": "Description for mock subtask",
                "priority": "normal",
                "assigned_role": "coder",
                "dependencies": [],
                "input_data": {}
            }
        ]
    })
    
    # Mock think 方法
    helper.think = AsyncMock(return_value={
        "analysis": "Mock analysis",
        "decision": "proceed",
        "subtasks": []
    })
    
    return helper


@pytest.fixture
def mock_llm_helper_enabled():
    """
    Mock AgentLLMHelper with LLM enabled
    
    用于测试 LLM 可用时的场景
    
    使用示例:
        async def test_with_llm_enabled(mock_llm_helper_enabled):
            agent = PlannerAgent(llm_helper=mock_llm_helper_enabled)
            # is_available() 返回 True
    """
    helper = MagicMock()
    helper.is_available = MagicMock(return_value=True)
    helper.generate = AsyncMock(return_value="Mock LLM response")
    helper.generate_json = AsyncMock(return_value={
        "reasoning": "Mock reasoning",
        "subtasks": []
    })
    helper.think = AsyncMock(return_value={
        "analysis": "Mock analysis",
        "decision": "proceed"
    })
    return helper


@pytest.fixture
def mock_llm_helper_factory():
    """
    Mock AgentLLMHelper factory for custom responses
    
    返回一个工厂函数，允许为每个测试创建自定义的 mock helper
    
    使用示例:
        async def test_custom(mock_llm_helper_factory):
            mock_helper = mock_llm_helper_factory(
                available=True,
                generate_json_response={"custom": "data"}
            )
            agent = PlannerAgent(llm_helper=mock_helper)
    """
    def _create_mock(
        available=False,
        generate_response="Mock response",
        generate_json_response=None,
        think_response=None
    ):
        helper = MagicMock()
        helper.is_available = MagicMock(return_value=available)
        helper.generate = AsyncMock(return_value=generate_response)
        helper.generate_json = AsyncMock(return_value=generate_json_response)
        helper.think = AsyncMock(return_value=think_response or {})
        return helper
    
    return _create_mock


# ============ 测试辅助函数 ============

def assert_response_ok(response):
    """断言响应成功"""
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def assert_response_error(response, expected_code: int = 400):
    """断言响应错误"""
    assert response.status_code == expected_code
    assert "error" in response.json()


async def assert_async_raises(exception_type, coro):
    """断言异步函数抛出异常"""
    try:
        await coro
        assert False, f"Expected {exception_type.__name__} to be raised"
    except exception_type:
        pass


# ============ 测试数据生成器 ============

class TestDataFactory:
    """测试数据工厂"""
    
    @staticmethod
    def create_task(
        title: str = "Test Task",
        status: str = "pending",
        priority: str = "normal",
    ) -> dict:
        """创建任务数据"""
        return {
            "title": title,
            "status": status,
            "priority": priority,
            "description": "Test description",
        }
    
    @staticmethod
    def create_agent(
        name: str = "TestAgent",
        role: str = "tester",
    ) -> dict:
        """创建 Agent 数据"""
        return {
            "name": name,
            "role": role,
            "status": "idle",
        }
    
    @staticmethod
    def create_user(
        username: str = "testuser",
        email: str = "test@example.com",
    ) -> dict:
        """创建用户数据"""
        return {
            "username": username,
            "email": email,
            "password": "testpassword123",
        }


# ============ 性能测试装饰器 ============

import time
from functools import wraps


def performance_test(threshold_ms: float = 100.0):
    """
    性能测试装饰器
    
    如果测试超过阈值则失败
    
    Args:
        threshold_ms: 性能阈值（毫秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed_ms = (time.time() - start) * 1000
            
            assert elapsed_ms < threshold_ms, (
                f"Performance test failed: {elapsed_ms:.2f}ms > {threshold_ms:.2f}ms"
            )
            
            return result
        return wrapper
    return decorator


# ============ 覆盖率配置 ============

# pytest-cov 配置
# 在 pytest.ini 或 pyproject.toml 中配置:
# [tool.coverage.run]
# source = ["src"]
# omit = ["tests/*", "*/__pycache__/*"]
# 
# [tool.coverage.report]
# exclude_lines = [
#     "pragma: no cover",
#     "def __repr__",
#     "raise NotImplementedError",
# ]
# 
# [tool.coverage.html]
# directory = "htmlcov"


# ============ CI/CD 集成 ============

# GitHub Actions 配置示例 (.github/workflows/test.yml):
# name: Tests
# 
# on: [push, pull_request]
# 
# jobs:
#   test:
#     runs-on: ubuntu-latest
#     steps:
#       - uses: actions/checkout@v2
#       - name: Set up Python
#         uses: actions/setup-python@v2
#         with:
#           python-version: 3.11
#       - name: Install dependencies
#         run: pip install -r requirements.txt
#       - name: Run tests
#         run: pytest tests/ -v --cov=src --cov-report=xml
#       - name: Upload coverage
#         uses: codecov/codecov-action@v2
