"""
批量 API 端点

优化批量操作，减少网络往返
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.crud import (
    create_task,
    delete_task,
    get_task_by_id,
    update_task,
)
from ..db.database import get_db
from ..db.models import TaskModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch", tags=["批量操作"])


# ============ 请求模型 ============

class TaskBatchGetRequest(BaseModel):
    """批量获取任务请求"""
    task_ids: list[int] = Field(..., description="任务 ID 列表", max_length=100)


class TaskBatchCreateRequest(BaseModel):
    """批量创建任务请求"""
    tasks: list[dict] = Field(..., description="任务数据列表", max_length=50)


class TaskBatchUpdateRequest(BaseModel):
    """批量更新任务请求"""
    updates: list[dict] = Field(..., description="更新数据列表", max_length=50)


class TaskBatchDeleteRequest(BaseModel):
    """批量删除任务请求"""
    task_ids: list[int] = Field(..., description="任务 ID 列表", max_length=100)


# ============ 响应模型 ============

class TaskBatchGetResponse(BaseModel):
    """批量获取任务响应"""
    tasks: list[dict]
    not_found: list[int] = []


class TaskBatchCreateResponse(BaseModel):
    """批量创建任务响应"""
    created: list[dict]
    failed: list[dict] = []


class TaskBatchUpdateResponse(BaseModel):
    """批量更新任务响应"""
    updated: list[dict]
    failed: list[dict] = []


class TaskBatchDeleteResponse(BaseModel):
    """批量删除任务响应"""
    deleted_count: int
    deleted_ids: list[int]
    not_found: list[int] = []


# ============ API 端点 ============

@router.post("/tasks/get", response_model=TaskBatchGetResponse)
async def batch_get_tasks(
    request: TaskBatchGetRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    批量获取任务

    一次请求获取多个任务，减少网络往返

    - **task_ids**: 任务 ID 列表（最多 100 个）
    """
    tasks = []
    not_found = []

    for task_id in request.task_ids:
        task = await get_task_by_id(db, task_id)
        if task:
            tasks.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "assignee": task.assignee,
                "agent": task.agent,
                "created_at": task.created_at.isoformat() if task.created_at else None,
            })
        else:
            not_found.append(task_id)

    logger.info(f"Batch get tasks: {len(tasks)} found, {len(not_found)} not found")

    return TaskBatchGetResponse(tasks=tasks, not_found=not_found)


@router.post("/tasks/create", response_model=TaskBatchCreateResponse)
async def batch_create_tasks(
    request: TaskBatchCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    批量创建任务

    一次请求创建多个任务

    - **tasks**: 任务数据列表（最多 50 个）
    """
    created = []
    failed = []

    for task_data in request.tasks:
        try:
            task = await create_task(
                db,
                title=task_data.get("title", "新任务"),
                description=task_data.get("description", ""),
                priority=task_data.get("priority", "normal"),
                status=task_data.get("status", "pending"),
                assignee=task_data.get("assignee", ""),
                agent=task_data.get("agent", ""),
            )
            created.append({
                "id": task.id,
                "title": task.title,
                "status": task.status,
            })
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            failed.append({
                "data": task_data,
                "error": str(e),
            })

    logger.info(f"Batch create tasks: {len(created)} created, {len(failed)} failed")

    return TaskBatchCreateResponse(created=created, failed=failed)


@router.post("/tasks/update", response_model=TaskBatchUpdateResponse)
async def batch_update_tasks(
    request: TaskBatchUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    批量更新任务

    一次请求更新多个任务

    - **updates**: 更新数据列表（最多 50 个）
    """
    updated = []
    failed = []

    for update_data in request.updates:
        task_id = update_data.get("id")
        if not task_id:
            failed.append({
                "data": update_data,
                "error": "Missing task id",
            })
            continue

        try:
            task = await update_task(
                db,
                task_id=task_id,
                title=update_data.get("title"),
                description=update_data.get("description"),
                priority=update_data.get("priority"),
                status=update_data.get("status"),
                assignee=update_data.get("assignee"),
                agent=update_data.get("agent"),
            )

            if task:
                updated.append({
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                })
            else:
                failed.append({
                    "data": update_data,
                    "error": "Task not found",
                })
        except Exception as e:
            logger.error(f"Failed to update task: {e}")
            failed.append({
                "data": update_data,
                "error": str(e),
            })

    logger.info(f"Batch update tasks: {len(updated)} updated, {len(failed)} failed")

    return TaskBatchUpdateResponse(updated=updated, failed=failed)


@router.post("/tasks/delete", response_model=TaskBatchDeleteResponse)
async def batch_delete_tasks(
    request: TaskBatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    批量删除任务

    一次请求删除多个任务

    - **task_ids**: 任务 ID 列表（最多 100 个）
    """
    deleted_ids = []
    not_found = []

    for task_id in request.task_ids:
        deleted = await delete_task(db, task_id)
        if deleted:
            deleted_ids.append(task_id)
        else:
            not_found.append(task_id)

    logger.info(f"Batch delete tasks: {len(deleted_ids)} deleted, {len(not_found)} not found")

    return TaskBatchDeleteResponse(
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
        not_found=not_found,
    )


@router.get("/tasks/stats")
async def get_batch_stats(db: AsyncSession = Depends(get_db)):
    """
    获取批量统计

    返回任务统计信息
    """
    from sqlalchemy import func

    result = await db.execute(
        func.count(TaskModel.id)
    )
    total = result.scalar()

    return {
        "total_tasks": total,
        "batch_endpoints": [
            "/api/v1/batch/tasks/get",
            "/api/v1/batch/tasks/create",
            "/api/v1/batch/tasks/update",
            "/api/v1/batch/tasks/delete",
        ],
    }
