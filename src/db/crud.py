"""
数据库 CRUD 操作模块

提供 Task、Agent、Workflow 的增删改查操作
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import TaskModel, AgentModel, WorkflowModel

logger = logging.getLogger(__name__)


# ============ Task CRUD ============

async def get_all_tasks(db: AsyncSession, limit: int = 100, offset: int = 0) -> list[TaskModel]:
    """获取所有任务"""
    result = await db.execute(
        select(TaskModel)
        .order_by(TaskModel.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


async def get_task_by_id(db: AsyncSession, task_id: int) -> Optional[TaskModel]:
    """根据 ID 获取任务"""
    result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
    return result.scalar_one_or_none()


async def create_task(
    db: AsyncSession,
    title: str,
    description: str = "",
    priority: str = "normal",
    status: str = "pending",
    assignee: str = "",
    agent: str = "",
) -> TaskModel:
    """创建新任务"""
    task = TaskModel(
        title=title,
        description=description,
        priority=priority,
        status=status,
        assignee=assignee,
        agent=agent,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    logger.info(f"创建任务：{task.id} - {title}")
    return task


async def update_task(
    db: AsyncSession,
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    agent: Optional[str] = None,
) -> Optional[TaskModel]:
    """更新任务"""
    task = await get_task_by_id(db, task_id)
    if not task:
        return None
    
    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if priority is not None:
        task.priority = priority
    if status is not None:
        task.status = status
        if status == "completed" and not task.completed_at:
            task.completed_at = datetime.now()
    if assignee is not None:
        task.assignee = assignee
    if agent is not None:
        task.agent = agent
    
    task.updated_at = datetime.now()
    await db.commit()
    await db.refresh(task)
    logger.info(f"更新任务：{task_id}")
    return task


async def delete_task(db: AsyncSession, task_id: int) -> bool:
    """删除任务"""
    result = await db.execute(delete(TaskModel).where(TaskModel.id == task_id))
    await db.commit()
    deleted = result.rowcount > 0
    if deleted:
        logger.info(f"删除任务：{task_id}")
    return deleted


async def get_task_stats(db: AsyncSession) -> dict:
    """获取任务统计"""
    from sqlalchemy import func
    
    result = await db.execute(
        select(
            func.count(TaskModel.id).label("total"),
            func.sum(func.case((TaskModel.status == "completed", 1), else_=0)).label("completed"),
            func.sum(func.case((TaskModel.status == "in_progress", 1), else_=0)).label("in_progress"),
            func.sum(func.case((TaskModel.status == "pending", 1), else_=0)).label("pending"),
        )
    )
    stats = result.first()
    return {
        "total": stats.total or 0,
        "completed": stats.completed or 0,
        "in_progress": stats.in_progress or 0,
        "pending": stats.pending or 0,
    }


# ============ Agent CRUD ============

async def get_all_agents(db: AsyncSession) -> list[AgentModel]:
    """获取所有 Agent"""
    result = await db.execute(select(AgentModel).order_by(AgentModel.name))
    return result.scalars().all()


async def get_agent_by_name(db: AsyncSession, name: str) -> Optional[AgentModel]:
    """根据名称获取 Agent"""
    result = await db.execute(select(AgentModel).where(AgentModel.name == name))
    return result.scalar_one_or_none()


async def create_agent(
    db: AsyncSession,
    name: str,
    role: str,
    description: str = "",
    status: str = "idle",
) -> AgentModel:
    """创建新 Agent"""
    agent = AgentModel(
        name=name,
        role=role,
        description=description,
        status=status,
        created_at=datetime.now(),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    logger.info(f"创建 Agent: {name} - {role}")
    return agent


async def update_agent_status(
    db: AsyncSession,
    name: str,
    status: str,
) -> Optional[AgentModel]:
    """更新 Agent 状态"""
    agent = await get_agent_by_name(db, name)
    if not agent:
        return None
    
    agent.status = status
    await db.commit()
    await db.refresh(agent)
    logger.debug(f"更新 Agent 状态：{name} -> {status}")
    return agent


async def increment_agent_tasks(
    db: AsyncSession,
    name: str,
    duration_ms: float,
    success: bool = True,
) -> Optional[AgentModel]:
    """增加 Agent 完成任务计数"""
    agent = await get_agent_by_name(db, name)
    if not agent:
        return None
    
    agent.tasks_completed += 1
    # 更新平均时间
    total_tasks = agent.tasks_completed
    agent.avg_time = ((agent.avg_time * (total_tasks - 1)) + duration_ms) / total_tasks
    # 更新成功率
    if success:
        successful = (agent.success_rate * (total_tasks - 1) + 100) / total_tasks
    else:
        successful = (agent.success_rate * (total_tasks - 1)) / total_tasks
    agent.success_rate = successful
    
    await db.commit()
    await db.refresh(agent)
    return agent


async def init_default_agents(db: AsyncSession) -> None:
    """初始化默认 Agent"""
    default_agents = [
        {"name": "Planner", "role": "任务规划师", "description": "负责任务分解和优先级排序"},
        {"name": "Architect", "role": "系统架构师", "description": "负责系统架构设计和技术选型"},
        {"name": "Coder", "role": "代码工程师", "description": "负责代码实现和功能开发"},
        {"name": "Tester", "role": "测试工程师", "description": "负责测试用例和质量保障"},
        {"name": "DocWriter", "role": "文档工程师", "description": "负责技术文档编写"},
        {"name": "SeniorArchitect", "role": "资深架构师", "description": "负责复杂系统设计和代码审查"},
        {"name": "ResearchAgent", "role": "研究助手", "description": "负责文献调研和技术分析"},
    ]
    
    for agent_data in default_agents:
        existing = await get_agent_by_name(db, agent_data["name"])
        if not existing:
            await create_agent(
                db,
                name=agent_data["name"],
                role=agent_data["role"],
                description=agent_data["description"],
            )
    
    logger.info("默认 Agent 初始化完成")


# ============ Workflow CRUD ============

async def get_all_workflows(db: AsyncSession) -> list[WorkflowModel]:
    """获取所有工作流"""
    result = await db.execute(select(WorkflowModel).order_by(WorkflowModel.created_at.desc()))
    return result.scalars().all()


async def create_workflow(
    db: AsyncSession,
    name: str,
    input_data: str = "",
) -> WorkflowModel:
    """创建工作流"""
    workflow = WorkflowModel(
        name=name,
        input_data=input_data,
        state="running",
        created_at=datetime.now(),
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    logger.info(f"创建工作流：{name}")
    return workflow


async def complete_workflow(
    db: AsyncSession,
    workflow_id: int,
    output_data: str = "",
) -> Optional[WorkflowModel]:
    """完成工作流"""
    result = await db.execute(select(WorkflowModel).where(WorkflowModel.id == workflow_id))
    workflow = result.scalar_one_or_none()
    
    if workflow:
        workflow.state = "completed"
        workflow.output_data = output_data
        workflow.completed_at = datetime.now()
        await db.commit()
        await db.refresh(workflow)
        logger.info(f"完成工作流：{workflow_id}")
    
    return workflow
