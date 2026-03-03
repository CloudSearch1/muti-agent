"""
API 路由
"""

from fastapi import APIRouter

from .agent import router as agent_router
from .task import router as task_router

router = APIRouter()

# 注册子路由
router.include_router(task_router, prefix="/tasks", tags=["tasks"])
router.include_router(agent_router, prefix="/agents", tags=["agents"])
