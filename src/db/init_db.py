"""
数据库初始化脚本

初始化数据库并创建默认数据
"""

import asyncio
import logging

from .crud import create_task, init_default_agents
from .database import get_database_manager, init_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_sample_data():
    """初始化示例数据"""
    db_manager = get_database_manager()

    async with db_manager.async_session_maker() as session:
        # 初始化默认 Agent
        await init_default_agents(session)

        # 创建示例任务
        sample_tasks = [
            {
                "title": "创建用户管理 API",
                "description": "实现用户注册、登录、权限管理等功能",
                "priority": "high",
                "status": "in_progress",
                "assignee": "张三",
                "agent": "Coder",
            },
            {
                "title": "数据库设计",
                "description": "设计用户表和权限表结构",
                "priority": "normal",
                "status": "completed",
                "assignee": "李四",
                "agent": "Architect",
            },
            {
                "title": "编写测试用例",
                "description": "为 API 接口编写单元测试",
                "priority": "normal",
                "status": "pending",
                "assignee": "王五",
                "agent": "Tester",
            },
            {
                "title": "性能优化",
                "description": "优化系统响应速度",
                "priority": "critical",
                "status": "in_progress",
                "assignee": "张三",
                "agent": "SeniorArchitect",
            },
            {
                "title": "文档更新",
                "description": "更新 API 文档和使用说明",
                "priority": "low",
                "status": "pending",
                "assignee": "李四",
                "agent": "DocWriter",
            },
        ]

        for task_data in sample_tasks:
            await create_task(session, **task_data)

        logger.info("示例数据初始化完成")


async def main():
    """主函数"""
    logger.info("开始初始化数据库...")

    # 初始化数据库（创建表）
    await init_database()
    logger.info("数据库表创建完成")

    # 初始化示例数据
    await init_sample_data()

    logger.info("数据库初始化完成！")


if __name__ == "__main__":
    asyncio.run(main())
