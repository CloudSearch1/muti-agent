"""
生产环境主入口

职责：配置生产环境，启用监控、日志等
"""

import sys
from pathlib import Path

import structlog

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from .config.settings import Settings


def setup_logging(settings: Settings) -> None:
    """配置生产环境日志"""

    log_format = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 配置 logging 模块
    import logging
    from logging.handlers import RotatingFileHandler

    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 文件处理器
    file_handler = RotatingFileHandler(
        log_dir / "intelliteam.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_format)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)

    # 根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def setup_monitoring(settings: Settings) -> None:
    """配置监控"""
    if not settings.is_production():
        return

    try:
        from prometheus_client import Counter, Histogram, start_http_server

        # 定义指标
        Counter(
            "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
        )

        Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
        )

        # 启动 Prometheus 服务器
        start_http_server(settings.api_port + 1)  # 默认 9091

        import logging

        logging.getLogger(__name__).info(
            "Prometheus metrics enabled",
            port=settings.api_port + 1,
        )

    except ImportError:
        import logging

        logging.getLogger(__name__).warning("Prometheus not installed, monitoring disabled")


def main():
    """生产环境主函数"""
    import uvicorn

    # 加载配置
    settings = Settings()

    # 配置日志
    setup_logging(settings)

    logger = structlog.get_logger(__name__)

    logger.info(
        "Starting IntelliTeam (Production)",
        version="1.0.0",
        environment=settings.app_env,
        workers=settings.api_workers,
    )

    # 配置监控
    setup_monitoring(settings)

    # 启动服务器
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers if settings.is_production() else 1,
        reload=False,
        log_level=settings.log_level.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    main()
