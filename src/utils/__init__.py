# IntelliTeam 工具模块

"""
工具模块提供通用功能：
- 配置管理
- 日志配置
- 工具函数
- 错误处理
"""

from .config import Settings, get_settings, reload_settings
from .error_handler import (
    AppError,
    ExternalServiceError,
    ForbiddenError,
    UnauthorizedError,
)
from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    CacheError,
    ConflictError,
    DatabaseError,
    IntelliTeamException,
    NotFoundError,
    RateLimitError,
    TaskError,
    ValidationError,
)
from .helpers import (
    filter_dict,
    format_duration,
    generate_id,
    hash_password,
    is_valid_email,
    is_valid_url,
    merge_dicts,
    safe_get,
    truncate_text,
)
from .logging import get_logger, setup_logging
from .text import clean_json_from_markdown

__all__ = [
    # 配置
    "Settings",
    "get_settings",
    "reload_settings",
    # 日志
    "setup_logging",
    "get_logger",
    # 工具函数
    "generate_id",
    "hash_password",
    "format_duration",
    "truncate_text",
    "safe_get",
    "merge_dicts",
    "filter_dict",
    "is_valid_email",
    "is_valid_url",
    "clean_json_from_markdown",
    # 错误处理
    "AppError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "UnauthorizedError",
    "ForbiddenError",
    "DatabaseError",
    "ExternalServiceError",
    # 异常
    "IntelliTeamException",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "CacheError",
    "TaskError",
]
