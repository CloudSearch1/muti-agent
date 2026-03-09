"""
API 响应标准化模块

提供统一的 API 响应格式，包括：
- 成功响应
- 错误响应
- 分页响应
- 响应构建器
"""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""

    success: bool = Field(..., description="请求是否成功")
    data: T | None = Field(default=None, description="响应数据")
    error: str | None = Field(default=None, description="错误信息")
    message: str | None = Field(default=None, description="提示信息")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="响应时间戳",
    )
    request_id: str | None = Field(default=None, description="请求 ID")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"key": "value"},
                "error": None,
                "message": "操作成功",
                "timestamp": "2026-03-08T12:00:00",
                "request_id": "req_123456",
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应格式"""

    success: bool = Field(default=True, description="请求是否成功")
    data: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="响应时间戳",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": [{"id": 1, "name": "Item 1"}],
                "total": 100,
                "page": 1,
                "page_size": 10,
                "total_pages": 10,
                "has_next": True,
                "has_prev": False,
                "timestamp": "2026-03-08T12:00:00",
            }
        }


class ErrorDetail(BaseModel):
    """错误详情"""

    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    field: str | None = Field(default=None, description="相关字段")
    value: Any | None = Field(default=None, description="相关值")


class ErrorResponse(BaseModel):
    """错误响应格式"""

    success: bool = Field(default=False, description="请求是否成功")
    error: ErrorDetail = Field(..., description="错误详情")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="响应时间戳",
    )
    request_id: str | None = Field(default=None, description="请求 ID")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "参数验证失败",
                    "field": "title",
                    "value": "",
                },
                "timestamp": "2026-03-08T12:00:00",
                "request_id": "req_123456",
            }
        }


# ============ 响应构建器 ============


class ResponseBuilder:
    """响应构建器"""

    @staticmethod
    def success(
        data: Any = None,
        message: str = "操作成功",
        request_id: str | None = None,
    ) -> APIResponse:
        """构建成功响应"""
        return APIResponse(
            success=True,
            data=data,
            message=message,
            request_id=request_id,
        )

    @staticmethod
    def error(
        code: str,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        request_id: str | None = None,
    ) -> ErrorResponse:
        """构建错误响应"""
        return ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=message,
                field=field,
                value=value,
            ),
            request_id=request_id,
        )

    @staticmethod
    def paginated(
        data: list[Any],
        total: int,
        page: int,
        page_size: int,
    ) -> PaginatedResponse:
        """构建分页响应"""
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return PaginatedResponse(
            data=data,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


# ============ 预定义错误 ============


class APIErrors:
    """预定义 API 错误"""

    @staticmethod
    def not_found(resource: str, request_id: str | None = None) -> ErrorResponse:
        return ResponseBuilder.error(
            code="NOT_FOUND",
            message=f"{resource} 不存在",
            request_id=request_id,
        )

    @staticmethod
    def validation_error(
        field: str,
        message: str,
        value: Any = None,
        request_id: str | None = None,
    ) -> ErrorResponse:
        return ResponseBuilder.error(
            code="VALIDATION_ERROR",
            message=message,
            field=field,
            value=value,
            request_id=request_id,
        )

    @staticmethod
    def unauthorized(request_id: str | None = None) -> ErrorResponse:
        return ResponseBuilder.error(
            code="UNAUTHORIZED",
            message="未授权访问",
            request_id=request_id,
        )

    @staticmethod
    def forbidden(request_id: str | None = None) -> ErrorResponse:
        return ResponseBuilder.error(
            code="FORBIDDEN",
            message="禁止访问",
            request_id=request_id,
        )

    @staticmethod
    def internal_error(
        message: str = "服务器内部错误",
        request_id: str | None = None,
    ) -> ErrorResponse:
        return ResponseBuilder.error(
            code="INTERNAL_ERROR",
            message=message,
            request_id=request_id,
        )

    @staticmethod
    def rate_limited(request_id: str | None = None) -> ErrorResponse:
        return ResponseBuilder.error(
            code="RATE_LIMITED",
            message="请求过于频繁，请稍后重试",
            request_id=request_id,
        )


# ============ 便捷函数 ============


def success_response(data: Any = None, message: str = "操作成功") -> APIResponse:
    """创建成功响应"""
    return ResponseBuilder.success(data=data, message=message)


def error_response(
    code: str,
    message: str,
    field: str | None = None,
) -> ErrorResponse:
    """创建错误响应"""
    return ResponseBuilder.error(code=code, message=message, field=field)


def paginated_response(
    data: list[Any],
    total: int,
    page: int,
    page_size: int,
) -> PaginatedResponse:
    """创建分页响应"""
    return ResponseBuilder.paginated(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
    )