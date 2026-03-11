"""
PI-Python Agent 会话管理

提供会话持久化和分支功能
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..ai import Message, parse_message


class Session:
    """
    Agent 会话

    特性:
    - JSONL 格式持久化
    - 树形结构（支持分支）
    - 自动压缩
    """

    def __init__(self, path: Optional[Path] = None):
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
        """添加消息"""
        self.messages.append(message)
        self.metadata["updated_at"] = datetime.now().isoformat()

    def save(self) -> None:
        """保存会话到 JSONL 文件"""
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
    def load(cls, path: Path) -> Session:
        """从 JSONL 文件加载会话"""
        session = cls(path)

        if not path.exists():
            return session

        with open(path, "r", encoding="utf-8") as f:
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

        Args:
            from_index: 分支点索引
            name: 分支名称

        Returns:
            Session: 新分支
        """
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

    def get_branch(self, name: str) -> Optional[Session]:
        """获取分支"""
        return self._branches.get(name)

    def list_branches(self) -> list[str]:
        """列出所有分支"""
        return list(self._branches.keys())

    def compress(self, max_messages: int = 50) -> None:
        """
        压缩旧消息

        保留系统消息和最近的消息
        """
        if len(self.messages) <= max_messages:
            return

        # 保留最近的 N 条消息
        self.messages = self.messages[-max_messages:]
        self.metadata["compressed"] = True
        self.metadata["compressed_at"] = datetime.now().isoformat()

    def export_json(self) -> str:
        """导出为 JSON 字符串"""
        return json.dumps({
            "metadata": self.metadata,
            "messages": [msg.model_dump() for msg in self.messages]
        }, ensure_ascii=False, indent=2)

    @classmethod
    def import_json(cls, json_str: str) -> Session:
        """从 JSON 字符串导入"""
        data = json.loads(json_str)
        session = cls()

        session.metadata = data.get("metadata", {})
        for msg_data in data.get("messages", []):
            msg = parse_message(msg_data)
            session.messages.append(msg)

        return session

    def get_last_user_message(self) -> Optional[Message]:
        """获取最后一条用户消息"""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg
        return None

    def get_last_assistant_message(self) -> Optional[Message]:
        """获取最后一条助手消息"""
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return msg
        return None

    def __len__(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return f"Session(messages={len(self.messages)}, path={self.path})"


class SessionManager:
    """会话管理器"""

    def __init__(self, sessions_dir: Path):
        """
        初始化会话管理器

        Args:
            sessions_dir: 会话存储目录
        """
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话"""
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
        """获取或创建会话"""
        path = self.sessions_dir / f"{name}.jsonl"
        return Session.load(path)

    def create_session(self, name: Optional[str] = None) -> Session:
        """创建新会话"""
        if name is None:
            name = f"session_{int(time.time())}"

        path = self.sessions_dir / f"{name}.jsonl"
        return Session(path)

    def delete_session(self, name: str) -> bool:
        """删除会话"""
        path = self.sessions_dir / f"{name}.jsonl"

        if path.exists():
            path.unlink()
            return True

        return False

    def get_recent_session(self) -> Optional[Session]:
        """获取最近的会话"""
        sessions = self.list_sessions()

        if not sessions:
            return None

        recent = sessions[0]
        return self.get_session(Path(recent["path"]).stem)