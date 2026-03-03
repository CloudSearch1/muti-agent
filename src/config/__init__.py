# IntelliTeam 配置管理

"""
配置模块：
- 环境变量管理
- 配置验证
- 多环境支持
"""

from .celery_config import celery_app, CELERY_BROKER_URL, CELERY_RESULT_BACKEND

__all__ = [
    "celery_app",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND"
]
