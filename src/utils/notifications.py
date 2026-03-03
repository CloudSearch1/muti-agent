"""
IntelliTeam 实时通知模块

基于 WebSocket 和 Redis Pub/Sub 的实时通知系统
"""

import asyncio
import json
from typing import Dict, List, Set, Optional
from datetime import datetime
import logging

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    通知管理器
    
    管理 WebSocket 连接和通知推送
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._pubsub = None
        
        # WebSocket 连接管理
        self.active_connections: Dict[int, List] = {}  # user_id -> [websockets]
        self.active_channels: Dict[str, Set[int]] = {}  # channel -> {user_ids}
    
    async def connect(self) -> bool:
        """连接 Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis 不可用，通知系统将无法工作")
            return False
        
        try:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis.ping()
            
            # 订阅通知频道
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe("notifications")
            
            logger.info("通知系统已连接")
            return True
        except Exception as e:
            logger.error(f"通知系统连接失败：{e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        
        if self._redis:
            await self._redis.close()
        
        logger.info("通知系统已断开")
    
    async def add_connection(self, user_id: int, websocket):
        """
        添加 WebSocket 连接
        
        Args:
            user_id: 用户 ID
            websocket: WebSocket 连接
        """
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        logger.info(f"用户 {user_id} 添加 WebSocket 连接")
    
    async def remove_connection(self, user_id: int, websocket):
        """
        移除 WebSocket 连接
        
        Args:
            user_id: 用户 ID
            websocket: WebSocket 连接
        """
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        
        logger.info(f"用户 {user_id} 移除 WebSocket 连接")
    
    async def subscribe_channel(self, user_id: int, channel: str):
        """
        订阅频道
        
        Args:
            user_id: 用户 ID
            channel: 频道名称
        """
        if channel not in self.active_channels:
            self.active_channels[channel] = set()
        
        self.active_channels[channel].add(user_id)
        logger.info(f"用户 {user_id} 订阅频道 {channel}")
    
    async def unsubscribe_channel(self, user_id: int, channel: str):
        """
        取消订阅频道
        
        Args:
            user_id: 用户 ID
            channel: 频道名称
        """
        if channel in self.active_channels:
            if user_id in self.active_channels[channel]:
                self.active_channels[channel].remove(user_id)
        
        logger.info(f"用户 {user_id} 取消订阅频道 {channel}")
    
    async def send_to_user(self, user_id: int, notification: dict):
        """
        发送通知给用户
        
        Args:
            user_id: 用户 ID
            notification: 通知内容
        """
        if user_id not in self.active_connections:
            logger.debug(f"用户 {user_id} 没有活跃的 WebSocket 连接")
            return
        
        message = json.dumps({
            "type": "notification",
            "data": notification,
            "timestamp": datetime.now().isoformat()
        })
        
        disconnected = []
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"发送通知失败：{e}")
                disconnected.append(websocket)
        
        # 清理断开的连接
        for ws in disconnected:
            await self.remove_connection(user_id, ws)
    
    async def broadcast_to_channel(self, channel: str, message: dict):
        """
        广播消息到频道
        
        Args:
            channel: 频道名称
            message: 消息内容
        """
        if channel not in self.active_channels:
            return
        
        notification = {
            "type": "channel_message",
            "channel": channel,
            "data": message,
            "timestamp": datetime.now().isoformat()
        }
        
        for user_id in self.active_channels[channel]:
            await self.send_to_user(user_id, notification)
    
    async def publish_notification(self, notification: dict):
        """
        发布通知到 Redis
        
        Args:
            notification: 通知内容
        """
        if not self._redis:
            return
        
        message = json.dumps(notification)
        await self._redis.publish("notifications", message)
        logger.debug(f"发布通知：{notification}")
    
    async def start_listening(self):
        """
        开始监听 Redis 通知
        
        在后台运行
        """
        if not self._pubsub:
            return
        
        logger.info("开始监听 Redis 通知")
        
        async for message in self._pubsub.listen():
            if message["type"] == "message":
                try:
                    notification = json.loads(message["data"])
                    user_id = notification.get("user_id")
                    
                    if user_id:
                        await self.send_to_user(user_id, notification)
                except Exception as e:
                    logger.error(f"处理通知失败：{e}")
    
    async def send_task_notification(
        self,
        user_id: int,
        task_id: int,
        task_title: str,
        status: str
    ):
        """
        发送任务通知
        
        Args:
            user_id: 用户 ID
            task_id: 任务 ID
            task_title: 任务标题
            status: 任务状态
        """
        notification = {
            "user_id": user_id,
            "type": "task_update",
            "data": {
                "task_id": task_id,
                "title": task_title,
                "status": status,
                "message": f"任务 {task_title} 状态更新为 {status}"
            }
        }
        
        await self.send_to_user(user_id, notification)
        await self.publish_notification(notification)
    
    async def send_agent_notification(
        self,
        user_id: int,
        agent_name: str,
        action: str
    ):
        """
        发送 Agent 通知
        
        Args:
            user_id: 用户 ID
            agent_name: Agent 名称
            action: 动作
        """
        notification = {
            "user_id": user_id,
            "type": "agent_update",
            "data": {
                "agent": agent_name,
                "action": action,
                "message": f"Agent {agent_name} {action}"
            }
        }
        
        await self.send_to_user(user_id, notification)
        await self.publish_notification(notification)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "active_users": len(self.active_connections),
            "active_channels": len(self.active_channels),
            "redis_connected": self._redis is not None
        }


# 全局通知管理器实例
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager(redis_url: str = "redis://localhost:6379/1") -> NotificationManager:
    """获取通知管理器单例"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager(redis_url)
    return _notification_manager


async def init_notifications(redis_url: str = "redis://localhost:6379/1") -> bool:
    """初始化通知系统"""
    manager = get_notification_manager(redis_url)
    return await manager.connect()
