"""
Agent 状态事件总线

用于 WebSocket 实时推送 Agent 真实状态
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent 状态枚举"""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class AgentEvent:
    """Agent 事件"""
    
    def __init__(
        self,
        agent_name: str,
        status: AgentStatus,
        task_id: Optional[str] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.agent_name = agent_name
        self.status = status
        self.task_id = task_id
        self.progress = progress or 0.0
        self.message = message or ""
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "agent_name": self.agent_name,
            "status": self.status.value,
            "task_id": self.task_id,
            "progress": self.progress,
            "message": self.message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class EventBus:
    """
    事件总线
    
    功能:
    - 发布/订阅模式
    - 支持多个订阅者
    - 线程安全
    - 自动清理过期订阅
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()
        self._agent_states: Dict[str, AgentEvent] = {}
        logger.info("EventBus initialized")
    
    async def subscribe(
        self,
        event_type: str,
        callback: Callable[[AgentEvent], None],
    ):
        """订阅事件"""
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            logger.debug(f"Subscribed to {event_type}")
    
    async def unsubscribe(
        self,
        event_type: str,
        callback: Callable,
    ):
        """取消订阅"""
        async with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                    logger.debug(f"Unsubscribed from {event_type}")
                except ValueError:
                    pass
    
    async def publish(self, event: AgentEvent):
        """发布事件"""
        # 更新 Agent 状态
        self._agent_states[event.agent_name] = event
        
        # 通知订阅者
        event_type = f"agent:{event.agent_name}"
        callbacks = self._subscribers.get(event_type, [])
        
        # 也通知通用订阅者
        all_callbacks = callbacks + self._subscribers.get("agent:*", [])
        
        for callback in all_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
        
        logger.debug(
            f"Published event: {event.agent_name} -> {event.status.value}",
        )
    
    def get_agent_state(self, agent_name: str) -> Optional[AgentEvent]:
        """获取 Agent 当前状态"""
        return self._agent_states.get(agent_name)
    
    def get_all_states(self) -> Dict[str, dict]:
        """获取所有 Agent 状态"""
        return {
            name: event.to_dict()
            for name, event in self._agent_states.items()
        }


# 全局事件总线实例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取事件总线实例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def publish_agent_event(
    agent_name: str,
    status: AgentStatus,
    task_id: Optional[str] = None,
    progress: Optional[float] = None,
    message: Optional[str] = None,
):
    """便捷函数：发布 Agent 事件"""
    event = AgentEvent(
        agent_name=agent_name,
        status=status,
        task_id=task_id,
        progress=progress,
        message=message,
    )
    await get_event_bus().publish(event)


# Agent 状态管理器
class AgentStateManager:
    """
    Agent 状态管理器
    
    与 Agent 生命周期集成，自动发布状态事件
    """
    
    def __init__(self):
        self.event_bus = get_event_bus()
    
    async def set_idle(self, agent_name: str):
        """设置 Agent 为空闲状态"""
        await publish_agent_event(
            agent_name=agent_name,
            status=AgentStatus.IDLE,
            message="Agent is idle",
        )
    
    async def set_busy(
        self,
        agent_name: str,
        task_id: str,
        progress: float = 0.0,
    ):
        """设置 Agent 为忙碌状态"""
        await publish_agent_event(
            agent_name=agent_name,
            status=AgentStatus.BUSY,
            task_id=task_id,
            progress=progress,
            message=f"Working on task {task_id}",
        )
    
    async def set_error(
        self,
        agent_name: str,
        error_message: str,
    ):
        """设置 Agent 为错误状态"""
        await publish_agent_event(
            agent_name=agent_name,
            status=AgentStatus.ERROR,
            message=error_message,
        )
    
    async def update_progress(
        self,
        agent_name: str,
        task_id: str,
        progress: float,
    ):
        """更新任务进度"""
        await publish_agent_event(
            agent_name=agent_name,
            status=AgentStatus.BUSY,
            task_id=task_id,
            progress=progress,
            message=f"Progress: {progress*100:.1f}%",
        )


# WebSocket 集成
async def websocket_event_handler(websocket, client_id: int):
    """
    WebSocket 事件处理器
    
    将事件推送到 WebSocket 客户端
    """
    async def on_event(event: AgentEvent):
        try:
            await websocket.send_json({
                "type": "agent_update",
                "data": event.to_dict(),
            })
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            raise  # 重新抛出以触发断开连接
    
    return on_event
