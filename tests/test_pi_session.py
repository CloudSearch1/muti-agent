"""
PI-Python Session 测试

测试 Session 和 SessionManager
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from pi_python.agent.session import Session, SessionManager
from pi_python.ai import UserMessage, AssistantMessage, TextContent


# ===========================================
# Session Tests
# ===========================================


class TestSession:
    """Session 测试"""

    def test_init(self):
        """测试初始化"""
        session = Session()

        assert session.path is None
        assert session.messages == []
        assert "created_at" in session.metadata
        assert "updated_at" in session.metadata

    def test_init_with_path(self):
        """测试带路径初始化"""
        path = Path("/tmp/test.jsonl")
        session = Session(path=path)

        assert session.path == path

    def test_add_message(self):
        """测试添加消息"""
        session = Session()
        msg = UserMessage.from_text("Hello")

        session.add_message(msg)

        assert len(session.messages) == 1
        assert session.messages[0] == msg
        assert "updated_at" in session.metadata

    def test_save_without_path(self):
        """测试没有路径时保存"""
        session = Session()
        session.add_message(UserMessage.from_text("Hello"))

        # 不应该抛出异常
        session.save()

    def test_save_and_load(self):
        """测试保存和加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.jsonl"
            session = Session(path=path)

            session.add_message(UserMessage.from_text("Hello"))
            session.add_message(AssistantMessage(content=[TextContent(text="Hi")]))

            session.save()

            # 加载
            loaded = Session.load(path)

            assert len(loaded.messages) == 2
            assert isinstance(loaded.messages[0], UserMessage)
            assert isinstance(loaded.messages[1], AssistantMessage)
            assert "created_at" in loaded.metadata

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        path = Path("/nonexistent/path/test.jsonl")
        session = Session.load(path)

        assert session.path == path
        assert session.messages == []

    def test_load_invalid_json(self):
        """测试加载无效 JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invalid.jsonl"

            # 写入无效内容
            with open(path, "w") as f:
                f.write("invalid json\n")
                f.write("\n")  # 空行
                f.write('{"type": "message", "data": {"role": "user", "content": [{"type": "text", "text": "Hello"}]}}\n')

            session = Session.load(path)

            # 无效行应该被跳过
            assert len(session.messages) == 1

    def test_branch(self):
        """测试创建分支"""
        session = Session()
        session.add_message(UserMessage.from_text("Msg 1"))
        session.add_message(UserMessage.from_text("Msg 2"))
        session.add_message(UserMessage.from_text("Msg 3"))

        branch = session.branch(from_index=2, name="test-branch")

        assert len(branch.messages) == 2
        assert branch.metadata["branch_point"] == 2
        assert branch.metadata["name"] == "test-branch"
        assert "test-branch" in session.list_branches()

    def test_get_branch(self):
        """测试获取分支"""
        session = Session()
        session.add_message(UserMessage.from_text("Msg 1"))
        branch = session.branch(from_index=1, name="test-branch")

        retrieved = session.get_branch("test-branch")

        assert retrieved == branch
        assert session.get_branch("nonexistent") is None

    def test_list_branches(self):
        """测试列出分支"""
        session = Session()
        session.add_message(UserMessage.from_text("Msg 1"))
        session.branch(from_index=1, name="branch-1")
        session.branch(from_index=1, name="branch-2")

        branches = session.list_branches()

        assert set(branches) == {"branch-1", "branch-2"}

    def test_compress_no_need(self):
        """测试不需要压缩"""
        session = Session()
        for i in range(10):
            session.add_message(UserMessage.from_text(f"Msg {i}"))

        session.compress(max_messages=50)

        assert len(session.messages) == 10

    def test_compress(self):
        """测试压缩"""
        session = Session()
        for i in range(100):
            session.add_message(UserMessage.from_text(f"Msg {i}"))

        session.compress(max_messages=50)

        assert len(session.messages) == 50
        assert session.metadata["compressed"] is True
        assert "compressed_at" in session.metadata

    def test_export_json(self):
        """测试导出 JSON"""
        session = Session()
        session.add_message(UserMessage.from_text("Hello"))
        session.add_message(AssistantMessage(content=[TextContent(text="Hi")]))

        json_str = session.export_json()

        # 验证是有效 JSON
        data = json.loads(json_str)
        assert "metadata" in data
        assert "messages" in data
        assert len(data["messages"]) == 2

    def test_import_json(self):
        """测试导入 JSON"""
        session = Session()
        session.add_message(UserMessage.from_text("Hello"))
        session.add_message(AssistantMessage(content=[TextContent(text="Hi")]))

        json_str = session.export_json()

        imported = Session.import_json(json_str)

        assert len(imported.messages) == 2
        assert isinstance(imported.messages[0], UserMessage)
        assert isinstance(imported.messages[1], AssistantMessage)

    def test_get_last_user_message(self):
        """测试获取最后用户消息"""
        session = Session()
        session.add_message(UserMessage.from_text("Hello"))
        session.add_message(AssistantMessage(content=[TextContent(text="Hi")]))
        session.add_message(UserMessage.from_text("World"))

        result = session.get_last_user_message()

        assert result is not None
        assert "World" in result.content[0].text

    def test_get_last_user_message_none(self):
        """测试没有用户消息时获取"""
        session = Session()
        session.add_message(AssistantMessage(content=[TextContent(text="Hi")]))

        result = session.get_last_user_message()

        assert result is None

    def test_get_last_assistant_message(self):
        """测试获取最后助手消息"""
        session = Session()
        session.add_message(UserMessage.from_text("Hello"))
        session.add_message(AssistantMessage(content=[TextContent(text="Hi")]))
        session.add_message(UserMessage.from_text("World"))

        result = session.get_last_assistant_message()

        assert result is not None
        assert "Hi" in result.content[0].text

    def test_get_last_assistant_message_none(self):
        """测试没有助手消息时获取"""
        session = Session()
        session.add_message(UserMessage.from_text("Hello"))

        result = session.get_last_assistant_message()

        assert result is None

    def test_len(self):
        """测试长度"""
        session = Session()
        session.add_message(UserMessage.from_text("Hello"))
        session.add_message(AssistantMessage(content=[TextContent(text="Hi")]))

        assert len(session) == 2

    def test_repr(self):
        """测试字符串表示"""
        session = Session()
        session.add_message(UserMessage.from_text("Hello"))

        repr_str = repr(session)

        assert "Session" in repr_str
        assert "messages=1" in repr_str


# ===========================================
# SessionManager Tests
# ===========================================


class TestSessionManager:
    """SessionManager 测试"""

    def test_init(self):
        """测试初始化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            assert manager.sessions_dir.exists()

    def test_create_session(self):
        """测试创建会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            session = manager.create_session("test-session")

            assert session.path is not None
            assert session.path.name == "test-session.jsonl"

    def test_create_session_auto_name(self):
        """测试自动命名创建会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            session = manager.create_session()

            assert session.path is not None
            assert session.path.name.startswith("session_")

    def test_get_session(self):
        """测试获取会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            # 创建会话
            session = manager.create_session("test-session")
            session.add_message(UserMessage.from_text("Hello"))
            session.save()

            # 获取会话
            retrieved = manager.get_session("test-session")

            assert len(retrieved.messages) == 1

    def test_get_nonexistent_session(self):
        """测试获取不存在的会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            session = manager.get_session("nonexistent")

            assert session.messages == []

    def test_delete_session(self):
        """测试删除会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            # 创建会话
            session = manager.create_session("test-session")
            session.save()

            # 删除
            result = manager.delete_session("test-session")

            assert result is True
            assert not session.path.exists()

    def test_delete_nonexistent_session(self):
        """测试删除不存在的会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            result = manager.delete_session("nonexistent")

            assert result is False

    def test_list_sessions(self):
        """测试列出会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            # 创建多个会话
            session1 = manager.create_session("session-1")
            session1.add_message(UserMessage.from_text("Hello"))
            session1.save()

            session2 = manager.create_session("session-2")
            session2.add_message(UserMessage.from_text("World"))
            session2.save()

            sessions = manager.list_sessions()

            assert len(sessions) == 2
            names = [s["name"] for s in sessions]
            assert "session-1" in names
            assert "session-2" in names

    def test_list_sessions_empty(self):
        """测试空目录列出会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            sessions = manager.list_sessions()

            assert sessions == []

    def test_list_sessions_with_invalid_file(self):
        """测试目录中有无效文件时列出会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            # 创建有效会话
            session = manager.create_session("valid")
            session.save()

            # 创建无效文件（完全无效的 JSON）
            invalid_path = Path(tmpdir) / "invalid.jsonl"
            with open(invalid_path, "w") as f:
                f.write("{\nnot valid json at all\n")  # 完全无效的 JSON

            sessions = manager.list_sessions()

            # 无效文件应该被跳过
            names = [s["name"] for s in sessions]
            assert "valid" in names

    def test_list_sessions_sorted_by_updated_at(self):
        """测试会话按更新时间排序"""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            # 创建第一个会话
            session1 = manager.create_session("session-1")
            session1.save()

            time.sleep(0.1)  # 确保时间差

            # 创建第二个会话
            session2 = manager.create_session("session-2")
            session2.save()

            sessions = manager.list_sessions()

            # 最新更新在前
            assert sessions[0]["name"] == "session-2"
            assert sessions[1]["name"] == "session-1"

    def test_get_recent_session(self):
        """测试获取最近会话"""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            # 创建会话
            session1 = manager.create_session("session-1")
            session1.save()

            time.sleep(0.1)

            session2 = manager.create_session("session-2")
            session2.save()

            recent = manager.get_recent_session()

            assert recent is not None
            assert recent.path.name == "session-2.jsonl"

    def test_get_recent_session_none(self):
        """测试没有会话时获取最近会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(Path(tmpdir))

            recent = manager.get_recent_session()

            assert recent is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])