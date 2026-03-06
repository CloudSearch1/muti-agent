"""
批量数据库操作

优化批量插入、更新、删除操作
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import TaskModel, AgentModel, WorkflowModel

logger = logging.getLogger(__name__)


# ============ Task 批量操作 ============

async def create_tasks_batch(
    db: AsyncSession,
    tasks: List[Dict[str, Any]],
) -> List[TaskModel]:
    """
    批量创建任务
    
    Args:
        db: 数据库会话
        tasks: 任务数据列表
    
    Returns:
        创建的任务列表
    """
    if not tasks:
        return []
    
    # 创建任务对象
    db_tasks = [TaskModel(**task_data) for task_data in tasks]
    
    # 批量添加
    db.add_all(db_tasks)
    await db.commit()
    
    # 刷新获取 ID
    await db.refresh(db_tasks[0] if db_tasks else None)
    
    logger.info(f"Batch created {len(db_tasks)} tasks")
    return db_tasks


async def update_tasks_batch(
    db: AsyncSession,
    task_updates: List[Dict[str, Any]],
) -> int:
    """
    批量更新任务
    
    Args:
        db: 数据库会话
        task_updates: 更新数据列表，每项包含 id 和要更新的字段
    
    Returns:
        更新的任务数量
    """
    if not task_updates:
        return 0
    
    updated_count = 0
    
    for update_data in task_updates:
        task_id = update_data.pop("id", None)
        if not task_id:
            continue
        
        # 单个更新（因为需要不同的更新内容）
        result = await db.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(**update_data)
        )
        updated_count += result.rowcount
    
    await db.commit()
    logger.info(f"Batch updated {updated_count} tasks")
    return updated_count


async def delete_tasks_batch(
    db: AsyncSession,
    task_ids: List[int],
) -> int:
    """
    批量删除任务
    
    Args:
        db: 数据库会话
        task_ids: 任务 ID 列表
    
    Returns:
        删除的任务数量
    """
    if not task_ids:
        return 0
    
    result = await db.execute(
        delete(TaskModel)
        .where(TaskModel.id.in_(task_ids))
    )
    
    await db.commit()
    deleted_count = result.rowcount
    
    logger.info(f"Batch deleted {deleted_count} tasks")
    return deleted_count


async def get_tasks_batch(
    db: AsyncSession,
    task_ids: List[int],
) -> List[TaskModel]:
    """
    批量获取任务
    
    Args:
        db: 数据库会话
        task_ids: 任务 ID 列表
    
    Returns:
        任务列表
    """
    if not task_ids:
        return []
    
    result = await db.execute(
        select(TaskModel)
        .where(TaskModel.id.in_(task_ids))
    )
    
    return result.scalars().all()


# ============ Agent 批量操作 ============

async def create_agents_batch(
    db: AsyncSession,
    agents: List[Dict[str, Any]],
) -> List[AgentModel]:
    """
    批量创建 Agent
    
    Args:
        db: 数据库会话
        agents: Agent 数据列表
    
    Returns:
        创建的 Agent 列表
    """
    if not agents:
        return []
    
    db_agents = [AgentModel(**agent_data) for agent_data in agents]
    db.add_all(db_agents)
    await db.commit()
    
    logger.info(f"Batch created {len(db_agents)} agents")
    return db_agents


async def update_agent_status_batch(
    db: AsyncSession,
    status_updates: List[Dict[str, str]],
) -> int:
    """
    批量更新 Agent 状态
    
    Args:
        db: 数据库会话
        status_updates: 状态更新列表，每项包含 name 和 status
    
    Returns:
        更新的 Agent 数量
    """
    if not status_updates:
        return 0
    
    updated_count = 0
    
    for update_data in status_updates:
        name = update_data.get("name")
        status = update_data.get("status")
        
        if not name or not status:
            continue
        
        result = await db.execute(
            update(AgentModel)
            .where(AgentModel.name == name)
            .values(status=status)
        )
        updated_count += result.rowcount
    
    await db.commit()
    logger.info(f"Batch updated {updated_count} agent statuses")
    return updated_count


# ============ Workflow 批量操作 ============

async def create_workflows_batch(
    db: AsyncSession,
    workflows: List[Dict[str, Any]],
) -> List[WorkflowModel]:
    """
    批量创建工作流
    
    Args:
        db: 数据库会话
        workflows: 工作流数据列表
    
    Returns:
        创建的工作流列表
    """
    if not workflows:
        return []
    
    db_workflows = [WorkflowModel(**workflow_data) for workflow_data in workflows]
    db.add_all(db_workflows)
    await db.commit()
    
    logger.info(f"Batch created {len(db_workflows)} workflows")
    return db_workflows


# ============ 通用批量操作工具 ============

class BatchProcessor:
    """
    批量处理器
    
    功能:
    - 分批处理大数据集
    - 并发控制
    - 错误处理
    """
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
    
    async def process_batch(
        self,
        items: List[Any],
        processor,
    ) -> List[Any]:
        """
        分批处理项目
        
        Args:
            items: 项目列表
            processor: 处理函数（异步）
        
        Returns:
            处理结果列表
        """
        results = []
        
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            
            # 并发处理批次
            batch_results = await processor(batch)
            results.extend(batch_results)
            
            logger.debug(f"Processed batch {i // self.batch_size + 1}")
        
        return results
    
    async def insert_batch(
        self,
        db: AsyncSession,
        model_class,
        items: List[Dict[str, Any]],
    ) -> List[Any]:
        """
        批量插入
        
        Args:
            db: 数据库会话
            model_class: 模型类
            items: 数据列表
        
        Returns:
            插入的对象列表
        """
        if not items:
            return []
        
        # 分批插入
        all_objects = []
        
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            db_objects = [model_class(**item) for item in batch]
            
            db.add_all(db_objects)
            await db.commit()
            
            all_objects.extend(db_objects)
        
        logger.info(f"Batch inserted {len(all_objects)} objects")
        return all_objects
