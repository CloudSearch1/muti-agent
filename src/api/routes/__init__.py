"""
API 路由
"""

from fastapi import APIRouter

from .agent import router as agent_router
from .event_sourcing import router as event_sourcing_router
from .llm import router as llm_router
from .local_llm import router as local_llm_router
from .memory import router as memory_router
from .pi import router as pi_router
from .settings import router as settings_router
from .skill import router as skill_router
from .task import router as task_router

router = APIRouter()

# 注册子路由
router.include_router(task_router, prefix="/tasks", tags=["tasks"])
router.include_router(agent_router, prefix="/agents", tags=["agents"])
router.include_router(skill_router, prefix="/skills", tags=["skills"])
router.include_router(memory_router, prefix="/memory", tags=["memory"])
router.include_router(event_sourcing_router, tags=["events"])
router.include_router(llm_router, prefix="/llm", tags=["llm"])
router.include_router(local_llm_router, tags=["Local LLM"])
router.include_router(pi_router, prefix="/pi", tags=["pi"])
router.include_router(settings_router, tags=["settings"])
