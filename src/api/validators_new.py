"""
API 参数验证模块

提供增强的参数验证功能，包括：
- 通用验证器
- 自定义验证规则
- 参数清洗
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ============ 基础验证模型 ============


class BaseRequestModel(BaseModel):
    """基础请求模型"""

    class Config:
        extra = "forbid"
        str_strip_whitespace = True


class PaginationRequest(BaseRequestModel):
    """分页请求参数"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页数量")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class SortRequest(BaseRequestModel):
    """排序请求参数"""

    sort_by: str | None = Field(default=None, description="排序字段")
    sort_order: str = Field(default="desc", description="排序方向")

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: str) -> str:
        if v.lower() not in ("asc", "desc"):
            raise ValueError("sort_order 必须是 'asc' 或 'desc'")
        return v.lower()


# ============ 任务相关验证 ============


class TaskCreateRequest(BaseRequestModel):
    """创建任务请求"""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    priority: str = Field(default="normal")
    assignee: str | None = Field(default=None, max_length=100)
    agent: str | None = Field(default=None, max_length=100)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        valid = ["low", "normal", "high", "urgent"]
        if v.lower() not in valid:
            raise ValueError(f"优先级必须是: {', '.join(valid)}")
        return v.lower()


class TaskUpdateRequest(BaseRequestModel):
    """更新任务请求"""

    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None)
    status: str | None = Field(default=None)
    priority: str | None = Field(default=None)
    assignee: str | None = Field(default=None)
    agent: str | None = Field(default=None)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is None:
            return None
        valid = ["pending", "in_progress", "completed", "cancelled"]
        if v.lower() not in valid:
            raise ValueError(f"状态必须是: {', '.join(valid)}")
        return v.lower()


class TaskQueryRequest(PaginationRequest, SortRequest):
    """任务查询请求"""

    status: str | None = Field(default=None)
    priority: str | None = Field(default=None)
    assignee: str | None = Field(default=None)
    keyword: str | None = Field(default=None, max_length=100)


# ============ Agent 相关验证 ============


class AgentCreateRequest(BaseRequestModel):
    """创建 Agent 请求"""

    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)


class AgentStatusUpdateRequest(BaseRequestModel):
    """更新 Agent 状态请求"""

    status: str = Field(...)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = ["idle", "busy", "offline", "error"]
        if v.lower() not in valid:
            raise ValueError(f"状态必须是: {', '.join(valid)}")
        return v.lower()


# ============ 工作流相关验证 ============


class WorkflowCreateRequest(BaseRequestModel):
    """创建工作流请求"""

    name: str = Field(..., min_length=1, max_length=200)
    input_data: dict[str, Any] | None = Field(default=None)


class WorkflowQueryRequest(PaginationRequest, SortRequest):
    """工作流查询请求"""

    state: str | None = Field(default=None)

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str | None) -> str | None:
        if v is None:
            return None
        valid = ["running", "completed", "failed", "cancelled"]
        if v.lower() not in valid:
            raise ValueError(f"状态必须是: {', '.join(valid)}")
        return v.lower()