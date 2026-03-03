"""
IntelliTeam Celery 配置模块

提供异步任务队列支持
"""

from celery import Celery, Task
from celery.schedules import crontab
from typing import Any, Optional
import os

# Celery 配置
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TIMEZONE = os.getenv("CELERY_TIMEZONE", "Asia/Shanghai")

# 创建 Celery 应用
celery_app = Celery(
    "intelliteam",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "src.tasks.agent_tasks",
        "src.tasks.notification_tasks",
        "src.tasks.cleanup_tasks"
    ]
)

# Celery 配置
celery_app.conf.update(
    timezone=CELERY_TIMEZONE,
    enable_utc=True,
    
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # 任务确认
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # 结果过期
    result_expires=3600,
    
    # 并发数
    worker_concurrency=4,
    
    # 预取限制
    worker_prefetch_multiplier=1,
    
    # 任务路由
    task_routes={
        "src.tasks.agent_tasks.*": {"queue": "agent_queue"},
        "src.tasks.notification_tasks.*": {"queue": "notification_queue"},
        "src.tasks.cleanup_tasks.*": {"queue": "cleanup_queue"}
    },
    
    # 定时任务
    beat_schedule={
        "cleanup-old-tasks": {
            "task": "src.tasks.cleanup_tasks.cleanup_old_tasks",
            "schedule": crontab(hour=2, minute=0),  # 每天凌晨 2 点
        },
        "send-daily-report": {
            "task": "src.tasks.notification_tasks.send_daily_report",
            "schedule": crontab(hour=9, minute=0),  # 每天早上 9 点
        }
    }
)


def create_task(name: str, **kwargs) -> Task:
    """
    创建 Celery 任务
    
    Args:
        name: 任务名称
        **kwargs: 任务参数
        
    Returns:
        Celery 任务
    """
    return celery_app.task(name=name, **kwargs)


def execute_task_async(task_name: str, *args, **kwargs):
    """
    异步执行任务
    
    Args:
        task_name: 任务名称
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        AsyncResult
    """
    task = celery_app.tasks.get(task_name)
    if task:
        return task.delay(*args, **kwargs)
    raise ValueError(f"Task {task_name} not found")


async def execute_task_await(task_name: str, *args, **kwargs):
    """
    等待执行任务
    
    Args:
        task_name: 任务名称
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        任务结果
    """
    result = execute_task_async(task_name, *args, **kwargs)
    return result.get()


# 自动发现任务
celery_app.autodiscover_tasks(["src.tasks"])
