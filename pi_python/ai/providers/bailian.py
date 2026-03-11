"""
PI-Python 阿里百炼提供商

支持通义千问系列模型
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Optional

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


class BailianProvider(BaseProvider):
    """阿里百炼提供商"""

    NAME = "bailian"
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 60,
    ):
        super().__init__(timeout=timeout)
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or self.DEFAULT_BASE_URL

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """流式调用百炼 API"""
        stream = AssistantMessageEventStream()
        api_key = self._get_api_key(options, "DASHSCOPE_API_KEY")

        if not api_key:
            stream.emit_sync(EventBuilder.error("百炼 API Key 未配置"))
            return stream

        # 构建请求 URL
        url = f"{self.base_url}/services/aigc/text-generation/generation"

        # 构建消息
        messages = []
        for msg in context.messages:
            role = msg.role
            # 百炼 API 的 role 只能是 user 或 assistant
            if role == "tool_result":
                role = "user"

            # 提取文本内容
            text_parts = []
            for c in msg.content:
                if hasattr(c, 'text') and c.text:
                    text_parts.append(c.text)

            if text_parts:
                messages.append({
                    "role": role,
                    "content": "\n".join(text_parts)
                })

        payload = {
            "model": model.id,
            "input": {"messages": messages},
            "parameters": {
                "temperature": options.temperature,
                "max_tokens": options.max_tokens,
                "incremental_output": True,  # 流式输出
                "result_format": "message",
            }
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-SSE": "enable",
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

                content_parts: list[str] = []
                usage: dict[str, int] = {}
                finish_reason = "stop"

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    # 处理 SSE 格式
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if not data_str:
                            continue

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # 提取输出
                        output = data.get("output", {})

                        # 处理增量文本
                        choices = output.get("choices", [])
                        if choices:
                            choice = choices[0]
                            message = choice.get("message", {})
                            content = message.get("content", "")

                            if content:
                                # 计算增量
                                delta = content[len("".join(content_parts)):]
                                if delta:
                                    content_parts.append(delta)
                                    stream.emit_sync(EventBuilder.text_delta(0, delta))

                            finish_reason = choice.get("finish_reason", "stop")

                        # 处理 usage
                        if "usage" in data:
                            usage = data["usage"]

                        # 处理错误
                        if "code" in data and data["code"] != "Success":
                            error_msg = data.get("message", "Unknown error")
                            stream.emit_sync(EventBuilder.error(error_msg))
                            return

                # 构建最终消息
                content: list[Content] = []
                if content_parts:
                    content.append(TextContent(text="".join(content_parts)))

                message = AssistantMessage(content=content)

                # 确定停止原因
                reason = StopReason.STOP
                if finish_reason == "tool_calls":
                    reason = StopReason.TOOL_USE
                elif finish_reason == "length":
                    reason = StopReason.MAX_TOKENS

                stream.emit_sync(EventBuilder.done(reason, message, usage))

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.text
            except Exception:
                pass
            stream.emit_sync(EventBuilder.error(
                f"HTTP 错误 {e.response.status_code}: {error_detail}"
            ))
        except httpx.TimeoutException:
            stream.emit_sync(EventBuilder.error("请求超时", StopReason.ABORTED))
        except Exception as e:
            stream.emit_sync(EventBuilder.error(str(e)))


# 注册提供商
from ..model import register_provider


async def bailian_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    provider = BailianProvider()
    return await provider.stream(model, context, options)


register_provider("bailian", bailian_stream)