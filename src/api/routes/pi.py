"""
Pi 系统 API 路由

提供 Agent 协作系统的 API 端点

端点:
- POST /api/pi/agents - 创建 Agent
- GET /api/pi/agents - 列出 Agents
- GET /api/pi/agents/{agent_id} - 获取 Agent 详情
- DELETE /api/pi/agents/{agent_id} - 删除 Agent
- POST /api/pi/tasks - 提交任务
- GET /api/pi/tasks - 获取任务状态
- POST /api/pi/execute - 执行工作流

版本: 1.0.0
"""


import structlog
from fastapi import APIRouter, HTTPException, Query

from src.pi.agent_manager import get_agent_manager
from src.pi.result_aggregator import get_result_aggregator
from src.pi.task_scheduler import get_task_scheduler
from src.pi.types import (
    AgentListResponse,
    ConflictResolution,
    CreateAgentRequest,
    CreateTaskRequest,
    ExecuteWorkflowRequest,
    PiAgentConfig,
    PiAgentInfo,
    PiAgentStatus,
    PiTaskConfig,
    PiTaskInfo,
    PiTaskPriority,
    PiTaskStatus,
    PiWorkflowResult,
    ResultEvaluation,
    TaskAssignmentStrategy,
    TaskListResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# ===========================================
# Agent 端点
# ===========================================


@router.post(
    "/agents",
    response_model=PiAgentInfo,
    summary="创建 Agent",
    description="创建新的 Agent 实例",
)
async def create_agent(request: CreateAgentRequest):
    """创建 Agent"""
    manager = get_agent_manager()

    config = PiAgentConfig(
        name=request.name,
        role=request.role,
        capabilities=request.capabilities,
        max_concurrent_tasks=request.max_concurrent_tasks,
        timeout_seconds=request.timeout_seconds,
        metadata=request.metadata,
    )

    try:
        agent = await manager.create_agent(config)
        logger.info("Agent created via API", agent_id=agent.id)
        return agent
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/agents",
    response_model=AgentListResponse,
    summary="列出 Agents",
    description="获取所有 Agent 列表，支持状态和角色过滤",
)
async def list_agents(
    status: str | None = Query(None, description="状态过滤"),
    role: str | None = Query(None, description="角色过滤"),
    capability: str | None = Query(None, description="能力过滤"),
    limit: int = Query(50, ge=1, le=100, description="数量限制"),
):
    """列出 Agents"""
    manager = get_agent_manager()

    # 转换状态
    status_enum = None
    if status:
        try:
            status_enum = PiAgentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    agents = manager.list_agents(
        status=status_enum,
        role=role,
        capability=capability,
    )

    agents = agents[:limit]

    return AgentListResponse(
        agents=agents,
        total=len(agents),
    )


@router.get(
    "/agents/{agent_id}",
    response_model=PiAgentInfo,
    summary="获取 Agent 详情",
)
async def get_agent(agent_id: str):
    """获取 Agent 详情"""
    manager = get_agent_manager()
    agent = manager.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent


@router.post(
    "/agents/{agent_id}/start",
    summary="启动 Agent",
)
async def start_agent(agent_id: str):
    """启动 Agent"""
    manager = get_agent_manager()
    success = await manager.start_agent(agent_id)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to start agent")

    return {"status": "started", "agent_id": agent_id}


@router.post(
    "/agents/{agent_id}/stop",
    summary="停止 Agent",
)
async def stop_agent(agent_id: str):
    """停止 Agent"""
    manager = get_agent_manager()
    success = await manager.stop_agent(agent_id)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to stop agent")

    return {"status": "stopped", "agent_id": agent_id}


@router.delete(
    "/agents/{agent_id}",
    summary="删除 Agent",
)
async def delete_agent(agent_id: str):
    """删除 Agent"""
    manager = get_agent_manager()
    success = await manager.destroy_agent(agent_id)

    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"status": "deleted", "agent_id": agent_id}


# ===========================================
# Task 端点
# ===========================================


@router.post(
    "/tasks",
    response_model=PiTaskInfo,
    summary="创建任务",
    description="提交新任务到调度队列",
)
async def create_task(request: CreateTaskRequest):
    """创建任务"""
    scheduler = get_task_scheduler()

    # 转换优先级
    try:
        priority = PiTaskPriority(request.priority)
    except ValueError:
        priority = PiTaskPriority.NORMAL

    config = PiTaskConfig(
        title=request.title,
        description=request.description,
        priority=priority,
        required_capabilities=request.required_capabilities,
        input_data=request.input_data,
        dependencies=request.dependencies,
        max_retries=request.max_retries,
        timeout_seconds=request.timeout_seconds,
    )

    task = await scheduler.submit_task(config)
    logger.info("Task created via API", task_id=task.id)

    return task


@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="列出任务",
    description="获取任务列表，支持状态和优先级过滤",
)
async def list_tasks(
    status: str | None = Query(None, description="状态过滤"),
    priority: str | None = Query(None, description="优先级过滤"),
    limit: int = Query(50, ge=1, le=100, description="数量限制"),
):
    """列出任务"""
    scheduler = get_task_scheduler()

    # 转换状态
    status_enum = None
    if status:
        try:
            status_enum = PiTaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    # 转换优先级
    priority_enum = None
    if priority:
        try:
            priority_enum = PiTaskPriority(priority)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    tasks = scheduler.list_tasks(
        status=status_enum,
        priority=priority_enum,
        limit=limit,
    )

    return TaskListResponse(
        tasks=tasks,
        total=len(tasks),
    )


@router.get(
    "/tasks/{task_id}",
    response_model=PiTaskInfo,
    summary="获取任务详情",
)
async def get_task(task_id: str):
    """获取任务详情"""
    scheduler = get_task_scheduler()
    task = scheduler.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.post(
    "/tasks/{task_id}/cancel",
    summary="取消任务",
)
async def cancel_task(task_id: str):
    """取消任务"""
    scheduler = get_task_scheduler()
    success = await scheduler.cancel_task(task_id)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel task")

    return {"status": "cancelled", "task_id": task_id}


@router.post(
    "/tasks/assign",
    summary="分配任务",
    description="手动分配待处理任务到可用 Agent",
)
async def assign_tasks(
    task_id: str | None = Query(None, description="指定任务 ID"),
    strategy: str = Query("smart", description="分配策略"),
):
    """分配任务"""
    scheduler = get_task_scheduler()

    # 转换策略
    try:
        strategy_enum = TaskAssignmentStrategy(strategy)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {strategy}")

    if task_id:
        assignment = await scheduler.assign_task(task_id, strategy_enum)
        if not assignment:
            raise HTTPException(status_code=400, detail="Failed to assign task")
        return assignment.model_dump()
    else:
        count = await scheduler.assign_pending_tasks()
        return {"assigned_count": count}


# ===========================================
# Workflow 端点
# ===========================================


@router.post(
    "/execute",
    response_model=PiWorkflowResult,
    summary="执行工作流",
    description="执行完整的工作流，自动创建任务并分配给 Agent",
)
async def execute_workflow(request: ExecuteWorkflowRequest):
    """执行工作流"""
    scheduler = get_task_scheduler()
    aggregator = get_result_aggregator()

    # 创建工作流结果
    result = PiWorkflowResult(
        name=request.name,
        total_tasks=len(request.tasks),
    )

    result.started_at = __import__('datetime').datetime.now()

    # 转换策略
    try:
        TaskAssignmentStrategy(request.assignment_strategy)
    except ValueError:
        pass

    # 提交所有任务
    task_ids = []
    for task_req in request.tasks:
        try:
            priority = PiTaskPriority(task_req.priority)
        except ValueError:
            priority = PiTaskPriority.NORMAL

        config = PiTaskConfig(
            title=task_req.title,
            description=task_req.description,
            priority=priority,
            required_capabilities=task_req.required_capabilities,
            input_data=task_req.input_data,
            dependencies=task_req.dependencies,
            max_retries=task_req.max_retries,
            timeout_seconds=task_req.timeout_seconds,
        )

        task = await scheduler.submit_task(config)
        task_ids.append(task.id)
        result.task_results[task.id] = task

    logger.info(
        "Workflow tasks submitted",
        workflow_name=request.name,
        task_count=len(task_ids),
    )

    # 分配任务
    await scheduler.assign_pending_tasks()

    # 模拟执行（实际应该由 Agent 执行）
    for task_id in task_ids:
        task = scheduler.get_task(task_id)
        if task and task.status == PiTaskStatus.ASSIGNED:
            # 标记开始
            await scheduler.start_task(task_id)

            # 模拟完成
            output = {
                "status": "completed",
                "output": f"Task {task.title} executed successfully",
            }
            await scheduler.complete_task(task_id, output, success=True)
            result.completed_tasks += 1

            # 收集结果
            aggregator.collect(task_id, task.assigned_agent_id, output)

            # 更新任务结果
            result.task_results[task_id] = scheduler.get_task(task_id)

    # 完成工作流
    result.completed_at = __import__('datetime').datetime.now()
    result.status = "completed"

    logger.info(
        "Workflow completed",
        workflow_name=request.name,
        completed=result.completed_tasks,
        failed=result.failed_tasks,
    )

    return result


# ===========================================
# Stats 端点
# ===========================================


@router.get(
    "/stats",
    summary="获取系统统计",
    description="获取 Pi 系统的运行统计信息",
)
async def get_system_stats():
    """获取系统统计"""
    manager = get_agent_manager()
    scheduler = get_task_scheduler()
    aggregator = get_result_aggregator()

    agent_stats = manager.get_stats()
    task_stats = scheduler.get_stats()
    result_stats = aggregator.get_stats()

    return {
        "agents": agent_stats,
        "tasks": task_stats,
        "results": result_stats,
    }


# ===========================================
# Evaluation 端点
# ===========================================


@router.post(
    "/evaluate/{task_id}",
    response_model=ResultEvaluation,
    summary="评估任务结果",
)
async def evaluate_task_result(task_id: str):
    """评估任务结果"""
    scheduler = get_task_scheduler()
    aggregator = get_result_aggregator()

    task = scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != PiTaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Task not completed yet")

    # 获取收集的结果
    collected = aggregator.get_collected_results(task_id)
    if not collected:
        raise HTTPException(status_code=404, detail="No results found for task")

    # 评估结果
    from .result_aggregator import ResultEvaluator
    evaluator = ResultEvaluator()

    evaluation = await evaluator.evaluate(
        task,
        collected[0]["result"],
        collected[0]["agent_id"],
    )

    return evaluation


@router.post(
    "/resolve/{task_id}",
    response_model=ConflictResolution,
    summary="解决结果冲突",
)
async def resolve_task_conflict(
    task_id: str,
    strategy: str = Query("majority", description="解决策略"),
):
    """解决任务结果冲突"""
    scheduler = get_task_scheduler()
    aggregator = get_result_aggregator()

    task = scheduler.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    collected = aggregator.get_collected_results(task_id)
    if len(collected) < 2:
        raise HTTPException(status_code=400, detail="No conflict to resolve")

    from .result_aggregator import ConflictResolver
    resolver = ConflictResolver()

    results = [c["result"] for c in collected]
    resolution = await resolver.resolve(task_id, results, strategy)

    return resolution


__all__ = ["router"]
