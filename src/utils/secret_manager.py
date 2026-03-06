"""
API Key 安全管理

安全存储和管理 LLM API Key，支持轮换和审计
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SecretManager:
    """
    密钥管理器
    
    功能:
    - 安全存储 API Key
    - 支持多提供商
    - 密钥轮换
    - 使用审计
    - 访问日志
    """
    
    def __init__(self, secrets_file: Optional[str] = None):
        self._secrets_file = Path(secrets_file or ".secrets.json")
        self._audit_log: list[dict] = []
        self._cache: Dict[str, str] = {}
        self._last_rotation: Dict[str, datetime] = {}
        
        # 创建 secrets 文件（如果不存在）
        if not self._secrets_file.exists():
            self._secrets_file.touch(mode=0o600)  # 仅所有者可读写
            logger.info(f"Created secrets file: {self._secrets_file}")
        
        logger.info("SecretManager initialized")
    
    def set_secret(self, key: str, value: str, encrypt: bool = True):
        """
        设置密钥
        
        Args:
            key: 密钥名称（如 openai_api_key）
            value: 密钥值
            encrypt: 是否加密存储
        """
        secrets = self._load_secrets()
        
        # 简单加密（XOR + Base64）
        if encrypt:
            value = self._simple_encrypt(value)
        
        secrets[key] = {
            "value": value,
            "encrypted": encrypt,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        self._save_secrets(secrets)
        self._cache[key] = value
        self._last_rotation[key] = datetime.now()
        
        logger.info(f"Secret set: {key}")
        self._log_audit("set_secret", key)
    
    def get_secret(self, key: str, decrypt: bool = True) -> Optional[str]:
        """
        获取密钥
        
        Args:
            key: 密钥名称
            decrypt: 是否解密
        
        Returns:
            密钥值，如果不存在返回 None
        """
        # 检查缓存
        if key in self._cache:
            self._log_audit("get_secret", key, cached=True)
            return self._cache[key]
        
        secrets = self._load_secrets()
        
        if key not in secrets:
            logger.warning(f"Secret not found: {key}")
            return None
        
        secret_data = secrets[key]
        value = secret_data["value"]
        
        # 解密
        if decrypt and secret_data.get("encrypted", False):
            value = self._simple_decrypt(value)
        
        # 缓存
        self._cache[key] = value
        
        self._log_audit("get_secret", key)
        return value
    
    def delete_secret(self, key: str):
        """删除密钥"""
        secrets = self._load_secrets()
        
        if key in secrets:
            del secrets[key]
            self._save_secrets(secrets)
            
            # 清除缓存
            if key in self._cache:
                del self._cache[key]
            
            logger.info(f"Secret deleted: {key}")
            self._log_audit("delete_secret", key)
    
    def rotate_secret(self, key: str, new_value: str):
        """
        轮换密钥
        
        Args:
            key: 密钥名称
            new_value: 新密钥值
        """
        old_value = self.get_secret(key)
        
        # 设置新密钥
        self.set_secret(key, new_value)
        
        # 记录轮换
        logger.info(f"Secret rotated: {key}")
        self._log_audit("rotate_secret", key, old_value_hash=self._hash_value(old_value))
    
    def list_secrets(self) -> list[str]:
        """列出所有密钥名称"""
        secrets = self._load_secrets()
        return list(secrets.keys())
    
    def get_audit_log(self, limit: int = 100) -> list[dict]:
        """获取审计日志"""
        return self._audit_log[-limit:]
    
    def _load_secrets(self) -> dict:
        """加载密钥文件"""
        try:
            if self._secrets_file.exists() and self._secrets_file.stat().st_size > 0:
                with open(self._secrets_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
        
        return {}
    
    def _save_secrets(self, secrets: dict):
        """保存密钥文件"""
        try:
            with open(self._secrets_file, "w", encoding="utf-8") as f:
                json.dump(secrets, f, indent=2, ensure_ascii=False)
            
            # 设置文件权限（仅所有者可读写）
            os.chmod(self._secrets_file, 0o600)
            
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            raise
    
    def _simple_encrypt(self, value: str) -> str:
        """简单加密（XOR + Base64）"""
        import base64
        
        key = os.getenv("SECRET_KEY", "default_secret_key")
        key_bytes = key.encode()
        value_bytes = value.encode()
        
        # XOR 加密
        encrypted = bytes([v ^ key_bytes[i % len(key_bytes)] for i, v in enumerate(value_bytes)])
        
        # Base64 编码
        return base64.b64encode(encrypted).decode()
    
    def _simple_decrypt(self, encrypted_value: str) -> str:
        """简单解密"""
        import base64
        
        key = os.getenv("SECRET_KEY", "default_secret_key")
        key_bytes = key.encode()
        
        # Base64 解码
        encrypted_bytes = base64.b64decode(encrypted_value.encode())
        
        # XOR 解密
        decrypted = bytes([e ^ key_bytes[i % len(key_bytes)] for i, e in enumerate(encrypted_bytes)])
        
        return decrypted.decode()
    
    def _hash_value(self, value: Optional[str]) -> str:
        """哈希值（用于审计）"""
        if not value:
            return "none"
        return hashlib.sha256(value.encode()).hexdigest()[:16]
    
    def _log_audit(self, action: str, key: str, **kwargs):
        """记录审计日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "key": key,
            **kwargs,
        }
        self._audit_log.append(log_entry)
        
        # 限制审计日志大小
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]
        
        logger.debug(f"Audit: {action} - {key}")


# 使用审计装饰器
def audit_secret_access(func):
    """审计密钥访问装饰器"""
    def wrapper(self, key: str, *args, **kwargs):
        result = func(self, key, *args, **kwargs)
        self._log_audit(func.__name__, key)
        return result
    return wrapper


# 全局密钥管理器实例
_secret_manager: Optional[SecretManager] = None


def get_secret_manager(secrets_file: Optional[str] = None) -> SecretManager:
    """获取密钥管理器实例"""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager(secrets_file)
    return _secret_manager


# 便捷函数
def get_api_key(provider: str) -> Optional[str]:
    """便捷函数：获取 API Key"""
    manager = get_secret_manager()
    key_name = f"{provider}_api_key"
    return manager.get_secret(key_name)


def set_api_key(provider: str, api_key: str):
    """便捷函数：设置 API Key"""
    manager = get_secret_manager()
    key_name = f"{provider}_api_key"
    manager.set_secret(key_name, api_key)


def rotate_api_key(provider: str, new_api_key: str):
    """便捷函数：轮换 API Key"""
    manager = get_secret_manager()
    key_name = f"{provider}_api_key"
    manager.rotate_secret(key_name, new_api_key)
