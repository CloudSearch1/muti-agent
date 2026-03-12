"""
PI-Python OpenAI 提供商

支持 OpenAI GPT 系列模型
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
    ToolCall,
)
from .base import BaseProvider


class OpenAIProvider(BaseProvider):
    """OpenAI GPT 提供商"""

    NAME = "openai"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 60,
    ):
        super().__init__(timeout=timeout)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or self.DEFAULT_BASE_URL

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """流式调用 OpenAI API"""
        stream = AssistantMessageEventStream()
        api_key = self._get_api_key(options, "OPENAI_API_KEY")

        if not api_key:
            stream.emit_sync(EventBuilder.error("OpenAI API Key 未配置"))
            return stream

        # 构建请求
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 转换消息格式
        messages = context.to_openai_messages()

        payload: dict[str, Any] = {
            "model": model.id,
            "messages": messages,
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
            "stream": True,
        }

        # 添加工具
        if context.tools:
            payload["tools"] = [t.to_openai_format() for t in context.tools]

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

                content_parts: list[str] = []
                tool_calls: dict[int, dict[str, Any]] = {}
                usage: dict[str, int] = {}
                finish_reason = "stop"

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data = line[6:]
                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    chunk_finish = chunk.get("choices", [{}])[0].get("finish_reason")

                    if chunk_finish:
                        finish_reason = chunk_finish

                    # 处理文本
                    if "content" in delta and delta["content"]:
                        content_parts.append(delta["content"])
                        stream.emit_sync(EventBuilder.text_delta(0, delta["content"]))

                    # 处理工具调用
                    if "tool_calls" in delta:
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls:
                                tool_calls[idx] = {
                                    "id": tc.get("id", ""),
                                    "name": "",
                                    "arguments": ""
                                }

                            if tc.get("id"):
                                tool_calls[idx]["id"] = tc["id"]
                            if tc.get("function", {}).get("name"):
                                tool_calls[idx]["name"] = tc["function"]["name"]
                            if tc.get("function", {}).get("arguments"):
                                tool_calls[idx]["arguments"] += tc["function"]["arguments"]

                    # 处理 usage
                    if "usage" in chunk:
                        usage = chunk["usage"]

                # 构建最终消息
                content: list[Content] = []

                if content_parts:
                    content.append(TextContent(text="".join(content_parts)))

                for idx, tc in sorted(tool_calls.items()):
                    try:
                        args = json.loads(tc["arguments"])
                    except json.JSONDecodeError:
                        args = {}

                    content.append(ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        input=args
                    ))

                message = AssistantMessage(content=content)

                # 确定停止原因
                reason = StopReason.STOP
                if finish_reason == "tool_calls":
                    reason = StopReason.TOOL_USE
                elif finish_reason == "length":
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


async def openai_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    provider = OpenAIProvider()
    return await provider.stream(model, context, options)

register_provider("openai", openai_stream)
