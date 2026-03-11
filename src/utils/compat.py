"""
Python 兼容性模块

提供统一的类型导入
"""

from datetime import UTC, timezone
from enum import Enum, StrEnum

__all__ = ["StrEnum", "UTC", "timezone", "Enum"]
