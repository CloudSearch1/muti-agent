# Agent 角色映射机制

## 概述

本文档介绍 Agent 角色到具体 Agent 类的映射机制。该机制解决了之前需要在多处维护角色到类映射关系的问题，提供了统一的工厂方法，降低了出错的可能性，并提高了系统的可扩展性。

## 问题背景

### 原有问题

在实现角色映射机制之前，`AgentRole` 枚举仅定义了角色类型，但缺乏到具体 Agent 类的映射机制：

```python
class AgentRole(StrEnum):
    """Agent 角色枚举"""
    PLANNER = "planner"
    ARCHITECT = "architect"
    CODER = "coder"
    TESTER = "tester"
    DOC_WRITER = "doc_writer"
    RESEARCHER = "researcher"
    SENIOR_ARCHITECT = "senior_architect"
    # 但没有工厂方法将角色映射到具体类
```

这导致了以下问题：

1. **需要在多处维护映射关系**：每次需要创建 Agent 时，都需要手动判断角色类型并实例化对应的类
2. **增加了出错的可能性**：手动映射容易遗漏或映射错误
3. **不利于扩展新的 Agent 类型**：添加新角色时需要修改多个地方的代码

### 解决方案

通过在 `AgentRole` 枚举中添加工厂方法，实现角色到类的自动映射：

```python
class AgentRole(StrEnum):
    """Agent 角色枚举"""
    
    @classmethod
    def get_agent_class(cls, role: "AgentRole") -> type | None:
        """获取角色对应的 Agent 类"""
        from ..agents import (
            ArchitectAgent,
            CoderAgent,
            DocWriterAgent,
            PlannerAgent,
            ResearchAgent,
            SeniorArchitectAgent,
            TesterAgent,
        )
        
        mapping = {
            cls.PLANNER: PlannerAgent,
            cls.ARCHITECT: ArchitectAgent,
            cls.CODER: CoderAgent,
            cls.TESTER: TesterAgent,
            cls.DOC_WRITER: DocWriterAgent,
            cls.RESEARCHER: ResearchAgent,
            cls.SENIOR_ARCHITECT: SeniorArchitectAgent,
        }
        return mapping.get(role)
```

## 功能说明

### 1. AgentRole.get_agent_class()

获取角色对应的 Agent 类。

**参数**：
- `role: AgentRole` - Agent 角色枚举值

**返回值**：
- `type | None` - Agent 类，如果角色未找到则返回 None

**使用示例**：

```python
from src.core.models import AgentRole

# 获取 PlannerAgent 类
agent_class = AgentRole.get_agent_class(AgentRole.PLANNER)
if agent_class:
    agent = agent_class(name="my_planner")
```

### 2. AgentRole.get_all_roles()

获取所有可用的角色列表。

**返回值**：
- `list[AgentRole]` - 角色列表

**使用示例**：

```python
from src.core.models import AgentRole

roles = AgentRole.get_all_roles()
# 返回: [
#     AgentRole.PLANNER,
#     AgentRole.ARCHITECT,
#     AgentRole.CODER,
#     AgentRole.TESTER,
#     AgentRole.DOC_WRITER,
#     AgentRole.RESEARCHER,
#     AgentRole.SENIOR_ARCHITECT,
# ]
```

### 3. AgentRole.from_string()

从字符串创建角色枚举（大小写不敏感）。

**参数**：
- `role_str: str` - 角色字符串（如 "planner", "architect"）

**返回值**：
- `AgentRole | None` - 对应的角色枚举，如果未找到则返回 None

**使用示例**：

```python
from src.core.models import AgentRole

# 从字符串创建
role = AgentRole.from_string("planner")  # AgentRole.PLANNER
role = AgentRole.from_string("PLANNER")  # AgentRole.PLANNER (大小写不敏感)
role = AgentRole.from_string("invalid")  # None
```

### 4. Container.create_agent_by_role()

根据角色创建 Agent 实例（推荐方式）。

**参数**：
- `role: AgentRole` - Agent 角色枚举
- `name: str | None` - Agent 名称（可选，默认使用角色名称）
- `**kwargs` - 传递给 Agent 构造函数的额外参数

**返回值**：
- `BaseAgent` - Agent 实例

**异常**：
- `ValueError` - 角色未找到对应的 Agent 类

**使用示例**：

```python
from src.core.container import get_agent_container
from src.core.models import AgentRole

container = get_agent_container()

# 创建 Planner Agent
planner = container.create_agent_by_role(AgentRole.PLANNER)

# 创建带自定义名称的 Coder Agent
coder = container.create_agent_by_role(
    AgentRole.CODER, 
    name="code_assistant"
)

# 创建带额外参数的 Agent
tester = container.create_agent_by_role(
    AgentRole.TESTER,
    name="qa_tester",
    testing_framework="pytest"
)
```

### 5. Container.create_all_agents()

创建所有角色的 Agent 实例。

**参数**：
- `**kwargs` - 传递给所有 Agent 构造函数的通用参数

**返回值**：
- `dict[str, BaseAgent]` - Agent 名称到实例的映射

**使用示例**：

```python
from src.core.container import get_agent_container

container = get_agent_container()

# 创建所有 Agent
agents = container.create_all_agents()

# 返回: {
#     "planner": PlannerAgent,
#     "architect": ArchitectAgent,
#     "coder": CoderAgent,
#     "tester": TesterAgent,
#     "doc_writer": DocWriterAgent,
#     "researcher": ResearchAgent,
#     "senior_architect": SeniorArchitectAgent,
# }

# 访问特定 Agent
planner = agents["planner"]
```

### 6. Container.get_agent_by_role()

根据角色获取 Agent 实例（智能缓存）。

**优先级**：
1. 已注册的同名 Agent 实例
2. 已注册的同名工厂函数
3. 自动创建并注册

**参数**：
- `role: AgentRole` - Agent 角色枚举

**返回值**：
- `BaseAgent` - Agent 实例

**异常**：
- `ValueError` - 角色未找到对应的 Agent 类

**使用示例**：

```python
from src.core.container import get_agent_container
from src.core.models import AgentRole

container = get_agent_container()

# 首次获取会自动创建
agent1 = container.get_agent_by_role(AgentRole.PLANNER)

# 再次获取返回同一个实例（缓存）
agent2 = container.get_agent_by_role(AgentRole.PLANNER)

assert agent1 is agent2  # True
```

## 使用场景

### 场景 1：动态创建 Agent

```python
from src.core.container import get_agent_container
from src.core.models import AgentRole

def create_agent_for_task(task_type: str):
    """根据任务类型动态创建对应的 Agent"""
    container = get_agent_container()
    
    # 将任务类型映射到角色
    role_mapping = {
        "planning": AgentRole.PLANNER,
        "coding": AgentRole.CODER,
        "testing": AgentRole.TESTER,
        "documentation": AgentRole.DOC_WRITER,
    }
    
    role = role_mapping.get(task_type)
    if role:
        return container.create_agent_by_role(role)
    
    return None
```

### 场景 2：批量初始化系统

```python
from src.core.container import get_agent_container

async def initialize_system():
    """初始化系统，创建所有 Agent"""
    container = get_agent_container()
    
    # 创建所有 Agent
    agents = container.create_all_agents()
    
    # 初始化所有 Agent
    for name, agent in agents.items():
        await agent.init()
        await agent.start()
    
    return agents
```

### 场景 3：基于配置的 Agent 创建

```python
from src.core.container import get_agent_container
from src.core.models import AgentRole

def create_agents_from_config(config: dict):
    """基于配置创建 Agent"""
    container = get_agent_container()
    
    agents = []
    for agent_config in config.get("agents", []):
        role_str = agent_config["role"]
        role = AgentRole.from_string(role_str)
        
        if role:
            agent = container.create_agent_by_role(
                role,
                name=agent_config.get("name"),
                **agent_config.get("options", {})
            )
            agents.append(agent)
    
    return agents
```

### 场景 4：测试中的 Mock Agent

```python
from src.core.container import AgentContainer
from src.core.models import AgentRole
from unittest.mock import Mock

def test_with_mock_agent():
    """测试中使用 Mock Agent"""
    # 创建测试容器
    AgentContainer.reset("test")
    container = AgentContainer("test")
    
    # 注册 Mock Agent
    mock_planner = Mock()
    container.register_agent("planner", mock_planner)
    
    # 获取 Mock Agent
    agent = container.get_agent_by_role(AgentRole.PLANNER)
    
    # 验证调用
    agent.execute(...)
    mock_planner.execute.assert_called_once()
```

## 最佳实践

### 1. 优先使用 create_agent_by_role

**推荐**：
```python
agent = container.create_agent_by_role(AgentRole.PLANNER)
```

**不推荐**：
```python
from src.agents import PlannerAgent
agent = PlannerAgent()
```

### 2. 利用容器缓存

```python
# 好的做法：利用容器的缓存机制
container = get_agent_container()
agent1 = container.get_agent_by_role(AgentRole.PLANNER)
agent2 = container.get_agent_by_role(AgentRole.PLANNER)
# agent1 和 agent2 是同一个实例

# 不好的做法：重复创建
agent1 = PlannerAgent()
agent2 = PlannerAgent()
# agent1 和 agent2 是不同的实例
```

### 3. 使用 from_string 处理用户输入

```python
def handle_user_request(role_str: str):
    """处理用户请求"""
    role = AgentRole.from_string(role_str)
    if not role:
        raise ValueError(f"Invalid role: {role_str}")
    
    container = get_agent_container()
    return container.create_agent_by_role(role)
```

### 4. 批量操作使用 create_all_agents

```python
# 批量初始化
agents = container.create_all_agents()
for agent in agents.values():
    await agent.start()
```

## 扩展指南

### 添加新的 Agent 角色

1. **定义新的枚举值**：

```python
# src/core/models.py
class AgentRole(StrEnum):
    # ... 现有角色
    DATA_SCIENTIST = "data_scientist"  # 新增角色
```

2. **创建新的 Agent 类**：

```python
# src/agents/data_scientist.py
from .base import BaseAgent
from ..core.models import AgentRole

class DataScientistAgent(BaseAgent):
    """数据科学家 Agent"""
    
    ROLE = AgentRole.DATA_SCIENTIST
    
    async def execute(self, task):
        # 实现执行逻辑
        pass
    
    async def think(self, context):
        # 实现思考逻辑
        pass
```

3. **在 __init__.py 中导出**：

```python
# src/agents/__init__.py
from .data_scientist import DataScientistAgent

__all__ = [
    # ... 现有导出
    "DataScientistAgent",
]
```

4. **更新映射关系**：

```python
# src/core/models.py
@classmethod
def get_agent_class(cls, role: "AgentRole") -> type | None:
    from ..agents import (
        # ... 现有导入
        DataScientistAgent,  # 新增导入
    )
    
    mapping = {
        # ... 现有映射
        cls.DATA_SCIENTIST: DataScientistAgent,  # 新增映射
    }
    return mapping.get(role)

@classmethod
def get_all_roles(cls) -> list["AgentRole"]:
    return [
        # ... 现有角色
        cls.DATA_SCIENTIST,  # 新增角色
    ]
```

## 性能考虑

### 1. 延迟导入

`get_agent_class()` 方法使用了延迟导入（Lazy Import）来避免循环依赖问题：

```python
@classmethod
def get_agent_class(cls, role: "AgentRole") -> type | None:
    # 延迟导入，避免循环依赖
    from ..agents import PlannerAgent, ...
    
    mapping = {...}
    return mapping.get(role)
```

这意味着只有在实际调用 `get_agent_class()` 时才会导入 Agent 类，避免了启动时的性能开销。

### 2. 容器缓存

容器的 `get_agent_by_role()` 方法实现了智能缓存：

- 首次调用时创建 Agent 实例并缓存
- 后续调用直接返回缓存的实例
- 避免重复创建相同的 Agent

### 3. 映射表性能

映射表使用字典实现，查找时间复杂度为 O(1)，性能优异。

## 常见问题

### Q1: 为什么使用延迟导入？

**A**: 延迟导入解决了循环依赖问题。`AgentRole` 定义在 `core.models` 中，而具体的 Agent 类在 `agents` 包中。如果 Agent 类需要引用 `AgentRole`，而 `AgentRole` 又需要引用 Agent 类，就会形成循环依赖。延迟导入通过在实际使用时才导入，打破了这种循环。

### Q2: 映射表会占用很多内存吗？

**A**: 不会。映射表只存储类对象的引用，不存储实例。无论创建多少个 Agent 实例，映射表本身的内存占用都是固定的。

### Q3: 如果忘记更新映射表会怎样？

**A**: `get_agent_class()` 会返回 `None`，调用方需要检查返回值。在使用 `create_agent_by_role()` 时，会抛出 `ValueError` 异常，提示角色未找到对应的 Agent 类。

### Q4: 可以动态注册新的映射关系吗？

**A**: 目前映射关系是硬编码在 `get_agent_class()` 方法中的。如果需要动态注册，可以通过容器的 `register_agent()` 或 `register_agent_factory()` 方法实现。

## 总结

Agent 角色映射机制提供了：

1. **统一的映射接口** - 通过 `AgentRole.get_agent_class()` 获取对应的 Agent 类
2. **便捷的创建方法** - 通过 `Container.create_agent_by_role()` 创建 Agent 实例
3. **智能的缓存机制** - 通过 `Container.get_agent_by_role()` 实现实例复用
4. **灵活的扩展能力** - 添加新角色只需更新映射表和创建新的 Agent 类

该机制显著提高了代码的可维护性和可扩展性，降低了出错的可能性，是 Agent 系统架构的重要组成部分。
