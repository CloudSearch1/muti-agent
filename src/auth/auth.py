"""
IntelliTeam 认证模块

提供 JWT 用户认证和授权
"""

import hashlib
from datetime import datetime, timedelta
from typing import Any

import jwt
from pydantic import BaseModel

# JWT 配置
JWT_SECRET = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


# ============ 数据模型 ============


class TokenData(BaseModel):
    """Token 数据"""

    user_id: int
    username: str
    exp: datetime


class UserCreate(BaseModel):
    """用户创建"""

    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    """用户登录"""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Token 响应"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ============ 工具函数 ============


def hash_password(password: str) -> str:
    """
    密码哈希

    Args:
        password: 原始密码

    Returns:
        哈希后的密码
    """
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码

    Args:
        password: 原始密码
        password_hash: 哈希后的密码

    Returns:
        是否匹配
    """
    return hash_password(password) == password_hash


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    创建访问 Token

    Args:
        data: Token 数据
        expires_delta: 过期时间增量

    Returns:
        JWT Token 字符串
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    解码访问 Token

    Args:
        token: JWT Token

    Returns:
        Token 数据字典，无效返回 None
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        return {
            "user_id": payload.get("user_id"),
            "username": payload.get("username"),
            "exp": datetime.fromtimestamp(payload.get("exp")),
        }
    except jwt.PyJWTError:
        return None


# ============ 认证管理器 ============


class AuthManager:
    """认证管理器"""

    def __init__(self, secret: str = JWT_SECRET):
        self.secret = secret

    def create_token(self, user_id: int, username: str) -> str:
        """
        创建用户 Token

        Args:
            user_id: 用户 ID
            username: 用户名

        Returns:
            JWT Token
        """
        return create_access_token({"user_id": user_id, "username": username})

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """
        验证 Token

        Args:
            token: JWT Token

        Returns:
            Token 数据字典，无效返回 None
        """
        return decode_access_token(token)

    def refresh_token(self, token: str) -> str | None:
        """
        刷新 Token

        Args:
            token: 旧 Token

        Returns:
            新 Token，无效返回 None
        """
        token_data = self.verify_token(token)
        if not token_data:
            return None

        # 创建新token，添加刷新时间戳确保唯一性
        new_payload = {
            "user_id": token_data["user_id"],
            "username": token_data["username"],
            "refreshed_at": datetime.utcnow().isoformat(),
        }
        return create_access_token(new_payload)


# ============ FastAPI 依赖 ============


async def get_current_user(token: str) -> dict[str, Any] | None:
    """
    获取当前用户（FastAPI 依赖）

    Usage:
        @app.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            pass
    """
    auth_manager = AuthManager()
    token_data = auth_manager.verify_token(token)

    if not token_data:
        return None

    return {"user_id": token_data.user_id, "username": token_data.username}


# ============ 全局实例 ============

auth_manager = AuthManager()


def get_auth_manager() -> AuthManager:
    """获取认证管理器单例"""
    return auth_manager
