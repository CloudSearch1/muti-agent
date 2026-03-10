"""
Pi 任务调度器

职责：
- 任务队列管理
- 智能任务分配算法
- 负载均衡
- 优先级调度

版本: 1.0.0
"""

import asyncio
import heapq
from datetime import datetime
from typing import Any

import structlog

from .agent_manager import AgentManager, get_agent_manager
from .types import (
    PiAgentInfo,
    PiAgentStatus,
    PiTaskConfig,
    PiTaskInfo,
    PiTaskPriority,
    PiTaskStatus,
    TaskAssignment,
    TaskAssignmentStrategy,
)

logger = structlog.get_logger(__name__)


class TaskScheduler:
    """
    任务调度器

    管理任务的分配、调度和执行

    使用方式:
        scheduler = TaskScheduler(agent_manager)
        task = await scheduler.submit_task(config)
        assignment = await scheduler.assign_task(task.id)
        await scheduler.complete_task(task.id, result)
    """

    def __init__(
        self,
        agent_manager: AgentManager | None = None,
        strategy: TaskAssignmentStrategy = TaskAssignmentStrategy.SMART,
    ):
        """
        初始化任务调度器

        Args:
            agent_manager: Agent 管理器
            strategy: 任务分配策略
        """
        self._agent_manager = agent_manager or get_agent_manager()
        self._strategy = strategy

        # 任务存储
        self._tasks: dict[str, PiTaskInfo] = {}
        self._pending_queue: list[tuple[int, str]] = []  # (priority, task_id)
        self._task_assignments: dict[str, TaskAssignment] = {}

        # 统计信息
        self._total_submitted = 0
        self._total_completed = 0
        self._total_failed = 0

        logger.info(
            "TaskScheduler initialized",
            strategy=strategy.value,
        )

    # ===========================================
    # 任务提交和管理
    # ===========================================

    async def submit_task(self, config: PiTaskConfig) -> PiTaskInfo:
        """
        提交任务

        Args:
            config: 任务配置

        Returns:
            任务信息
        """
        # 创建任务
        task = PiTaskInfo(
            title=config.title,
            description=config.description,
            priority=config.priority,
            required_capabilities=config.required_capabilities,
            input_data=config.input_data,
            dependencies=config.dependencies,
            max_retries=config.max_retries,
            metadata=config.metadata.copy(),
        )

        # 存储任务
        self._tasks[task.id] = task
        self._total_submitted += 1

        # 加入待处理队列
        priority_level = self._get_priority_level(task.priority)
        heapq.heappush(self._pending_queue, (-priority_level, task.id))

        # 更新状态
        task.status = PiTaskStatus.QUEUED

        logger.info(
            "Task submitted",
            task_id=task.id,
            title=task.title,
            priority=task.priority.value,
        )

        return task

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功取消
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        # 只能取消待处理的任务
        if task.status in [PiTaskStatus.COMPLETED, PiTaskStatus.FAILED]:
            return False

        task.status = PiTaskStatus.CANCELLED

        logger.info("Task cancelled", task_id=task_id)

        return True

    def get_task(self, task_id: str) -> PiTaskInfo | None:
        """获取任务信息"""
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: PiTaskStatus | None = None,
        priority: PiTaskPriority | None = None,
        limit: int = 50,
    ) -> list[PiTaskInfo]:
        """
        列出任务

        Args:
            status: 状态过滤
            priority: 优先级过滤
            limit: 数量限制

        Returns:
            任务列表
        """
        tasks = list(self._tasks.values())

        # 状态过滤
        if status:
            tasks = [t for t in tasks if t.status == status]

        # 优先级过滤
        if priority:
            tasks = [t for t in tasks if t.priority == priority]

        # 按创建时间倒序
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return tasks[:limit]

    # ===========================================
    # 任务分配
    # ===========================================

    async def assign_task(
        self,
        task_id: str | None = None,
        strategy: TaskAssignmentStrategy | None = None,
    ) -> TaskAssignment | None:
        """
        分配任务

        Args:
            task_id: 指定任务 ID（None 则自动选择）
            strategy: 分配策略（None 使用默认策略）

        Returns:
            任务分配记录
        """
        # 获取待分配任务
        task = None
        if task_id:
            task = self._tasks.get(task_id)
            if not task or task.status not in [
                PiTaskStatus.QUEUED,
                PiTaskStatus.PENDING,
            ]:
                logger.warning("Task not available for assignment", task_id=task_id)
                return None
        else:
            # 从队列中获取最高优先级任务
            task = await self._get_next_task()
            if not task:
                return None

        # 使用指定策略或默认策略
        use_strategy = strategy or self._strategy

        # 检查依赖
        if not await self._check_dependencies(task):
            logger.debug("Task dependencies not satisfied", task_id=task.id)
            return None

        # 根据策略选择 Agent
        agent = await self._select_agent(task, use_strategy)
        if not agent:
            logger.warning(
                "No available agent for task",
                task_id=task.id,
                capabilities=task.required_capabilities,
            )
            return None

        # 创建分配记录
        assignment = TaskAssignment(
            task_id=task.id,
            agent_id=agent.id,
            reason=f"Strategy: {use_strategy.value}",
            score=self._calculate_match_score(task, agent),
        )

        # 更新状态
        task.status = PiTaskStatus.ASSIGNED
        task.assigned_agent_id = agent.id
        self._task_assignments[task.id] = assignment

        # 更新 Agent 状态
        self._agent_manager.set_agent_busy(agent.id, task.id)

        logger.info(
            "Task assigned",
            task_id=task.id,
            agent_id=agent.id,
            strategy=use_strategy.value,
        )

        return assignment

    async def assign_pending_tasks(self) -> int:
        """
        分配所有待处理任务

        Returns:
            成功分配的任务数
        """
        assigned = 0

        while self._pending_queue:
            assignment = await self.assign_task()
            if assignment:
                assigned += 1
            else:
                break

        return assigned

    # ===========================================
    # 任务执行和完成
    # ===========================================

    async def start_task(self, task_id: str) -> bool:
        """
        开始执行任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功开始
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status != PiTaskStatus.ASSIGNED:
            return False

        task.status = PiTaskStatus.IN_PROGRESS
        task.started_at = datetime.now()

        logger.info("Task started", task_id=task_id)

        return True

    async def complete_task(
        self,
        task_id: str,
        output_data: dict[str, Any] | None = None,
        success: bool = True,
    ) -> bool:
        """
        完成任务

        Args:
            task_id: 任务 ID
            output_data: 输出数据
            success: 是否成功

        Returns:
            是否成功完成
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        # 更新任务状态
        if success:
            task.status = PiTaskStatus.COMPLETED
            task.output_data = output_data or {}
            self._total_completed += 1
        else:
            task.status = PiTaskStatus.FAILED
            self._total_failed += 1

        task.completed_at = datetime.now()

        # 更新 Agent 状态
        if task.assigned_agent_id:
            execution_time = 0.0
            if task.started_at and task.completed_at:
                execution_time = (
                    task.completed_at - task.started_at
                ).total_seconds()

            self._agent_manager.record_task_completion(
                task.assigned_agent_id,
                success,
                execution_time,
            )
            self._agent_manager.set_agent_idle(task.assigned_agent_id, task_id)

        logger.info(
            "Task completed",
            task_id=task_id,
            success=success,
        )

        return True

    async def fail_task(
        self,
        task_id: str,
        error_message: str,
    ) -> bool:
        """
        任务失败

        Args:
            task_id: 任务 ID
            error_message: 错误信息

        Returns:
            是否成功记录失败
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.error_message = error_message
        task.retry_count += 1

        # 检查是否可以重试
        if task.retry_count < task.max_retries:
            task.status = PiTaskStatus.PENDING
            task.assigned_agent_id = None
            task.started_at = None
            task.error_message = None

            # 重新加入队列
            priority_level = self._get_priority_level(task.priority)
            heapq.heappush(self._pending_queue, (-priority_level, task.id))

            logger.info(
                "Task scheduled for retry",
                task_id=task_id,
                retry_count=task.retry_count,
                max_retries=task.max_retries,
            )
        else:
            # 标记为失败
            await self.complete_task(task_id, success=False)
            task.error_message = error_message

            logger.warning(
                "Task failed permanently",
                task_id=task_id,
                error=error_message,
            )

        return True

    # ===========================================
    # 统计信息
    # ===========================================

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        pending = sum(
            1 for t in self._tasks.values()
            if t.status in [PiTaskStatus.PENDING, PiTaskStatus.QUEUED]
        )
        in_progress = sum(
            1 for t in self._tasks.values()
            if t.status == PiTaskStatus.IN_PROGRESS
        )
        completed = sum(
            1 for t in self._tasks.values()
            if t.status == PiTaskStatus.COMPLETED
        )
        failed = sum(
            1 for t in self._tasks.values()
            if t.status == PiTaskStatus.FAILED
        )

        # 计算平均执行时间
        completed_tasks = [
            t for t in self._tasks.values()
            if t.status == PiTaskStatus.COMPLETED and t.started_at and t.completed_at
        ]
        avg_duration = 0.0
        if completed_tasks:
            total_duration = sum(
                (t.completed_at - t.started_at).total_seconds()
                for t in completed_tasks
            )
            avg_duration = total_duration / len(completed_tasks)

        return {
            "total_submitted": self._total_submitted,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "pending_tasks": pending,
            "in_progress_tasks": in_progress,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "avg_task_duration": round(avg_duration, 3),
            "queue_size": len(self._pending_queue),
        }

    # ===========================================
    # 内部方法
    # ===========================================

    def _get_priority_level(self, priority: PiTaskPriority) -> int:
        """获取优先级数值"""
        levels = {
            PiTaskPriority.LOW: 1,
            PiTaskPriority.NORMAL: 2,
            PiTaskPriority.HIGH: 3,
            PiTaskPriority.CRITICAL: 4,
        }
        return levels.get(priority, 2)

    async def _get_next_task(self) -> PiTaskInfo | None:
        """从队列获取下一个待处理任务"""
        while self._pending_queue:
            _, task_id = heapq.heappop(self._pending_queue)
            task = self._tasks.get(task_id)

            if task and task.status in [PiTaskStatus.QUEUED, PiTaskStatus.PENDING]:
                return task

        return None

    async def _check_dependencies(self, task: PiTaskInfo) -> bool:
        """检查任务依赖是否满足"""
        if not task.dependencies:
            return True

        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if not dep_task or dep_task.status != PiTaskStatus.COMPLETED:
                return False

        return True

    async def _select_agent(
        self,
        task: PiTaskInfo,
        strategy: TaskAssignmentStrategy,
    ) -> PiAgentInfo | None:
        """
        根据策略选择 Agent

        Args:
            task: 任务信息
            strategy: 分配策略

        Returns:
            选中的 Agent 或 None
        """
        # 获取可用 Agent
        available_agents = self._agent_manager.get_available_agents(
            capabilities=task.required_capabilities if task.required_capabilities else None,
        )

        if not available_agents:
            return None

        if strategy == TaskAssignmentStrategy.ROUND_ROBIN:
            return self._select_round_robin(available_agents)
        elif strategy == TaskAssignmentStrategy.LEAST_LOADED:
            return self._select_least_loaded(available_agents)
        elif strategy == TaskAssignmentStrategy.CAPABILITY_MATCH:
            return self._select_capability_match(available_agents, task)
        elif strategy == TaskAssignmentStrategy.PRIORITY_FIRST:
            return self._select_priority_first(available_agents, task)
        else:  # SMART
            return self._select_smart(available_agents, task)

    def _select_round_robin(self, agents: list[PiAgentInfo]) -> PiAgentInfo:
        """轮询选择"""
        return agents[0]

    def _select_least_loaded(self, agents: list[PiAgentInfo]) -> PiAgentInfo:
        """选择负载最低的"""
        return min(agents, key=lambda a: a.get_load())

    def _select_capability_match(
        self,
        agents: list[PiAgentInfo],
        task: PiTaskInfo,
    ) -> PiAgentInfo:
        """选择能力匹配度最高的"""
        if not task.required_capabilities:
            return agents[0]

        best_agent = None
        best_score = -1

        for agent in agents:
            score = self._calculate_match_score(task, agent)
            if score > best_score:
                best_score = score
                best_agent = agent

        return best_agent or agents[0]

    def _select_priority_first(
        self,
        agents: list[PiAgentInfo],
        task: PiTaskInfo,
    ) -> PiAgentInfo:
        """优先级优先选择"""
        if task.is_high_priority():
            # 高优先级任务选择成功率最高的
            return max(
                agents,
                key=lambda a: a.completed_tasks / max(1, a.completed_tasks + a.failed_tasks)
            )
        else:
            # 普通任务选择负载最低的
            return self._select_least_loaded(agents)

    def _select_smart(
        self,
        agents: list[PiAgentInfo],
        task: PiTaskInfo,
    ) -> PiAgentInfo:
        """
        智能选择

        综合考虑：
        1. 能力匹配度
        2. 负载情况
        3. 历史成功率
        4. 任务优先级
        """
        best_agent = None
        best_score = -1

        for agent in agents:
            score = self._calculate_smart_score(task, agent)
            if score > best_score:
                best_score = score
                best_agent = agent

        return best_agent or agents[0]

    def _calculate_match_score(self, task: PiTaskInfo, agent: PiAgentInfo) -> float:
        """计算能力匹配分数"""
        if not task.required_capabilities:
            return 1.0

        matched = sum(
            1 for cap in task.required_capabilities
            if cap in agent.capabilities
        )
        return matched / len(task.required_capabilities)

    def _calculate_smart_score(self, task: PiTaskInfo, agent: PiAgentInfo) -> float:
        """
        计算智能分配分数

        分数 = 能力匹配 * 0.3 + 负载因子 * 0.3 + 成功率 * 0.3 + 优先级因子 * 0.1
        """
        # 能力匹配分数
        capability_score = self._calculate_match_score(task, agent)

        # 负载分数（负载越低分数越高）
        load_score = 1.0 - agent.get_load()

        # 成功率分数
        total = agent.completed_tasks + agent.failed_tasks
        success_score = agent.completed_tasks / total if total > 0 else 1.0

        # 优先级因子（高优先级任务倾向于选择成功率高的 Agent）
        priority_factor = 1.0
        if task.is_high_priority():
            priority_factor = success_score

        # 综合分数
        return (
            capability_score * 0.3 +
            load_score * 0.3 +
            success_score * 0.3 +
            priority_factor * 0.1
        )


# 全局单例
_task_scheduler: TaskScheduler | None = None


def get_task_scheduler() -> TaskScheduler:
    """获取任务调度器单例"""
    global _task_scheduler
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler()
    return _task_scheduler


__all__ = [
    "TaskScheduler",
    "get_task_scheduler",
]