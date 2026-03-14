"""
PI-Python 集成基类

提供统一的平台集成框架
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Awaitable
import asyncio


@dataclass
class IntegrationMessage:
    """集成消息"""
    
    platform: str  # slack/teams/discord
    channel_id: str
    user_id: str
    user_name: str
    text: str
    timestamp: float
    raw_data: dict[str, Any] | None = None


@dataclass 
class IntegrationResponse:
    """集成响应"""
    
    text: str
    thread_id: str | None = None  # 用于线程回复
    ephemeral: bool = False  # 是否仅对用户可见


# 处理器类型定义
IntegrationHandler = Callable[[IntegrationMessage], Awaitable[IntegrationResponse | None]]


class BaseIntegration(ABC):
    """集成基类
    
    所有平台集成（Slack、Teams、Discord等）都应继承此类
    """
    
    def __init__(self, name: str, config: dict[str, Any]):
        """
        初始化集成
        
        Args:
            name: 集成名称（如 'slack', 'teams'）
            config: 配置字典
        """
        self.name = name
        self.config = config
        self._handlers: list[IntegrationHandler] = []
        self._running = False
    
    @abstractmethod
    async def start(self) -> None:
        """启动集成"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止集成"""
        pass
    
    @abstractmethod
    async def send_message(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None
    ) -> None:
        """
        发送消息到平台
        
        Args:
            channel_id: 频道ID
            text: 消息文本
            thread_id: 线程ID（用于回复）
        """
        pass
    
    def on_message(self, handler: IntegrationHandler) -> None:
        """
        注册消息处理器
        
        Args:
            handler: 消息处理函数
        """
        self._handlers.append(handler)
    
    async def _handle_message(self, message: IntegrationMessage) -> None:
        """
        处理收到的消息
        
        并行调用所有注册的处理器
        """
        if not self._handlers:
            return
        
        tasks = [
            handler(message) for handler in self._handlers
        ]
        
        # 并行处理所有处理器
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 发送非异常响应
        for result in results:
            if isinstance(result, Exception):
                # 记录异常但不中断其他处理器
                print(f"处理器错误: {result}")
                continue
            
            if isinstance(result, IntegrationResponse):
                await self.send_message(
                    message.channel_id,
                    result.text,
                    result.thread_id
                )
