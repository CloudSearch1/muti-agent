"""
IntelliTeam 项目启动器

职责：一键启动所有服务
"""

import asyncio
import sys
import structlog
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config.settings import get_settings
from src.api.main import create_app
from src.memory.short_term import ShortTermMemory
from src.memory.session import SessionManager
from src.core.blackboard_enhanced import get_blackboard_manager


logger = structlog.get_logger(__name__)


async def startup_services():
    """启动所有服务"""
    logger.info("Starting IntelliTeam services...")
    
    # 1. 初始化配置
    settings = get_settings()
    logger.info("Configuration loaded", app_name=settings.app_name)
    
    # 2. 初始化 Redis 记忆
    try:
        memory = ShortTermMemory(redis_url=settings.redis_url)
        await memory.connect()
        logger.info("Redis memory connected")
    except Exception as e:
        logger.warning("Redis not available, using in-memory storage", error=str(e))
        memory = None
    
    # 3. 初始化会话管理
    if memory:
        session_manager = SessionManager(memory=memory)
        logger.info("Session manager initialized")
    else:
        session_manager = None
    
    # 4. 初始化黑板系统
    blackboard_manager = get_blackboard_manager()
    default_blackboard = blackboard_manager.get_default()
    logger.info("Blackboard system initialized")
    
    # 5. 启动 API 服务
    logger.info("Starting API server...", host=settings.api_host, port=settings.api_port)
    
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development(),
        log_level=settings.logging.level.lower(),
    )


def main():
    """主函数"""
    print("=" * 60)
    print("  IntelliTeam - 智能研发协作平台")
    print("=" * 60)
    print()
    print("启动服务...")
    print()
    
    try:
        asyncio.run(startup_services())
    except KeyboardInterrupt:
        print()
        print("服务已停止")
    except Exception as e:
        print(f"启动失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
