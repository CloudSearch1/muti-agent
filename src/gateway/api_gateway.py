"""
API 网关

统一的 API 网关，提供路由、限流、认证等功能
"""

import time
import logging
from typing import Dict, List, Optional, Callable
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import httpx

logger = logging.getLogger(__name__)


class APIGateway:
    """
    API 网关
    
    功能:
    - 请求路由
    - 速率限制
    - 认证授权
    - 请求日志
    - 响应缓存
    - 熔断器
    """
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.routes: Dict[str, Dict[str, Any]] = {}
        self.rate_limiter = RateLimiter()
        self.auth_handler: Optional[Callable] = None
        self.cache = {}
        self.circuit_breaker = CircuitBreaker()
        
        logger.info("APIGateway initialized")
    
    def add_route(
        self,
        path: str,
        methods: List[str],
        target: str,
        auth_required: bool = False,
        rate_limit: Optional[int] = None,
        cache_ttl: Optional[int] = None,
    ):
        """
        添加路由
        
        Args:
            path: 路径
            methods: HTTP 方法
            target: 目标服务
            auth_required: 是否需要认证
            rate_limit: 速率限制（请求/分钟）
            cache_ttl: 缓存时间（秒）
        """
        self.routes[path] = {
            "methods": methods,
            "target": target,
            "auth_required": auth_required,
            "rate_limit": rate_limit,
            "cache_ttl": cache_ttl,
        }
        
        logger.info(f"Route added: {path} -> {target}")
    
    async def handle_request(self, request: Request) -> Response:
        """处理请求"""
        path = request.url.path
        method = request.method
        
        # 检查路由
        if path not in self.routes:
            return await self._default_handler(request)
        
        route = self.routes[path]
        
        # 检查方法
        if method not in route["methods"]:
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail="Method not allowed",
            )
        
        # 速率限制
        if route["rate_limit"]:
            client_ip = request.client.host
            if not self.rate_limiter.is_allowed(
                client_ip,
                max_requests=route["rate_limit"],
                window_seconds=60,
            ):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests",
                )
        
        # 认证
        if route["auth_required"]:
            if self.auth_handler:
                user = await self.auth_handler(request)
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Unauthorized",
                    )
        
        # 缓存（仅 GET 请求）
        if method == "GET" and route["cache_ttl"]:
            cache_key = f"{path}:{request.query_params}"
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if time.time() - cached["time"] < route["cache_ttl"]:
                    return JSONResponse(content=cached["data"])
        
        # 转发请求
        try:
            response = await self._forward_request(request, route["target"])
            
            # 缓存响应
            if method == "GET" and route["cache_ttl"] and response.status_code == 200:
                self.cache[cache_key] = {
                    "data": response.json(),
                    "time": time.time(),
                }
            
            return response
            
        except Exception as e:
            logger.error(f"Gateway error: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Bad gateway",
            )
    
    async def _default_handler(self, request: Request) -> Response:
        """默认处理器"""
        return await self.app(request.scope, request.receive, self._send_response)
    
    async def _forward_request(self, request: Request, target: str) -> Response:
        """转发请求"""
        async with httpx.AsyncClient() as client:
            # 构建目标 URL
            url = f"{target}{request.url.path}"
            if request.url.query:
                url += f"?{request.url.query}"
            
            # 获取请求体
            body = await request.body()
            
            # 转发
            response = await client.request(
                method=request.method,
                url=url,
                headers=dict(request.headers),
                content=body,
                timeout=30.0,
            )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
    
    def _send_response(self, message):
        """发送响应"""
        pass
    
    def set_auth_handler(self, handler: Callable):
        """设置认证处理器"""
        self.auth_handler = handler
        logger.info("Auth handler set")


class RateLimiter:
    """速率限制器"""
    
    def __init__(self):
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(
        self,
        identifier: str,
        max_requests: int,
        window_seconds: int,
    ) -> bool:
        """检查是否允许请求"""
        now = time.time()
        window_start = now - window_seconds
        
        # 清理过期请求
        if identifier in self.requests:
            self.requests[identifier] = [
                ts for ts in self.requests[identifier]
                if ts > window_start
            ]
        else:
            self.requests[identifier] = []
        
        # 检查是否超限
        if len(self.requests[identifier]) >= max_requests:
            return False
        
        # 记录请求
        self.requests[identifier].append(now)
        return True


class CircuitBreaker:
    """熔断器"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures: Dict[str, int] = {}
        self.last_failure: Dict[str, float] = {}
        self.state: Dict[str, str] = {}  # closed, open, half-open
    
    def is_available(self, service: str) -> bool:
        """检查服务是否可用"""
        state = self.state.get(service, "closed")
        
        if state == "closed":
            return True
        
        if state == "open":
            # 检查是否应该尝试恢复
            if time.time() - self.last_failure.get(service, 0) > self.recovery_timeout:
                self.state[service] = "half-open"
                return True
            return False
        
        # half-open
        return True
    
    def record_success(self, service: str):
        """记录成功"""
        self.failures[service] = 0
        self.state[service] = "closed"
    
    def record_failure(self, service: str):
        """记录失败"""
        self.failures[service] = self.failures.get(service, 0) + 1
        self.last_failure[service] = time.time()
        
        if self.failures[service] >= self.failure_threshold:
            self.state[service] = "open"
            logger.warning(f"Circuit breaker opened for {service}")


# ============ 中间件 ============

class GatewayMiddleware:
    """网关中间件"""
    
    def __init__(self, app, gateway: APIGateway):
        self.app = app
        self.gateway = gateway
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        request = Request(scope, receive)
        
        try:
            response = await self.gateway.handle_request(request)
            return await response(scope, receive, send)
        except HTTPException as e:
            response = JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
            )
            return await response(scope, receive, send)
        except Exception as e:
            logger.error(f"Gateway error: {e}")
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
            return await response(scope, receive, send)
