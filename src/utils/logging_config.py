"""
IntelliTeam 日志配置模块

提供统一的日志配置和结构化日志
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化为 JSON"""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加额外字段
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    log_format: str = "json",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    配置日志系统

    Args:
        level: 日志级别
        log_file: 日志文件路径
        log_format: 日志格式 (json/text)
        max_bytes: 单个日志文件最大大小
        backup_count: 备份文件数量
    """
    # 创建日志目录
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    # 根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # 清除现有处理器
    root_logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    if log_format == "json":
        console_formatter = JSONFormatter()
    else:
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    if log_file:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(console_formatter)
        root_logger.addHandler(file_handler)

    # 设置第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.WARNING)

    # 记录启动信息
    logger = logging.getLogger(__name__)
    logger.info(f"日志系统已初始化，级别：{level}, 格式：{log_format}")


def get_logger(name: str) -> logging.Logger:
    """
    获取日志器

    Args:
        name: 日志器名称

    Returns:
        日志器实例
    """
    return logging.getLogger(name)


class RequestContextFilter(logging.Filter):
    """请求上下文过滤器"""

    def __init__(self, request_id: str, user_id: str | None = None):
        super().__init__()
        self.request_id = request_id
        self.user_id = user_id

    def filter(self, record: logging.LogRecord) -> bool:
        """添加上下文信息"""
        record.request_id = self.request_id
        if self.user_id:
            record.user_id = self.user_id
        return True


def log_api_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration: float,
    request_id: str,
    user_id: str | None = None,
):
    """
    记录 API 请求日志

    Args:
        logger: 日志器
        method: HTTP 方法
        path: 请求路径
        status_code: 状态码
        duration: 处理时间（秒）
        request_id: 请求 ID
        user_id: 用户 ID
    """
    extra = {
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration": f"{duration:.4f}s",
    }

    if user_id:
        extra["user_id"] = user_id

    if status_code >= 500:
        logger.error("API 请求失败", extra=extra)
    elif status_code >= 400:
        logger.warning("API 请求客户端错误", extra=extra)
    else:
        logger.info("API 请求成功", extra=extra)
