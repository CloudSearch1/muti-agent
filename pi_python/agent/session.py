"""
PI-Python Agent 会话管理

提供会话持久化和分支功能
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..ai import Message, parse_message

__all__ = [
    "Session",
    "SessionManager",
]


class Session:
    """
    Agent 会话

    特性:
    - JSONL 格式持久化
    - 树形结构（支持分支）
    - 自动压缩
    """

    def __init__(self, path: Path | None = None):
        """
        初始化会话

        Args:
            path: 会话文件路径（JSONL 格式）
        """
        self.path = path
        self.messages: list[Message] = []
        self.metadata: dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self._branches: dict[str, Session] = {}

    def add_message(self, message: Message) -> None:
        """
        添加消息到会话

        Args:
            message: 要添加的消息对象
        """
        self.messages.append(message)
        self.metadata["updated_at"] = datetime.now().isoformat()

    def save(self) -> None:
        """
        保存会话到 JSONL 文件

        将会话元数据和消息以 JSONL 格式写入文件。
        如果会话没有指定路径，则不执行任何操作。
        """
        if not self.path:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.path, "w", encoding="utf-8") as f:
            # 写入元数据
            f.write(json.dumps({
                "type": "metadata",
                "data": self.metadata
            }, ensure_ascii=False) + "\n")

            # 写入消息
            for msg in self.messages:
                f.write(json.dumps({
                    "type": "message",
                    "data": msg.model_dump()
                }, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: Path) -> "Session":
        """
        从 JSONL 文件加载会话

        Args:
            path: 会话文件路径

        Returns:
            Session: 加载的会话实例

        Note:
            如果文件不存在或解析失败，返回空会话。
        """
        session = cls(path)

        if not path.exists():
            return session

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    if entry.get("type") == "metadata":
                        session.metadata = entry.get("data", {})
                    elif entry.get("type") == "message":
                        msg_data = entry.get("data", {})
                        msg = parse_message(msg_data)
                        session.messages.append(msg)
                except (json.JSONDecodeError, ValueError):
                    continue

        return session

    def branch(self, from_index: int, name: str) -> Session:
        """
        从指定点创建分支

        创建一个新分支，包含原会话中 from_index 之前的所有消息。
        如果 from_index 超出范围，将自动调整为有效范围。

        Args:
            from_index: 分支点索引（从0开始）
            name: 分支名称

        Returns:
            Session: 新创建的分支会话

        Raises:
            ValueError: 当 from_index 为负数时
        """
        # 验证 from_index
        if from_index < 0:
            raise ValueError(
                f"Invalid from_index: {from_index}. "
                "Index must be non-negative."
            )

        # 调整超出范围的索引
        if from_index > len(self.messages):
            from_index = len(self.messages)

        branch = Session()
        branch.messages = self.messages[:from_index].copy()
        branch.metadata = {
            "parent": str(self.path) if self.path else None,
            "branch_point": from_index,
            "name": name,
            "created_at": datetime.now().isoformat(),
        }

        self._branches[name] = branch
        return branch

    def get_branch(self, name: str) -> "Session | None":
        """
        获取指定名称的分支

        Args:
            name: 分支名称

        Returns:
            Session | None: 分支会话，如果不存在则返回 None
        """
        return self._branches.get(name)

    def list_branches(self) -> list[str]:
        """
        列出所有分支名称

        Returns:
            list[str]: 分支名称列表
        """
        return list(self._branches.keys())

    def compress(self, max_messages: int = 50) -> None:
        """
        压缩旧消息

        保留系统消息和最近的消息，用于控制上下文大小。
        空消息列表或消息数少于 max_messages 时不会执行压缩。

        Args:
            max_messages: 最大保留消息数，默认 50

        Raises:
            ValueError: 当 max_messages 小于 1 时
        """
        # 验证参数
        if max_messages < 1:
            raise ValueError(
                f"Invalid max_messages: {max_messages}. "
                "Must be at least 1."
            )

        # 空列表或消息数不足时跳过
        if len(self.messages) <= max_messages:
            return

        # 保留最近的 N 条消息
        self.messages = self.messages[-max_messages:]
        self.metadata["compressed"] = True
        self.metadata["compressed_at"] = datetime.now().isoformat()

    def export_json(self) -> str:
        """
        导出会话为 JSON 字符串

        Returns:
            str: JSON 格式的会话数据
        """
        return json.dumps({
            "metadata": self.metadata,
            "messages": [msg.model_dump() for msg in self.messages]
        }, ensure_ascii=False, indent=2)

    @classmethod
    def import_json(cls, json_str: str) -> "Session":
        """
        从 JSON 字符串导入会话

        Args:
            json_str: JSON 格式的会话数据

        Returns:
            Session: 导入的会话实例

        Raises:
            json.JSONDecodeError: 当 JSON 格式无效时
        """
        data = json.loads(json_str)
        session = cls()

        session.metadata = data.get("metadata", {})
        for msg_data in data.get("messages", []):
            msg = parse_message(msg_data)
            session.messages.append(msg)

        return session

    def get_last_user_message(self) -> Message | None:
        """
        获取最后一条用户消息

        从消息列表末尾向前搜索，返回第一条角色为 user 的消息。

        Returns:
            Message | None: 最后一条用户消息，如果没有则返回 None
        """
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg
        return None

    def get_last_assistant_message(self) -> Message | None:
        """
        获取最后一条助手消息

        从消息列表末尾向前搜索，返回第一条角色为 assistant 的消息。

        Returns:
            Message | None: 最后一条助手消息，如果没有则返回 None
        """
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return msg
        return None

    def __len__(self) -> int:
        """
        返回消息数量

        Returns:
            int: 当前会话中的消息数量
        """
        return len(self.messages)

    def __repr__(self) -> str:
        """
        返回会话的字符串表示

        Returns:
            str: 包含消息数量和路径的描述字符串
        """
        return f"Session(messages={len(self.messages)}, path={self.path})"


class SessionManager:
    """
    会话管理器

    管理多个会话的创建、加载、删除和列表操作。
    会话以 JSONL 格式存储在指定目录中。

    Attributes:
        sessions_dir: 会话存储目录
    """

    def __init__(self, sessions_dir: Path):
        """
        初始化会话管理器

        Args:
            sessions_dir: 会话存储目录，如果不存在会自动创建
        """
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        列出所有会话

        扫描会话目录，加载所有 .jsonl 文件的元数据。
        结果按更新时间降序排列（最近的在前）。

        Returns:
            list[dict[str, Any]]: 会话信息列表，每项包含 path、name、
                                  message_count、created_at、updated_at
        """
        sessions = []

        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                session = Session.load(path)
                sessions.append({
                    "path": str(path),
                    "name": path.stem,
                    "message_count": len(session),
                    "created_at": session.metadata.get("created_at"),
                    "updated_at": session.metadata.get("updated_at"),
                })
            except Exception:
                continue

        # 按更新时间排序
        sessions.sort(
            key=lambda x: x.get("updated_at", ""),
            reverse=True
        )

        return sessions

    def get_session(self, name: str) -> Session:
        """
        获取或创建会话

        如果会话文件存在则加载，否则创建新的空会话。

        Args:
            name: 会话名称（不包含扩展名）

        Returns:
            Session: 会话实例
        """
        path = self.sessions_dir / f"{name}.jsonl"
        return Session.load(path)

    def create_session(self, name: str | None = None) -> Session:
        """
        创建新会话

        Args:
            name: 会话名称（可选，默认使用时间戳生成）

        Returns:
            Session: 新创建的会话实例
        """
        if name is None:
            name = f"session_{int(time.time())}"

        path = self.sessions_dir / f"{name}.jsonl"
        return Session(path)

    def delete_session(self, name: str) -> bool:
        """
        删除会话

        Args:
            name: 要删除的会话名称

        Returns:
            bool: 删除成功返回 True，会话不存在返回 False
        """
        path = self.sessions_dir / f"{name}.jsonl"

        if path.exists():
            path.unlink()
            return True

        return False

    def get_recent_session(self) -> Session | None:
        """
        获取最近的会话

        返回最近更新的会话。

        Returns:
            Session | None: 最近的会话，如果没有会话则返回 None
        """
        sessions = self.list_sessions()

        if not sessions:
            return None

        recent = sessions[0]
        return self.get_session(Path(recent["path"]).stem)
