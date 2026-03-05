"""
IntelliTeam 统一异常处理模块

提供统一的异常类和错误响应
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ============ 异常类定义 ============


class IntelliTeamException(Exception):
    """基础异常类"""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "UNKNOWN_ERROR",
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()

        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class ValidationError(IntelliTeamException):
    """验证错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message, status_code=400, error_code="VALIDATION_ERROR", details=details
        )


class NotFoundError(IntelliTeamException):
    """资源不存在"""

    def __init__(self, resource: str, resource_id: Any):
        super().__init__(
            message=f"{resource} not found: {resource_id}",
            status_code=404,
            error_code="NOT_FOUND",
            details={"resource": resource, "resource_id": resource_id},
        )


class AuthenticationError(IntelliTeamException):
    """认证错误"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, status_code=401, error_code="AUTHENTICATION_ERROR")


class AuthorizationError(IntelliTeamException):
    """授权错误"""

    def __init__(self, message: str = "Not authorized"):
        super().__init__(message=message, status_code=403, error_code="AUTHORIZATION_ERROR")


class ConflictError(IntelliTeamException):
    """冲突错误"""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message=message, status_code=409, error_code="CONFLICT_ERROR")


class RateLimitError(IntelliTeamException):
    """限流错误"""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message=message, status_code=429, error_code="RATE_LIMIT_ERROR")


class DatabaseError(IntelliTeamException):
    """数据库错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message, status_code=500, error_code="DATABASE_ERROR", details=details
        )


class CacheError(IntelliTeamException):
    """缓存错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message, status_code=500, error_code="CACHE_ERROR", details=details
        )


class TaskError(IntelliTeamException):
    """任务执行错误"""

    def __init__(self, message: str, task_id: int | None = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="TASK_ERROR",
            details={"task_id": task_id} if task_id else None,
        )


# ============ 错误响应格式化 ============


def format_error_response(error: Exception, include_details: bool = True) -> dict[str, Any]:
    """
    格式化错误响应

    Args:
        error: 异常对象
        include_details: 是否包含详细信息

    Returns:
        错误响应字典
    """
    if isinstance(error, IntelliTeamException):
        response = error.to_dict()
        if not include_details:
            response.pop("details", None)
        return response

    # 普通异常
    return {
        "error": "INTERNAL_ERROR",
        "message": str(error),
        "status_code": 500,
        "timestamp": datetime.now().isoformat(),
    }


def create_error_response(
    message: str,
    status_code: int = 500,
    error_code: str = "UNKNOWN_ERROR",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    创建错误响应

    Args:
        message: 错误消息
        status_code: HTTP 状态码
        error_code: 错误代码
        details: 详细信息

    Returns:
        错误响应字典
    """
    return {
        "error": error_code,
        "message": message,
        "status_code": status_code,
        "details": details or {},
        "timestamp": datetime.now().isoformat(),
    }


# ============ FastAPI 异常处理器 ============


def register_exception_handlers(app):
    """
    注册异常处理器到 FastAPI 应用

    Args:
        app: FastAPI 应用实例
    """
    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from pydantic import ValidationError

    @app.exception_handler(IntelliTeamException)
    async def intelliteam_exception_handler(request: Request, exc: IntelliTeamException):
        """处理自定义异常"""
        logger.warning(
            f"自定义异常：{exc.error_code}",
            extra={"path": str(request.url.path), "method": request.method, "error": exc.message},
        )

        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证异常"""
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(x) for x in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        logger.warning("请求验证失败", extra={"path": str(request.url.path), "errors": errors})

        return JSONResponse(
            status_code=400,
            content=create_error_response(
                message="请求验证失败",
                status_code=400,
                error_code="VALIDATION_ERROR",
                details={"errors": errors},
            ),
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
        """处理 Pydantic 验证异常"""
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(x) for x in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        return JSONResponse(
            status_code=400,
            content=create_error_response(
                message="数据验证失败",
                status_code=400,
                error_code="VALIDATION_ERROR",
                details={"errors": errors},
            ),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理未捕获的异常"""
        logger.error(
            f"未捕获的异常：{str(exc)}",
            extra={
                "path": str(request.url.path),
                "method": request.method,
                "exception_type": type(exc).__name__,
            },
            exc_info=True,
        )

        return JSONResponse(
            status_code=500,
            content=create_error_response(
                message="服务器内部错误", status_code=500, error_code="INTERNAL_ERROR"
            ),
        )

    logger.info("异常处理器已注册")
