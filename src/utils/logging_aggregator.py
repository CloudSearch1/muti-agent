"""
日志聚合模块

集成 ELK Stack，支持结构化日志和日志分析
"""

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any

# ============ JSON 格式化器 ============

class JSONFormatter(logging.Formatter):
    """
    JSON 格式日志格式化器

    输出格式:
    {
        "timestamp": "2026-03-06T16:00:00.000Z",
        "level": "INFO",
        "logger": "myapp.module",
        "message": "Log message",
        "module": "module_name",
        "function": "function_name",
        "line": 123,
        "extra_field": "value"
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.thread,
        }

        # 添加额外字段
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message",
            ]:
                try:
                    json.dumps(value)  # 验证是否可 JSON 序列化
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        # 添加异常信息
        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


# ============ 结构化日志记录器 ============

class StructuredLogger:
    """
    结构化日志记录器

    用法:
        logger = StructuredLogger("myapp")
        logger.info("User logged in", user_id=123, ip="192.168.1.1")
    """

    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False

    def _log(self, level: int, message: str, **kwargs):
        """内部日志方法"""
        extra = {"extra": kwargs} if kwargs else {}
        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs):
        self._log(logging.ERROR, message, exc_info=True, **kwargs)


# ============ 日志处理器配置 ============

def create_file_handler(
    log_file: str,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    json_format: bool = True,
) -> RotatingFileHandler:
    """
    创建文件处理器

    Args:
        log_file: 日志文件路径
        level: 日志级别
        max_bytes: 单个文件最大大小
        backup_count: 备份文件数量
        json_format: 是否使用 JSON 格式

    Returns:
        文件处理器实例
    """
    # 确保目录存在
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

    return handler


def create_timed_file_handler(
    log_file: str,
    level: int = logging.INFO,
    when: str = "midnight",
    interval: int = 1,
    backup_count: int = 30,
    json_format: bool = True,
) -> TimedRotatingFileHandler:
    """
    创建定时轮转文件处理器

    Args:
        log_file: 日志文件路径
        level: 日志级别
        when: 轮转时间（'midnight', 'H', 'M', 'S'）
        interval: 轮转间隔
        backup_count: 备份文件数量
        json_format: 是否使用 JSON 格式

    Returns:
        定时轮转处理器实例
    """
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    handler = TimedRotatingFileHandler(
        log_file,
        when=when,
        interval=interval,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

    return handler


def create_console_handler(
    level: int = logging.INFO,
    json_format: bool = False,
) -> logging.StreamHandler:
    """
    创建控制台处理器

    Args:
        level: 日志级别
        json_format: 是否使用 JSON 格式

    Returns:
        控制台处理器实例
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

    return handler


# ============ 日志配置 ============

def setup_logging(
    name: str = "app",
    level: int = logging.INFO,
    log_file: str | None = None,
    console_output: bool = True,
    json_format: bool = True,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> StructuredLogger:
    """
    设置日志配置

    Args:
        name: 日志名称
        level: 日志级别
        log_file: 日志文件路径（None 表示不写入文件）
        console_output: 是否输出到控制台
        json_format: 是否使用 JSON 格式
        max_bytes: 单个文件最大大小
        backup_count: 备份文件数量

    Returns:
        结构化日志记录器实例
    """
    logger = StructuredLogger(name, level)
    base_logger = logging.getLogger(name)
    base_logger.setLevel(level)
    base_logger.propagate = False

    # 添加文件处理器
    if log_file:
        file_handler = create_file_handler(
            log_file,
            level=level,
            max_bytes=max_bytes,
            backup_count=backup_count,
            json_format=json_format,
        )
        base_logger.addHandler(file_handler)

    # 添加控制台处理器
    if console_output:
        console_handler = create_console_handler(
            level=level,
            json_format=json_format,
        )
        base_logger.addHandler(console_handler)

    return logger


# ============ 审计日志 ============

class AuditLogger:
    """
    审计日志记录器

    专门用于记录安全相关操作
    """

    def __init__(self, log_file: str = "logs/audit.log"):
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # 使用定时轮转，保留 90 天
        handler = create_timed_file_handler(
            log_file,
            level=logging.INFO,
            when="midnight",
            interval=1,
            backup_count=90,
            json_format=True,
        )
        self.logger.addHandler(handler)

    def log(
        self,
        action: str,
        user: str,
        resource: str,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        """
        记录审计日志

        Args:
            action: 操作类型（login, logout, create, update, delete）
            user: 用户标识
            resource: 资源标识
            details: 详细信息
            ip_address: IP 地址
            user_agent: 用户代理
        """
        log_data = {
            "action": action,
            "user": user,
            "resource": resource,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        if details:
            log_data["details"] = details

        if ip_address:
            log_data["ip_address"] = ip_address

        if user_agent:
            log_data["user_agent"] = user_agent

        self.logger.info(json.dumps(log_data, ensure_ascii=False))

    def log_login(self, user: str, success: bool, **kwargs):
        """记录登录审计"""
        self.log(
            action="login",
            user=user,
            resource="auth",
            details={"success": success},
            **kwargs,
        )

    def log_logout(self, user: str, **kwargs):
        """记录登出审计"""
        self.log(action="logout", user=user, resource="auth", **kwargs)

    def log_create(self, user: str, resource: str, resource_id: str, **kwargs):
        """记录创建操作审计"""
        self.log(
            action="create",
            user=user,
            resource=resource,
            details={"resource_id": resource_id},
            **kwargs,
        )

    def log_update(self, user: str, resource: str, resource_id: str, **kwargs):
        """记录更新操作审计"""
        self.log(
            action="update",
            user=user,
            resource=resource,
            details={"resource_id": resource_id},
            **kwargs,
        )

    def log_delete(self, user: str, resource: str, resource_id: str, **kwargs):
        """记录删除操作审计"""
        self.log(
            action="delete",
            user=user,
            resource=resource,
            details={"resource_id": resource_id},
            **kwargs,
        )


# ============ 全局审计日志实例 ============

_audit_logger: AuditLogger | None = None


def get_audit_logger(log_file: str = "logs/audit.log") -> AuditLogger:
    """获取审计日志记录器"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(log_file)
    return _audit_logger
