"""
GraphQL API 支持

提供 GraphQL 查询接口，更灵活的数据获取

版本：2.0.0
更新时间：2026-03-12
改进：
- 集成数据库 CRUD 操作
- 实现真实数据持久化
- 添加 WebSocket 订阅支持
"""

import asyncio
from datetime import datetime
from typing import AsyncGenerator

import strawberry
from strawberry.fastapi import GraphQLRouter

from ..db.crud import (
    create_task as db_create_task,
    delete_task as db_delete_task,
    get_agent_by_name,
    get_all_agents,
    get_all_tasks,
    get_task_by_id,
    get_task_stats,
    get_tasks_with_stats,
    init_default_agents,
    update_task as db_update_task,
)
from ..db.database import get_database_manager

# ============ GraphQL 类型 ============

@strawberry.type
class Task:
    """任务类型"""
    id: int
    title: str
    description: str
    status: str
    priority: str
    assignee: str | None
    agent: str | None
    created_at: datetime
    updated_at: datetime | None

    @classmethod
    def from_model(cls, model) -> "Task":
        """从数据库模型创建 GraphQL 类型"""
        return cls(
            id=model.id,
            title=model.title,
            description=model.description or "",
            status=model.status,
            priority=model.priority,
            assignee=model.assignee,
            agent=model.agent,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


@strawberry.type
class Agent:
    """Agent 类型"""
    id: int
    name: str
    role: str
    description: str
    status: str
    tasks_completed: int
    avg_time: float
    success_rate: float
    created_at: datetime

    @classmethod
    def from_model(cls, model) -> "Agent":
        """从数据库模型创建 GraphQL 类型"""
        return cls(
            id=model.id,
            name=model.name,
            role=model.role,
            description=model.description or "",
            status=model.status,
            tasks_completed=model.tasks_completed,
            avg_time=model.avg_time,
            success_rate=model.success_rate,
            created_at=model.created_at,
        )


@strawberry.type
class Workflow:
    """工作流类型"""
    id: int
    name: str
    state: str
    created_at: datetime
    completed_at: datetime | None


@strawberry.type
class Stats:
    """统计类型"""
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    pending_tasks: int
    total_agents: int
    active_agents: int
    completion_rate: float


# ============ 数据库会话管理 ============

async def get_db_session():
    """获取数据库会话"""
    db_manager = get_database_manager()
    async for session in db_manager.get_session():
        yield session


# ============ 查询 ============

@strawberry.type
class Query:
    """GraphQL 查询"""

    @strawberry.field
    async def task(self, id: int) -> Task | None:
        """获取单个任务"""
        async for db in get_db_session():
            task_model = await get_task_by_id(db, id)
            if task_model:
                return Task.from_model(task_model)
            return None

    @strawberry.field
    async def tasks(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        priority: str | None = None,
    ) -> list[Task]:
        """获取任务列表"""
        async for db in get_db_session():
            tasks = await get_all_tasks(db, limit=limit, offset=offset)
            result = []
            for task in tasks:
                # 过滤状态
                if status and task.status != status:
                    continue
                # 过滤优先级
                if priority and task.priority != priority:
                    continue
                result.append(Task.from_model(task))
            return result

    @strawberry.field
    async def agent(self, name: str) -> Agent | None:
        """获取 Agent"""
        async for db in get_db_session():
            agent_model = await get_agent_by_name(db, name)
            if agent_model:
                return Agent.from_model(agent_model)
            return None

    @strawberry.field
    async def agents(self) -> list[Agent]:
        """获取所有 Agent"""
        async for db in get_db_session():
            agents = await get_all_agents(db)
            return [Agent.from_model(agent) for agent in agents]

    @strawberry.field
    async def stats(self) -> Stats:
        """获取统计信息"""
        async for db in get_db_session():
            # 获取任务统计
            task_stats = await get_tasks_with_stats(db)
            
            # 获取 Agent 统计
            agents = await get_all_agents(db)
            total_agents = len(agents)
            active_agents = sum(1 for a in agents if a.status in ["idle", "busy"])
            
            # 计算完成率
            total_tasks = task_stats["total"]
            completed_tasks = task_stats["completed"]
            completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

            return Stats(
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                in_progress_tasks=task_stats["in_progress"],
                pending_tasks=task_stats["pending"],
                total_agents=total_agents,
                active_agents=active_agents,
                completion_rate=round(completion_rate, 2),
            )


# ============ 变更 ============

@strawberry.type
class Mutation:
    """GraphQL 变更"""

    @strawberry.mutation
    async def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "normal",
        assignee: str | None = None,
        agent: str | None = None,
    ) -> Task:
        """创建任务"""
        async for db in get_db_session():
            task_model = await db_create_task(
                db,
                title=title,
                description=description,
                priority=priority,
                assignee=assignee or "",
                agent=agent or "",
            )
            return Task.from_model(task_model)

    @strawberry.mutation
    async def update_task(
        self,
        id: int,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ) -> Task | None:
        """更新任务"""
        async for db in get_db_session():
            task_model = await db_update_task(
                db,
                task_id=id,
                title=title,
                description=description,
                status=status,
                priority=priority,
            )
            if task_model:
                return Task.from_model(task_model)
            return None

    @strawberry.mutation
    async def delete_task(self, id: int) -> bool:
        """删除任务"""
        async for db in get_db_session():
            return await db_delete_task(db, id)

    @strawberry.mutation
    async def init_agents(self) -> bool:
        """初始化默认 Agent"""
        async for db in get_db_session():
            await init_default_agents(db)
            return True


# ============ 订阅 ============

# 任务更新订阅管理器
_task_subscribers: dict[int, list[asyncio.Queue]] = {}


async def notify_task_update(task_id: int, task_data: Task) -> None:
    """通知任务更新"""
    if task_id in _task_subscribers:
        for queue in _task_subscribers[task_id]:
            await queue.put(task_data)


@strawberry.type
class Subscription:
    """GraphQL 订阅"""

    @strawberry.subscription
    async def task_updates(self, task_id: int) -> AsyncGenerator[Task, None]:
        """
        订阅任务更新
        
        通过 WebSocket 实时推送任务状态变化
        """
        # 创建消息队列
        queue: asyncio.Queue[Task] = asyncio.Queue()
        
        # 注册订阅者
        if task_id not in _task_subscribers:
            _task_subscribers[task_id] = []
        _task_subscribers[task_id].append(queue)
        
        try:
            # 首先发送当前任务状态
            async for db in get_db_session():
                task_model = await get_task_by_id(db, task_id)
                if task_model:
                    await queue.put(Task.from_model(task_model))
                break
            
            # 持续监听更新
            while True:
                try:
                    # 等待更新，超时后检查任务状态
                    task_update = await asyncio.wait_for(
                        queue.get(),
                        timeout=30.0
                    )
                    yield task_update
                    
                    # 如果任务已完成或失败，结束订阅
                    if task_update.status in ["completed", "failed"]:
                        break
                        
                except asyncio.TimeoutError:
                    # 超时检查任务当前状态
                    async for db in get_db_session():
                        task_model = await get_task_by_id(db, task_id)
                        if task_model:
                            current_task = Task.from_model(task_model)
                            yield current_task
                            if current_task.status in ["completed", "failed"]:
                                return
                        break
        finally:
            # 清理订阅者
            if task_id in _task_subscribers:
                _task_subscribers[task_id].remove(queue)
                if not _task_subscribers[task_id]:
                    del _task_subscribers[task_id]

    @strawberry.subscription
    async def all_task_updates(self) -> AsyncGenerator[Task, None]:
        """订阅所有任务更新"""
        queue: asyncio.Queue[Task] = asyncio.Queue()
        
        # 注册全局订阅者
        global_queue_key = "global"
        if global_queue_key not in _task_subscribers:
            _task_subscribers[global_queue_key] = []
        _task_subscribers[global_queue_key].append(queue)
        
        try:
            while True:
                try:
                    task_update = await asyncio.wait_for(
                        queue.get(),
                        timeout=30.0
                    )
                    yield task_update
                except asyncio.TimeoutError:
                    # 发送心跳
                    continue
        finally:
            if global_queue_key in _task_subscribers:
                _task_subscribers[global_queue_key].remove(queue)


# ============ Schema ============

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)

graphql_app = GraphQLRouter(schema)


# ============ 使用示例 ============

GRAPHQL_EXAMPLES = """
# GraphQL 使用示例

## 查询任务

```graphql
query {
  task(id: 1) {
    id
    title
    description
    status
    priority
    assignee
    agent
    createdAt
  }
}
```

## 查询任务列表

```graphql
query {
  tasks(limit: 10, status: "pending") {
    id
    title
    status
    priority
  }
}
```

## 查询 Agent

```graphql
query {
  agents {
    id
    name
    role
    status
    tasksCompleted
    successRate
  }
}
```

## 查询统计

```graphql
query {
  stats {
    totalTasks
    completedTasks
    inProgressTasks
    pendingTasks
    totalAgents
    activeAgents
    completionRate
  }
}
```

## 创建任务

```graphql
mutation {
  createTask(
    title: "New Task"
    description: "Task description"
    priority: "high"
    assignee: "张三"
    agent: "Coder"
  ) {
    id
    title
    status
    createdAt
  }
}
```

## 更新任务

```graphql
mutation {
  updateTask(
    id: 1
    status: "completed"
  ) {
    id
    title
    status
    updatedAt
  }
}
```

## 订阅任务更新

```graphql
subscription {
  taskUpdates(taskId: 1) {
    id
    status
    updatedAt
  }
}
```

## 复杂查询

```graphql
query GetDashboard {
  stats {
    totalTasks
    completedTasks
    completionRate
    activeAgents
  }
  agents {
    name
    role
    status
    tasksCompleted
  }
  tasks(limit: 5, status: "in_progress") {
    id
    title
    assignee
    agent
  }
}
```
"""
