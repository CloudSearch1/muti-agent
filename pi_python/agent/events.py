"""
PI-Python Agent 事件系统
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..ai import Message


class AgentEventType(str, Enum):
    """Agent 事件类型"""
    # 生命周期
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"

    # 消息
    MESSAGE_START = "message_start"
    MESSAGE_UPDATE = "message_update"
    MESSAGE_END = "message_end"

    # 工具
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_END = "tool_execution_end"

    # 错误
    ERROR = "error"


@dataclass
class AgentEvent:
    """Agent 事件"""
    type: AgentEventType

    # 消息相关
    message: Message | None = None
    delta: str | None = None

    # 工具相关
    tool_call_id: str | None = None
    tool_name: str | None = None
    args: dict[str, Any] | None = None
    result: Any | None = None

    # 错误相关
    error: str | None = None

    # 元数据
    timestamp: float = field(default_factory=lambda: __import__('time').time())

    def __repr__(self) -> str:
        parts = [f"AgentEvent({self.type.value}"]
        if self.delta:
            parts.append(f"delta={len(self.delta)} chars")
        if self.tool_name:
            parts.append(f"tool={self.tool_name}")
        if self.error:
            parts.append(f"error={self.error[:50]}")
        parts.append(")")
        return " ".join(parts)
