# IntelliTeam 认证模块

"""
认证和授权模块：
- JWT Token 认证
- 密码哈希和验证
- 用户管理
"""

from .auth import (
    # 配置
    JWT_SECRET,
    JWT_ALGORITHM,
    JWT_EXPIRE_HOURS,
    
    # 数据模型
    TokenData,
    UserCreate,
    UserLogin,
    TokenResponse,
    
    # 工具函数
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    
    # 认证管理器
    AuthManager,
    get_current_user,
    get_auth_manager
)

__all__ = [
    # 配置
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "JWT_EXPIRE_HOURS",
    
    # 数据模型
    "TokenData",
    "UserCreate",
    "UserLogin",
    "TokenResponse",
    
    # 工具函数
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    
    # 认证管理器
    "AuthManager",
    "get_current_user",
    "get_auth_manager"
]
