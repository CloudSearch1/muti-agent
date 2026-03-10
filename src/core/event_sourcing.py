"""
事件溯源模块

记录系统状态变更历史，支持时间旅行调试
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer

logger = logging.getLogger(__name__)


# ============ 事件类型 ============

class EventType(str, Enum):
    """事件类型"""
    # 任务事件
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_DELETED = "task.deleted"
    TASK_COMPLETED = "task.completed"
    
    # Agent 事件
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_STATUS_CHANGED = "agent.status_changed"
    
    # 工作流事件
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    
    # 系统事件
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    ERROR_OCCURRED = "error.occurred"
    CONFIG_CHANGED = "config.changed"


# ============ 事件模型 ============

class Event(BaseModel):
    """领域事件"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EventType
    aggregate_type: str  # 聚合根类型（task, agent, workflow）
    aggregate_id: str  # 聚合根 ID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1  # 版本号
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_serializer('timestamp')
    def serialize_timestamp(self, dt: datetime, _info) -> str:
        return dt.isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.value,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "data": self.data,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        return cls(
            id=data["id"],
            type=EventType(data["type"]),
            aggregate_type=data["aggregate_type"],
            aggregate_id=data["aggregate_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            version=data["version"],
            data=data.get("data", {}),
            metadata=data.get("metadata", {}),
        )


# ============ 事件存储 ============

class EventStore:
    """
    事件存储
    
    功能:
    - 事件持久化
    - 事件查询
    - 聚合根状态重建
    """
    
    def __init__(self):
        self._events: list[Event] = []
        self._event_handlers: dict[EventType, list] = {}
        logger.info("EventStore initialized")
    
    def append(self, event: Event):
        """
        追加事件
        
        Args:
            event: 事件对象
        """
        self._events.append(event)
        logger.debug(f"Event appended: {event.type.value} for {event.aggregate_type}:{event.aggregate_id}")
        
        # 触发事件处理器
        self._trigger_handlers(event)
    
    def append_many(self, events: list[Event]):
        """批量追加事件"""
        self._events.extend(events)
        logger.info(f"Appended {len(events)} events")

    def get_events(
        self,
        aggregate_type: str | None = None,
        aggregate_id: str | None = None,
        event_type: EventType | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """
        查询事件
        
        Args:
            aggregate_type: 聚合根类型
            aggregate_id: 聚合根 ID
            event_type: 事件类型
            since: 起始时间
            limit: 返回数量限制
        
        Returns:
            事件列表
        """
        events = self._events
        
        if aggregate_type:
            events = [e for e in events if e.aggregate_type == aggregate_type]
        
        if aggregate_id:
            events = [e for e in events if e.aggregate_id == aggregate_id]
        
        if event_type:
            events = [e for e in events if e.type == event_type]
        
        if since:
            events = [e for e in events if e.timestamp >= since]
        
        # 按时间排序
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)
        
        return events[:limit]
    
    def get_events_for_aggregate(
        self,
        aggregate_type: str,
        aggregate_id: str,
    ) -> list[Event]:
        """获取聚合根的所有事件"""
        return self.get_events(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            limit=1000,
        )
    
    def rebuild_aggregate(
        self,
        aggregate_type: str,
        aggregate_id: str,
    ) -> dict[str, Any]:
        """
        重建聚合根状态
        
        通过按顺序应用事件来重建状态
        
        Args:
            aggregate_type: 聚合根类型
            aggregate_id: 聚合根 ID
        
        Returns:
            聚合根状态
        """
        events = self.get_events_for_aggregate(aggregate_type, aggregate_id)
        
        # 按时间正序排列
        events = sorted(events, key=lambda e: e.timestamp)
        
        state = {
            "id": aggregate_id,
            "type": aggregate_type,
        }
        
        # 应用每个事件
        for event in events:
            state = self._apply_event(state, event)
        
        return state
    
    def _apply_event(self, state: dict, event: Event) -> dict:
        """应用事件到状态"""
        # 根据事件类型更新状态
        if event.type == EventType.TASK_CREATED:
            state.update(event.data)
            state["created_at"] = event.timestamp.isoformat()
        
        elif event.type == EventType.TASK_UPDATED:
            state.update(event.data)
            state["updated_at"] = event.timestamp.isoformat()
        
        elif event.type == EventType.TASK_COMPLETED:
            state["status"] = "completed"
            state["completed_at"] = event.timestamp.isoformat()
        
        elif event.type == EventType.AGENT_STATUS_CHANGED:
            state["status"] = event.data.get("new_status")
        
        # 添加更多事件类型处理...
        
        return state
    
    def register_handler(self, event_type: EventType, handler):
        """注册事件处理器"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.debug(f"Registered handler for {event_type.value}")
    
    def _trigger_handlers(self, event: Event):
        """触发事件处理器"""
        handlers = self._event_handlers.get(event.type, [])
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}", exc_info=True)
    
    def get_all_events(self, limit: int = 1000) -> list[Event]:
        """获取所有事件"""
        return sorted(self._events, key=lambda e: e.timestamp, reverse=True)[:limit]
    
    def get_stats(self) -> dict:
        """获取事件统计"""
        return {
            "total_events": len(self._events),
            "by_type": self._count_by_type(),
            "by_aggregate_type": self._count_by_aggregate_type(),
        }
    
    def _count_by_type(self) -> dict:
        """按类型统计"""
        counts = {}
        for event in self._events:
            event_type = event.type.value
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts
    
    def _count_by_aggregate_type(self) -> dict:
        """按聚合根类型统计"""
        counts = {}
        for event in self._events:
            agg_type = event.aggregate_type
            counts[agg_type] = counts.get(agg_type, 0) + 1
        return counts


# ============ 事件记录装饰器 ============

def record_event(event_type: EventType, aggregate_type: str):
    """
    记录事件装饰器
    
    用法:
        @record_event(EventType.TASK_CREATED, "task")
        async def create_task(data):
            ...
    """
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            # 执行函数
            result = await func(self, *args, **kwargs)
            
            # 记录事件
            if isinstance(result, dict) and "id" in result:
                event_store = get_event_store()
                event = Event(
                    type=event_type,
                    aggregate_type=aggregate_type,
                    aggregate_id=str(result["id"]),
                    data=result,
                    metadata={
                        "function": func.__name__,
                        "args": str(args),
                        "kwargs": str(kwargs),
                    },
                )
                event_store.append(event)
            
            return result
        return wrapper
    return decorator


# ============ 全局事件存储实例 ============

_event_store: EventStore | None = None


def get_event_store() -> EventStore:
    """获取事件存储实例"""
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
    return _event_store


def init_event_store() -> EventStore:
    """初始化事件存储"""
    global _event_store
    _event_store = EventStore()
    logger.info("EventStore initialized")
    return _event_store
