"""
任务路由

提供任务管理相关的 API 端点
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import structlog


logger = structlog.get_logger(__name__)


router = APIRouter()


# ===========================================
# 请求/响应模型
# ===========================================

class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    title: str
    description: str = ""
    priority: str = "normal"
    input_data: dict[str, Any] = {}


class TaskResponse(BaseModel):
    """任务响应"""
    id: str
    title: str
    description: str
    status: str
    priority: str
    created_at: str
    updated_at: str


# ===========================================
# 模拟数据存储 (临时)
# ===========================================

_tasks_db: dict[str, dict] = {}


# ===========================================
# API 端点
# ===========================================

@router.post(
    "/",
    response_model=TaskResponse,
    summary="创建任务",
)
async def create_task(request: TaskCreateRequest):
    """创建新任务"""
    from datetime import datetime
    import uuid
    
    task_id = str(uuid.uuid4())
    
    task = {
        "id": task_id,
        "title": request.title,
        "description": request.description,
        "status": "pending",
        "priority": request.priority,
        "input_data": request.input_data,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    
    _tasks_db[task_id] = task
    
    logger.info("Task created", task_id=task_id)
    
    return TaskResponse(**task)


@router.get(
    "/",
    response_model=list[TaskResponse],
    summary="列出任务",
)
async def list_tasks(
    status: str = Query(None, description="状态过滤"),
    limit: int = Query(50, ge=1, le=100, description="数量限制"),
):
    """获取任务列表"""
    tasks = [_tasks_db[k] for k in _tasks_db]
    
    # 状态过滤
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    
    # 限制数量
    tasks = tasks[:limit]
    
    return [TaskResponse(**t) for t in tasks]


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="获取任务详情",
)
async def get_task(task_id: str):
    """获取任务详细信息"""
    task = _tasks_db.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse(**task)


@router.delete(
    "/{task_id}",
    summary="删除任务",
)
async def delete_task(task_id: str):
    """删除任务"""
    if task_id not in _tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del _tasks_db[task_id]
    
    logger.info("Task deleted", task_id=task_id)
    
    return {"status": "deleted", "task_id": task_id}
