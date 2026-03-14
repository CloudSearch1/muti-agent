"""
PI-Python 消息路由和委托系统

实现智能消息路由和多 Agent 协作
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .base import IntegrationMessage, IntegrationResponse
from ..agent import Agent


@dataclass
class Route:
    """路由规则"""
    
    pattern: str  # 匹配模式（正则表达式）
    agent_id: str  # 目标 Agent ID
    platform: str | None = None  # 限制特定平台
    channels: list[str] | None = None  # 限制特定频道
    priority: int = 0  # 优先级（数字越大优先级越高）
    
    def matches(self, message: IntegrationMessage) -> bool:
        """
        检查消息是否匹配路由规则
        
        Args:
            message: 集成消息
            
        Returns:
            是否匹配
        """
        # 平台匹配
        if self.platform and self.platform != message.platform:
            return False
        
        # 频道匹配
        if self.channels and message.channel_id not in self.channels:
            return False
        
        # 内容匹配（正则）
        try:
            return bool(re.search(self.pattern, message.text, re.IGNORECASE))
        except re.error:
            # 正则表达式错误时，使用简单包含匹配
            return self.pattern.lower() in message.text.lower()


class MessageRouter:
    """消息路由和委托系统"""
    
    def __init__(self):
        self.routes: list[Route] = []
        self.agent_pool: dict[str, Agent] = {}  # Agent 池
        self._handler: Callable[[IntegrationMessage], Awaitable[IntegrationResponse | None]] | None = None
    
    def add_route(self, route: Route) -> None:
        """
        添加路由规则
        
        Args:
            route: 路由规则
        """
        self.routes.append(route)
        # 按优先级排序（降序）
        self.routes.sort(key=lambda r: r.priority, reverse=True)
    
    def add_agent(self, agent_id: str, agent: Agent) -> None:
        """
        添加 Agent 到池
        
        Args:
            agent_id: Agent ID
            agent: Agent 实例
        """
        self.agent_pool[agent_id] = agent
    
    def set_default_handler(
        self,
        handler: Callable[[IntegrationMessage], Awaitable[IntegrationResponse | None]]
    ) -> None:
        """
        设置默认处理器（当没有匹配的路由时）
        
        Args:
            handler: 处理函数
        """
        self._handler = handler
    
    async def handle_message(
        self,
        message: IntegrationMessage
    ) -> IntegrationResponse | None:
        """
        处理消息
        
        Args:
            message: 集成消息
            
        Returns:
            响应或 None
        """
        # 查找匹配的 Agent
        agent = self._find_agent(message)
        
        if agent:
            # 使用 Agent 处理消息
            return await self._process_with_agent(agent, message)
        elif self._handler:
            # 使用默认处理器
            return await self._handler(message)
        else:
            # 没有可用的处理器
            return IntegrationResponse(
                text="抱歉，我没有找到合适的 Agent 来处理您的请求。",
                thread_id=message.raw_data.get("thread_ts") if message.raw_data else None
            )
    
    def _find_agent(self, message: IntegrationMessage) -> Agent | None:
        """
        根据消息查找合适的 Agent
        
        Args:
            message: 集成消息
            
        Returns:
            Agent 实例或 None
        """
        # 按优先级遍历路由规则
        for route in self.routes:
            if route.matches(message):
                return self.agent_pool.get(route.agent_id)
        
        # 平台默认 Agent
        platform_agent = self.agent_pool.get(f"default_{message.platform}")
        if platform_agent:
            return platform_agent
        
        # 全局默认 Agent
        return self.agent_pool.get("default")
    
    async def _process_with_agent(
        self,
        agent: Agent,
        message: IntegrationMessage
    ) -> IntegrationResponse:
        """
        使用 Agent 处理消息
        
        Args:
            agent: Agent 实例
            message: 集成消息
            
        Returns:
            集成响应
        """
        # 收集完整响应
        response_parts = []
        
        def on_event(event: Any) -> None:
            """收集 Agent 输出"""
            if hasattr(event, 'type') and event.type == "message_update":
                if hasattr(event, 'delta') and event.delta:
                    response_parts.append(event.delta)
        
        # 订阅 Agent 事件
        agent.subscribe(on_event)
        
        # 发送提示
        await agent.prompt(message.text)
        
        # 构建响应
        response_text = "".join(response_parts)
        if not response_text:
            response_text = "处理完成，但没有返回内容。"
        
        # 获取线程ID（用于回复）
        thread_id = None
        if message.raw_data and "ts" in message.raw_data:
            thread_id = message.raw_data["ts"]
        
        return IntegrationResponse(
            text=response_text,
            thread_id=thread_id
        )


# 便捷函数
def create_router() -> MessageRouter:
    """
    创建消息路由器
    
    Returns:
        MessageRouter 实例
    """
    return MessageRouter()


async def route_message(
    router: MessageRouter,
    message: IntegrationMessage
) -> IntegrationResponse | None:
    """
    路由消息（便捷函数）
    
    Args:
        router: 消息路由器
        message: 集成消息
        
    Returns:
        响应或 None
    """
    return await router.handle_message(message)
