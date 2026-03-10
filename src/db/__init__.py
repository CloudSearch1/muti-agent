"""
数据库模块

提供完整的数据库管理功能：
- 连接池优化
- 事务管理
- 性能监控
- 健康检查
"""

from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from .crud import (
    complete_workflow,
    create_agent,
    create_task,
    create_workflow,
    delete_task,
    get_agent_by_name,
    get_all_agents,
    get_all_tasks,
    get_all_workflows,
    get_task_by_id,
    get_task_stats,
    get_tasks_by_ids,
    get_tasks_with_stats,
    increment_agent_tasks,
    init_default_agents,
    update_agent_status,
    update_task,
)
from .database import (
    AgentModel,
    Base,
    DatabaseManager,
    QueryPerformanceMonitor,
    TaskModel,
    TransactionManager,
    UserModel,
    WorkflowModel,
    database_health_check,
    get_database_manager,
    get_db_session,
    get_query_monitor,
    get_transaction,
    init_database,
)

logger = structlog.get_logger(__name__)

__all__ = [
    # 数据库管理
    "DatabaseManager",
    "TransactionManager",
    "QueryPerformanceMonitor",
    "get_database_manager",
    "get_db_session",
    "get_transaction",
    "get_query_monitor",
    "init_database",
    "database_health_check",
    # 模型
    "Base",
    "TaskModel",
    "AgentModel",
    "WorkflowModel",
    "UserModel",
    # CRUD 操作
    "get_all_tasks",
    "get_task_by_id",
    "get_tasks_by_ids",
    "get_tasks_with_stats",
    "create_task",
    "update_task",
    "delete_task",
    "get_task_stats",
    "create_agent",
    "get_all_agents",
    "get_agent_by_name",
    "update_agent_status",
    "increment_agent_tasks",
    "init_default_agents",
    "create_workflow",
    "complete_workflow",
    "get_all_workflows",
]


# 向后兼容的 get_db 函数
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（用于依赖注入）"""
    db_manager = get_database_manager()
    async for session in db_manager.get_session():
        yield session
