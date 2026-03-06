"""
消息队列完善

支持 RabbitMQ、Kafka 等消息队列
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageQueueClient:
    """
    消息队列客户端
    
    支持:
    - RabbitMQ
    - Kafka (TODO)
    - Redis Streams (TODO)
    """
    
    def __init__(
        self,
        broker: str = "rabbitmq",
        host: str = "localhost",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
        virtual_host: str = "/",
    ):
        self.broker = broker
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.virtual_host = virtual_host
        
        self._connection = None
        self._channel = None
        self._callbacks: Dict[str, Callable] = {}
        
        logger.info(f"MessageQueueClient initialized ({broker})")
    
    async def connect(self):
        """连接消息队列"""
        if self.broker == "rabbitmq":
            await self._connect_rabbitmq()
        else:
            logger.warning(f"Unsupported broker: {self.broker}")
    
    async def _connect_rabbitmq(self):
        """连接 RabbitMQ"""
        try:
            import aio_pika
            
            self._connection = await aio_pika.connect_robust(
                f"amqp://{self.username}:{self.password}@{self.host}:{self.port}/{self.virtual_host}"
            )
            
            self._channel = await self._connection.channel()
            
            # 设置 QoS
            await self._channel.set_qos(prefetch_count=10)
            
            logger.info(f"RabbitMQ connected: {self.host}:{self.port}")
            
        except ImportError:
            logger.warning("aio_pika not installed, using mock mode")
        except Exception as e:
            logger.error(f"RabbitMQ connection failed: {e}")
    
    async def disconnect(self):
        """断开连接"""
        if self._connection:
            await self._connection.close()
            logger.info("MessageQueue disconnected")
    
    async def publish(
        self,
        exchange: str,
        routing_key: str,
        message: Dict[str, Any],
        durable: bool = True,
    ):
        """
        发布消息
        
        Args:
            exchange: 交换机名
            routing_key: 路由键
            message: 消息体
            durable: 是否持久化
        """
        if self.broker != "rabbitmq" or not self._channel:
            logger.info(f"Mock publish to {exchange}/{routing_key}: {message}")
            return
        
        try:
            import aio_pika
            
            # 声明交换机
            exchange_obj = await self._channel.declare_exchange(
                exchange,
                aio_pika.ExchangeType.DIRECT,
                durable=durable,
            )
            
            # 创建消息
            message_body = json.dumps(message, ensure_ascii=False).encode()
            msg = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                timestamp=datetime.utcnow(),
            )
            
            # 发布
            await exchange_obj.publish(msg, routing_key=routing_key)
            
            logger.debug(f"Published to {exchange}/{routing_key}")
            
        except Exception as e:
            logger.error(f"Publish failed: {e}")
    
    async def subscribe(
        self,
        queue_name: str,
        routing_key: str,
        callback: Callable,
        durable: bool = True,
    ):
        """
        订阅消息
        
        Args:
            queue_name: 队列名
            routing_key: 路由键
            callback: 回调函数
            durable: 是否持久化
        """
        if self.broker != "rabbitmq" or not self._channel:
            logger.info(f"Mock subscribe to {queue_name}/{routing_key}")
            self._callbacks[queue_name] = callback
            return
        
        try:
            import aio_pika
            
            # 声明交换机
            exchange = await self._channel.declare_exchange(
                routing_key.split('.')[0] if '.' in routing_key else queue_name,
                aio_pika.ExchangeType.DIRECT,
                durable=durable,
            )
            
            # 声明队列
            queue = await self._channel.declare_queue(
                queue_name,
                durable=durable,
            )
            
            # 绑定
            await queue.bind(exchange, routing_key=routing_key)
            
            # 消费
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            body = json.loads(message.body.decode())
                            await callback(body)
                        except Exception as e:
                            logger.error(f"Message processing error: {e}")
            
        except Exception as e:
            logger.error(f"Subscribe failed: {e}")
    
    async def publish_task(self, task_type: str, task_data: Dict[str, Any]):
        """发布任务消息"""
        await self.publish(
            exchange="tasks",
            routing_key=f"task.{task_type}",
            message={
                "type": task_type,
                "data": task_data,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    
    async def publish_event(self, event_type: str, event_data: Dict[str, Any]):
        """发布事件消息"""
        await self.publish(
            exchange="events",
            routing_key=f"event.{event_type}",
            message={
                "event": event_type,
                "data": event_data,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
    
    async def subscribe_tasks(self, task_type: str, callback: Callable):
        """订阅任务"""
        await self.subscribe(
            queue_name=f"tasks.{task_type}",
            routing_key=f"task.{task_type}",
            callback=callback,
        )
    
    async def subscribe_events(self, event_type: str, callback: Callable):
        """订阅事件"""
        await self.subscribe(
            queue_name=f"events.{event_type}",
            routing_key=f"event.{event_type}",
            callback=callback,
        )


# ============ 全局客户端 ============

_client: Optional[MessageQueueClient] = None


def get_message_queue() -> MessageQueueClient:
    """获取消息队列客户端"""
    global _client
    if _client is None:
        _client = MessageQueueClient()
    return _client


async def init_message_queue(**kwargs) -> MessageQueueClient:
    """初始化消息队列"""
    global _client
    _client = MessageQueueClient(**kwargs)
    await _client.connect()
    logger.info("Message queue initialized")
    return _client


async def close_message_queue():
    """关闭消息队列"""
    global _client
    if _client:
        await _client.disconnect()
        _client = None
