"""
Python 3.10 兼容性模块

提供 Python 3.11+ 特性的向后兼容支持
"""

import sys
from datetime import timezone
from enum import Enum

# StrEnum 在 Python 3.11+ 中可用
if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    # Python 3.10 兼容性：手动实现 StrEnum
    class StrEnum(str, Enum):
        """字符串枚举基类，兼容 Python 3.10"""

        def __str__(self) -> str:
            return str(self.value)

        def __repr__(self) -> str:
            return str(self.value)


# UTC 在 Python 3.11+ 中可用
if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    # Python 3.10 兼容性：使用 timezone.utc
    UTC = timezone.utc

__all__ = ["StrEnum", "UTC"]