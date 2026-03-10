"""
Pi Agent 管理器

职责：
- Agent 生命周期管理（创建、启动、停止、销毁）
- Agent 状态监控
- Agent 配置管理
- Agent 能力注册和发现

版本: 1.0.0
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog

from .types import (
    AgentLoadInfo,
    PiAgentConfig,
    PiAgentInfo,
    PiAgentStatus,
)

logger = structlog.get_logger(__name__)


class AgentManager:
    """
    Agent 管理器

    管理所有 Agent 的生命周期、状态和能力

    使用方式:
        manager = AgentManager()
        agent = await manager.create_agent(config)
        await manager.start_agent(agent.id)
        info = manager.get_agent_info(agent.id)
        await manager.stop_agent(agent.id)
    """

    def __init__(self, max_agents: int = 100):
        """
        初始化 Agent 管理器

        Args:
            max_agents: 最大 Agent 数量
        """
        self._agents: dict[str, PiAgentInfo] = {}
        self._max_agents = max_agents

        # 回调函数
        self._on_agent_created: Callable | None = None
        self._on_agent_started: Callable | None = None
        self._on_agent_stopped: Callable | None = None
        self._on_agent_destroyed: Callable | None = None
        self._on_status_change: Callable | None = None

        # 统计信息
        self._created_count = 0
        self._started_at: datetime | None = None

        logger.info("AgentManager initialized", max_agents=max_agents)

    # ===========================================
    # Agent 生命周期管理
    # ===========================================

    async def create_agent(self, config: PiAgentConfig) -> PiAgentInfo:
        """
        创建 Agent

        Args:
            config: Agent 配置

        Returns:
            创建的 Agent 信息

        Raises:
            ValueError: 参数错误或达到最大数量
        """
        # 检查数量限制
        if len(self._agents) >= self._max_agents:
            raise ValueError(f"Maximum agent limit reached: {self._max_agents}")

        # 验证配置
        if not config.name:
            raise ValueError("Agent name is required")
        if not config.role:
            raise ValueError("Agent role is required")

        # 创建 Agent 信息
        agent = PiAgentInfo(
            name=config.name,
            role=config.role,
            status=PiAgentStatus.IDLE,
            capabilities=config.capabilities,
            max_concurrent_tasks=config.max_concurrent_tasks,
            metadata=config.metadata.copy(),
        )

        # 存储到字典
        self._agents[agent.id] = agent
        self._created_count += 1

        # 触发回调
        if self._on_agent_created:
            await self._safe_callback(self._on_agent_created, agent)

        logger.info(
            "Agent created",
            agent_id=agent.id,
            name=agent.name,
            role=agent.role,
        )

        return agent

    async def start_agent(self, agent_id: str) -> bool:
        """
        启动 Agent

        Args:
            agent_id: Agent ID

        Returns:
            是否成功启动
        """
        agent = self._agents.get(agent_id)
        if not agent:
            logger.warning("Agent not found", agent_id=agent_id)
            return False

        if agent.status not in [PiAgentStatus.IDLE, PiAgentStatus.OFFLINE]:
            logger.warning(
                "Agent cannot be started",
                agent_id=agent_id,
                status=agent.status,
            )
            return False

        # 更新状态
        old_status = agent.status
        agent.status = PiAgentStatus.IDLE
        agent.last_active_at = datetime.now()

        # 记录启动时间
        if self._started_at is None:
            self._started_at = datetime.now()

        # 触发回调
        if self._on_agent_started:
            await self._safe_callback(self._on_agent_started, agent)
        if self._on_status_change:
            await self._safe_callback(
                self._on_status_change, agent_id, old_status, agent.status
            )

        logger.info("Agent started", agent_id=agent_id)

        return True

    async def stop_agent(self, agent_id: str) -> bool:
        """
        停止 Agent

        Args:
            agent_id: Agent ID

        Returns:
            是否成功停止
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        if agent.status == PiAgentStatus.OFFLINE:
            return True

        # 更新状态
        old_status = agent.status
        agent.status = PiAgentStatus.OFFLINE

        # 触发回调
        if self._on_agent_stopped:
            await self._safe_callback(self._on_agent_stopped, agent)
        if self._on_status_change:
            await self._safe_callback(
                self._on_status_change, agent_id, old_status, agent.status
            )

        logger.info("Agent stopped", agent_id=agent_id)

        return True

    async def destroy_agent(self, agent_id: str) -> bool:
        """
        销毁 Agent

        Args:
            agent_id: Agent ID

        Returns:
            是否成功销毁
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        # 先停止
        if agent.status != PiAgentStatus.OFFLINE:
            await self.stop_agent(agent_id)

        # 从字典中移除
        del self._agents[agent_id]

        # 触发回调
        if self._on_agent_destroyed:
            await self._safe_callback(self._on_agent_destroyed, agent)

        logger.info("Agent destroyed", agent_id=agent_id)

        return True

    # ===========================================
    # 状态管理
    # ===========================================

    def set_agent_busy(self, agent_id: str, task_id: str | None = None) -> bool:
        """
        设置 Agent 为忙碌状态

        Args:
            agent_id: Agent ID
            task_id: 任务 ID

        Returns:
            是否成功
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        agent.status = PiAgentStatus.BUSY
        if task_id and task_id not in agent.current_tasks:
            agent.current_tasks.append(task_id)
        agent.last_active_at = datetime.now()

        logger.debug("Agent set busy", agent_id=agent_id, task_id=task_id)
        return True

    def set_agent_idle(self, agent_id: str, task_id: str | None = None) -> bool:
        """
        设置 Agent 为空闲状态

        Args:
            agent_id: Agent ID
            task_id: 任务 ID（从当前任务列表移除）

        Returns:
            是否成功
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        # 从当前任务列表移除
        if task_id and task_id in agent.current_tasks:
            agent.current_tasks.remove(task_id)

        # 如果没有其他任务，设置为空闲
        if not agent.current_tasks:
            agent.status = PiAgentStatus.IDLE

        agent.last_active_at = datetime.now()

        logger.debug("Agent set idle", agent_id=agent_id, task_id=task_id)
        return True

    def set_agent_error(self, agent_id: str, error_message: str | None = None) -> bool:
        """
        设置 Agent 为错误状态

        Args:
            agent_id: Agent ID
            error_message: 错误信息

        Returns:
            是否成功
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        old_status = agent.status
        agent.status = PiAgentStatus.ERROR
        if error_message:
            agent.metadata["last_error"] = error_message
        agent.last_active_at = datetime.now()

        logger.warning(
            "Agent set error",
            agent_id=agent_id,
            error=error_message,
        )

        # 异步触发状态变更回调
        if self._on_status_change:
            asyncio.create_task(
                self._safe_callback(
                    self._on_status_change, agent_id, old_status, agent.status
                )
            )

        return True

    def record_task_completion(
        self,
        agent_id: str,
        success: bool,
        execution_time: float = 0.0,
    ) -> bool:
        """
        记录任务完成

        Args:
            agent_id: Agent ID
            success: 是否成功
            execution_time: 执行时间（秒）

        Returns:
            是否成功记录
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        if success:
            agent.completed_tasks += 1
        else:
            agent.failed_tasks += 1

        # 更新平均执行时间
        total_tasks = agent.completed_tasks + agent.failed_tasks
        if total_tasks > 0:
            agent.avg_execution_time = (
                agent.avg_execution_time * (total_tasks - 1) + execution_time
            ) / total_tasks

        logger.debug(
            "Task completion recorded",
            agent_id=agent_id,
            success=success,
            execution_time=execution_time,
        )

        return True

    # ===========================================
    # 查询接口
    # ===========================================

    def get_agent(self, agent_id: str) -> PiAgentInfo | None:
        """获取 Agent 信息"""
        return self._agents.get(agent_id)

    def get_agent_info(self, agent_id: str) -> dict[str, Any] | None:
        """获取 Agent 详细信息"""
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        return agent.model_dump()

    def list_agents(
        self,
        status: PiAgentStatus | None = None,
        role: str | None = None,
        capability: str | None = None,
    ) -> list[PiAgentInfo]:
        """
        列出 Agent

        Args:
            status: 状态过滤
            role: 角色过滤
            capability: 能力过滤

        Returns:
            Agent 列表
        """
        agents = list(self._agents.values())

        # 状态过滤
        if status:
            agents = [a for a in agents if a.status == status]

        # 角色过滤
        if role:
            agents = [a for a in agents if a.role == role]

        # 能力过滤
        if capability:
            agents = [a for a in agents if capability in a.capabilities]

        return agents

    def get_available_agents(
        self,
        capabilities: list[str] | None = None,
        exclude_ids: list[str] | None = None,
    ) -> list[PiAgentInfo]:
        """
        获取可用的 Agent

        Args:
            capabilities: 所需能力列表
            exclude_ids: 排除的 Agent ID 列表

        Returns:
            可用的 Agent 列表
        """
        agents = []

        for agent in self._agents.values():
            # 检查是否可用
            if not agent.is_available():
                continue

            # 检查是否在排除列表中
            if exclude_ids and agent.id in exclude_ids:
                continue

            # 检查能力
            if capabilities:
                if not all(cap in agent.capabilities for cap in capabilities):
                    continue

            agents.append(agent)

        # 按负载排序
        agents.sort(key=lambda a: a.get_load())

        return agents

    def get_agent_load(self, agent_id: str) -> AgentLoadInfo | None:
        """
        获取 Agent 负载信息

        Args:
            agent_id: Agent ID

        Returns:
            负载信息
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        total_tasks = agent.completed_tasks + agent.failed_tasks
        success_rate = (
            agent.completed_tasks / total_tasks if total_tasks > 0 else 1.0
        )

        return AgentLoadInfo(
            agent_id=agent.id,
            current_tasks=len(agent.current_tasks),
            max_tasks=agent.max_concurrent_tasks,
            load_ratio=agent.get_load(),
            recent_success_rate=success_rate,
            avg_response_time=agent.avg_execution_time,
        )

    # ===========================================
    # 统计信息
    # ===========================================

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        total = len(self._agents)
        active = sum(
            1 for a in self._agents.values()
            if a.status != PiAgentStatus.OFFLINE
        )
        idle = sum(
            1 for a in self._agents.values()
            if a.status == PiAgentStatus.IDLE
        )
        busy = sum(
            1 for a in self._agents.values()
            if a.status == PiAgentStatus.BUSY
        )
        error = sum(
            1 for a in self._agents.values()
            if a.status == PiAgentStatus.ERROR
        )

        return {
            "total_agents": total,
            "active_agents": active,
            "idle_agents": idle,
            "busy_agents": busy,
            "error_agents": error,
            "created_count": self._created_count,
            "uptime_seconds": (
                (datetime.now() - self._started_at).total_seconds()
                if self._started_at else 0
            ),
        }

    # ===========================================
    # 回调注册
    # ===========================================

    def on_agent_created(self, callback: Callable) -> None:
        """注册 Agent 创建回调"""
        self._on_agent_created = callback

    def on_agent_started(self, callback: Callable) -> None:
        """注册 Agent 启动回调"""
        self._on_agent_started = callback

    def on_agent_stopped(self, callback: Callable) -> None:
        """注册 Agent 停止回调"""
        self._on_agent_stopped = callback

    def on_agent_destroyed(self, callback: Callable) -> None:
        """注册 Agent 销毁回调"""
        self._on_agent_destroyed = callback

    def on_status_change(self, callback: Callable) -> None:
        """注册状态变更回调"""
        self._on_status_change = callback

    # ===========================================
    # 内部方法
    # ===========================================

    async def _safe_callback(self, callback: Callable, *args) -> None:
        """安全执行回调"""
        try:
            import asyncio
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error("Callback failed", error=str(e), callback=callback.__name__)

    async def cleanup_idle_agents(self, max_idle_seconds: int = 3600) -> int:
        """
        清理长时间空闲的 Agent

        Args:
            max_idle_seconds: 最大空闲时间（秒）

        Returns:
            清理的 Agent 数量
        """
        now = datetime.now()
        cleaned = 0

        to_remove = []
        for agent_id, agent in self._agents.items():
            if agent.status == PiAgentStatus.IDLE and agent.last_active_at:
                idle_time = (now - agent.last_active_at).total_seconds()
                if idle_time > max_idle_seconds:
                    to_remove.append(agent_id)

        for agent_id in to_remove:
            await self.destroy_agent(agent_id)
            cleaned += 1

        if cleaned > 0:
            logger.info("Cleaned up idle agents", count=cleaned)

        return cleaned


# 全局单例
_agent_manager: AgentManager | None = None


def get_agent_manager() -> AgentManager:
    """获取 Agent 管理器单例"""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
    return _agent_manager


__all__ = [
    "AgentManager",
    "get_agent_manager",
]
