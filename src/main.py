"""
IntelliTeam - 智能研发协作平台

主入口
"""

import structlog

from .config.settings import get_settings

# 配置结构化日志
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger("INFO"),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)


logger = structlog.get_logger(__name__)


def main():
    """主函数"""
    import uvicorn

    settings = get_settings()

    logger.info(
        "Starting IntelliTeam",
        version="1.0.0",
        environment=settings.app_env,
    )

    # 启动服务器
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development(),
    )


if __name__ == "__main__":
    main()
