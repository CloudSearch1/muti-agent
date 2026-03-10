"""
输入验证增强

使用 Pydantic 进行严格的输入验证，防止注入攻击
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.utils.compat import StrEnum


class TaskPriority(StrEnum):
    """任务优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(StrEnum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="任务标题",
    )
    description: str = Field(
        default="",
        max_length=5000,
        description="任务描述",
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="优先级",
    )
    requirements: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="需求列表",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="元数据",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """验证标题"""
        # 去除首尾空白
        v = v.strip()

        # 检查危险字符（防止注入）
        dangerous_chars = ["<", ">", ";", "--", "/*", "*/", "xp_", "UNION", "SELECT"]
        for char in dangerous_chars:
            if char.lower() in v.lower():
                raise ValueError(f"Title contains dangerous characters: {char}")

        # 检查长度
        if len(v) < 1:
            raise ValueError("Title cannot be empty")

        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """验证描述"""
        # 去除首尾空白
        v = v.strip()

        # 检查过长的内容
        if len(v) > 5000:
            raise ValueError("Description too long (max 5000 characters)")

        return v

    @field_validator("requirements")
    @classmethod
    def validate_requirements(cls, v: list[str]) -> list[str]:
        """验证需求列表"""
        if not v:
            return v

        # 验证每个需求
        validated = []
        for req in v:
            req = req.strip()
            if len(req) < 1:
                continue
            if len(req) > 1000:
                raise ValueError("Each requirement must be less than 1000 characters")
            validated.append(req)

        return validated


class TaskUpdateRequest(BaseModel):
    """更新任务请求"""
    title: str | None = Field(
        None,
        min_length=1,
        max_length=200,
    )
    description: str | None = Field(
        None,
        max_length=5000,
    )
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    assignee: str | None = Field(
        None,
        max_length=100,
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        dangerous_chars = ["<", ">", ";", "--"]
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Title contains dangerous characters: {char}")
        return v


class AgentExecuteRequest(BaseModel):
    """Agent 执行请求"""
    task_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$",  # 只允许字母数字下划线横线
    )
    parameters: dict[str, Any] | None = Field(
        default=None,
        description="执行参数",
    )
    timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="超时时间（秒）",
    )

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        """验证任务 ID（防止注入）"""
        if not v.strip():
            raise ValueError("Task ID cannot be empty")
        return v.strip()

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """验证参数"""
        if v is None:
            return v

        # 验证参数键
        for key in v.keys():
            if not isinstance(key, str):
                raise ValueError("Parameter keys must be strings")
            if len(key) > 100:
                raise ValueError("Parameter key too long")
            # 检查危险字符
            if any(char in key for char in ["<", ">", ";", "'", '"']):
                raise ValueError("Parameter key contains invalid characters")

        return v


class LLMGenerateRequest(BaseModel):
    """LLM 生成请求"""
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="提示词",
    )
    system_prompt: str | None = Field(
        None,
        max_length=5000,
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="温度",
    )
    max_tokens: int = Field(
        default=2048,
        ge=1,
        le=8192,
        description="最大 token 数",
    )

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        """验证提示词"""
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Prompt cannot be empty")

        # 检查 prompt 注入攻击
        injection_patterns = [
            r"ignore\s+previous\s+instructions",
            r"forget\s+all\s+instructions",
            r"you\s+are\s+now\s+",
            r"system\s+instruction:",
        ]

        for pattern in injection_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Prompt contains potential injection attack")

        return v


class CodeExecutionRequest(BaseModel):
    """代码执行请求"""
    code: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="代码",
    )
    language: str = Field(
        default="python",
        pattern=r"^(python|javascript|typescript|java|cpp|go|rust)$",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
    )

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """验证代码（防止危险操作）"""
        # 检查危险函数调用
        dangerous_functions = [
            "os.system",
            "subprocess.call",
            "subprocess.Popen",
            "eval(",
            "exec(",
            "__import__",
            "open(",
        ]

        for func in dangerous_functions:
            if func in v:
                raise ValueError(f"Code contains dangerous function: {func}")

        return v


class BatchOperationRequest(BaseModel):
    """批量操作请求"""
    operations: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="操作列表",
    )

    @field_validator("operations")
    @classmethod
    def validate_operations(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """验证批量操作"""
        if len(v) > 100:
            raise ValueError("Maximum 100 operations per batch")

        for i, op in enumerate(v):
            if not isinstance(op, dict):
                raise ValueError(f"Operation {i} must be a dictionary")

            if "type" not in op:
                raise ValueError(f"Operation {i} missing 'type' field")

            if not isinstance(op["type"], str):
                raise ValueError(f"Operation {i} 'type' must be a string")

        return v


# 响应模型
class TaskResponse(BaseModel):
    """任务响应"""
    id: str
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    assignee: str | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    message: str
    details: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class SuccessResponse(BaseModel):
    """成功响应"""
    status: str = "success"
    message: str
    data: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
