"""
IntelliTeam 应用工厂模块

创建和配置 FastAPI 应用
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .api.routes import router as api_router
from .api.docs import setup_openapi_docs
from .api.security import setup_security_middleware
from .api.middleware import setup_middlewares
from .utils.exceptions import register_exception_handlers
from .utils.logging_config import setup_logging
from .monitoring.prometheus import metrics_collector
from .monitoring.health import init_health_checks, get_health_checker
from .config.celery_config import celery_app

logger = logging.getLogger(__name__)


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
        log_file="logs/intelliteam.log" if config_name == "production" else None
    )
    
    # 创建应用
    app = FastAPI(
        title="IntelliTeam API",
        description="智能研发协作平台",
        version="2.0.0",
        docs_url=None,  # 自定义
        redoc_url=None,  # 自定义
        openapi_url="/openapi.json"
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if config_name == "development" else ["https://your-domain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
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
    
    # 初始化健康检查
    @app.on_event("startup")
    async def startup_event():
        logger.info("应用启动中...")
        await init_health_checks()
        
        # 连接缓存
        from .api.response_cache import init_response_cacher
        await init_response_cacher()
        
        # 连接速率限制器
        from .api.rate_limiter import init_rate_limiter
        await init_rate_limiter()
        
        logger.info("应用启动完成")
    
    # 关闭事件
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("应用关闭中...")
        # 清理资源
        logger.info("应用已关闭")
    
    # Prometheus 指标
    @app.get("/metrics", include_in_schema=False)
    async def get_metrics():
        """获取 Prometheus 指标"""
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        from fastapi.responses import Response
        
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    
    logger.info(f"应用已创建，配置：{config_name}")
    
    return app


# 创建应用实例
app = create_app()
