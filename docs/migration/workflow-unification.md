# 工作流执行器统一迁移文档

**迁移日期**: 2026-03-12  
**迁移版本**: v2.1.0  
**影响范围**: 工作流编排模块

---

## 迁移概述

将 `src/core/executor.py` 的功能统一迁移到 `src/graph/workflow.py`，消除双重工作流执行器的架构问题。

### 迁移原因

1. **功能重叠**: 两套执行器提供相似的工作流编排能力
2. **维护成本高**: 新功能需要在两处同步实现
3. **使用混乱**: 开发者难以选择使用哪个执行器
4. **代码重复**: 工作流验证、状态管理等逻辑重复实现

---

## 迁移内容

### 1. 数据类迁移

**从**: `src/core/executor.py`  
**到**: `src/graph/workflow.py`

| 原类名 | 新类名 | 说明 |
|--------|--------|------|
| `WorkflowTask` | `WorkflowTask` | 工作流任务定义，支持依赖关系 |
| `Workflow` | `WorkflowDefinition` | 工作流定义，支持复杂依赖 |

### 2. 方法迁移

| 原方法 | 新方法 | 位置 |
|--------|--------|------|
| `AgentExecutor.register_agent()` | `AgentWorkflow._agents[name] = agent` | 直接赋值 |
| `AgentExecutor.register_event_handler()` | `AgentWorkflow.register_event_handler()` | 类方法 |
| `AgentExecutor.execute_workflow()` | `AgentWorkflow.execute_workflow_definition()` | 类方法 |
| `AgentExecutor.create_standard_workflow()` | `AgentWorkflow.create_standard_workflow()` | 类方法 |
| `AgentExecutor.get_workflow_status()` | `AgentWorkflow.get_workflow_status()` | 类方法 |

### 3. 全局函数迁移

| 原函数 | 新函数 | 说明 |
|--------|--------|------|
| `get_executor()` | `get_workflow()` | 获取全局实例 |
| `init_executor(agents)` | `init_workflow(agents)` | 初始化工作流 |

---

## API 变更指南

### 旧代码 (executor.py)

```python
from src.core.executor import AgentExecutor, Workflow, WorkflowTask

# 创建执行器
executor = AgentExecutor()
executor.register_agent("planner", PlannerAgent())

# 创建工作流
workflow = Workflow(
    name="My Workflow",
    description="Test workflow",
)
workflow.tasks = [
    WorkflowTask(agent_name="planner", task_description="Plan"),
]

# 执行
result = await executor.execute_workflow(workflow)
```

### 新代码 (workflow.py)

```python
from src.graph.workflow import (
    AgentWorkflow,
    WorkflowDefinition,
    WorkflowTask,
)

# 创建工作流实例
workflow = AgentWorkflow()
workflow._agents["planner"] = PlannerAgent()

# 创建工作流定义
workflow_def = WorkflowDefinition(
    name="My Workflow",
    description="Test workflow",
)
workflow_def.tasks = [
    WorkflowTask(agent_name="planner", task_description="Plan"),
]

# 执行
result = await workflow.execute_workflow_definition(workflow_def)
```

---

## 新增功能

### 1. 事件处理器机制

```python
# 注册事件处理器
workflow.register_event_handler("workflow_started", on_start)
workflow.register_event_handler("task_completed", on_task_done)

async def on_start(data):
    print(f"Workflow started: {data['workflow_name']}")

async def on_task_done(data):
    print(f"Task completed: {data['agent_name']}")
```

支持的事件类型:
- `workflow_started`: 工作流开始
- `workflow_completed`: 工作流完成
- `workflow_failed`: 工作流失败
- `task_started`: 任务开始
- `task_completed`: 任务完成

### 2. 灵活的任务依赖

```python
# 支持复杂的依赖关系
workflow_def = WorkflowDefinition(
    name="Complex Workflow",
    tasks=[
        WorkflowTask(agent_name="a", task_description="Task A", dependencies=[]),
        WorkflowTask(agent_name="b", task_description="Task B", dependencies=["a"]),
        WorkflowTask(agent_name="c", task_description="Task C", dependencies=["a"]),
        WorkflowTask(agent_name="d", task_description="Task D", dependencies=["b", "c"]),
    ],
)
# B 和 C 可以并行执行，D 等待 B 和 C 都完成
```

### 3. 向后兼容

```python
# 旧的导入仍然可用（向后兼容）
from src.graph.workflow import Workflow  # WorkflowDefinition 的别名

# 旧的全局函数
workflow = get_workflow()  # 等同于 get_executor()
await init_workflow(agents)  # 等同于 init_executor()
```

---

## 测试更新

### 更新的测试文件

- `tests/test_integration.py`: 从 `executor.py` 迁移到 `workflow.py`

### 测试变更

| 原测试 | 新测试 | 说明 |
|--------|--------|------|
| `test_standard_workflow(executor)` | `test_standard_workflow(workflow)` | fixture 更新 |
| `test_parallel_tasks(executor)` | `test_parallel_tasks(workflow)` | fixture 更新 |
| `test_task_failure_handling(executor)` | `test_task_failure_handling(workflow)` | fixture 更新 |

---

## 迁移检查清单

- [x] 迁移 `WorkflowTask` 和 `Workflow` 数据类
- [x] 迁移 `AgentExecutor` 核心方法到 `AgentWorkflow`
- [x] 添加事件处理器机制
- [x] 添加灵活的任务依赖支持
- [x] 更新测试文件
- [x] 移除 `src/core/executor.py`
- [x] 添加向后兼容层
- [ ] 更新文档和示例
- [ ] 通知相关开发人员

---

## 风险评估

### 低风险
- 新增功能不影响现有代码
- 向后兼容层确保旧代码可以继续工作

### 中风险
- 导入路径变更需要更新所有引用
- 测试需要验证新实现的功能完整性

### 缓解措施
1. **渐进式迁移**: 提供向后兼容层，允许渐进式迁移
2. **充分测试**: 保持测试覆盖，验证功能一致性
3. **文档更新**: 提供清晰的迁移指南和示例

---

## 后续工作

1. **文档更新**: 更新项目文档中的工作流使用示例
2. **示例更新**: 更新 `examples/` 目录中的示例代码
3. **监控**: 观察生产环境中的工作流执行情况
4. **清理**: 在下一个主版本中移除向后兼容层

---

## 常见问题

### Q: 旧代码会立即失效吗？

**A**: 不会。我们提供了向后兼容层，旧代码可以继续工作。但建议尽快迁移到新 API。

### Q: 性能有变化吗？

**A**: 没有。新的实现保持了相同的性能特性，并利用 LangGraph 的优化。

### Q: 如何处理循环依赖检测？

**A**: `execute_workflow_definition()` 会自动检测循环依赖并抛出异常。

### Q: 可以混合使用旧 API 和新 API 吗？

**A**: 不建议。请选择一种 API 风格并在项目中保持一致。

---

## 参考资料

- [LangGraph 文档](https://github.com/langchain-ai/langgraph)
- [工作流设计最佳实践](./best-practices.md)
- [Agent 协作模式](./agent-collaboration.md)

---

**维护者**: IntelliTeam 核心团队  
**最后更新**: 2026-03-12
