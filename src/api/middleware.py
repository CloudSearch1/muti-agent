"""
IntelliTeam API 中间件模块

提供请求验证、限流、认证等中间件
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta
from typing import Dict, Optional
import time


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件
    
    限制每个 IP 的请求频率
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_history: Dict[str, list] = {}
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        now = datetime.now()
        
        # 清理过期记录
        if client_ip in self.request_history:
            self.request_history[client_ip] = [
                req_time for req_time in self.request_history[client_ip]
                if now - req_time < timedelta(minutes=1)
            ]
        else:
            self.request_history[client_ip] = []
        
        # 检查是否超限
        if len(self.request_history[client_ip]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"error": "请求过于频繁，请稍后再试"}
            )
        
        # 记录请求
        self.request_history[client_ip].append(now)
        
        # 继续处理请求
        response = await call_next(request)
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    请求耗时统计中间件
    
    记录每个请求的处理时间
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全头中间件
    
    添加安全相关的 HTTP 头
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 添加安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


def create_exception_handler(app):
    """
    创建全局异常处理器
    
    Args:
        app: FastAPI 应用实例
    """
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": "服务器内部错误",
                "message": str(exc),
                "path": str(request.url.path)
            }
        )


def setup_middlewares(app, rate_limit: int = 60):
    """
    配置所有中间件
    
    Args:
        app: FastAPI 应用实例
        rate_limit: 每分钟请求限制
    """
    # 添加中间件
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestTimingMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=rate_limit)
    
    # 配置异常处理
    create_exception_handler(app)
