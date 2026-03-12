"""
标准工具错误模型

定义工具系统使用的标准错误码和错误结构。

错误处理架构:
┌─────────────────────────────────────────────────────────────┐
│                       ToolError                              │
│  - 标准化错误码                                              │
│  - 错误详情                                                  │
│  - 重试建议                                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     StandardError                            │
│  {                                                           │
│    "code": "VALIDATION_ERROR",                               │
│    "message": "human readable",                              │
│    "retryable": false,                                       │
│    "details": {},                                            │
│    "hint": "string"                                          │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘

使用示例:
    # 抛出工具错误
    raise ToolError(
        code=ErrorCode.VALIDATION_ERROR,
        message="参数 path 不能为空",
        retryable=False
    )
    
    # 创建标准错误对象
    error = StandardError(
        code=ErrorCode.NOT_FOUND,
        message="文件不存在",
        details={"path": "/path/to/file"},
        hint="请检查文件路径是否正确"
    )
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """
    标准错误码枚举
    
    所有工具必须使用这些标准错误码来保证一致性。
    """
    
    # 参数验证错误
    VALIDATION_ERROR = "VALIDATION_ERROR"
    
    # 认证授权错误
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    
    # 资源错误
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    
    # 执行错误
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    
    # 依赖错误
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    
    # 安全错误
    SECURITY_BLOCKED = "SECURITY_BLOCKED"
    
    # 内部错误
    INTERNAL_ERROR = "INTERNAL_ERROR"


class StandardError(BaseModel):
    """
    标准错误结构
    
    所有工具错误都应返回此结构，包含错误码、人类可读消息、
    是否可重试、详细信息以及可选的提示信息。
    """
    
    code: ErrorCode = Field(..., description="错误码")
    message: str = Field(..., description="人类可读的错误消息")
    retryable: bool = Field(default=False, description="是否可重试")
    details: Dict[str, Any] = Field(default_factory=dict, description="错误详情")
    hint: Optional[str] = Field(default=None, description="解决建议")
    
    def __str__(self) -> str:
        """返回错误消息字符串"""
        hint_str = f" (Hint: {self.hint})" if self.hint else ""
        return f"[{self.code}] {self.message}{hint_str}"


class ToolError(Exception):
    """
    工具异常类
    
    工具可以抛出此异常，框架会自动转换为 ToolResult。
    支持标准错误码和详细信息。
    
    Attributes:
        error: 标准错误对象
    
    示例:
        raise ToolError(
            code=ErrorCode.VALIDATION_ERROR,
            message="参数 path 不能为空",
            retryable=False,
            path="/invalid/path"
        )
    """
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        retryable: bool = False,
        hint: Optional[str] = None,
        **details: Any,
    ):
        """
        初始化工具错误
        
        Args:
            code: 错误码
            message: 错误消息
            retryable: 是否可重试
            hint: 解决建议
            **details: 错误详情键值对
        """
        self.error = StandardError(
            code=code,
            message=message,
            retryable=retryable,
            details=details,
            hint=hint,
        )
        super().__init__(message)
    
    def __str__(self) -> str:
        """返回错误消息"""
        return str(self.error)
    
    def __repr__(self) -> str:
        """返回错误详情"""
        return f"ToolError(code={self.error.code}, message={self.error.message!r})"


# 便捷错误创建函数
def validation_error(message: str, **details: Any) -> ToolError:
    """创建验证错误"""
    return ToolError(ErrorCode.VALIDATION_ERROR, message, retryable=False, **details)


def not_found_error(message: str, **details: Any) -> ToolError:
    """创建未找到错误"""
    return ToolError(ErrorCode.NOT_FOUND, message, retryable=False, **details)


def unauthorized_error(message: str, **details: Any) -> ToolError:
    """创建未授权错误"""
    return ToolError(ErrorCode.UNAUTHORIZED, message, retryable=False, **details)


def forbidden_error(message: str, **details: Any) -> ToolError:
    """创建禁止访问错误"""
    return ToolError(ErrorCode.FORBIDDEN, message, retryable=False, **details)


def timeout_error(message: str, **details: Any) -> ToolError:
    """创建超时错误"""
    return ToolError(ErrorCode.TIMEOUT, message, retryable=True, **details)


def security_blocked_error(message: str, **details: Any) -> ToolError:
    """创建安全阻止错误"""
    return ToolError(ErrorCode.SECURITY_BLOCKED, message, retryable=False, **details)


def internal_error(message: str, **details: Any) -> ToolError:
    """创建内部错误"""
    return ToolError(ErrorCode.INTERNAL_ERROR, message, retryable=False, **details)
