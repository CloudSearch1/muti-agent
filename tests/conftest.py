"""
测试配置

pytest 测试套件配置
"""

import asyncio
from collections.abc import Generator

import pytest

# ===========================================
# pytest 配置
# ===========================================


def pytest_configure(config):
    """pytest 配置钩子"""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests",
    )


# ===========================================
# Fixture: 事件循环
# ===========================================


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建会话级事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ===========================================
# Fixture: 测试配置
# ===========================================


@pytest.fixture
def test_settings():
    """测试配置"""
    from src.config.settings import Settings

    return Settings(
        app_name="IntelliTeam-Test",
        app_env="testing",
        debug=True,
        database_url="postgresql+asyncpg://localhost:5432/intelliteam_test",
        redis_url="redis://localhost:6379/1",  # 使用不同数据库
    )


# ===========================================
# Fixture: 内存数据库
# ===========================================


@pytest.fixture
def in_memory_db():
    """内存数据存储 (用于单元测试)"""
    return {
        "tasks": {},
        "agents": {},
        "workflows": {},
    }


# ===========================================
# Fixture: Mock 对象
# ===========================================


@pytest.fixture
def mock_llm():
    """Mock LLM 调用"""

    class MockLLM:
        async def generate(self, prompt: str, **kwargs):
            return {
                "content": "Mock LLM response",
                "usage": {"tokens": 100},
            }

    return MockLLM()


@pytest.fixture
def mock_redis():
    """Mock Redis 客户端"""

    class MockRedis:
        def __init__(self):
            self._data = {}

        async def setex(self, key: str, ttl: int, value: str):
            self._data[key] = value
            return True

        async def get(self, key: str):
            return self._data.get(key)

        async def delete(self, *keys):
            for key in keys:
                self._data.pop(key, None)

        async def close(self):
            pass

    return MockRedis()


# ===========================================
# Fixture: Agent 实例
# ===========================================


@pytest.fixture
def sample_agent():
    """示例 Agent"""
    from src.core.models import Agent, AgentRole, AgentState

    return Agent(
        id="test-agent-001",
        name="TestAgent",
        role=AgentRole.CODER,
        state=AgentState.IDLE,
    )


@pytest.fixture
def sample_task():
    """示例任务"""
    from src.core.models import Task, TaskPriority, TaskStatus

    return Task(
        id="test-task-001",
        title="Test Task",
        description="A test task for unit testing",
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
    )


# ===========================================
# 工具 Fixture
# ===========================================


@pytest.fixture
def sample_workflow():
    """示例工作流"""
    from src.core.models import Workflow, WorkflowStatus

    return Workflow(
        id="test-workflow-001",
        name="Test Workflow",
        status=WorkflowStatus.CREATED,
    )


# ===========================================
# Async Fixture 辅助函数
# ===========================================


def async_fixture(func):
    """装饰器：将 async fixture 转换为普通 fixture"""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(func(*args, **kwargs))

    return wrapper
