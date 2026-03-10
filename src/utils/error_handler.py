"""
统一错误处理模块

提供统一的错误类型和处理装饰器
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


# ============ 基础错误类 ============

class AppError(Exception):
    """应用基础错误"""
    code: str = "UNKNOWN_ERROR"
    message: str = "未知错误"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str | None = None, **kwargs):
        if message:
            self.message = message
        super().__init__(self.message)


# ============ 业务错误 ============

class ValidationError(AppError):
    """验证错误"""
    code = "VALIDATION_ERROR"
    message = "数据验证失败"
    status_code = status.HTTP_400_BAD_REQUEST


class NotFoundError(AppError):
    """未找到错误"""
    code = "NOT_FOUND"
    message = "资源未找到"
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    """冲突错误"""
    code = "CONFLICT"
    message = "资源冲突"
    status_code = status.HTTP_409_CONFLICT


class UnauthorizedError(AppError):
    """未授权错误"""
    code = "UNAUTHORIZED"
    message = "未授权访问"
    status_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(AppError):
    """禁止访问错误"""
    code = "FORBIDDEN"
    message = "禁止访问"
    status_code = status.HTTP_403_FORBIDDEN


# ============ 系统错误 ============

class DatabaseError(AppError):
    """数据库错误"""
    code = "DATABASE_ERROR"
    message = "数据库操作失败"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class ExternalServiceError(AppError):
    """外部服务错误"""
    code = "EXTERNAL_SERVICE_ERROR"
    message = "外部服务调用失败"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class LLMError(AppError):
    """LLM 调用错误"""
    code = "LLM_ERROR"
    message = "LLM 调用失败"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


# ============ 错误处理装饰器 ============

def handle_errors(default_return: Any = None, raise_on_error: bool = False):
    """
    错误处理装饰器

    Args:
        default_return: 错误时的默认返回值
        raise_on_error: 是否重新抛出错误

    用法:
        @handle_errors(default_return={"error": "处理失败"})
        async def api_handler():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except AppError as e:
                logger.error(f"App error in {func.__name__}: {e.message}", exc_info=False)
                if raise_on_error:
                    raise
                return default_return
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
                if raise_on_error:
                    raise
                return default_return

        return wrapper
    return decorator


def http_error_handler(func: Callable):
    """
    HTTP 错误处理器装饰器

    将 AppError 转换为 HTTPException

    用法:
        @http_error_handler
        async def api_handler():
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except AppError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": e.code,
                    "message": e.message,
                },
            )

    return wrapper


# ============ 统一错误响应 ============

def create_error_response(
    error: str,
    message: str,
    status_code: int = 500,
    details: dict | None = None,
) -> dict:
    """
    创建统一的错误响应

    Args:
        error: 错误代码
        message: 错误消息
        status_code: HTTP 状态码
        details: 详细错误信息

    Returns:
        错误响应字典
    """
    response = {
        "error": error,
        "message": message,
        "status_code": status_code,
    }

    if details:
        response["details"] = details

    return response


# ============ 快捷错误函数 ============

def raise_validation_error(message: str = "数据验证失败"):
    """抛出验证错误"""
    raise ValidationError(message)


def raise_not_found_error(message: str = "资源未找到"):
    """抛出未找到错误"""
    raise NotFoundError(message)


def raise_conflict_error(message: str = "资源冲突"):
    """抛出冲突错误"""
    raise ConflictError(message)


def raise_unauthorized_error(message: str = "未授权访问"):
    """抛出未授权错误"""
    raise UnauthorizedError(message)


def raise_forbidden_error(message: str = "禁止访问"):
    """抛出禁止访问错误"""
    raise ForbiddenError(message)


# ============ 异常上下文管理器 ============

from contextlib import contextmanager


@contextmanager
def handle_exception(error_class: type[AppError], message: str):
    """
    异常上下文管理器

    用法:
        with handle_exception(DatabaseError, "数据库操作失败"):
            # 可能抛出异常的代码
            await db.execute(...)
    """
    try:
        yield
    except Exception as e:
        logger.error(f"{message}: {e}", exc_info=True)
        raise error_class(f"{message}: {str(e)}")
