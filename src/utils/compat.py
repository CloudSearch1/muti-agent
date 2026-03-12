"""
Python 兼容性模块

提供统一的类型导入
"""

from datetime import timezone
from enum import Enum

# Python 3.10 兼容性：StrEnum 在 3.11+ 才有
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        """字符串枚举基类"""
        pass

# Python 3.10 兼容性：UTC 在 3.11+ 才有
UTC = timezone.utc

__all__ = ["StrEnum", "UTC", "timezone", "Enum"]
