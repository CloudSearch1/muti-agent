"""
测试认证模块
"""

import pytest
from datetime import datetime, timedelta
from src.auth.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    AuthManager
)


class TestAuth:
    """测试认证功能"""
    
    def test_hash_password(self):
        """测试密码哈希"""
        password = "test123"
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) == 64
    
    def test_verify_password(self):
        """测试密码验证"""
        password = "test123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
        assert verify_password("wrong", hashed) is False
    
    def test_create_access_token(self):
        """测试创建 Token"""
        data = {"user_id": 1, "username": "test"}
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_decode_access_token(self):
        """测试解码 Token"""
        data = {"user_id": 1, "username": "test"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["user_id"] == 1
        assert decoded["username"] == "test"
    
    def test_decode_invalid_token(self):
        """测试解码无效 Token"""
        decoded = decode_access_token("invalid_token")
        assert decoded is None
    
    def test_auth_manager_create_token(self):
        """测试认证管理器创建 Token"""
        auth = AuthManager()
        token = auth.create_token(user_id=1, username="test")
        assert isinstance(token, str)
    
    def test_auth_manager_verify_token(self):
        """测试认证管理器验证 Token"""
        auth = AuthManager()
        token = auth.create_token(user_id=1, username="test")
        token_data = auth.verify_token(token)
        assert token_data is not None
        assert token_data.user_id == 1
        assert token_data.username == "test"
    
    def test_auth_manager_refresh_token(self):
        """测试刷新 Token"""
        auth = AuthManager()
        old_token = auth.create_token(user_id=1, username="test")
        new_token = auth.refresh_token(old_token)
        assert new_token is not None
        assert new_token != old_token
