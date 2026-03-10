"""
Pi 通信协议

职责：
- 消息传递机制
- 事件总线
- 广播和点对点通信
- 消息订阅和发布

版本: 1.0.0
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog

from .types import (
    MessageType,
    PiMessage,
)

logger = structlog.get_logger(__name__)


class EventBus:
    """
    事件总线

    实现 Agent 间的消息传递和事件广播

    使用方式:
        bus = EventBus()
        bus.subscribe("task_completed", callback)
        bus.publish("task_completed", {"task_id": "123"})
    """

    def __init__(self, max_history: int = 1000):
        """
        初始化事件总线

        Args:
            max_history: 最大历史消息数
        """
        self._subscribers: dict[str, list[Callable]] = {}
        self._history: list[PiMessage] = []
        self._max_history = max_history

        logger.info("EventBus initialized", max_history=max_history)

    def subscribe(
        self,
        event_type: str,
        callback: Callable,
    ) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(callback)

        logger.debug(
            "Event subscribed",
            event_type=event_type,
            callback=callback.__name__,
        )

    def unsubscribe(
        self,
        event_type: str,
        callback: Callable,
    ) -> bool:
        """
        取消订阅

        Args:
            event_type: 事件类型
            callback: 回调函数

        Returns:
            是否成功取消
        """
        if event_type not in self._subscribers:
            return False

        try:
            self._subscribers[event_type].remove(callback)
            return True
        except ValueError:
            return False

    async def publish(
        self,
        event_type: str,
        data: Any = None,
        sender_id: str | None = None,
    ) -> None:
        """
        发布事件

        Args:
            event_type: 事件类型
            data: 事件数据
            sender_id: 发送者 ID
        """
        # 创建消息
        message = PiMessage(
            type=MessageType.BROADCAST,
            sender_id=sender_id,
            subject=event_type,
            content=data,
        )

        # 存储历史
        self._history.append(message)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # 通知订阅者
        callbacks = self._subscribers.get(event_type, [])
        for callback in callbacks:
            try:
                result = callback(message)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(
                    "Event callback failed",
                    event_type=event_type,
                    error=str(e),
                )

        logger.debug(
            "Event published",
            event_type=event_type,
            subscribers=len(callbacks),
        )

    def get_history(
        self,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[PiMessage]:
        """
        获取历史消息

        Args:
            event_type: 事件类型过滤
            limit: 数量限制

        Returns:
            消息列表
        """
        messages = self._history

        if event_type:
            messages = [m for m in messages if m.subject == event_type]

        return messages[-limit:]

    def clear_history(self) -> int:
        """
        清除历史消息

        Returns:
            清除的消息数
        """
        count = len(self._history)
        self._history.clear()
        return count


class MessageBus:
    """
    消息总线

    实现点对点和广播消息传递

    使用方式:
        bus = MessageBus()
        bus.register_agent("agent-1", callback)
        bus.send_to("agent-1", message)
        bus.broadcast(message)
    """

    def __init__(self, max_pending: int = 100):
        """
        初始化消息总线

        Args:
            max_pending: 每个 Agent 最大待处理消息数
        """
        # Agent 消息队列
        self._agent_queues: dict[str, asyncio.Queue] = {}
        # Agent 回调
        self._agent_callbacks: dict[str, Callable] = {}
        # 最大待处理消息数
        self._max_pending = max_pending
        # 消息历史
        self._message_history: list[PiMessage] = []
        self._max_history = 1000

        logger.info("MessageBus initialized", max_pending=max_pending)

    def register_agent(
        self,
        agent_id: str,
        callback: Callable | None = None,
    ) -> bool:
        """
        注册 Agent

        Args:
            agent_id: Agent ID
            callback: 消息回调函数

        Returns:
            是否成功注册
        """
        if agent_id in self._agent_queues:
            logger.warning("Agent already registered", agent_id=agent_id)
            return False

        self._agent_queues[agent_id] = asyncio.Queue(maxsize=self._max_pending)
        if callback:
            self._agent_callbacks[agent_id] = callback

        logger.info("Agent registered", agent_id=agent_id)

        return True

    def unregister_agent(self, agent_id: str) -> bool:
        """
        注销 Agent

        Args:
            agent_id: Agent ID

        Returns:
            是否成功注销
        """
        if agent_id not in self._agent_queues:
            return False

        del self._agent_queues[agent_id]
        if agent_id in self._agent_callbacks:
            del self._agent_callbacks[agent_id]

        logger.info("Agent unregistered", agent_id=agent_id)

        return True

    async def send_to(
        self,
        receiver_id: str,
        message: PiMessage,
    ) -> bool:
        """
        发送点对点消息

        Args:
            receiver_id: 接收者 ID
            message: 消息

        Returns:
            是否成功发送
        """
        queue = self._agent_queues.get(receiver_id)
        if not queue:
            logger.warning("Receiver not found", receiver_id=receiver_id)
            return False

        try:
            queue.put_nowait(message)

            # 存储历史
            self._message_history.append(message)
            if len(self._message_history) > self._max_history:
                self._message_history.pop(0)

            # 触发回调
            callback = self._agent_callbacks.get(receiver_id)
            if callback:
                try:
                    result = callback(message)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(
                        "Message callback failed",
                        receiver_id=receiver_id,
                        error=str(e),
                    )

            logger.debug(
                "Message sent",
                message_id=message.id,
                receiver_id=receiver_id,
            )

            return True

        except asyncio.QueueFull:
            logger.warning(
                "Agent queue full",
                receiver_id=receiver_id,
            )
            return False

    async def broadcast(
        self,
        message: PiMessage,
        exclude_ids: list[str] | None = None,
    ) -> int:
        """
        广播消息

        Args:
            message: 消息
            exclude_ids: 排除的 Agent ID 列表

        Returns:
            成功发送的消息数
        """
        exclude_ids = exclude_ids or []
        sent_count = 0

        # 设置消息类型为广播
        message.type = MessageType.BROADCAST

        # 存储历史
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history.pop(0)

        # 发送给所有注册的 Agent
        for agent_id, queue in self._agent_queues.items():
            if agent_id in exclude_ids:
                continue

            try:
                queue.put_nowait(message)
                sent_count += 1

                # 触发回调
                callback = self._agent_callbacks.get(agent_id)
                if callback:
                    try:
                        result = callback(message)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(
                            "Broadcast callback failed",
                            agent_id=agent_id,
                            error=str(e),
                        )

            except asyncio.QueueFull:
                logger.warning(
                    "Agent queue full during broadcast",
                    agent_id=agent_id,
                )

        logger.debug(
            "Message broadcasted",
            message_id=message.id,
            sent_count=sent_count,
        )

        return sent_count

    async def receive(
        self,
        agent_id: str,
        timeout: float | None = None,
    ) -> PiMessage | None:
        """
        接收消息

        Args:
            agent_id: Agent ID
            timeout: 超时时间（秒）

        Returns:
            消息或 None
        """
        queue = self._agent_queues.get(agent_id)
        if not queue:
            return None

        try:
            if timeout:
                message = await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                message = await queue.get()
            return message
        except asyncio.TimeoutError:
            return None

    def get_pending_count(self, agent_id: str) -> int:
        """
        获取待处理消息数

        Args:
            agent_id: Agent ID

        Returns:
            待处理消息数
        """
        queue = self._agent_queues.get(agent_id)
        if not queue:
            return 0
        return queue.qsize()

    def get_history(
        self,
        agent_id: str | None = None,
        message_type: MessageType | None = None,
        limit: int = 50,
    ) -> list[PiMessage]:
        """
        获取消息历史

        Args:
            agent_id: Agent ID 过滤
            message_type: 消息类型过滤
            limit: 数量限制

        Returns:
            消息列表
        """
        messages = self._message_history

        if agent_id:
            messages = [
                m for m in messages
                if m.receiver_id == agent_id or m.sender_id == agent_id
            ]

        if message_type:
            messages = [m for m in messages if m.type == message_type]

        return messages[-limit:]


class CommunicationHub:
    """
    通信中心

    整合事件总线和消息总线，提供统一的通信接口

    使用方式:
        hub = CommunicationHub()
        hub.register_agent("agent-1")
        hub.send_message("agent-1", "agent-2", "Hello")
        hub.broadcast("agent-1", "System update")
    """

    def __init__(self):
        """初始化通信中心"""
        self._event_bus = EventBus()
        self._message_bus = MessageBus()

        logger.info("CommunicationHub initialized")

    # ===========================================
    # Agent 管理
    # ===========================================

    def register_agent(
        self,
        agent_id: str,
        message_callback: Callable | None = None,
    ) -> bool:
        """注册 Agent"""
        return self._message_bus.register_agent(agent_id, message_callback)

    def unregister_agent(self, agent_id: str) -> bool:
        """注销 Agent"""
        return self._message_bus.unregister_agent(agent_id)

    # ===========================================
    # 消息传递
    # ===========================================

    async def send_message(
        self,
        sender_id: str,
        receiver_id: str,
        subject: str,
        content: Any = None,
        message_type: MessageType = MessageType.TASK,
    ) -> bool:
        """
        发送点对点消息

        Args:
            sender_id: 发送者 ID
            receiver_id: 接收者 ID
            subject: 主题
            content: 内容
            message_type: 消息类型

        Returns:
            是否成功发送
        """
        message = PiMessage(
            type=message_type,
            sender_id=sender_id,
            receiver_id=receiver_id,
            subject=subject,
            content=content,
        )

        return await self._message_bus.send_to(receiver_id, message)

    async def broadcast(
        self,
        sender_id: str,
        subject: str,
        content: Any = None,
        exclude_ids: list[str] | None = None,
    ) -> int:
        """
        广播消息

        Args:
            sender_id: 发送者 ID
            subject: 主题
            content: 内容
            exclude_ids: 排除的 Agent ID 列表

        Returns:
            成功发送的消息数
        """
        message = PiMessage(
            type=MessageType.BROADCAST,
            sender_id=sender_id,
            subject=subject,
            content=content,
        )

        return await self._message_bus.broadcast(message, exclude_ids)

    async def receive_message(
        self,
        agent_id: str,
        timeout: float | None = None,
    ) -> PiMessage | None:
        """接收消息"""
        return await self._message_bus.receive(agent_id, timeout)

    # ===========================================
    # 事件订阅
    # ===========================================

    def subscribe_event(
        self,
        event_type: str,
        callback: Callable,
    ) -> None:
        """订阅事件"""
        self._event_bus.subscribe(event_type, callback)

    def unsubscribe_event(
        self,
        event_type: str,
        callback: Callable,
    ) -> bool:
        """取消订阅事件"""
        return self._event_bus.unsubscribe(event_type, callback)

    async def publish_event(
        self,
        event_type: str,
        data: Any = None,
        sender_id: str | None = None,
    ) -> None:
        """发布事件"""
        await self._event_bus.publish(event_type, data, sender_id)

    # ===========================================
    # 状态查询
    # ===========================================

    def get_pending_messages(self, agent_id: str) -> int:
        """获取待处理消息数"""
        return self._message_bus.get_pending_count(agent_id)

    def get_event_history(
        self,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[PiMessage]:
        """获取事件历史"""
        return self._event_bus.get_history(event_type, limit)

    def get_message_history(
        self,
        agent_id: str | None = None,
        message_type: MessageType | None = None,
        limit: int = 50,
    ) -> list[PiMessage]:
        """获取消息历史"""
        return self._message_bus.get_history(agent_id, message_type, limit)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "registered_agents": len(self._message_bus._agent_queues),
            "event_subscribers": sum(
                len(callbacks) for callbacks in self._event_bus._subscribers.values()
            ),
            "event_history_size": len(self._event_bus._history),
            "message_history_size": len(self._message_bus._message_history),
        }


# 全局单例
_communication_hub: CommunicationHub | None = None


def get_communication_hub() -> CommunicationHub:
    """获取通信中心单例"""
    global _communication_hub
    if _communication_hub is None:
        _communication_hub = CommunicationHub()
    return _communication_hub


__all__ = [
    "EventBus",
    "MessageBus",
    "CommunicationHub",
    "get_communication_hub",
]