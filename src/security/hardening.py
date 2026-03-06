"""
安全加固模块

实现全面的安全防护措施
"""

import re
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()


# ============ 密码安全 ============

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    哈希密码
    
    Args:
        password: 明文密码
        salt: 盐值（可选，自动生成）
    
    Returns:
        (哈希值，盐值)
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    # 使用 SHA-256 + 盐
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """验证密码"""
    new_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(new_hash, hashed)


# ============ JWT Token ============

def create_access_token(
    data: dict,
    secret_key: str,
    expires_delta: timedelta = timedelta(hours=1),
) -> str:
    """
    创建访问令牌
    
    Args:
        data: 载荷数据
        secret_key: 密钥
        expires_delta: 过期时间
    
    Returns:
        JWT Token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str, secret_key: str) -> Optional[dict]:
    """
    解码访问令牌
    
    Args:
        token: JWT Token
        secret_key: 密钥
    
    Returns:
        载荷数据，失败返回 None
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ============ 输入验证 ============

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    清理输入
    
    Args:
        text: 输入文本
        max_length: 最大长度
    
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 限制长度
    text = text[:max_length]
    
    # 移除危险字符
    dangerous_patterns = [
        r'<script.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe.*?</iframe>',
        r'<object.*?</object>',
    ]
    
    for pattern in dangerous_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    return text.strip()


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_username(username: str) -> bool:
    """验证用户名格式"""
    if len(username) < 3 or len(username) > 50:
        return False
    
    pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, username))


# ============ 速率限制 ============

class RateLimiter:
    """
    速率限制器
    
    基于 IP 和用户的速率限制
    """
    
    def __init__(self):
        self._requests: dict[str, list] = {}
    
    def is_allowed(
        self,
        identifier: str,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> bool:
        """
        检查请求是否允许
        
        Args:
            identifier: 标识符（IP 或用户 ID）
            max_requests: 最大请求数
            window_seconds: 时间窗口（秒）
        
        Returns:
            是否允许
        """
        now = datetime.utcnow().timestamp()
        window_start = now - window_seconds
        
        # 清理过期请求
        if identifier in self._requests:
            self._requests[identifier] = [
                ts for ts in self._requests[identifier]
                if ts > window_start
            ]
        else:
            self._requests[identifier] = []
        
        # 检查是否超限
        if len(self._requests[identifier]) >= max_requests:
            return False
        
        # 记录请求
        self._requests[identifier].append(now)
        return True
    
    def get_remaining(
        self,
        identifier: str,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> int:
        """获取剩余请求数"""
        now = datetime.utcnow().timestamp()
        window_start = now - window_seconds
        
        if identifier not in self._requests:
            return max_requests
        
        current_requests = len([
            ts for ts in self._requests[identifier]
            if ts > window_start
        ])
        
        return max(0, max_requests - current_requests)


# ============ CSRF 保护 ============

def generate_csrf_token() -> str:
    """生成 CSRF Token"""
    return secrets.token_urlsafe(32)


def validate_csrf_token(token: str, session_token: str) -> bool:
    """验证 CSRF Token"""
    return secrets.compare_digest(token, session_token)


# ============ 安全中间件 ============

class SecurityMiddleware:
    """
    安全中间件
    
    提供全面的安全防护
    """
    
    def __init__(self, app, secret_key: str):
        self.app = app
        self.secret_key = secret_key
        self.rate_limiter = RateLimiter()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        request = Request(scope, receive)
        
        # 1. 速率限制
        client_ip = request.client.host
        if not self.rate_limiter.is_allowed(client_ip, max_requests=100, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
            )
        
        # 2. 安全头
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
                    (b"content-security-policy", b"default-src 'self'"),
                ])
                message["headers"] = headers
            await send(message)
        
        await self.app(scope, receive, send_wrapper)


# ============ 审计日志 ============

class AuditLogger:
    """
    审计日志
    
    记录所有安全相关操作
    """
    
    def __init__(self, log_file: str = "logs/audit.log"):
        self.log_file = log_file
    
    def log(
        self,
        action: str,
        user: str,
        resource: str,
        ip_address: str,
        status: str = "success",
        details: Optional[dict] = None,
    ):
        """记录审计日志"""
        import json
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user": user,
            "resource": resource,
            "ip_address": ip_address,
            "status": status,
            "details": details or {},
        }
        
        # 追加到日志文件
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    def log_login(self, user: str, ip: str, success: bool):
        """记录登录审计"""
        self.log(
            action="login",
            user=user,
            resource="auth",
            ip_address=ip,
            status="success" if success else "failed",
        )
    
    def log_access(self, user: str, resource: str, ip: str):
        """记录访问审计"""
        self.log(
            action="access",
            user=user,
            resource=resource,
            ip_address=ip,
            status="success",
        )
    
    def log_modification(self, user: str, resource: str, ip: str, changes: dict):
        """记录修改审计"""
        self.log(
            action="modification",
            user=user,
            resource=resource,
            ip_address=ip,
            status="success",
            details={"changes": changes},
        )


# ============ 安全依赖 ============

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = security,
) -> dict:
    """
    获取当前用户
    
    Args:
        credentials: HTTP 认证凭证
    
    Returns:
        用户信息
    
    Raises:
        HTTPException: 认证失败
    """
    import os
    
    secret_key = os.getenv("SECURITY_SECRET_KEY", "change-me")
    
    payload = decode_access_token(credentials.credentials, secret_key)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


# ============ 安全工具函数 ============

def generate_api_key() -> str:
    """生成 API Key"""
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """哈希 API Key"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """常量时间比较（防止时序攻击）"""
    return secrets.compare_digest(a.encode(), b.encode())
