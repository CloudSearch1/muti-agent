"""
PI-Python Agent 事件系统
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

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
    message: Optional[Message] = None
    delta: Optional[str] = None

    # 工具相关
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    args: Optional[dict[str, Any]] = None
    result: Optional[Any] = None

    # 错误相关
    error: Optional[str] = None

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