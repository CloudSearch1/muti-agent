"""
FastAPI 应用入口

职责：创建和配置 FastAPI 应用
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..config.settings import AppSettings as Settings, get_settings
from ..memory.session import SessionManager
from ..memory.short_term import ShortTermMemory
from .routes import router as api_router

logger = structlog.get_logger(__name__)


# 全局资源
_resources: dict[str, Any] = {}


# Web UI 静态文件目录
WEBUI_DIR = Path(__file__).parent.parent.parent / "webui"
STATIC_DIR = WEBUI_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("Application starting up")

    settings = get_settings()

    # 初始化 Redis
    memory = ShortTermMemory(redis_url=settings.redis_url)
    try:
        await memory.connect()
    except Exception as e:
        logger.warning(f"Redis connection failed, using in-memory storage: {e}")
        # 继续使用内存存储
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

    # 注册 API 路由
    app.include_router(api_router, prefix="/api/v1")

    # 挂载 Web UI 静态文件
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        logger.info("Web UI 静态文件挂载成功", path=str(STATIC_DIR))

    # 健康检查
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "app": settings.app_name,
            "environment": settings.app_env,
        }

    # Web UI 主页面
    @app.get("/")
    async def root():
        """返回 Web UI 主页面"""
        index_file = WEBUI_DIR / "index_v5.html"
        if index_file.exists():
            with open(index_file, encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        # 降级到 API 信息
        return {
            "name": settings.app_name,
            "version": "1.0.0",
            "docs": "/docs",
            "message": "Web UI not found, please check webui/index_v5.html",
        }

    # PWA Manifest
    @app.get("/manifest.json")
    async def get_manifest():
        """返回 PWA manifest"""
        manifest_file = WEBUI_DIR / "manifest.json"
        if manifest_file.exists():
            from fastapi.responses import FileResponse
            return FileResponse(path=str(manifest_file), media_type="application/json")
        return {"error": "manifest.json not found"}

    # 离线页面
    @app.get("/offline.html")
    async def get_offline():
        """返回离线页面"""
        offline_file = WEBUI_DIR / "offline.html"
        if offline_file.exists():
            from fastapi.responses import FileResponse
            return FileResponse(path=str(offline_file), media_type="text/html")
        return HTMLResponse(content="<html><body><h1>Offline</h1></body></html>")

    # 任务详情页面
    @app.get("/task-detail.html")
    async def get_task_detail():
        """返回任务详情页面"""
        task_detail_file = WEBUI_DIR / "task-detail.html"
        if task_detail_file.exists():
            from fastapi.responses import FileResponse
            return FileResponse(path=str(task_detail_file), media_type="text/html")
        return HTMLResponse(content="<html><body><h1>Task detail page not found</h1></body></html>")

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
