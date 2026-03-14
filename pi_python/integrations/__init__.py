"""
PI-Python 平台集成模块

提供与 Slack、Teams、Discord 等平台的集成能力
"""

from .base import (
    BaseIntegration,
    IntegrationMessage,
    IntegrationResponse,
    IntegrationHandler,
)
from .registry import IntegrationRegistry, get_integration_registry
from .router import MessageRouter, Route

__all__ = [
    # 基类和类型
    "BaseIntegration",
    "IntegrationMessage",
    "IntegrationResponse",
    "IntegrationHandler",

    # 注册表和路由
    "IntegrationRegistry",
    "get_integration_registry",
    "MessageRouter",
    "Route",
]
