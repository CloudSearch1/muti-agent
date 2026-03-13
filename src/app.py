"""
IntelliTeam 应用工厂模块

创建和配置 FastAPI 应用
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .api.batch_endpoints import router as batch_router
from .api.docs import setup_openapi_docs
from .api.middleware import setup_middlewares
from .api.routes import router as api_router
from .api.routes.knowledge import router as knowledge_router
from .api.routes.tools import router as tools_router
from .api.security import setup_security_middleware
from .monitoring.health import init_health_checks
from .utils.exceptions import register_exception_handlers
from .utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("应用启动中...")
    await init_health_checks()

    # 连接缓存
    from .api.response_cache import init_response_cacher
    await init_response_cacher()

    # 连接速率限制器
    from .api.rate_limiter import init_rate_limiter
    await init_rate_limiter()

    logger.info("应用启动完成")
    yield
    # 关闭时
    logger.info("应用关闭中...")
    # 清理资源
    logger.info("应用已关闭")


def create_app(config_name: str = "production") -> FastAPI:
    """
    创建 FastAPI 应用

    Args:
        config_name: 配置名称（development, production）

    Returns:
        FastAPI 应用实例
    """
    # 初始化日志
    setup_logging(
        level="DEBUG" if config_name == "development" else "INFO",
        log_file="logs/intelliteam.log" if config_name == "production" else None,
    )

    # 创建应用
    app = FastAPI(
        title="IntelliTeam API",
        description="智能研发协作平台",
        version="2.0.0",
        docs_url=None,  # 自定义
        redoc_url=None,  # 自定义
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if config_name == "development" else ["https://your-domain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip 压缩 - 响应大于 1KB 时自动压缩
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 安全中间件
    setup_security_middleware(app, rate_limit=60)

    # API 中间件
    setup_middlewares(app)

    # 异常处理
    register_exception_handlers(app)

    # API 文档
    setup_openapi_docs(app)

    # 注册路由
    app.include_router(api_router, prefix="/api/v1")

    # 注册批量端点路由
    app.include_router(batch_router, prefix="/api/v1")

    # 注册知识库路由
    app.include_router(knowledge_router, prefix="/api/v1")

    # 注册工具系统路由
    app.include_router(tools_router, prefix="/api/v1")

    # Prometheus 指标
    @app.get("/metrics", include_in_schema=False)
    async def get_metrics():
        """获取 Prometheus 指标"""
        from fastapi.responses import Response
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    logger.info(f"应用已创建，配置：{config_name}")

    return app


# 创建应用实例
app = create_app()
