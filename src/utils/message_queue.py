"""
消息队列模块

使用 asyncio Queue 实现轻量级消息队列
支持未来升级到 Redis/RabbitMQ
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.utils.compat import StrEnum

logger = logging.getLogger(__name__)


class MessageType(StrEnum):
    """消息类型"""
    TASK = "task"
    EVENT = "event"
    COMMAND = "command"
    RESPONSE = "response"


@dataclass
class Message:
    """消息"""
    id: str
    type: MessageType
    topic: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0  # 越高越优先
    retries: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "topic": self.topic,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
            "retries": self.retries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Message':
        return cls(
            id=data["id"],
            type=MessageType(data["type"]),
            topic=data["topic"],
            payload=data["payload"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=data.get("priority", 0),
            retries=data.get("retries", 0),
            max_retries=data.get("max_retries", 3),
        )


class MessageQueue:
    """
    消息队列

    功能:
    - 发布/订阅模式
    - 优先级队列
    - 消息持久化（可选）
    - 自动重试
    """

    def __init__(self, max_size: int = 10000):
        self._queues: dict[str, asyncio.PriorityQueue] = {}
        self._subscribers: dict[str, list[Callable]] = {}
        self._max_size = max_size
        self._running = False
        self._worker_tasks: list[asyncio.Task] = []
        self._stats = {
            "published": 0,
            "consumed": 0,
            "failed": 0,
        }
        self._lock = asyncio.Lock()

    async def start(self):
        """启动消息队列"""
        self._running = True
        logger.info("MessageQueue started")

    async def stop(self):
        """停止消息队列"""
        self._running = False

        # 取消所有 worker
        for task in self._worker_tasks:
            task.cancel()

        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        logger.info("MessageQueue stopped")

    async def publish(self, topic: str, payload: dict[str, Any], priority: int = 0):
        """
        发布消息

        Args:
            topic: 主题
            payload: 消息内容
            priority: 优先级
        """
        message = Message(
            id=f"msg_{datetime.now().timestamp()}_{topic}",
            type=MessageType.EVENT,
            topic=topic,
            payload=payload,
            priority=priority,
        )

        async with self._lock:
            if topic not in self._queues:
                self._queues[topic] = asyncio.PriorityQueue(maxsize=self._max_size)

        # 放入队列（负优先级使高优先级先出）
        await self._queues[topic].put((-priority, message))
        self._stats["published"] += 1

        # 通知订阅者
        await self._notify_subscribers(topic, message)

        logger.debug(f"Message published: {topic}")

    async def subscribe(self, topic: str, callback: Callable[[Message], None]):
        """
        订阅主题

        Args:
            topic: 主题
            callback: 回调函数
        """
        async with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)

        logger.info(f"Subscribed to topic: {topic}")

    async def unsubscribe(self, topic: str, callback: Callable):
        """取消订阅"""
        async with self._lock:
            if topic in self._subscribers and callback in self._subscribers[topic]:
                self._subscribers[topic].remove(callback)

        logger.info(f"Unsubscribed from topic: {topic}")

    async def consume(self, topic: str, timeout: float | None = None) -> Message | None:
        """
        消费消息

        Args:
            topic: 主题
            timeout: 超时时间

        Returns:
            消息，超时返回 None
        """
        if topic not in self._queues:
            return None

        try:
            priority, message = await asyncio.wait_for(
                self._queues[topic].get(),
                timeout=timeout,
            )
            self._stats["consumed"] += 1
            logger.debug(f"Message consumed: {topic}")
            return message
        except TimeoutError:
            return None

    async def _notify_subscribers(self, topic: str, message: Message):
        """通知订阅者"""
        subscribers = self._subscribers.get(topic, [])

        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Subscriber callback error: {e}")

    def get_stats(self) -> dict:
        """获取统计"""
        queue_sizes = {
            topic: queue.qsize()
            for topic, queue in self._queues.items()
        }

        return {
            **self._stats,
            "topics": list(self._queues.keys()),
            "queue_sizes": queue_sizes,
            "subscribers": {
                topic: len(subs)
                for topic, subs in self._subscribers.items()
            },
        }


class AgentTaskQueue(MessageQueue):
    """
    Agent 任务队列

    专门用于 Agent 间任务传递
    """

    def __init__(self):
        super().__init__()
        self._task_results: dict[str, asyncio.Future] = {}

    async def submit_task(
        self,
        agent_name: str,
        task_data: dict[str, Any],
        wait_for_result: bool = False,
    ) -> dict[str, Any] | None:
        """
        提交任务给 Agent

        Args:
            agent_name: Agent 名称
            task_data: 任务数据
            wait_for_result: 是否等待结果

        Returns:
            任务结果（如果等待）
        """
        task_id = f"task_{agent_name}_{datetime.now().timestamp()}"

        # 发布任务
        await self.publish(f"agent.{agent_name}.tasks", {
            "task_id": task_id,
            **task_data,
        }, priority=task_data.get("priority", 0))

        if not wait_for_result:
            return None

        # 等待结果
        future = asyncio.Future()
        self._task_results[task_id] = future

        try:
            result = await asyncio.wait_for(future, timeout=300)
            return result
        except TimeoutError:
            return {"error": "Task timeout"}
        finally:
            del self._task_results[task_id]

    async def complete_task(self, task_id: str, result: dict[str, Any]):
        """完成任务"""
        if task_id in self._task_results:
            self._task_results[task_id].set_result(result)

    async def fail_task(self, task_id: str, error: str):
        """任务失败"""
        if task_id in self._task_results:
            self._task_results[task_id].set_exception(Exception(error))


# 全局消息队列实例
_message_queue: MessageQueue | None = None
_agent_task_queue: AgentTaskQueue | None = None


def get_message_queue() -> MessageQueue:
    """获取消息队列"""
    global _message_queue
    if _message_queue is None:
        _message_queue = MessageQueue()
    return _message_queue


def get_agent_task_queue() -> AgentTaskQueue:
    """获取 Agent 任务队列"""
    global _agent_task_queue
    if _agent_task_queue is None:
        _agent_task_queue = AgentTaskQueue()
    return _agent_task_queue


async def init_message_queues():
    """初始化消息队列"""
    mq = get_message_queue()
    get_agent_task_queue()
    await mq.start()
    logger.info("Message queues initialized")


async def shutdown_message_queues():
    """关闭消息队列"""
    mq = get_message_queue()
    get_agent_task_queue()
    await mq.stop()
    logger.info("Message queues shut down")
