"""
GraphQL API 支持

提供 GraphQL 查询接口，更灵活的数据获取
"""

from typing import Any, Dict, List, Optional
import strawberry
from strawberry.fastapi import GraphQLRouter
from datetime import datetime


# ============ GraphQL 类型 ============

@strawberry.type
class Task:
    """任务类型"""
    id: int
    title: str
    description: str
    status: str
    priority: str
    assignee: Optional[str]
    agent: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


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


@strawberry.type
class Workflow:
    """工作流类型"""
    id: int
    name: str
    state: str
    created_at: datetime
    completed_at: Optional[datetime]


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


# ============ 查询 ============

@strawberry.type
class Query:
    """GraphQL 查询"""
    
    @strawberry.field
    async def task(self, id: int) -> Optional[Task]:
        """获取单个任务"""
        # TODO: 从数据库获取
        return Task(
            id=id,
            title=f"Task {id}",
            description="Task description",
            status="pending",
            priority="normal",
            assignee=None,
            agent=None,
            created_at=datetime.now(),
            updated_at=None,
        )
    
    @strawberry.field
    async def tasks(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[Task]:
        """获取任务列表"""
        # TODO: 从数据库获取
        return [
            Task(
                id=i,
                title=f"Task {i}",
                description="Task description",
                status="pending",
                priority="normal",
                assignee=None,
                agent=None,
                created_at=datetime.now(),
                updated_at=None,
            )
            for i in range(offset, offset + limit)
        ]
    
    @strawberry.field
    async def agent(self, name: str) -> Optional[Agent]:
        """获取 Agent"""
        # TODO: 从数据库获取
        return Agent(
            id=1,
            name=name,
            role="Coder",
            description="Code generator",
            status="idle",
            tasks_completed=100,
            avg_time=2.5,
            success_rate=95.0,
            created_at=datetime.now(),
        )
    
    @strawberry.field
    async def agents(self) -> List[Agent]:
        """获取所有 Agent"""
        # TODO: 从数据库获取
        return [
            Agent(
                id=i,
                name=name,
                role=role,
                description="Agent description",
                status="idle",
                tasks_completed=100,
                avg_time=2.5,
                success_rate=95.0,
                created_at=datetime.now(),
            )
            for i, (name, role) in enumerate([
                ("Coder", "代码工程师"),
                ("Tester", "测试工程师"),
                ("DocWriter", "文档工程师"),
                ("Architect", "架构师"),
            ], start=1)
        ]
    
    @strawberry.field
    async def stats(self) -> Stats:
        """获取统计信息"""
        return Stats(
            total_tasks=100,
            completed_tasks=60,
            in_progress_tasks=20,
            pending_tasks=20,
            total_agents=6,
            active_agents=2,
            completion_rate=60.0,
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
        assignee: Optional[str] = None,
        agent: Optional[str] = None,
    ) -> Task:
        """创建任务"""
        # TODO: 创建到数据库
        return Task(
            id=999,
            title=title,
            description=description,
            status="pending",
            priority=priority,
            assignee=assignee,
            agent=agent,
            created_at=datetime.now(),
            updated_at=None,
        )
    
    @strawberry.mutation
    async def update_task(
        self,
        id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> Optional[Task]:
        """更新任务"""
        # TODO: 更新数据库
        return Task(
            id=id,
            title=title or "Task",
            description=description or "",
            status=status or "pending",
            priority=priority or "normal",
            assignee=None,
            agent=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
    
    @strawberry.mutation
    async def delete_task(self, id: int) -> bool:
        """删除任务"""
        # TODO: 从数据库删除
        return True


# ============ 订阅 ============

@strawberry.type
class Subscription:
    """GraphQL 订阅"""
    
    @strawberry.subscription
    async def task_updates(self, task_id: int) -> Task:
        """订阅任务更新"""
        # TODO: 实现 WebSocket 推送
        while True:
            yield Task(
                id=task_id,
                title=f"Task {task_id}",
                description="Updated",
                status="in_progress",
                priority="normal",
                assignee=None,
                agent="Coder",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            await asyncio.sleep(5)


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
