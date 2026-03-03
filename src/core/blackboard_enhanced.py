"""
黑板系统增强

职责：实现完整的黑板通信机制，支持消息订阅和发布
"""

from typing import Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
import json
import structlog

from .models import Blackboard, Message, MessageType
from .models.blackboard import BlackboardEntry


logger = structlog.get_logger(__name__)


class MessageSubscription:
    """消息订阅"""
    
    def __init__(
        self,
        callback: Callable[[Message], Awaitable[None]],
        message_type: Optional[MessageType] = None,
        sender_role: Optional[str] = None,
    ):
        self.callback = callback
        self.message_type = message_type
        self.sender_role = sender_role
    
    def matches(self, message: Message) -> bool:
        """检查消息是否匹配订阅条件"""
        if self.message_type and message.type != self.message_type:
            return False
        if self.sender_role and message.sender_role != self.sender_role:
            return False
        return True
    
    async def notify(self, message: Message) -> None:
        """通知订阅者"""
        try:
            await self.callback(message)
        except Exception as e:
            logger.error(
                "Subscription callback failed",
                error=str(e),
            )


class EnhancedBlackboard(Blackboard):
    """
    增强黑板
    
    在基础黑板功能上增加：
    - 消息订阅/发布
    - 条目变更通知
    - TTL 管理
    - 查询优化
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 订阅管理
        self._subscriptions: list[MessageSubscription] = []
        
        # 条目变更回调
        self._entry_callbacks: dict[str, list[Callable]] = {}
        
        logger.info(
            "EnhancedBlackboard initialized",
            name=self.name,
        )
    
    # ===========================================
    # 消息订阅/发布
    # ===========================================
    
    def subscribe(
        self,
        callback: Callable[[Message], Awaitable[None]],
        message_type: Optional[MessageType] = None,
        sender_role: Optional[str] = None,
    ) -> None:
        """
        订阅消息
        
        Args:
            callback: 消息回调函数
            message_type: 消息类型过滤
            sender_role: 发送者角色过滤
        """
        subscription = MessageSubscription(
            callback,
            message_type,
            sender_role,
        )
        
        self._subscriptions.append(subscription)
        
        logger.debug(
            "Subscription added",
            message_type=message_type,
            sender_role=sender_role,
        )
    
    def unsubscribe(self, callback: Callable) -> int:
        """
        取消订阅
        
        Args:
            callback: 要移除的回调函数
            
        Returns:
            移除的订阅数量
        """
        original_count = len(self._subscriptions)
        self._subscriptions = [
            s for s in self._subscriptions
            if s.callback != callback
        ]
        
        removed_count = original_count - len(self._subscriptions)
        
        logger.debug(
            "Subscriptions removed",
            count=removed_count,
        )
        
        return removed_count
    
    def post_message(self, message: Message) -> None:
        """
        发布消息（增强版）
        
        除了存储消息，还会通知订阅者
        """
        # 调用父类方法存储消息
        super().post_message(message)
        
        # 通知订阅者
        self._notify_subscribers(message)
    
    def _notify_subscribers(self, message: Message) -> None:
        """通知所有匹配的订阅者"""
        notified_count = 0
        
        for subscription in self._subscriptions:
            if subscription.matches(message):
                # 异步通知（不阻塞）
                import asyncio
                asyncio.create_task(subscription.notify(message))
                notified_count += 1
        
        logger.debug(
            "Subscribers notified",
            message_id=message.id,
            notified_count=notified_count,
        )
    
    # ===========================================
    # 条目变更通知
    # ===========================================
    
    def on_entry_change(
        self,
        key: str,
        callback: Callable[[str, Any, Any], None],
    ) -> None:
        """
        注册条目变更回调
        
        Args:
            key: 条目键名
            callback: 回调函数 (key, old_value, new_value)
        """
        if key not in self._entry_callbacks:
            self._entry_callbacks[key] = []
        
        self._entry_callbacks[key].append(callback)
        
        logger.debug(
            "Entry change callback registered",
            key=key,
        )
    
    def put(
        self,
        key: str,
        value: Any,
        owner_id: Optional[str] = None,
        **kwargs,
    ) -> BlackboardEntry:
        """
        放置条目（增强版）
        
        会触发变更通知
        """
        # 获取旧值
        old_value = self.get(key)
        
        # 创建/更新条目
        entry = super().put(key, value, owner_id, **kwargs)
        
        # 触发变更回调
        self._trigger_entry_callbacks(key, old_value, value)
        
        return entry
    
    def _trigger_entry_callbacks(
        self,
        key: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        """触发条目变更回调"""
        callbacks = self._entry_callbacks.get(key, [])
        
        for callback in callbacks:
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                logger.error(
                    "Entry callback failed",
                    key=key,
                    error=str(e),
                )
    
    # ===========================================
    # TTL 管理
    # ===========================================
    
    def set_ttl(self, key: str, ttl_seconds: int) -> bool:
        """
        设置条目 TTL
        
        Args:
            key: 条目键名
            ttl_seconds: TTL（秒）
            
        Returns:
            是否设置成功
        """
        if key not in self.entries:
            return False
        
        entry = self.entries[key]
        entry.expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        
        logger.debug(
            "TTL set",
            key=key,
            ttl_seconds=ttl_seconds,
        )
        
        return True
    
    def get_ttl(self, key: str) -> Optional[int]:
        """
        获取条目剩余 TTL
        
        Args:
            key: 条目键名
            
        Returns:
            剩余秒数，None 表示不存在或无 TTL
        """
        if key not in self.entries:
            return None
        
        entry = self.entries[key]
        
        if not entry.expires_at:
            return None
        
        remaining = (entry.expires_at - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def cleanup_expired(self) -> int:
        """
        清理过期条目和消息
        
        Returns:
            清理的数量
        """
        # 调用父类清理
        cleaned = super().cleanup_expired()
        
        logger.info(
            "Expired items cleaned",
            count=cleaned,
        )
        
        return cleaned
    
    # ===========================================
    # 查询优化
    # ===========================================
    
    def find_entries(
        self,
        owner_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        expired: bool = False,
    ) -> list[BlackboardEntry]:
        """
        查找条目
        
        Args:
            owner_id: 所有者 ID 过滤
            tags: 标签过滤
            expired: 是否包含过期条目
            
        Returns:
            条目列表
        """
        results = []
        
        for entry in self.entries.values():
            # 检查过期
            if not expired and entry.is_expired():
                continue
            
            # 所有者过滤
            if owner_id and entry.owner_id != owner_id:
                continue
            
            # 标签过滤
            if tags and not any(tag in entry.description for tag in tags):
                continue
            
            results.append(entry)
        
        return results
    
    def search_messages(
        self,
        keyword: str,
        limit: int = 50,
    ) -> list[Message]:
        """
        搜索消息
        
        Args:
            keyword: 搜索关键词
            limit: 结果数量限制
            
        Returns:
            消息列表
        """
        results = []
        
        for msg in self.messages:
            if keyword.lower() in msg.subject.lower() or \
               keyword.lower() in str(msg.content).lower():
                results.append(msg)
                
                if len(results) >= limit:
                    break
        
        return results
    
    # ===========================================
    # 统计和监控
    # ===========================================
    
    def get_stats(self) -> dict[str, Any]:
        """获取详细统计信息"""
        now = datetime.now()
        
        # 条目统计
        total_entries = len(self.entries)
        expired_entries = sum(1 for e in self.entries.values() if e.is_expired())
        
        # 消息统计
        total_messages = len(self.messages)
        unread_messages = sum(1 for m in self.messages if not m.read)
        expired_messages = sum(1 for m in self.messages if m.is_expired())
        
        # 订阅统计
        subscription_count = len(self._subscriptions)
        
        return {
            "entries": {
                "total": total_entries,
                "expired": expired_entries,
                "active": total_entries - expired_entries,
            },
            "messages": {
                "total": total_messages,
                "unread": unread_messages,
                "expired": expired_messages,
                "active": total_messages - expired_messages,
            },
            "subscriptions": subscription_count,
            "entry_callbacks": len(self._entry_callbacks),
            "uptime_hours": (now - self.created_at).total_seconds() / 3600,
        }
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典（包含统计信息）"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "stats": self.get_stats(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ===========================================
# 黑板管理器
# ===========================================

class BlackboardManager:
    """
    黑板管理器
    
    管理多个黑板实例
    """
    
    def __init__(self):
        self._blackboards: dict[str, EnhancedBlackboard] = {}
        self._default_blackboard: Optional[str] = None
        
        logger.info("BlackboardManager initialized")
    
    def create_blackboard(
        self,
        name: str,
        description: str = "",
        max_messages: int = 1000,
        max_entries: int = 100,
    ) -> EnhancedBlackboard:
        """
        创建黑板
        
        Args:
            name: 黑板名称
            description: 描述
            max_messages: 最大消息数
            max_entries: 最大条目数
            
        Returns:
            黑板实例
        """
        if name in self._blackboards:
            logger.warning(
                "Blackboard already exists, returning existing",
                name=name,
            )
            return self._blackboards[name]
        
        blackboard = EnhancedBlackboard(
            name=name,
            description=description,
            max_messages=max_messages,
            max_entries=max_entries,
        )
        
        self._blackboards[name] = blackboard
        
        # 设置默认黑板
        if not self._default_blackboard:
            self._default_blackboard = name
        
        logger.info(
            "Blackboard created",
            name=name,
        )
        
        return blackboard
    
    def get_blackboard(self, name: str) -> Optional[EnhancedBlackboard]:
        """获取黑板"""
        return self._blackboards.get(name)
    
    def get_default(self) -> Optional[EnhancedBlackboard]:
        """获取默认黑板"""
        if not self._default_blackboard:
            # 自动创建默认黑板
            return self.create_blackboard("default")
        
        return self._blackboards.get(self._default_blackboard)
    
    def remove_blackboard(self, name: str) -> bool:
        """移除黑板"""
        if name in self._blackboards:
            del self._blackboards[name]
            
            if self._default_blackboard == name:
                self._default_blackboard = None
            
            logger.info(
                "Blackboard removed",
                name=name,
            )
            return True
        
        return False
    
    def list_blackboards(self) -> list[str]:
        """列出所有黑板"""
        return list(self._blackboards.keys())
    
    def cleanup_all(self) -> int:
        """清理所有黑板的过期数据"""
        total_cleaned = 0
        
        for blackboard in self._blackboards.values():
            cleaned = blackboard.cleanup_expired()
            total_cleaned += cleaned
        
        return total_cleaned


# 全局单例
_manager: Optional[BlackboardManager] = None


def get_blackboard_manager() -> BlackboardManager:
    """获取黑板管理器单例"""
    global _manager
    if _manager is None:
        _manager = BlackboardManager()
    return _manager


def get_default_blackboard() -> EnhancedBlackboard:
    """获取默认黑板"""
    return get_blackboard_manager().get_default()
