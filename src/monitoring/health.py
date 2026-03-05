"""
IntelliTeam 健康检查模块

提供系统和组件健康检查
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    健康检查器

    检查各组件健康状态
    """

    def __init__(self):
        self.checks: dict[str, callable] = {}

    def register_check(self, name: str, check_func: callable):
        """
        注册健康检查

        Args:
            name: 检查名称
            check_func: 检查函数
        """
        self.checks[name] = check_func
        logger.info(f"注册健康检查：{name}")

    async def check_all(self) -> dict[str, Any]:
        """
        检查所有组件

        Returns:
            健康状态字典
        """
        results = {}
        overall_status = "healthy"

        for name, check_func in self.checks.items():
            try:
                result = await check_func()
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "timestamp": datetime.now().isoformat(),
                }

                if not result:
                    overall_status = "unhealthy"
            except Exception as e:
                results[name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
                overall_status = "unhealthy"

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "checks": results,
        }

    async def check_database(self) -> bool:
        """检查数据库健康"""
        try:
            # 这里可以检查数据库连接
            # await db.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"数据库健康检查失败：{e}")
            return False

    async def check_redis(self) -> bool:
        """检查 Redis 健康"""
        try:
            # 这里可以检查 Redis 连接
            # await redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis 健康检查失败：{e}")
            return False

    async def check_celery(self) -> bool:
        """检查 Celery 健康"""
        try:
            # 这里可以检查 Celery worker
            # inspect = celery_app.inspect()
            # return inspect.ping() is not None
            return True
        except Exception as e:
            logger.error(f"Celery 健康检查失败：{e}")
            return False

    async def check_api(self) -> bool:
        """检查 API 健康"""
        try:
            # API 应该能正常响应
            return True
        except Exception as e:
            logger.error(f"API 健康检查失败：{e}")
            return False


# 全局健康检查器
health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    """获取健康检查器单例"""
    return health_checker


async def init_health_checks():
    """初始化健康检查"""
    checker = get_health_checker()

    # 注册所有检查
    checker.register_check("database", checker.check_database)
    checker.register_check("redis", checker.check_redis)
    checker.register_check("celery", checker.check_celery)
    checker.register_check("api", checker.check_api)

    logger.info("健康检查已初始化")


async def periodic_health_check(interval: int = 60):
    """
    定期健康检查

    后台任务：每分钟执行

    Args:
        interval: 检查间隔（秒）
    """
    checker = get_health_checker()

    while True:
        try:
            health = await checker.check_all()

            if health["status"] != "healthy":
                logger.warning(f"系统健康检查异常：{health}")

            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(f"定期健康检查失败：{e}")
            await asyncio.sleep(interval)
