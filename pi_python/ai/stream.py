"""
PI-Python 流式 API

提供异步流式响应处理
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional

from .types import (
    ApiType,
    AssistantMessage,
    Content,
    Context,
    Model,
    StopReason,
    TextContent,
    ToolCall,
    ToolResultMessage,
)


@dataclass
class AssistantMessageEvent:
    """流式事件"""
    type: str
    # text_delta / thinking_delta
    content_index: Optional[int] = None
    delta: Optional[str] = None
    # tool_call
    tool_call: Optional[ToolCall] = None
    partial_tool_call: Optional[dict[str, Any]] = None
    # done / error
    reason: Optional[StopReason] = None
    message: Optional[AssistantMessage] = None
    error: Optional[str] = None
    # usage
    usage: Optional[dict[str, int]] = None


class AssistantMessageEventStream:
    """流式事件流"""

    def __init__(self):
        self._queue: asyncio.Queue[AssistantMessageEvent] = asyncio.Queue()
        self._closed = False

    async def emit(self, event: AssistantMessageEvent) -> None:
        """发射事件"""
        await self._queue.put(event)

    def emit_sync(self, event: AssistantMessageEvent) -> None:
        """同步发射事件（用于回调）"""
        self._queue.put_nowait(event)

    async def __aiter__(self) -> AsyncIterator[AssistantMessageEvent]:
        """异步迭代"""
        while True:
            event = await self._queue.get()
            yield event
            if event.type in ("done", "error"):
                break

    def close(self) -> None:
        """关闭流"""
        self._closed = True

    async def collect(self) -> AssistantMessage:
        """收集所有事件并返回完整消息"""
        content: list[Content] = []
        current_text = ""
        current_thinking = ""
        usage = {}

        async for event in self:
            if event.type == "text_delta":
                current_text += event.delta or ""
            elif event.type == "thinking_delta":
                current_thinking += event.delta or ""
            elif event.type == "tool_call" and event.tool_call:
                content.append(event.tool_call)
            elif event.type == "done":
                if current_text:
                    content.insert(0, TextContent(text=current_text))
                if current_thinking:
                    content.insert(0, ThinkingContent(thinking=current_thinking))
                if event.message:
                    return event.message
                return AssistantMessage(content=content)
            elif event.type == "error":
                raise RuntimeError(event.error or "Unknown error")
            if event.usage:
                usage = event.usage

        return AssistantMessage(content=content)


@dataclass
class StreamOptions:
    """流式调用选项"""
    api_key: Optional[str] = None
    timeout: int = 60
    temperature: float = 0.7
    max_tokens: int = 4096
    reasoning: str = "off"  # off, low, medium, high
    thinking_budget: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ============ 流式 API 函数 ============

from .model import ModelRegistry


def register_provider(name: str, provider_cls: Callable) -> None:
    """注册提供商"""
    ModelRegistry.register_provider(name, provider_cls)


def get_provider(name: str) -> Optional[Callable]:
    """获取提供商"""
    return ModelRegistry.get_provider(name)


async def stream(
    model: Model,
    context: Context,
    options: Optional[StreamOptions] = None,
) -> AssistantMessageEventStream:
    """
    流式调用 LLM

    Args:
        model: 模型定义
        context: 调用上下文
        options: 调用选项

    Returns:
        AssistantMessageEventStream: 流式事件流
    """
    options = options or StreamOptions()

    # 获取提供商
    provider_fn = get_provider(model.provider)
    if not provider_fn:
        raise ValueError(f"Unknown provider: {model.provider}")

    # 调用提供商
    return await provider_fn(model, context, options)


async def stream_simple(
    model: Model,
    context: Context,
    options: Optional[StreamOptions] = None,
    reasoning: str = "off",
    thinking_budgets: Optional[dict[str, int]] = None,
) -> AssistantMessageEventStream:
    """
    简化流式调用（带推理支持）

    Args:
        model: 模型定义
        context: 调用上下文
        options: 调用选项
        reasoning: 推理级别 (off, low, medium, high)
        thinking_budgets: 各级别的思考 token 预算

    Returns:
        AssistantMessageEventStream: 流式事件流
    """
    options = options or StreamOptions()

    # 设置推理配置
    if model.reasoning and reasoning != "off":
        thinking_budgets = thinking_budgets or {
            "low": 1024,
            "medium": 2048,
            "high": 4096
        }
        options.reasoning = reasoning
        options.thinking_budget = thinking_budgets.get(reasoning)

    return await stream(model, context, options)


async def complete(
    model: Model,
    context: Context,
    options: Optional[StreamOptions] = None,
) -> AssistantMessage:
    """
    完成调用（非流式）

    Args:
        model: 模型定义
        context: 调用上下文
        options: 调用选项

    Returns:
        AssistantMessage: 完成的助手消息
    """
    event_stream = await stream(model, context, options)
    return await event_stream.collect()


# ============ 内置事件类型 ============

class EventBuilder:
    """事件构建器"""

    @staticmethod
    def start() -> AssistantMessageEvent:
        """创建开始事件"""
        return AssistantMessageEvent(type="start")

    @staticmethod
    def text_start(index: int) -> AssistantMessageEvent:
        """创建文本开始事件"""
        return AssistantMessageEvent(
            type="text_start",
            content_index=index
        )

    @staticmethod
    def text_delta(index: int, delta: str) -> AssistantMessageEvent:
        """创建文本增量事件"""
        return AssistantMessageEvent(
            type="text_delta",
            content_index=index,
            delta=delta
        )

    @staticmethod
    def text_end(index: int, content: str) -> AssistantMessageEvent:
        """创建文本结束事件"""
        return AssistantMessageEvent(
            type="text_end",
            content_index=index,
            delta=content
        )

    @staticmethod
    def thinking_start(index: int) -> AssistantMessageEvent:
        """创建思考开始事件"""
        return AssistantMessageEvent(
            type="thinking_start",
            content_index=index
        )

    @staticmethod
    def thinking_delta(index: int, delta: str) -> AssistantMessageEvent:
        """创建思考增量事件"""
        return AssistantMessageEvent(
            type="thinking_delta",
            content_index=index,
            delta=delta
        )

    @staticmethod
    def thinking_end(index: int, content: str) -> AssistantMessageEvent:
        """创建思考结束事件"""
        return AssistantMessageEvent(
            type="thinking_end",
            content_index=index,
            delta=content
        )

    @staticmethod
    def tool_call_start(index: int, partial: dict) -> AssistantMessageEvent:
        """创建工具调用开始事件"""
        return AssistantMessageEvent(
            type="tool_call_start",
            content_index=index,
            partial_tool_call=partial
        )

    @staticmethod
    def tool_call_delta(index: int, delta: str) -> AssistantMessageEvent:
        """创建工具调用增量事件"""
        return AssistantMessageEvent(
            type="tool_call_delta",
            content_index=index,
            delta=delta
        )

    @staticmethod
    def tool_call_end(tool_call: ToolCall) -> AssistantMessageEvent:
        """创建工具调用结束事件"""
        return AssistantMessageEvent(
            type="tool_call",
            tool_call=tool_call
        )

    @staticmethod
    def done(
        reason: StopReason,
        message: AssistantMessage,
        usage: Optional[dict[str, int]] = None
    ) -> AssistantMessageEvent:
        """创建完成事件"""
        return AssistantMessageEvent(
            type="done",
            reason=reason,
            message=message,
            usage=usage
        )

    @staticmethod
    def error(error: str, reason: StopReason = StopReason.ERROR) -> AssistantMessageEvent:
        """创建错误事件"""
        return AssistantMessageEvent(
            type="error",
            reason=reason,
            error=error
        )