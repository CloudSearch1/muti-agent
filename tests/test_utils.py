"""
测试工具函数模块
"""

from src.utils.helpers import (
    filter_dict,
    format_duration,
    generate_id,
    hash_password,
    is_valid_email,
    is_valid_url,
    merge_dicts,
    safe_get,
    truncate_text,
)


class TestHelpers:
    """测试工具函数"""

    def test_generate_id(self):
        """测试生成 ID"""
        id1 = generate_id()
        id2 = generate_id()
        assert id1 != id2  # 每次生成不同
        assert len(id1) > 14  # 时间戳格式 + 随机后缀

    def test_generate_id_with_prefix(self):
        """测试带前缀的 ID"""
        id_with_prefix = generate_id("test_")
        assert id_with_prefix.startswith("test_")

    def test_hash_password(self):
        """测试密码哈希"""
        password = "test123"
        hashed = hash_password(password)
        assert hashed != password  # 哈希后不同
        assert len(hashed) == 64  # SHA256 长度
        assert hash_password(password) == hashed  # 相同密码哈希相同

    def test_format_duration(self):
        """测试时长格式化"""
        assert format_duration(30) == "30.00s"
        assert format_duration(90) == "1.50m"
        assert format_duration(3600) == "1.00h"

    def test_truncate_text(self):
        """测试文本截断"""
        text = "这是一段很长的文本"
        assert truncate_text(text, 5) == "这是一段很..."
        assert truncate_text(text, 100) == text  # 不超过最大长度

    def test_safe_get(self):
        """测试安全获取"""
        data = {"key": "value"}
        assert safe_get(data, "key") == "value"
        assert safe_get(data, "missing", "default") == "default"

    def test_merge_dicts(self):
        """测试合并字典"""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3, "d": 4}
        merged = merge_dicts(dict1, dict2)
        assert merged == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_filter_dict(self):
        """测试过滤字典"""
        data = {"a": 1, "b": 2, "c": 3}
        filtered = filter_dict(data, ["a", "c"])
        assert filtered == {"a": 1, "c": 3}

    def test_is_valid_email(self):
        """测试邮箱验证"""
        assert is_valid_email("test@example.com") is True
        assert is_valid_email("invalid") is False
        assert is_valid_email("test@invalid") is False

    def test_is_valid_url(self):
        """测试 URL 验证"""
        assert is_valid_url("https://example.com") is True
        assert is_valid_url("http://example.com") is True
        assert is_valid_url("invalid") is False
