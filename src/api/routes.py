"""
IntelliTeam API 路由模块

包含所有 API 端点
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

# 导入批量端点路由
from .batch_endpoints import router as batch_router

from ..api.rate_limiter import get_rate_limiter
from ..api.response_cache import cache_response, get_response_cacher
from ..models.schemas import AgentResponse, PaginationResponse, TaskCreate, TaskResponse, TaskUpdate
from ..utils.exceptions import ValidationError

router = APIRouter()


# ============ 任务管理 ============


@router.get("/tasks", response_model=PaginationResponse[TaskResponse])
@cache_response(ttl=300)
async def get_tasks(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    获取任务列表

    - **status**: 任务状态
    - **priority**: 优先级
    - **page**: 页码
    - **page_size**: 每页数量
    """
    # 限流检查
    limiter = get_rate_limiter()
    rate_limit = await limiter.is_allowed("tasks:list", max_requests=100, window_seconds=60)

    if not rate_limit["allowed"]:
        raise HTTPException(
            status_code=429, detail=f"请求过于频繁，剩余：{rate_limit['remaining']}"
        )

    # 模拟数据
    tasks = [
        {
            "id": i,
            "title": f"Task {i}",
            "description": "Test task",
            "status": "pending",
            "priority": "normal",
            "assignee": None,
            "agent": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "completed_at": None,
        }
        for i in range(1, 21)
    ]

    return {
        "items": tasks,
        "total": 100,
        "page": page,
        "page_size": page_size,
        "total_pages": 5,
        "has_next": page < 5,
        "has_prev": page > 1,
    }


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(task: TaskCreate):
    """
    创建任务

    - **title**: 任务标题
    - **description**: 任务描述
    - **priority**: 优先级
    """
    # 验证
    if not task.title.strip():
        raise ValidationError("标题不能为空")

    # 模拟创建
    return {
        "id": 1,
        "title": task.title,
        "description": task.description,
        "status": "pending",
        "priority": task.priority,
        "assignee": task.assignee,
        "agent": task.agent,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "completed_at": None,
    }


@router.get("/tasks/{task_id}", response_model=TaskResponse)
@cache_response(ttl=600)
async def get_task(task_id: int):
    """
    获取任务详情

    - **task_id**: 任务 ID
    """
    # 限流检查
    limiter = get_rate_limiter()
    rate_limit = await limiter.is_allowed(f"tasks:{task_id}", max_requests=60, window_seconds=60)

    if not rate_limit["allowed"]:
        raise HTTPException(status_code=429, detail="请求过于频繁")

    # 模拟数据
    return {
        "id": task_id,
        "title": f"Task {task_id}",
        "description": "Test task",
        "status": "pending",
        "priority": "normal",
        "assignee": None,
        "agent": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "completed_at": None,
    }


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task: TaskUpdate):
    """
    更新任务

    - **task_id**: 任务 ID
    - **title**: 新标题
    - **description**: 新描述
    - **status**: 新状态
    """
    # 清除缓存
    cacher = get_response_cacher()
    await cacher.delete(f"cache:*:task_id={task_id}")

    return {
        "id": task_id,
        "title": task.title or f"Task {task_id}",
        "description": task.description or "",
        "status": task.status or "pending",
        "priority": "normal",
        "assignee": None,
        "agent": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "completed_at": None,
    }


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int):
    """
    删除任务

    - **task_id**: 任务 ID
    """
    # 清除缓存
    cacher = get_response_cacher()
    await cacher.delete(f"cache:*:task_id={task_id}")

    return None


# ============ Agent 管理 ============


@router.get("/agents", response_model=list[AgentResponse])
@cache_response(ttl=60)
async def get_agents():
    """获取 Agent 列表"""
    return [
        {
            "id": 1,
            "name": "Planner",
            "role": "任务规划师",
            "description": "负责任务分解和优先级排序",
            "status": "idle",
            "tasks_completed": 45,
            "avg_time": 2.3,
            "success_rate": 98.0,
            "created_at": datetime.now().isoformat(),
        },
        {
            "id": 2,
            "name": "Coder",
            "role": "代码工程师",
            "description": "负责代码实现和功能开发",
            "status": "busy",
            "tasks_completed": 89,
            "avg_time": 8.2,
            "success_rate": 94.0,
            "created_at": datetime.now().isoformat(),
        },
    ]


@router.get("/agents/{agent_id}", response_model=AgentResponse)
@cache_response(ttl=300)
async def get_agent(agent_id: int):
    """获取 Agent 详情"""
    return {
        "id": agent_id,
        "name": "Agent",
        "role": "Agent Role",
        "description": "Agent description",
        "status": "idle",
        "tasks_completed": 100,
        "avg_time": 5.0,
        "success_rate": 95.0,
        "created_at": datetime.now().isoformat(),
    }


# ============ 统计信息 ============


@router.get("/stats")
@cache_response(ttl=60)
async def get_stats():
    """获取系统统计"""
    return {
        "total_tasks": 156,
        "active_agents": 8,
        "completion_rate": 93,
        "timestamp": datetime.now().isoformat(),
    }


# ============ 健康检查 ============


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# 注册批量端点路由
# 在主应用中通过 include_router 注册
