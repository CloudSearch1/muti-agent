"""
IntelliTeam API 响应优化模块

提供分页、过滤、排序、压缩等优化功能
"""

from math import ceil
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginationParams(BaseModel):
    """分页参数"""

    page: int = 1
    page_size: int = 20
    sort: str = "created_at"
    order: str = "desc"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"page": 1, "page_size": 20, "sort": "created_at", "order": "desc"}
        }
    )


class PaginationResponse(BaseModel, Generic[T]):
    """分页响应"""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(
        cls, items: list[T], total: int, page: int, page_size: int
    ) -> "PaginationResponse[T]":
        """创建分页响应"""
        total_pages = ceil(total / page_size) if total > 0 else 0

        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class QueryFilters(BaseModel):
    """查询过滤器"""

    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    agent: str | None = None
    keyword: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in self.dict().items() if v is not None}


class FieldFilter:
    """字段过滤器"""

    @staticmethod
    def filter_fields(data: dict[str, Any], fields: str | None) -> dict[str, Any]:
        """
        过滤返回字段

        Args:
            data: 原始数据
            fields: 字段列表（逗号分隔）

        Returns:
            过滤后的数据
        """
        if not fields:
            return data

        field_list = [f.strip() for f in fields.split(",")]
        return {k: v for k, v in data.items() if k in field_list}


class ResponseOptimizer:
    """响应优化器"""

    @staticmethod
    def paginate(
        items: list[Any], total: int, page: int = 1, page_size: int = 20
    ) -> PaginationResponse:
        """
        分页响应

        Args:
            items: 数据列表
            total: 总数
            page: 页码
            page_size: 每页数量

        Returns:
            分页响应
        """
        return PaginationResponse.create(items, total, page, page_size)

    @staticmethod
    def apply_sort(
        items: list[dict[str, Any]], sort_by: str = "created_at", order: str = "desc"
    ) -> list[dict[str, Any]]:
        """
        应用排序

        Args:
            items: 数据列表
            sort_by: 排序字段
            order: 排序方向（asc/desc）

        Returns:
            排序后的列表
        """
        reverse = order.lower() == "desc"
        return sorted(items, key=lambda x: x.get(sort_by, ""), reverse=reverse)

    @staticmethod
    def apply_filters(items: list[dict[str, Any]], filters: QueryFilters) -> list[dict[str, Any]]:
        """
        应用过滤

        Args:
            items: 数据列表
            filters: 过滤器

        Returns:
            过滤后的列表
        """
        result = items

        if filters.status:
            result = [i for i in result if i.get("status") == filters.status]

        if filters.priority:
            result = [i for i in result if i.get("priority") == filters.priority]

        if filters.assignee:
            result = [i for i in result if i.get("assignee") == filters.assignee]

        if filters.agent:
            result = [i for i in result if i.get("agent") == filters.agent]

        if filters.keyword:
            keyword = filters.keyword.lower()
            result = [
                i
                for i in result
                if keyword in i.get("title", "").lower()
                or keyword in i.get("description", "").lower()
            ]

        return result

    @staticmethod
    def compress_response(data: dict[str, Any], min_size: int = 1000) -> dict[str, Any]:
        """
        压缩响应（标记用于 GZip）

        Args:
            data: 响应数据
            min_size: 最小压缩大小

        Returns:
            压缩标记的响应
        """
        # FastAPI 的 GZipMiddleware 会自动处理
        return data
