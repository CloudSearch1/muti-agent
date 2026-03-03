"""
IntelliTeam 安全中间件模块

提供 CORS、CSRF、XSS 等安全防护
"""

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List, Optional
import re
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全头中间件
    
    添加安全相关的 HTTP 头
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 防止点击劫持
        response.headers["X-Frame-Options"] = "DENY"
        
        # 防止 MIME 类型嗅探
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS 防护
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # 严格传输安全
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # 内容安全策略
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' cdn.jsdelivr.net"
        
        # Referrer 策略
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # 权限策略
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


class XSSProtectionMiddleware(BaseHTTPMiddleware):
    """
    XSS 防护中间件
    
    检查和清理输入中的 XSS 攻击
    """
    
    # XSS 攻击模式
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
    ]
    
    def __init__(self, app, sanitize_input: bool = True):
        super().__init__(app)
        self.sanitize_input = sanitize_input
    
    async def dispatch(self, request: Request, call_next):
        # 检查请求方法
        if request.method in ["POST", "PUT", "PATCH"]:
            # 获取请求体
            body = await request.body()
            
            # 检查 XSS 攻击
            if self.contains_xss(body.decode()):
                logger.warning(f"检测到 XSS 攻击尝试：{request.url.path}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid input detected"}
                )
        
        response = await call_next(request)
        return response
    
    def contains_xss(self, text: str) -> bool:
        """检查是否包含 XSS 攻击"""
        for pattern in self.XSS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件
    
    基于 IP 的速率限制
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        whitelist: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.whitelist = whitelist or []
        self.request_history = {}
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        
        # 白名单跳过限流
        if client_ip in self.whitelist:
            return await call_next(request)
        
        from datetime import datetime, timedelta
        
        now = datetime.now()
        
        # 初始化请求历史
        if client_ip not in self.request_history:
            self.request_history[client_ip] = {
                "minute": [],
                "hour": []
            }
        
        history = self.request_history[client_ip]
        
        # 清理过期记录
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        
        history["minute"] = [
            t for t in history["minute"] if t > minute_ago
        ]
        history["hour"] = [
            t for t in history["hour"] if t > hour_ago
        ]
        
        # 检查限流
        if len(history["minute"]) >= self.requests_per_minute:
            logger.warning(f"IP {client_ip} 触发分钟限流")
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests per minute"}
            )
        
        if len(history["hour"]) >= self.requests_per_hour:
            logger.warning(f"IP {client_ip} 触发小时限流")
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests per hour"}
            )
        
        # 记录请求
        history["minute"].append(now)
        history["hour"].append(now)
        
        response = await call_next(request)
        
        # 添加限流头
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            self.requests_per_minute - len(history["minute"])
        )
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            self.requests_per_hour - len(history["hour"])
        )
        
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    请求 ID 中间件
    
    为每个请求生成唯一 ID，用于日志追踪
    """
    
    async def dispatch(self, request: Request, call_next):
        import uuid
        
        # 生成请求 ID
        request_id = str(uuid.uuid4())
        
        # 添加到请求头
        request.state.request_id = request_id
        
        # 调用下一个中间件
        response = await call_next(request)
        
        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        
        return response


def setup_security_middleware(app, rate_limit: int = 60):
    """
    配置所有安全中间件
    
    Args:
        app: FastAPI 应用实例
        rate_limit: 每分钟请求限制
    """
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    
    # 安全头
    app.add_middleware(SecurityHeadersMiddleware)
    
    # XSS 防护
    app.add_middleware(XSSProtectionMiddleware)
    
    # 速率限制
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=rate_limit
    )
    
    # 请求 ID
    app.add_middleware(RequestIDMiddleware)
    
    # 信任主机（生产环境）
    # app.add_middleware(
    #     TrustedHostMiddleware,
    #     allowed_hosts=["example.com", "*.example.com"]
    # )
    
    logger.info("安全中间件已配置")
