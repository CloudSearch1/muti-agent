"""
FastAPI 应用入口

职责：创建和配置 FastAPI 应用
"""

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config.settings import AppSettings as Settings, get_settings
from ..memory.session import SessionManager
from ..memory.short_term import ShortTermMemory
from .routes import router as api_router

logger = structlog.get_logger(__name__)


# 全局资源
_resources: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("Application starting up")

    settings = get_settings()

    # 初始化 Redis
    memory = ShortTermMemory(redis_url=settings.redis_url)
    await memory.connect()
    _resources["memory"] = memory

    # 初始化会话管理器
    session_manager = SessionManager(memory=memory)
    _resources["session_manager"] = session_manager

    logger.info("Application started")

    yield

    # 关闭时清理
    logger.info("Application shutting down")

    if "memory" in _resources:
        await _resources["memory"].disconnect()

    logger.info("Application stopped")


def create_app(settings: Settings = None) -> FastAPI:
    """
    创建 FastAPI 应用

    Args:
        settings: 配置对象，None 则使用默认配置

    Returns:
        FastAPI 应用实例
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="IntelliTeam - 智能研发协作平台 API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该限制
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(api_router, prefix="/api/v1")

    # 健康检查
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "app": settings.app_name,
            "environment": settings.app_env,
        }

    # 根路径
    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": "1.0.0",
            "docs": "/docs",
        }

    logger.info(
        "FastAPI app created",
        host=settings.api_host,
        port=settings.api_port,
    )

    return app


# 默认应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers if settings.is_production() else 1,
        reload=settings.is_development(),
    )
