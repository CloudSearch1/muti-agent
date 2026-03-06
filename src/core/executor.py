"""
Agent 执行引擎

统一管理和调度 Agent 执行，支持工作流编排
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..core.models import Task
from ..db.crud import create_task as crud_create_task
from ..db.database import get_db_session

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowTask:
    """工作流中的任务"""
    agent_name: str
    task_description: str
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 3
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class Workflow:
    """工作流定义"""
    name: str
    description: str
    tasks: List[WorkflowTask] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentExecutor:
    """
    Agent 执行引擎
    
    功能:
    - 工作流编排和执行
    - 任务调度（支持依赖）
    - 并发执行
    - 错误处理和重试
    - 状态管理
    """
    
    def __init__(self):
        self._agents: Dict[str, Any] = {}
        self._workflows: Dict[str, Workflow] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        logger.info("AgentExecutor initialized")
    
    def register_agent(self, name: str, agent_instance: Any):
        """注册 Agent"""
        self._agents[name] = agent_instance
        logger.info(f"Agent registered: {name}")
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """触发事件"""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
    
    async def execute_workflow(
        self,
        workflow: Workflow,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行工作流
        
        Args:
            workflow: 工作流定义
            context: 执行上下文
        
        Returns:
            执行结果
        """
        logger.info(f"Starting workflow: {workflow.name}")
        await self._emit_event("workflow_started", {
            "workflow_name": workflow.name,
            "task_count": len(workflow.tasks),
        })
        
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now()
        
        try:
            # 构建任务依赖图
            task_map = {i: task for i, task in enumerate(workflow.tasks)}
            completed_tasks = set()
            results = {}
            
            # 执行任务（考虑依赖）
            while len(completed_tasks) < len(workflow.tasks):
                # 找到所有可以执行的任务（依赖已满足）
                ready_tasks = []
                for i, task in task_map.items():
                    if i in completed_tasks:
                        continue
                    if all(dep in completed_tasks for dep in task.dependencies):
                        ready_tasks.append((i, task))
                
                if not ready_tasks:
                    # 检查是否有循环依赖
                    remaining = [i for i in task_map if i not in completed_tasks]
                    if remaining:
                        raise ValueError(f"Circular dependency detected: {remaining}")
                    break
                
                # 并发执行就绪任务
                tasks_to_run = [
                    self._execute_task(task, context, results)
                    for _, task in ready_tasks
                ]
                
                task_results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
                
                # 处理结果
                for (task_idx, task), result in zip(ready_tasks, task_results):
                    if isinstance(result, Exception):
                        task.status = TaskStatus.FAILED
                        task.error = str(result)
                        logger.error(f"Task failed: {task.agent_name} - {result}")
                        
                        # 如果是关键任务失败，可以选择终止工作流
                        if task.retry_count == 0:
                            workflow.status = WorkflowStatus.FAILED
                            workflow.completed_at = datetime.now()
                            await self._emit_event("workflow_failed", {
                                "workflow_name": workflow.name,
                                "failed_task": task.agent_name,
                                "error": str(result),
                            })
                            return {"status": "failed", "error": str(result)}
                    else:
                        task.status = TaskStatus.COMPLETED
                        task.result = result
                        task.completed_at = datetime.now()
                        completed_tasks.add(task_idx)
                        results[task.agent_name] = result
                        
                        logger.info(f"Task completed: {task.agent_name}")
                        await self._emit_event("task_completed", {
                            "agent_name": task.agent_name,
                            "result": result,
                        })
            
            # 所有任务完成
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.now()
            
            await self._emit_event("workflow_completed", {
                "workflow_name": workflow.name,
                "results": results,
            })
            
            return {
                "status": "completed",
                "results": results,
                "workflow_name": workflow.name,
            }
            
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.completed_at = datetime.now()
            logger.error(f"Workflow failed: {e}", exc_info=True)
            
            await self._emit_event("workflow_failed", {
                "workflow_name": workflow.name,
                "error": str(e),
            })
            
            return {"status": "failed", "error": str(e)}
    
    async def _execute_task(
        self,
        task: WorkflowTask,
        context: Dict[str, Any],
        previous_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行单个任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        logger.info(f"Executing task: {task.agent_name}")
        await self._emit_event("task_started", {
            "agent_name": task.agent_name,
            "description": task.task_description,
        })
        
        # 获取 Agent
        agent = self._agents.get(task.agent_name)
        if not agent:
            raise ValueError(f"Agent not found: {task.agent_name}")
        
        # 准备任务数据
        task_input = {
            "description": task.task_description,
            "context": context,
            "previous_results": previous_results,
        }
        
        # 创建任务对象
        task_obj = Task(
            id=f"workflow_task_{task.agent_name}",
            title=task.agent_name,
            description=task.task_description,
            input_data=task_input,
        )
        
        # 执行 Agent
        try:
            result = await asyncio.wait_for(
                agent.execute(task_obj),
                timeout=task.timeout_seconds,
            )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task timeout: {task.agent_name} ({task.timeout_seconds}s)")
    
    def create_standard_workflow(self, workflow_name: str) -> Workflow:
        """
        创建标准研发工作流
        
        包含：Planner → Architect → Coder → Tester → DocWriter
        """
        workflow = Workflow(
            name=workflow_name,
            description="标准研发工作流",
        )
        
        # 添加标准任务
        workflow.tasks = [
            WorkflowTask(
                agent_name="Planner",
                task_description="分析需求，制定任务计划",
                dependencies=[],
            ),
            WorkflowTask(
                agent_name="Architect",
                task_description="设计系统架构",
                dependencies=[0],  # 依赖 Planner
            ),
            WorkflowTask(
                agent_name="Coder",
                task_description="实现代码",
                dependencies=[1],  # 依赖 Architect
            ),
            WorkflowTask(
                agent_name="Tester",
                task_description="编写和执行测试",
                dependencies=[2],  # 依赖 Coder
            ),
            WorkflowTask(
                agent_name="DocWriter",
                task_description="编写文档",
                dependencies=[2],  # 依赖 Coder（可以和 Tester 并行）
            ),
        ]
        
        return workflow
    
    def get_workflow_status(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """获取工作流状态"""
        workflow = self._workflows.get(workflow_name)
        if not workflow:
            return None
        
        return {
            "name": workflow.name,
            "status": workflow.status.value,
            "created_at": workflow.created_at.isoformat(),
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
            "tasks": [
                {
                    "agent": task.agent_name,
                    "status": task.status.value,
                    "error": task.error,
                }
                for task in workflow.tasks
            ],
        }


# 全局执行引擎实例
_executor: Optional[AgentExecutor] = None


def get_executor() -> AgentExecutor:
    """获取执行引擎实例"""
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor


async def init_executor(agents: Dict[str, Any]) -> AgentExecutor:
    """初始化执行引擎"""
    executor = get_executor()
    for name, agent in agents.items():
        executor.register_agent(name, agent)
    return executor
