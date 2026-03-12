"""
PI-Python Anthropic 提供商

支持 Claude 系列模型
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

from ..stream import (
    AssistantMessageEventStream,
    EventBuilder,
    StreamOptions,
)
from ..types import (
    AssistantMessage,
    Content,
    Context,
    Model,
    StopReason,
    TextContent,
    ThinkingContent,
    ToolCall,
)
from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    """Anthropic Claude 提供商"""

    NAME = "anthropic"
    DEFAULT_BASE_URL = "https://api.anthropic.com"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 120,
    ):
        super().__init__(timeout=timeout)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = self.DEFAULT_BASE_URL

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """流式调用 Anthropic API"""
        stream = AssistantMessageEventStream()
        api_key = self._get_api_key(options, "ANTHROPIC_API_KEY")

        if not api_key:
            stream.emit_sync(EventBuilder.error("Anthropic API Key 未配置"))
            return stream

        # 构建请求
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        # 转换消息格式
        messages = context.to_anthropic_messages()

        payload: dict[str, Any] = {
            "model": model.id,
            "max_tokens": options.max_tokens,
            "messages": messages,
            "stream": True,
        }

        # 添加系统提示
        if context.system_prompt:
            payload["system"] = context.system_prompt

        # 添加工具
        if context.tools:
            payload["tools"] = [t.to_anthropic_format() for t in context.tools]

        # 添加推理配置
        if model.reasoning and options.reasoning != "off":
            budget = options.thinking_budget or 2048
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": budget
            }

        # 启动流式处理
        asyncio.create_task(self._process_stream(stream, url, headers, payload))

        return stream

    async def _process_stream(
        self,
        stream: AssistantMessageEventStream,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> None:
        """处理流式响应"""
        try:
            stream.emit_sync(EventBuilder.start())

            async with self.client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()

                content: list[Content] = []
                current_text = ""
                current_thinking = ""
                current_tool: dict[str, Any] | None = None
                usage: dict[str, int] = {}
                stop_reason = "end_turn"

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data = line[6:]
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type", "")

                    # 消息开始
                    if event_type == "message_start":
                        usage = event.get("message", {}).get("usage", {})

                    # 内容块开始
                    elif event_type == "content_block_start":
                        block = event.get("content_block", {})
                        block_type = block.get("type", "")
                        idx = event.get("index", 0)

                        if block_type == "text":
                            stream.emit_sync(EventBuilder.text_start(idx))
                        elif block_type == "thinking":
                            stream.emit_sync(EventBuilder.thinking_start(idx))
                        elif block_type == "tool_use":
                            current_tool = {
                                "id": block.get("id", ""),
                                "name": block.get("name", ""),
                                "input": ""
                            }

                    # 内容块增量
                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        idx = event.get("index", 0)

                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            current_text += text
                            stream.emit_sync(EventBuilder.text_delta(idx, text))

                        elif delta.get("type") == "thinking_delta":
                            think = delta.get("thinking", "")
                            current_thinking += think
                            stream.emit_sync(EventBuilder.thinking_delta(idx, think))

                        elif delta.get("type") == "input_json_delta":
                            if current_tool:
                                current_tool["input"] += delta.get("partial_json", "")

                    # 内容块结束
                    elif event_type == "content_block_stop":
                        idx = event.get("index", 0)

                        if current_text:
                            content.append(TextContent(text=current_text))
                            stream.emit_sync(EventBuilder.text_end(idx, current_text))
                            current_text = ""

                        if current_thinking:
                            content.append(ThinkingContent(thinking=current_thinking))
                            stream.emit_sync(EventBuilder.thinking_end(idx, current_thinking))
                            current_thinking = ""

                        if current_tool:
                            try:
                                args = json.loads(current_tool["input"])
                            except json.JSONDecodeError:
                                args = {}

                            tool_call = ToolCall(
                                id=current_tool["id"],
                                name=current_tool["name"],
                                input=args
                            )
                            content.append(tool_call)
                            stream.emit_sync(EventBuilder.tool_call_end(tool_call))
                            current_tool = None

                    # 消息增量（usage 更新）
                    elif event_type == "message_delta":
                        delta = event.get("delta", {})
                        if delta.get("stop_reason"):
                            stop_reason = delta["stop_reason"]
                        usage_update = event.get("usage", {})
                        usage.update(usage_update)

                    # 消息结束
                    elif event_type == "message_stop":
                        break

                # 构建最终消息
                message = AssistantMessage(content=content)

                # 确定停止原因
                reason = StopReason.STOP
                if stop_reason == "tool_use":
                    reason = StopReason.TOOL_USE
                elif stop_reason == "max_tokens":
                    reason = StopReason.MAX_TOKENS

                stream.emit_sync(EventBuilder.done(reason, message, usage))

        except httpx.HTTPStatusError as e:
            stream.emit_sync(EventBuilder.error(f"HTTP 错误: {e.response.status_code}"))
        except httpx.TimeoutException:
            stream.emit_sync(EventBuilder.error("请求超时", StopReason.ABORTED))
        except Exception as e:
            stream.emit_sync(EventBuilder.error(str(e)))


# 注册提供商
from ..model import register_provider


async def anthropic_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    provider = AnthropicProvider()
    return await provider.stream(model, context, options)

register_provider("anthropic", anthropic_stream)
