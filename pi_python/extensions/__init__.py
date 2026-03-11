"""
PI-Python 扩展系统

提供插件化的扩展能力
"""

from .api import ExtensionAPI, ExtensionContext
from .loader import ExtensionLoader

__all__ = [
    "ExtensionAPI",
    "ExtensionContext",
    "ExtensionLoader",
]