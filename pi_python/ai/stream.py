"""
PI-Python 流式 API

提供异步流式响应处理
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from .types import (
    AssistantMessage,
    Content,
    Context,
    Model,
    StopReason,
    TextContent,
    ThinkingContent,
    ToolCall,
)

__all__ = [
    "AssistantMessageEvent",
    "AssistantMessageEventStream",
    "StreamOptions",
    "EventBuilder",
    "register_provider",
    "get_provider",
    "stream",
    "stream_simple",
    "complete",
]


@dataclass
class AssistantMessageEvent:
    """流式事件"""
    type: str
    # text_delta / thinking_delta
    content_index: int | None = None
    delta: str | None = None
    # tool_call
    tool_call: ToolCall | None = None
    partial_tool_call: dict[str, Any] | None = None
    # done / error
    reason: StopReason | None = None
    message: AssistantMessage | None = None
    error: str | None = None
    # usage
    usage: dict[str, int] | None = None


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
        _usage = {}

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
                _usage = event.usage

        return AssistantMessage(content=content)


@dataclass
class StreamOptions:
    """流式调用选项"""
    api_key: str | None = None
    timeout: int = 60
    temperature: float = 0.7
    max_tokens: int = 4096
    reasoning: str = "off"  # off, low, medium, high
    thinking_budget: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ============ 流式 API 函数 ============

from .model import ModelRegistry


def register_provider(name: str, provider_cls: Callable) -> None:
    """注册提供商"""
    ModelRegistry.register_provider(name, provider_cls)


def get_provider(name: str) -> Callable | None:
    """获取提供商"""
    return ModelRegistry.get_provider(name)


async def stream(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """
    流式调用 LLM

    Args:
        model: 模型定义
        context: 调用上下文
        options: 调用选项

    Returns:
        AssistantMessageEventStream: 流式事件流

    Raises:
        ValueError: 当提供商不存在或配置无效时
    """
    options = options or StreamOptions()

    # 获取提供商
    provider_fn = get_provider(model.provider)
    if not provider_fn:
        available_providers = list(ModelRegistry._providers.keys())
        raise ValueError(
            f"Unknown provider: '{model.provider}'. "
            f"Available providers: {', '.join(available_providers) if available_providers else 'none registered'}. "
            f"Please register a provider using 'register_provider()' or use a valid provider name."
        )

    # 调用提供商
    return await provider_fn(model, context, options)


async def stream_simple(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
    reasoning: str = "off",
    thinking_budgets: dict[str, int] | None = None,
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
    options: StreamOptions | None = None,
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
    def _create_event(
        event_type: str,
        content_index: int | None = None,
        delta: str | None = None,
        tool_call: ToolCall | None = None,
        partial_tool_call: dict[str, Any] | None = None,
        reason: StopReason | None = None,
        message: AssistantMessage | None = None,
        error: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> AssistantMessageEvent:
        """创建事件的通用方法"""
        return AssistantMessageEvent(
            type=event_type,
            content_index=content_index,
            delta=delta,
            tool_call=tool_call,
            partial_tool_call=partial_tool_call,
            reason=reason,
            message=message,
            error=error,
            usage=usage,
        )

    @staticmethod
    def start() -> AssistantMessageEvent:
        """创建开始事件"""
        return EventBuilder._create_event("start")

    @staticmethod
    def text_start(index: int) -> AssistantMessageEvent:
        """创建文本开始事件"""
        return EventBuilder._create_event("text_start", content_index=index)

    @staticmethod
    def text_delta(index: int, delta: str) -> AssistantMessageEvent:
        """创建文本增量事件"""
        return EventBuilder._create_event("text_delta", content_index=index, delta=delta)

    @staticmethod
    def text_end(index: int, content: str) -> AssistantMessageEvent:
        """创建文本结束事件"""
        return EventBuilder._create_event("text_end", content_index=index, delta=content)

    @staticmethod
    def thinking_start(index: int) -> AssistantMessageEvent:
        """创建思考开始事件"""
        return EventBuilder._create_event("thinking_start", content_index=index)

    @staticmethod
    def thinking_delta(index: int, delta: str) -> AssistantMessageEvent:
        """创建思考增量事件"""
        return EventBuilder._create_event("thinking_delta", content_index=index, delta=delta)

    @staticmethod
    def thinking_end(index: int, content: str) -> AssistantMessageEvent:
        """创建思考结束事件"""
        return EventBuilder._create_event("thinking_end", content_index=index, delta=content)

    @staticmethod
    def tool_call_start(index: int, partial: dict) -> AssistantMessageEvent:
        """创建工具调用开始事件"""
        return EventBuilder._create_event("tool_call_start", content_index=index, partial_tool_call=partial)

    @staticmethod
    def tool_call_delta(index: int, delta: str) -> AssistantMessageEvent:
        """创建工具调用增量事件"""
        return EventBuilder._create_event("tool_call_delta", content_index=index, delta=delta)

    @staticmethod
    def tool_call_end(tool_call: ToolCall) -> AssistantMessageEvent:
        """创建工具调用结束事件"""
        return EventBuilder._create_event("tool_call", tool_call=tool_call)

    @staticmethod
    def done(
        reason: StopReason,
        message: AssistantMessage,
        usage: dict[str, int] | None = None
    ) -> AssistantMessageEvent:
        """创建完成事件"""
        return EventBuilder._create_event("done", reason=reason, message=message, usage=usage)

    @staticmethod
    def error(error: str, reason: StopReason = StopReason.ERROR) -> AssistantMessageEvent:
        """创建错误事件"""
        return EventBuilder._create_event("error", reason=reason, error=error)
