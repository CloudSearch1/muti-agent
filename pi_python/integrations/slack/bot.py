"""
Slack 集成实现

基于 slack-bolt SDK 的 Slack Bot 实现
"""

from __future__ import annotations

import os
from typing import Any

try:
    from slack_bolt.async_app import AsyncApp
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False
    AsyncApp = None
    AsyncSocketModeHandler = None

from ..base import BaseIntegration, IntegrationMessage, IntegrationResponse


class SlackIntegration(BaseIntegration):
    """Slack 集成"""
    
    def __init__(self, config: dict[str, Any] | None = None):
        """
        初始化 Slack 集成
        
        Args:
            config: 配置字典，包含:
                - bot_token: Bot User OAuth Token
                - app_token: Socket Mode Token
                - signing_secret: Signing Secret
        """
        if not SLACK_AVAILABLE:
            raise ImportError(
                "Slack 集成需要安装 slack-bolt 和 slack-sdk，\n"
                "请运行: pip install slack-bolt slack-sdk"
            )
        
        config = config or {}
        super().__init__("slack", config)
        
        # 从配置或环境变量获取凭证
        bot_token = config.get("bot_token") or os.getenv("SLACK_BOT_TOKEN")
        signing_secret = config.get("signing_secret") or os.getenv("SLACK_SIGNING_SECRET")
        
        if not bot_token:
            raise ValueError("未提供 bot_token，请在 config 中设置或设置 SLACK_BOT_TOKEN 环境变量")
        
        if not signing_secret:
            raise ValueError("未提供 signing_secret，请在 config 中设置或设置 SLACK_SIGNING_SECRET 环境变量")
        
        # 初始化 Slack App
        self.app = AsyncApp(
            token=bot_token,
            signing_secret=signing_secret
        )
        
        self.handler: AsyncSocketModeHandler | None = None
        
        # 注册事件处理器
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """注册 Slack 事件处理器"""
        
        @self.app.event("app_mention")
        async def handle_mention(event: dict[str, Any], say: Any) -> None:
            """处理 @bot 提及"""
            try:
                # 获取用户信息
                user_info = await self.app.client.users_info(user=event["user"])
                user_name = user_info["user"]["name"]
                
                message = IntegrationMessage(
                    platform="slack",
                    channel_id=event["channel"],
                    user_id=event["user"],
                    user_name=user_name,
                    text=event["text"],
                    timestamp=float(event["ts"]),
                    raw_data=event
                )
                await self._handle_message(message)
            except Exception as e:
                print(f"处理 Slack 事件失败: {e}")
        
        @self.app.message()
        async def handle_message(message: dict[str, Any], say: Any) -> None:
            """处理直接消息"""
            try:
                # 只处理 DM，不处理频道消息（避免重复）
                if message.get("channel_type") != "im":
                    return
                
                # 获取用户信息
                user_info = await self.app.client.users_info(user=message["user"])
                user_name = user_info["user"]["name"]
                
                integration_message = IntegrationMessage(
                    platform="slack",
                    channel_id=message["channel"],
                    user_id=message["user"],
                    user_name=user_name,
                    text=message["text"],
                    timestamp=float(message["ts"]),
                    raw_data=message
                )
                await self._handle_message(integration_message)
            except Exception as e:
                print(f"处理 Slack 消息失败: {e}")
    
    async def start(self) -> None:
        """启动 Slack Bot"""
        if self._running:
            print("Slack 集成已在运行中")
            return
        
        app_token = self.config.get("app_token") or os.getenv("SLACK_APP_TOKEN")
        if not app_token:
            raise ValueError("未提供 app_token，请在 config 中设置或设置 SLACK_APP_TOKEN 环境变量")
        
        if not self.handler:
            self.handler = AsyncSocketModeHandler(self.app, app_token)
        
        # 异步启动
        import asyncio
        asyncio.create_task(self.handler.start_async())
        self._running = True
        print("Slack 集成已启动")
    
    async def stop(self) -> None:
        """停止 Slack Bot"""
        if not self._running:
            return
        
        self._running = False
        print("Slack 集成已停止")
    
    async def send_message(
        self,
        channel_id: str,
        text: str,
        thread_id: str | None = None
    ) -> None:
        """
        发送消息到 Slack
        
        Args:
            channel_id: Slack 频道ID或用户ID
            text: 消息文本
            thread_id: 线程时间戳（用于回复）
        """
        try:
            await self.app.client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_id
            )
        except Exception as e:
            print(f"发送 Slack 消息失败: {e}")
