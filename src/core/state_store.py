"""
统一状态管理

类似 Redux 的状态管理模式，管理所有 Agent 和系统状态
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models import AgentState as AgentStatusEnum

logger = logging.getLogger(__name__)


@dataclass
class AgentStatusData:
    """Agent 状态数据"""
    name: str
    status: AgentStatusEnum = AgentStatusEnum.IDLE
    current_task: str | None = None
    progress: float = 0.0
    message: str = ""
    last_updated: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "current_task": self.current_task,
            "progress": self.progress,
            "message": self.message,
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SystemState:
    """系统全局状态"""
    active_workflows: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_agents: int = 0
    total_agents: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_workflows": self.active_workflows,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "active_agents": self.active_agents,
            "total_agents": self.total_agents,
            "last_updated": self.last_updated.isoformat(),
        }


class StateStore:
    """
    状态存储

    功能:
    - 集中管理所有状态
    - 支持状态订阅和通知
    - 线程安全
    - 状态历史
    """

    def __init__(self):
        self._agent_states: dict[str, AgentStatusData] = {}
        self._system_state = SystemState()
        self._subscribers: list[Callable] = []
        self._lock = asyncio.Lock()
        self._history: list[dict[str, Any]] = []
        logger.info("StateStore initialized")

    async def subscribe(self, callback: Callable[[dict[str, Any]], None]):
        """订阅状态变化"""
        async with self._lock:
            self._subscribers.append(callback)
            logger.debug(f"Subscriber added, total: {len(self._subscribers)}")

    async def unsubscribe(self, callback: Callable):
        """取消订阅"""
        async with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)
                logger.debug(f"Subscriber removed, total: {len(self._subscribers)}")

    async def _notify_subscribers(self, change: dict[str, Any]):
        """通知订阅者"""
        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(change)
                else:
                    callback(change)
            except Exception as e:
                logger.error(f"State subscriber error: {e}")

    async def set_agent_state(
        self,
        agent_name: str,
        status: AgentStatusEnum,
        current_task: str | None = None,
        progress: float = 0.0,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        """设置 Agent 状态"""
        async with self._lock:
            # 获取或创建 Agent 状态
            if agent_name not in self._agent_states:
                self._agent_states[agent_name] = AgentStatusData(name=agent_name)

            agent_state = self._agent_states[agent_name]
            old_status = agent_state.status

            # 更新状态
            agent_state.status = status
            agent_state.current_task = current_task
            agent_state.progress = progress
            agent_state.message = message
            agent_state.last_updated = datetime.now()
            if metadata:
                agent_state.metadata.update(metadata)

            # 更新系统状态
            self._update_system_state()

            # 记录历史
            change = {
                "type": "agent_state_change",
                "agent_name": agent_name,
                "old_status": old_status.value,
                "new_status": status.value,
                "timestamp": datetime.now().isoformat(),
            }
            self._history.append(change)

            # 限制历史记录大小
            if len(self._history) > 1000:
                self._history = self._history[-1000:]

            logger.debug(
                f"Agent state changed: {agent_name} {old_status.value} -> {status.value}",
            )

        # 通知订阅者（在锁外）
        await self._notify_subscribers(change)

    async def get_agent_state(self, agent_name: str) -> AgentStatusData | None:
        """获取 Agent 状态"""
        return self._agent_states.get(agent_name)

    async def get_all_agent_states(self) -> dict[str, dict[str, Any]]:
        """获取所有 Agent 状态"""
        return {
            name: state.to_dict()
            for name, state in self._agent_states.items()
        }

    async def get_system_state(self) -> SystemState:
        """获取系统状态"""
        return self._system_state

    def _update_system_state(self):
        """更新系统状态"""
        self._system_state.active_agents = sum(
            1 for state in self._agent_states.values()
            if state.status == AgentStatusEnum.BUSY
        )
        self._system_state.total_agents = len(self._agent_states)
        self._system_state.last_updated = datetime.now()

    async def increment_workflow_count(self):
        """增加活跃工作流计数"""
        async with self._lock:
            self._system_state.active_workflows += 1
            self._system_state.last_updated = datetime.now()

    async def decrement_workflow_count(self):
        """减少活跃工作流计数"""
        async with self._lock:
            self._system_state.active_workflows = max(0, self._system_state.active_workflows - 1)
            self._system_state.last_updated = datetime.now()

    async def record_task_completion(self, success: bool = True):
        """记录任务完成"""
        async with self._lock:
            self._system_state.total_tasks += 1
            if success:
                self._system_state.completed_tasks += 1
            else:
                self._system_state.failed_tasks += 1
            self._system_state.last_updated = datetime.now()

    async def get_state_snapshot(self) -> dict[str, Any]:
        """获取状态快照"""
        return {
            "system": self._system_state.to_dict(),
            "agents": await self.get_all_agent_states(),
            "timestamp": datetime.now().isoformat(),
        }

    async def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取状态变更历史"""
        return self._history[-limit:]


# 全局状态存储实例
_state_store: StateStore | None = None


def get_state_store() -> StateStore:
    """获取状态存储实例"""
    global _state_store
    if _state_store is None:
        _state_store = StateStore()
    return _state_store


async def init_state_store() -> StateStore:
    """初始化状态存储"""
    store = get_state_store()
    logger.info("StateStore initialized")
    return store


# 便捷函数
async def set_agent_status(
    agent_name: str,
    status: AgentStatusEnum,
    **kwargs,
):
    """便捷函数：设置 Agent 状态"""
    store = get_state_store()
    await store.set_agent_state(agent_name, status, **kwargs)


async def get_agent_status(agent_name: str) -> AgentStatusData | None:
    """便捷函数：获取 Agent 状态"""
    store = get_state_store()
    return await store.get_agent_state(agent_name)


async def get_system_status() -> SystemState:
    """便捷函数：获取系统状态"""
    store = get_state_store()
    return await store.get_system_state()
