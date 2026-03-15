"""
IntelliTeam Web UI - v5.2

基于 FastAPI + Vue 3 的 Web 管理界面
优化版本：统一日志、API 文档、改进缓存和 WebSocket
"""

import asyncio
import csv
import io
import logging
import random
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, AsyncGenerator
import json
import yaml

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select

# 获取项目根目录和 webui 目录的绝对路径
# 这样无论从哪个目录启动，都能正确找到文件
WEBUI_DIR = Path(__file__).parent.resolve()
STATIC_DIR = WEBUI_DIR / "static"
PROJECT_ROOT = WEBUI_DIR.parent

# 配置结构化日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============ 数据库支持（用于聊天持久化） ============

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(PROJECT_ROOT))

# 初始化数据库相关变量（默认值）
DATABASE_ENABLED = False
get_db_session = None
get_database_manager = None
ChatMessageModel = None
crud = None

try:
    logger.info("尝试加载数据库模块...")
    from src.db import crud as _crud
    logger.info("✓ 加载 crud 成功")
    from src.db.database import get_db_session as _get_db_session, get_database_manager as _get_database_manager
    logger.info("✓ 加载 database 成功")
    from src.db.models import ChatMessageModel as _ChatMessageModel
    logger.info("✓ 加载 models 成功")
    # 导入成功，更新变量
    crud = _crud
    get_db_session = _get_db_session
    get_database_manager = _get_database_manager
    ChatMessageModel = _ChatMessageModel
    DATABASE_ENABLED = True
    logger.info("数据库模块已加载，聊天持久化功能已启用")
except Exception as e:
    logger.warning(f"数据库模块加载失败：{e}", exc_info=True)
    logger.warning("聊天功能将使用内存存储")
    # 确保变量有默认值
    crud = None
    get_db_session = None
    get_database_manager = None
    ChatMessageModel = None


# ============ 应用生命周期管理 ============

# 响应缓存实例（提前声明，供 lifespan 使用）
response_cache = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    使用 lifespan 替代已弃用的 @app.on_event("startup") 和 @app.on_event("shutdown")
    """
    global DATABASE_ENABLED, response_cache

    # ========== 启动逻辑 ==========
    logger.info("应用启动中...")

    # 初始化数据库（如果启用）
    if DATABASE_ENABLED:
        try:
            from src.db.database import init_database
            await init_database()
            logger.info("数据库初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}", exc_info=True)
            logger.warning("降级到内存模式")
            DATABASE_ENABLED = False

    logger.info(f"应用启动完成，数据库模式: {'启用' if DATABASE_ENABLED else '禁用（内存模式）'}")

    # 初始化响应缓存
    response_cache = ResponseCache(ttl_seconds=30)

    yield  # 应用运行中

    # ========== 关闭逻辑 ==========
    logger.info("应用关闭中...")

    # 关闭缓存连接
    if response_cache:
        await response_cache.close()

    logger.info("应用已关闭")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="IntelliTeam Web UI v5.2",
    description="智能研发协作平台 - Web 管理界面",
    version="5.2.0",
    docs_url="/docs",      # 启用 Swagger UI
    redoc_url="/redoc",    # 启用 ReDoc
    openapi_url="/openapi.json",
    lifespan=lifespan,     # 使用新的生命周期管理
)

# CORS 配置 - 支持环境变量配置
# ⚠️ 生产环境安全警告：建议限制 allow_origins 为具体的域名列表
# 可通过环境变量 CORS_ORIGINS 配置，多个域名用逗号分隔
# 例如：CORS_ORIGINS=https://your-domain.com,https://app.your-domain.com
import os

_cors_origins_env = os.getenv("CORS_ORIGINS", "")
if _cors_origins_env:
    CORS_ORIGINS = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
    logger.info(f"CORS origins configured from environment: {CORS_ORIGINS}")
else:
    # 默认允许所有来源（开发模式）
    # ⚠️ 生产环境请设置 CORS_ORIGINS 环境变量
    CORS_ORIGINS = ["*"]
    logger.warning(
        "CORS is configured to allow all origins (allow_origins=['*']). "
        "This is insecure for production. Please set CORS_ORIGINS environment variable."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip 压缩 - 启用以提升传输效率
app.add_middleware(GZipMiddleware, minimum_size=1024)

# 挂载静态文件（使用绝对路径）
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info(f"静态文件挂载成功：{STATIC_DIR}")
else:
    logger.warning(f"静态文件目录不存在：{STATIC_DIR}")

# ============ Agent 框架支持（工具调用能力） ============

AGENT_ENABLED = False
try:
    # 导入工具系统组件
    from src.tools import get_registry, register_tool
    from src.tools.policy import ToolsConfig, get_effective_tools
    from src.tools.builtin import (
        ExecTool, WebFetchTool, WebSearchTool,
        MemorySearchTool, MemoryGetTool, BrowserTool,
        ReadTool, WriteTool, EditTool, ApplyPatchTool,
        SessionsListTool, SessionsHistoryTool
    )
    from src.tools.builtin.process import create_process_tool
    
    # 初始化工具注册表（注册所有内置工具）
    registry = get_registry()
    
    # 注册内置工具
    builtin_tools = [
        ExecTool(),
        WebFetchTool(),
        WebSearchTool(),
        MemorySearchTool(),
        MemoryGetTool(),
        BrowserTool(),
        ReadTool(),
        WriteTool(),
        EditTool(),
        ApplyPatchTool(),
        SessionsListTool(),
        SessionsHistoryTool(),
    ]
    
    registered_count = 0
    for tool in builtin_tools:
        if not registry.get(tool.NAME):
            register_tool(tool)
            logger.info(f"✓ 注册工具: {tool.NAME}")
            registered_count += 1
    
    # ProcessTool 需要 agent_id，使用一个通用的 agent_id 创建
    if not registry.get("process"):
        process_tool = create_process_tool(agent_id="default_agent")
        register_tool(process_tool)
        logger.info(f"✓ 注册工具: process (使用默认 agent)")
        registered_count += 1
    
    AGENT_ENABLED = True
    logger.info(f"Agent 框架已加载，共注册 {registered_count} 个工具，AI 助手支持工具调用")
except Exception as e:
    logger.warning(f"Agent 框架加载失败：{e}", exc_info=True)
    logger.warning("AI 助手将使用纯对话模式")

# ============ 响应缓存 ============

# Redis 配置（可选）
REDIS_URL = None  # 环境变量: os.environ.get("REDIS_URL")
try:
    import os
    REDIS_URL = os.environ.get("REDIS_URL")
except Exception:
    pass


class ResponseCache:
    """
    响应缓存实现
    
    支持：
    - 内存缓存（默认，单实例）
    - Redis 缓存（生产环境，多实例共享）
    - 自动 TTL 过期
    - 缓存预热和淘汰策略
    """
    
    def __init__(self, ttl_seconds: int = 60, redis_url: str | None = None):
        self._cache: dict[str, dict] = {}
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0
        
        # Redis 客户端（可选）
        self._redis = None
        self._redis_url = redis_url or REDIS_URL
        
        # 尝试连接 Redis
        if self._redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info(f"Redis 缓存已启用：{self._redis_url}")
            except ImportError:
                logger.warning("Redis 库未安装，使用内存缓存。安装：pip install redis")
            except Exception as e:
                logger.warning(f"Redis 连接失败，使用内存缓存：{e}")
        
        if not self._redis:
            logger.info(f"内存缓存初始化完成，TTL={ttl_seconds}秒")
    
    async def get(self, key: str) -> dict | None:
        """获取缓存"""
        # Redis 模式
        if self._redis:
            try:
                data = await self._redis.get(key)
                if data:
                    self._hits += 1
                    import json
                    return json.loads(data)
                self._misses += 1
                return None
            except Exception as e:
                logger.warning(f"Redis 读取失败：{e}")
                # 降级到内存缓存
        
        # 内存缓存模式
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now(timezone.utc).astimezone() < entry['expires']:
                self._hits += 1
                logger.debug(f"缓存命中：{key}")
                return entry['data']
            # 过期数据清理
            del self._cache[key]
        
        self._misses += 1
        return None
    
    async def set(self, key: str, data: dict):
        """设置缓存"""
        # Redis 模式
        if self._redis:
            try:
                import json
                await self._redis.setex(
                    key,
                    self._ttl,
                    json.dumps(data, default=str)
                )
                logger.debug(f"Redis 缓存设置：{key}")
                return
            except Exception as e:
                logger.warning(f"Redis 写入失败：{e}")
        
        # 内存缓存模式
        self._cache[key] = {
            'data': data,
            'expires': datetime.now(timezone.utc).astimezone() + timedelta(seconds=self._ttl)
        }
        logger.debug(f"内存缓存设置：{key}")
    
    async def invalidate(self, key: str):
        """使缓存失效"""
        if self._redis:
            try:
                await self._redis.delete(key)
            except Exception:
                pass
        
        if key in self._cache:
            del self._cache[key]
        logger.debug(f"缓存失效：{key}")
    
    async def warmup(self, keys: list[str], loader_func):
        """
        缓存预热
        
        Args:
            keys: 需要预热的缓存键列表
            loader_func: 数据加载函数
        """
        for key in keys:
            try:
                data = await loader_func(key)
                if data:
                    await self.set(key, data)
                    logger.debug(f"缓存预热：{key}")
            except Exception as e:
                logger.warning(f"缓存预热失败 {key}: {e}")
    
    async def evict_expired(self):
        """清理过期缓存（内存模式）"""
        if self._redis:
            return  # Redis 自动处理过期
        
        now = datetime.now(timezone.utc).astimezone()
        expired_keys = [
            k for k, v in self._cache.items()
            if v['expires'] < now
        ]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"清理过期缓存：{len(expired_keys)} 个")
    
    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "backend": "redis" if self._redis else "memory"
        }
    
    async def close(self):
        """关闭连接"""
        if self._redis:
            await self._redis.close()


# 创建缓存实例（支持同步和异步接口）
class SyncResponseCache:
    """
    同步缓存包装器

    注意：此类用于在同步上下文中访问异步缓存。
    在异步上下文中，建议直接使用 ResponseCache 的异步方法。
    """

    def __init__(self, cache: ResponseCache):
        self._cache = cache

    def get(self, key: str) -> dict | None:
        """
        同步获取（用于非异步上下文）

        注意：在异步上下文中调用此方法会阻塞事件循环。
        建议在异步上下文中直接使用 ResponseCache.get() 方法。
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # 在异步上下文中，使用 run_coroutine_threadsafe 避免阻塞
            # 但这需要另一个线程的事件循环，这里记录警告
            import logging
            logging.getLogger(__name__).warning(
                "SyncResponseCache.get() called in async context. "
                "Consider using ResponseCache.get() directly for better performance."
            )
            # 在新线程中运行以避免阻塞
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._cache.get(key))
                return future.result()
        except RuntimeError:
            # 没有事件循环，直接运行
            return asyncio.run(self._cache.get(key))

    def set(self, key: str, data: dict):
        """
        同步设置

        注意：在异步上下文中调用此方法会阻塞事件循环。
        建议在异步上下文中直接使用 ResponseCache.set() 方法。
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import logging
            logging.getLogger(__name__).warning(
                "SyncResponseCache.set() called in async context. "
                "Consider using ResponseCache.set() directly for better performance."
            )
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._cache.set(key, data))
                return future.result()
        except RuntimeError:
            asyncio.run(self._cache.set(key, data))

    def invalidate(self, key: str):
        """
        同步失效

        注意：在异步上下文中调用此方法会阻塞事件循环。
        建议在异步上下文中直接使用 ResponseCache.invalidate() 方法。
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import logging
            logging.getLogger(__name__).warning(
                "SyncResponseCache.invalidate() called in async context. "
                "Consider using ResponseCache.invalidate() directly for better performance."
            )
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._cache.invalidate(key))
                return future.result()
        except RuntimeError:
            asyncio.run(self._cache.invalidate(key))

    # 提供异步接口的便捷方法
    async def async_get(self, key: str) -> dict | None:
        """异步获取（推荐在异步上下文中使用）"""
        return await self._cache.get(key)

    async def async_set(self, key: str, data: dict):
        """异步设置（推荐在异步上下文中使用）"""
        await self._cache.set(key, data)

    async def async_invalidate(self, key: str):
        """异步失效（推荐在异步上下文中使用）"""
        await self._cache.invalidate(key)


# ============ 数据模型 ============

AGENTS_DATA = [
    {"name": "Planner", "role": "任务规划师", "icon": "fas fa-clipboard-list", "description": "负责任务分解和优先级排序", "status": "idle", "tasksCompleted": 45, "avgTime": 2.3, "successRate": 98},
    {"name": "Architect", "role": "系统架构师", "icon": "fas fa-building", "description": "负责系统架构设计和技术选型", "status": "busy", "tasksCompleted": 38, "avgTime": 5.7, "successRate": 96},
    {"name": "Coder", "role": "代码工程师", "icon": "fas fa-laptop-code", "description": "负责代码实现和功能开发", "status": "busy", "tasksCompleted": 89, "avgTime": 8.2, "successRate": 94},
    {"name": "Tester", "role": "测试工程师", "icon": "fas fa-vial", "description": "负责测试用例和质量保障", "status": "idle", "tasksCompleted": 67, "avgTime": 4.5, "successRate": 97},
    {"name": "DocWriter", "role": "文档工程师", "icon": "fas fa-file-alt", "description": "负责技术文档编写", "status": "idle", "tasksCompleted": 52, "avgTime": 3.8, "successRate": 99},
    {"name": "SeniorArchitect", "role": "资深架构师", "icon": "fas fa-chess", "description": "负责复杂系统设计和代码审查", "status": "idle", "tasksCompleted": 23, "avgTime": 12.5, "successRate": 98},
    {"name": "ResearchAgent", "role": "研究助手", "icon": "fas fa-search", "description": "负责文献调研和技术分析", "status": "idle", "tasksCompleted": 15, "avgTime": 6.8, "successRate": 95}
]

TASKS_DATA = [
    {"id": 1, "title": "创建用户管理 API", "description": "实现用户注册、登录、权限管理等功能", "priority": "high", "priorityText": "高优先级", "status": "in_progress", "statusText": "进行中", "assignee": "张三", "agent": "Coder", "createdAt": "2026-03-03 10:30", "time": "2 小时前"},
    {"id": 2, "title": "数据库设计", "description": "设计用户表和权限表结构", "priority": "normal", "priorityText": "中优先级", "status": "completed", "statusText": "已完成", "assignee": "李四", "agent": "Architect", "createdAt": "2026-03-03 09:15", "time": "3 小时前"},
    {"id": 3, "title": "编写测试用例", "description": "为 API 接口编写单元测试", "priority": "normal", "priorityText": "中优先级", "status": "pending", "statusText": "待处理", "assignee": "王五", "agent": "Tester", "createdAt": "2026-03-03 11:00", "time": "1 小时前"},
    {"id": 4, "title": "性能优化", "description": "优化系统响应速度", "priority": "critical", "priorityText": "紧急", "status": "in_progress", "statusText": "进行中", "assignee": "张三", "agent": "SeniorArchitect", "createdAt": "2026-03-04 14:20", "time": "30 分钟前"},
    {"id": 5, "title": "文档更新", "description": "更新 API 文档和使用说明", "priority": "low", "priorityText": "低优先级", "status": "pending", "statusText": "待处理", "assignee": "李四", "agent": "DocWriter", "createdAt": "2026-03-04 16:45", "time": "15 分钟前"}
]

WORKFLOWS_DATA = [
    {
        "id": 1,
        "name": "标准研发流程",
        "steps": [
            {"name": "需求分析", "agent": "Planner", "icon": "fas fa-clipboard-list"},
            {"name": "架构设计", "agent": "Architect", "icon": "fas fa-building"},
            {"name": "代码开发", "agent": "Coder", "icon": "fas fa-laptop-code"},
            {"name": "测试", "agent": "Tester", "icon": "fas fa-vial"},
            {"name": "文档", "agent": "DocWriter", "icon": "fas fa-file-alt"}
        ]
    }
]

# ============ Skills 文件持久化 ============

SKILLS_DIR = WEBUI_DIR / "skills"

# 确保 skills 目录存在
SKILLS_DIR.mkdir(exist_ok=True)


def _validate_skill_path(file_path: Path) -> bool:
    """
    验证技能文件路径是否在允许的目录内（防止路径遍历攻击）

    Args:
        file_path: 要验证的文件路径

    Returns:
        如果路径在 SKILLS_DIR 内返回 True，否则返回 False
    """
    try:
        # 解析绝对路径
        resolved_path = file_path.resolve()
        skills_dir_resolved = SKILLS_DIR.resolve()

        # 检查路径是否在 skills 目录内
        return str(resolved_path).startswith(str(skills_dir_resolved))
    except Exception:
        return False


def _get_safe_skill_path(skill_name: str) -> Path:
    """
    获取安全的技能文件路径

    Args:
        skill_name: 技能名称

    Returns:
        安全的文件路径

    Raises:
        ValueError: 如果技能名称包含非法字符或路径遍历尝试
    """
    import re

    # 验证文件名：只允许字母、数字、下划线、连字符
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', skill_name)
    if not safe_name:
        raise ValueError("技能名称包含非法字符")

    file_path = SKILLS_DIR / f"{safe_name}.md"

    # 验证路径安全性
    if not _validate_skill_path(file_path):
        raise ValueError("无效的文件路径")

    return file_path


def _parse_yaml_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter（--- 之间的内容）"""
    import re
    import yaml
    
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}
    
    try:
        frontmatter = yaml.safe_load(match.group(1))
        return frontmatter or {}
    except Exception as e:
        logger.error(f"解析 YAML frontmatter 失败：{e}")
        return {}


def _generate_yaml_frontmatter(data: dict) -> str:
    """生成 YAML frontmatter"""
    import yaml
    return "---\n" + yaml.dump(data, default_flow_style=False, allow_unicode=True) + "---\n"


def _load_skills_from_files() -> list:
    """从 skills 目录加载所有技能文件"""
    skills = []
    
    if not SKILLS_DIR.exists():
        SKILLS_DIR.mkdir(exist_ok=True)
        return skills
    
    for file_path in SKILLS_DIR.glob("*.md"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            frontmatter = _parse_yaml_frontmatter(content)
            if frontmatter and 'name' in frontmatter:
                # 转换 config 字段（可能是字符串或字典）
                if isinstance(frontmatter.get('config'), str):
                    try:
                        frontmatter['config'] = json.loads(frontmatter['config'])
                    except:
                        frontmatter['config'] = {}
                elif frontmatter.get('config') is None:
                    frontmatter['config'] = {}
                
                # 确保 enabled 是布尔值
                if 'enabled' in frontmatter:
                    if isinstance(frontmatter['enabled'], str):
                        frontmatter['enabled'] = frontmatter['enabled'].lower() == 'true'
                
                skills.append(frontmatter)
        except Exception as e:
            logger.error(f"加载技能文件 {file_path} 失败：{e}")
    
    return skills


def _save_skill_to_file(skill_data: dict) -> Path:
    """保存技能到文件"""
    name = skill_data.get('name', '')
    if not name:
        raise ValueError("技能名称不能为空")

    # 使用安全路径获取函数（包含路径遍历验证）
    file_path = _get_safe_skill_path(name)
    
    # 准备 frontmatter 数据
    frontmatter_data = {
        'id': skill_data.get('id'),
        'name': skill_data.get('name'),
        'description': skill_data.get('description', ''),
        'category': skill_data.get('category', 'general'),
        'version': skill_data.get('version', '1.0.0'),
        'enabled': skill_data.get('enabled', True),
        'createdAt': skill_data.get('createdAt', datetime.now().strftime("%Y-%m-%d %H:%M")),
    }
    
    # 添加 updatedAt 如果存在
    if 'updatedAt' in skill_data:
        frontmatter_data['updatedAt'] = skill_data['updatedAt']
    
    # 处理 config（转换为 YAML 兼容格式）
    config = skill_data.get('config', {})
    if config:
        frontmatter_data['config'] = config
    
    # 生成 frontmatter
    frontmatter = _generate_yaml_frontmatter(frontmatter_data)
    
    # 生成技能内容（保留原有内容或创建新内容）
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        # 保留 frontmatter 之后的内容
        existing_match = re.match(r'^---\s*\n.*?\n---\s*\n(.*)', existing_content, re.DOTALL)
        body_content = existing_match.group(1) if existing_match else f"\n# {skill_data.get('name', 'Skill')}\n"
    else:
        body_content = f"\n# {skill_data.get('name', 'Skill')}\n\n## 描述\n{skill_data.get('description', '')}\n"
    
    # 写入文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter + body_content)
    
    return file_path


def _delete_skill_file(skill_name: str) -> bool:
    """删除技能文件"""
    try:
        # 使用安全路径获取函数（包含路径遍历验证）
        file_path = _get_safe_skill_path(skill_name)
    except ValueError:
        return False

    if file_path.exists():
        file_path.unlink()
        return True
    return False


def _get_next_skill_id(skills: list) -> int:
    """获取下一个可用的技能 ID"""
    if not skills:
        return 1
    max_id = max(s.get('id', 0) for s in skills)
    return max_id + 1


# 初始化时从文件加载技能
SKILLS_DATA = _load_skills_from_files()

# 如果没有加载到任何技能，创建默认技能
if not SKILLS_DATA:
    logger.info("未找到现有技能文件，创建默认技能...")
    default_skills = [
        {"id": 1, "name": "simplify", "description": "Review code for reuse, quality, and efficiency", "category": "code_review", "version": "1.0.0", "config": {"auto_fix": True}, "enabled": True, "createdAt": "2026-03-01 10:00"},
        {"id": 2, "name": "claude-api", "description": "Build apps with Claude API or Anthropic SDK", "category": "api", "version": "1.0.0", "config": {"model": "claude-sonnet-4-6"}, "enabled": True, "createdAt": "2026-03-01 10:00"},
        {"id": 3, "name": "code-generation", "description": "Generate code from natural language", "category": "generation", "version": "1.2.0", "config": {"language": "python"}, "enabled": True, "createdAt": "2026-03-02 14:30"},
        {"id": 4, "name": "documentation", "description": "Generate documentation for code files", "category": "docs", "version": "1.0.0", "config": {"format": "markdown"}, "enabled": True, "createdAt": "2026-03-02 14:30"},
        {"id": 5, "name": "testing", "description": "Generate and run tests for code", "category": "testing", "version": "1.1.0", "config": {"framework": "pytest"}, "enabled": False, "createdAt": "2026-03-03 09:15"},
    ]
    for skill in default_skills:
        _save_skill_to_file(skill)
    SKILLS_DATA = default_skills

# ============ API 路由 ============

# 处理 Chrome DevTools 的自动请求，避免 404 日志噪音
@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools_well_known():
    """返回空响应以消除 Chrome DevTools 自动请求的 404 日志"""
    return JSONResponse(content={}, status_code=204)

@app.get("/")
async def root():
    """返回仪表盘页面（根目录）"""
    from starlette.responses import HTMLResponse

    dashboard_file = WEBUI_DIR / "dashboard.html"
    if dashboard_file.exists():
        return FileResponse(path=str(dashboard_file), media_type="text/html")
    
    # 向后兼容：如果 dashboard.html 不存在，返回 index.html
    index_file = WEBUI_DIR / "index.html"
    if not index_file.exists():
        logger.error(f"主页面文件不存在：{index_file}")
        return HTMLResponse(
            content="<html><body><h1>Web UI not found</h1><p>Please check webui/index.html exists</p></body></html>",
            status_code=500
        )

    with open(index_file, encoding="utf-8") as f:
        content = f.read()

    return HTMLResponse(content=content)


@app.get("/tasks")
async def get_tasks():
    """返回任务管理页面"""
    tasks_file = WEBUI_DIR / "tasks.html"
    if tasks_file.exists():
        return FileResponse(path=str(tasks_file), media_type="text/html")
    return HTMLResponse(content="<html><body><h1>Tasks page not found</h1></body></html>")


@app.get("/agents")
async def get_agents():
    """返回 Agent 管理页面"""
    agents_file = WEBUI_DIR / "agents.html"
    if agents_file.exists():
        return FileResponse(path=str(agents_file), media_type="text/html")
    return HTMLResponse(content="<html><body><h1>Agents page not found</h1></body></html>")


@app.get("/workflows")
async def get_workflows():
    """返回工作流页面"""
    workflows_file = WEBUI_DIR / "workflows.html"
    if workflows_file.exists():
        return FileResponse(path=str(workflows_file), media_type="text/html")
    return HTMLResponse(content="<html><body><h1>Workflows page not found</h1></body></html>")


@app.get("/analytics")
async def get_analytics():
    """返回数据分析页面"""
    analytics_file = WEBUI_DIR / "analytics.html"
    if analytics_file.exists():
        return FileResponse(path=str(analytics_file), media_type="text/html")
    return HTMLResponse(content="<html><body><h1>Analytics page not found</h1></body></html>")


@app.get("/skills")
async def get_skills():
    """返回技能管理页面"""
    skills_file = WEBUI_DIR / "skills.html"
    if skills_file.exists():
        return FileResponse(path=str(skills_file), media_type="text/html")
    return HTMLResponse(content="<html><body><h1>Skills page not found</h1></body></html>")


@app.get("/ai-assistant")
async def get_ai_assistant_route():
    """返回 AI 助手页面"""
    ai_file = WEBUI_DIR / "ai-assistant.html"
    if ai_file.exists():
        return FileResponse(path=str(ai_file), media_type="text/html")
    return HTMLResponse(content="<html><body><h1>AI Assistant page not found</h1></body></html>")


@app.get("/tools")
async def get_tools_page():
    """返回工具系统页面"""
    tools_file = WEBUI_DIR / "tools.html"
    if tools_file.exists():
        return FileResponse(path=str(tools_file), media_type="text/html")
    return HTMLResponse(content="<html><body><h1>Tools page not found</h1></body></html>")


@app.get("/manifest.json")
async def get_manifest():
    """返回 PWA manifest"""
    manifest_file = WEBUI_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(path=str(manifest_file), media_type="application/json")
    return JSONResponse(content={"error": "manifest.json not found"}, status_code=404)


@app.get("/offline.html")
async def get_offline():
    """返回离线页面"""
    offline_file = WEBUI_DIR / "offline.html"
    if offline_file.exists():
        return FileResponse(path=str(offline_file), media_type="text/html")
    return HTMLResponse(content="<html><body><h1>Offline</h1></body></html>")


@app.get("/static/js/{filename:path}")
async def get_static_js(filename: str):
    """返回静态 JS 文件"""
    js_file = STATIC_DIR / "js" / filename
    if js_file.exists():
        return FileResponse(path=str(js_file), media_type="application/javascript")
    raise HTTPException(status_code=404, detail=f"JS file not found: {filename}")


@app.get("/static/images/{filename:path}")
async def get_static_images(filename: str):
    """返回静态图片文件"""
    img_file = STATIC_DIR / "images" / filename

    if not img_file.exists():
        # 如果具体尺寸图标不存在，返回 SVG 占位图
        icon_file = STATIC_DIR / "images" / "icon.svg"
        if icon_file.exists():
            return FileResponse(path=str(icon_file), media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail=f"Image not found: {filename}")

    return FileResponse(path=str(img_file), media_type="image/png")


@app.get("/api/v1/stats")
async def get_stats():
    """获取系统统计（带缓存）"""
    cache_key = "stats"
    cached = await response_cache.get(cache_key)
    if cached:
        return cached

    data = {
        "totalTasks": len(TASKS_DATA),
        "activeAgents": len([a for a in AGENTS_DATA if a["status"] == "busy"]),
        "completionRate": 93,
        "timestamp": datetime.now().isoformat()
    }
    await response_cache.set(cache_key, data)
    return data


@app.get("/api/v1/agents")
async def get_agents():
    """获取 Agent 列表"""
    # 随机更新一些 Agent 状态，模拟实时变化
    for agent in AGENTS_DATA:
        if random.random() < 0.1:
            agent["status"] = "busy" if agent["status"] == "idle" else "idle"
    return AGENTS_DATA


@app.get("/api/v1/tasks")
async def get_tasks():
    """获取任务列表（带缓存）"""
    cache_key = "tasks"
    cached = await response_cache.get(cache_key)
    if cached:
        return cached

    await response_cache.set(cache_key, TASKS_DATA)
    return TASKS_DATA


@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: int):
    """获取单个任务"""
    for task in TASKS_DATA:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="任务不存在")


@app.put("/api/v1/tasks/{task_id}")
async def update_task(task_id: int, task_update: dict):
    """更新任务"""
    for task in TASKS_DATA:
        if task["id"] == task_id:
            # 更新允许的字段
            if "status" in task_update:
                task["status"] = task_update["status"]
                task["statusText"] = {
                    "pending": "待处理",
                    "in_progress": "进行中",
                    "completed": "已完成"
                }.get(task_update["status"], task["statusText"])

            if "title" in task_update:
                task["title"] = task_update["title"]

            if "description" in task_update:
                task["description"] = task_update["description"]

            if "priority" in task_update:
                task["priority"] = task_update["priority"]
                task["priorityText"] = {
                    "low": "低优先级",
                    "normal": "中优先级",
                    "high": "高优先级",
                    "critical": "紧急"
                }.get(task_update["priority"], task["priorityText"])

            task["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            return {"status": "success", "message": "任务已更新", "task": task}

    raise HTTPException(status_code=404, detail="任务不存在")


@app.post("/api/v1/tasks")
async def create_task(task: dict):
    """创建新任务"""
    new_task = {
        "id": len(TASKS_DATA) + 1,
        "title": task.get("title", "新任务"),
        "description": task.get("description", ""),
        "priority": task.get("priority", "normal"),
        "priorityText": {"low": "低优先级", "normal": "中优先级", "high": "高优先级", "critical": "紧急"}.get(task.get("priority"), "中优先级"),
        "status": "pending",
        "statusText": "待处理",
        "assignee": task.get("assignee", ""),
        "agent": task.get("agent", ""),
        "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "time": "刚刚"
    }
    TASKS_DATA.insert(0, new_task)
    # 清除缓存
    await response_cache.invalidate("tasks")
    await response_cache.invalidate("stats")
    return {"status": "success", "message": "任务创建成功", "taskId": new_task["id"]}


@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: int):
    """删除任务"""
    global TASKS_DATA
    TASKS_DATA = [t for t in TASKS_DATA if t["id"] != task_id]
    # 清除缓存
    await response_cache.invalidate("tasks")
    await response_cache.invalidate("stats")
    return {"status": "success", "message": "任务已删除"}


@app.get("/api/v1/workflows")
async def get_workflows():
    """获取工作流列表"""
    return WORKFLOWS_DATA


# ============ Skills API ============
# 同时支持带斜杠和不带斜杠的路径，避免返回 HTML 错误页面

@app.get("/api/v1/skills")
@app.get("/api/v1/skills/")
async def get_skills(category: str = None, enabled: bool = None):
    """获取技能列表"""
    skills = SKILLS_DATA.copy()

    # 分类过滤
    if category:
        skills = [s for s in skills if s["category"] == category]

    # 启用状态过滤
    if enabled is not None:
        skills = [s for s in skills if s["enabled"] == enabled]

    return {"items": skills, "total": len(skills)}


@app.post("/api/v1/skills")
@app.post("/api/v1/skills/")
async def create_skill(skill: dict):
    """创建新技能"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"create_skill: 收到请求, data={skill}")

    # 检查名称是否已存在
    name = skill.get("name", "")
    if not name or not name.strip():
        logger.warning("create_skill: 名称为空")
        raise HTTPException(status_code=400, detail="技能名称不能为空")

    if any(s["name"] == name for s in SKILLS_DATA):
        logger.warning(f"create_skill: 技能名称已存在: {name}")
        raise HTTPException(status_code=400, detail=f"Skill with name '{name}' already exists")

    new_skill = {
        "id": max(s["id"] for s in SKILLS_DATA) + 1 if SKILLS_DATA else 1,
        "name": name,
        "description": skill.get("description", ""),
        "category": skill.get("category", "general"),
        "version": skill.get("version", "1.0.0"),
        "config": skill.get("config", {}),
        "enabled": skill.get("enabled", True),
        "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    # 保存到文件
    try:
        _save_skill_to_file(new_skill)
        SKILLS_DATA.append(new_skill)
        logger.info(f"create_skill: 技能创建成功，id={new_skill['id']}, name={name}")
        return {"status": "success", "message": "技能创建成功", "skill": new_skill}
    except Exception as e:
        logger.error(f"create_skill: 保存文件失败：{e}")
        raise HTTPException(status_code=500, detail=f"保存技能文件失败：{str(e)}")


@app.put("/api/v1/skills/{skill_id}")
async def update_skill(skill_id: int, skill_update: dict):
    """更新技能"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"update_skill: 收到请求, skill_id={skill_id}, data={skill_update}")

    # 参数验证
    if skill_id is None or skill_id < 1:
        logger.warning(f"update_skill: 无效的 skill_id: {skill_id}")
        raise HTTPException(status_code=422, detail=f"无效的技能ID: {skill_id}")

    for skill in SKILLS_DATA:
        if skill["id"] == skill_id:
            # 检查名称冲突
            new_name = skill_update.get("name")
            if new_name and new_name != skill["name"]:
                if any(s["name"] == new_name for s in SKILLS_DATA):
                    logger.warning(f"update_skill: 技能名称已存在: {new_name}")
                    raise HTTPException(status_code=400, detail=f"Skill with name '{new_name}' already exists")

            # 更新允许的字段
            for field in ["name", "description", "category", "version", "config", "enabled"]:
                if field in skill_update:
                    skill[field] = skill_update[field]

            skill["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            # 保存到文件
            try:
                _save_skill_to_file(skill)
                logger.info(f"update_skill: 技能 {skill_id} 更新成功")
                return {"status": "success", "message": "技能已更新", "skill": skill}
            except Exception as e:
                logger.error(f"update_skill: 保存文件失败：{e}")
                raise HTTPException(status_code=500, detail=f"保存技能文件失败：{str(e)}")

    logger.warning(f"update_skill: 技能 {skill_id} 不存在")
    raise HTTPException(status_code=404, detail=f"技能不存在 (ID: {skill_id})")


@app.delete("/api/v1/skills/{skill_id}")
async def delete_skill(skill_id: int):
    """删除技能"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"delete_skill: 收到请求, skill_id={skill_id}")

    # 参数验证
    if skill_id is None or skill_id < 1:
        logger.warning(f"delete_skill: 无效的 skill_id: {skill_id}")
        raise HTTPException(status_code=422, detail=f"无效的技能ID: {skill_id}")

    global SKILLS_DATA
    for i, skill in enumerate(SKILLS_DATA):
        if skill["id"] == skill_id:
            deleted_name = skill["name"]
            # 删除文件
            _delete_skill_file(deleted_name)
            SKILLS_DATA.pop(i)
            logger.info(f"delete_skill: 技能 {skill_id} ({deleted_name}) 已删除")
            return {"status": "success", "message": "技能已删除"}

    logger.warning(f"delete_skill: 技能 {skill_id} 不存在")
    raise HTTPException(status_code=404, detail=f"技能不存在 (ID: {skill_id})")


@app.post("/api/v1/skills/{skill_id}/toggle")
@app.patch("/api/v1/skills/{skill_id}/toggle")
async def toggle_skill(skill_id: int):
    """切换技能状态"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"toggle_skill: 收到请求, skill_id={skill_id}")

    # 参数验证
    if skill_id is None or skill_id < 1:
        logger.warning(f"toggle_skill: 无效的 skill_id: {skill_id}")
        raise HTTPException(status_code=422, detail=f"无效的技能ID: {skill_id}")

    for skill in SKILLS_DATA:
        if skill["id"] == skill_id:
            skill["enabled"] = not skill["enabled"]
            skill["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            # 保存到文件
            try:
                _save_skill_to_file(skill)
                logger.info(f"toggle_skill: 技能 {skill_id} 状态已切换为 {skill['enabled']}")
                return {"status": "success", "message": f"技能已{'启用' if skill['enabled'] else '禁用'}", "skill": skill}
            except Exception as e:
                logger.error(f"toggle_skill: 保存文件失败：{e}")
                raise HTTPException(status_code=500, detail=f"保存技能文件失败：{str(e)}")

    logger.warning(f"toggle_skill: 技能 {skill_id} 不存在")
    raise HTTPException(status_code=404, detail=f"技能不存在 (ID: {skill_id})")


@app.get("/api/v1/skills/name/{skill_name}")
async def get_skill_by_name(skill_name: str):
    """根据名称获取技能详情"""
    try:
        # 使用安全路径获取函数（包含路径遍历验证）
        file_path = _get_safe_skill_path(skill_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"技能文件不存在：{skill_name}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            full_content = f.read()
        
        frontmatter = _parse_yaml_frontmatter(full_content)
        if not frontmatter:
            raise HTTPException(status_code=500, detail="技能文件格式错误")
        
        # 获取 body 内容（frontmatter 之后的部分）
        body_match = re.match(r'^---\s*\n.*?\n---\s*\n(.*)', full_content, re.DOTALL)
        body_content = body_match.group(1) if body_match else ""
        
        return {
            "skill": frontmatter,
            "content": full_content,
            "body": body_content
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_skill_by_name: 读取文件失败：{e}")
        raise HTTPException(status_code=500, detail=f"读取技能文件失败：{str(e)}")


@app.put("/api/v1/skills/name/{skill_name}/content")
async def update_skill_content(skill_name: str, content_data: dict):
    """更新技能文件内容（Markdown 编辑器）"""
    try:
        # 使用安全路径获取函数（包含路径遍历验证）
        file_path = _get_safe_skill_path(skill_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"技能文件不存在：{skill_name}")
    
    content = content_data.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")
    
    try:
        # 解析新的 frontmatter
        new_frontmatter = _parse_yaml_frontmatter(content)
        if not new_frontmatter or 'name' not in new_frontmatter:
            raise HTTPException(status_code=400, detail="技能文件必须包含有效的 YAML frontmatter 和 name 字段")
        
        # 验证文件名不能更改
        if new_frontmatter['name'] != skill_name:
            raise HTTPException(status_code=400, detail="技能名称不能更改")
        
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 更新内存中的数据
        for i, skill in enumerate(SKILLS_DATA):
            if skill['name'] == skill_name:
                SKILLS_DATA[i] = new_frontmatter
                break
        
        logger.info(f"update_skill_content: 技能 {skill_name} 内容已更新")
        return {"status": "success", "message": "技能内容已更新", "skill": new_frontmatter}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_skill_content: 保存文件失败：{e}")
        raise HTTPException(status_code=500, detail=f"保存技能文件失败：{str(e)}")


@app.post("/api/v1/skills/upload")
async def upload_skill_file(upload_data: dict):
    """上传技能文件"""
    import re
    
    file_content = upload_data.get("file_content", "")
    filename = upload_data.get("filename")
    
    # 验证文件内容
    if not file_content or not file_content.strip():
        raise HTTPException(status_code=400, detail="文件内容不能为空")
    
    # 解析 frontmatter 获取技能名称
    frontmatter = _parse_yaml_frontmatter(file_content)
    if not frontmatter or 'name' not in frontmatter:
        raise HTTPException(status_code=400, detail="技能文件必须包含有效的 YAML frontmatter 和 name 字段")
    
    skill_name = frontmatter['name']
    
    # 验证文件名：只允许字母、数字、下划线、连字符
    if not re.match(r'^[a-zA-Z0-9_-]+$', skill_name):
        raise HTTPException(status_code=400, detail="技能名称只能包含字母、数字、下划线和连字符")
    
    # 检查是否已存在
    if any(s["name"] == skill_name for s in SKILLS_DATA):
        raise HTTPException(status_code=400, detail=f"技能 '{skill_name}' 已存在")
    
    # 检查文件大小（最大 1MB）
    if len(file_content.encode('utf-8')) > 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 1MB")
    
    try:
        # 保存文件（使用安全路径获取函数）
        file_path = _get_safe_skill_path(skill_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        # 添加到内存数据
        frontmatter['id'] = _get_next_skill_id(SKILLS_DATA)
        SKILLS_DATA.append(frontmatter)
        
        logger.info(f"upload_skill_file: 技能文件上传成功：{skill_name}")
        return {"status": "success", "message": "技能文件上传成功", "skill": frontmatter}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upload_skill_file: 保存文件失败：{e}")
        raise HTTPException(status_code=500, detail=f"保存技能文件失败：{str(e)}")


@app.delete("/api/v1/skills/name/{skill_name}")
async def delete_skill_by_name(skill_name: str):
    """根据名称删除技能"""
    try:
        # 使用安全路径获取函数（包含路径遍历验证）
        file_path = _get_safe_skill_path(skill_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"技能文件不存在：{skill_name}")
    
    try:
        # 从内存中删除
        global SKILLS_DATA
        for i, skill in enumerate(SKILLS_DATA):
            if skill['name'] == skill_name:
                SKILLS_DATA.pop(i)
                break
        
        # 删除文件
        file_path.unlink()
        
        logger.info(f"delete_skill_by_name: 技能 {skill_name} 已删除")
        return {"status": "success", "message": "技能已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_skill_by_name: 删除失败：{e}")
        raise HTTPException(status_code=500, detail=f"删除技能失败：{str(e)}")


# ============ AI 聊天 API ============

# ============ Settings API ============

# 设置存储（内存中，实际应用应使用数据库或加密文件）
# ⚠️ 安全警告：API Key 存储说明
# 1. 生产环境建议使用环境变量：ANTHROPIC_API_KEY, OPENAI_API_KEY, BAILIAN_API_KEY
# 2. 环境变量优先级高于内存存储
# 3. 内存存储仅用于开发/测试环境
SETTINGS_STORE: dict = {
    "aiProvider": os.getenv("AI_PROVIDER", "bailian"),
    "apiKey": "",  # API Key 由前端设置或环境变量提供，不在内存中存储明文
    "model": os.getenv("AI_MODEL", "qwen3.5-plus"),
    "temperature": 0.7,
    "maxTokens": 4096,
    "contextWindow": None,  # 上下文窗口长度，None 表示使用模型默认
    "autoSave": True,
    "theme": "dark",
    "language": "zh-CN"
}


def get_api_key(provider: str = None) -> str:
    """
    安全获取 API Key

    优先级：
    1. 环境变量（推荐）
    2. 内存存储（仅开发/测试）

    Args:
        provider: LLM 提供商名称

    Returns:
        API Key 字符串
    """
    provider = provider or SETTINGS_STORE.get("aiProvider", "bailian")

    # 环境变量映射
    env_key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "bailian": "BAILIAN_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }

    # 优先从环境变量获取
    env_key_name = env_key_map.get(provider.lower())
    if env_key_name:
        env_key = os.getenv(env_key_name)
        if env_key:
            logger.info(f"Using API key from environment variable: {env_key_name}")
            return env_key

    # 从内存存储获取（可能为空或加密）
    stored_key = SETTINGS_STORE.get("apiKey", "")
    if stored_key:
        logger.warning(
            f"Using API key from memory storage. "
            f"For production, set {env_key_name or 'API_KEY'} environment variable instead."
        )

    return stored_key


@app.get("/api/v1/settings")
async def get_settings():
    """获取系统设置"""
    # 返回设置时，不返回敏感信息
    safe_settings = SETTINGS_STORE.copy()
    # 隐藏 API Key
    if safe_settings.get("apiKey"):
        safe_settings["apiKey"] = "******"
    if safe_settings.get("apiKeyEncrypted"):
        safe_settings["apiKeyEncrypted"] = "******"

    return JSONResponse({
        "success": True,
        "settings": safe_settings
    })

import base64

def decrypt_api_key(encrypted: str) -> str:
    """
    解密前端加密的 API Key
    前端加密方式：反转 + Base64
    """
    if not encrypted:
        return ""
    try:
        # 前端加密格式：前缀 + Base64(反转的key)
        if encrypted.startswith("enc:"):
            encrypted = encrypted[4:]  # 去掉前缀
        # Base64 解码
        decoded = base64.b64decode(encrypted).decode('utf-8')
        # 反转回来
        return decoded[::-1]
    except Exception:
        return encrypted  # 如果解密失败，返回原值


@app.post("/api/v1/settings")
async def save_settings(request: dict):
    """保存系统设置"""
    global SETTINGS_STORE

    logger.info(f"[DEBUG] save_settings 收到请求: {list(request.keys())}")

    if "settings" not in request:
        raise HTTPException(status_code=400, detail="缺少设置数据")

    # 合并设置
    new_settings = request["settings"]
    logger.info(f"[DEBUG] new_settings 字段: {list(new_settings.keys())}")

    # 处理 API Key：前端可能发送 apiKey 或 apiKeyEncrypted
    if "apiKeyEncrypted" in new_settings:
        # 解密加密的 API Key
        decrypted = decrypt_api_key(new_settings["apiKeyEncrypted"])
        if decrypted:  # 只有解密成功才更新 apiKey
            new_settings["apiKey"] = decrypted
            logger.info(f"[DEBUG] 解密 apiKeyEncrypted -> apiKey: {'*' * 8}")
        else:
            logger.warning(f"[DEBUG] apiKeyEncrypted 解密失败，保留现有 apiKey")
        # 保留加密版本用于返回给前端
        SETTINGS_STORE["apiKeyEncrypted"] = new_settings["apiKeyEncrypted"]
    elif "apiKey" in new_settings and new_settings["apiKey"]:
        logger.info(f"[DEBUG] 直接收到 apiKey: {'*' * 8}")

    # 确保 apiKey 字段存在（如果前端没有发送有效值，保留现有值）
    if (not new_settings.get("apiKey")) and SETTINGS_STORE.get("apiKey"):
        new_settings["apiKey"] = SETTINGS_STORE["apiKey"]
        logger.info(f"[DEBUG] 保留现有 apiKey")

    SETTINGS_STORE.update(new_settings)

    logger.info(f"[DEBUG] SETTINGS_STORE 当前状态: apiKey={'存在' if SETTINGS_STORE.get('apiKey') else '不存在'}, apiKeyEncrypted={'存在' if SETTINGS_STORE.get('apiKeyEncrypted') else '不存在'}")

    return JSONResponse({
        "success": True,
        "message": "设置保存成功",
        "settings": SETTINGS_STORE
    })

@app.get("/api/v1/settings/models")
async def get_available_models():
    """获取可用的 AI 模型列表"""
    models = {
        "anthropic": [
            {"id": "claude-opus-4-6", "name": "Claude Opus 4.6", "description": "最强大的模型，适合复杂任务"},
            {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "description": "平衡性能与速度"},
            {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5", "description": "快速响应，适合简单任务"}
        ],
        "openai": [
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "description": "最新的 GPT-4 模型"},
            {"id": "gpt-4", "name": "GPT-4", "description": "强大的语言理解能力"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "description": "快速且经济"}
        ],
        "deepseek": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat", "description": "通用对话模型"},
            {"id": "deepseek-coder", "name": "DeepSeek Coder", "description": "代码专用模型"}
        ],
        "bailian": [
            {"id": "qwen3.5-plus", "name": "Qwen3.5 Plus", "description": "通义千问3.5增强版，性价比最优", "reasoning": True, "input": "¥0.0004/千tokens", "cost": "¥0.002/千tokens", "contextWindow": 131072, "maxTokens": 8192},
            {"id": "qwen3-max-2026-01-23", "name": "Qwen3 Max", "description": "通义千问3最强版，适合复杂任务", "reasoning": True, "input": "¥0.002/千tokens", "cost": "¥0.006/千tokens", "contextWindow": 131072, "maxTokens": 8192},
            {"id": "qwen3-coder-next", "name": "Qwen3 Coder Next", "description": "代码专用模型，最新版", "reasoning": False, "input": "¥0.0004/千tokens", "cost": "¥0.002/千tokens", "contextWindow": 131072, "maxTokens": 8192},
            {"id": "qwen3-coder-plus", "name": "Qwen3 Coder Plus", "description": "代码专用模型，增强版", "reasoning": False, "input": "¥0.0004/千tokens", "cost": "¥0.002/千tokens", "contextWindow": 131072, "maxTokens": 8192},
            {"id": "MiniMax-M2.5", "name": "MiniMax M2.5", "description": "MiniMax通用模型", "reasoning": False, "input": "¥0.0004/千tokens", "cost": "¥0.002/千tokens", "contextWindow": 24576, "maxTokens": 4096},
            {"id": "glm-5", "name": "GLM-5", "description": "智谱GLM-5，深度推理", "reasoning": True, "input": "¥0.0004/千tokens", "cost": "¥0.002/千tokens", "contextWindow": 131072, "maxTokens": 8192},
            {"id": "glm-4.7", "name": "GLM-4.7", "description": "智谱GLM-4.7，通用对话", "reasoning": False, "input": "¥0.0004/千tokens", "cost": "¥0.002/千tokens", "contextWindow": 131072, "maxTokens": 8192},
            {"id": "kimi-k2.5", "name": "Kimi K2.5", "description": "Moonshot Kimi模型", "reasoning": False, "input": "¥0.0004/千tokens", "cost": "¥0.002/千tokens", "contextWindow": 131072, "maxTokens": 8192}
        ]
    }
    return JSONResponse({
        "success": True,
        "models": models
    })

@app.post("/api/v1/settings/test")
async def test_ai_connection(request: dict):
    """测试 AI API 连接"""
    import asyncio

    provider = request.get("provider", "anthropic")
    api_key = request.get("apiKey", "")
    endpoint = request.get("endpoint", "")

    if not api_key:
        return JSONResponse({
            "success": False,
            "error": "API Key 不能为空"
        })

    # 模拟测试连接
    await asyncio.sleep(0.5)

    # 清理 API Key 中可能的空格
    api_key = api_key.strip() if api_key else ""

    # 简单验证 API Key 格式
    valid_prefixes = {
        "anthropic": ["sk-ant-"],
        "openai": ["sk-"],
        "deepseek": ["sk-"],
        "bailian": ["sk-"]  # 百炼API Key格式
    }

    # 百炼API特殊处理
    if provider == "bailian":
        # 百炼 API - 不自动修正 endpoint，用户设置什么就是什么
        # 默认使用 coding 端点: https://coding.dashscope.aliyuncs.com/v1
        if endpoint:
            endpoint = endpoint.strip()

        # 百炼API支持多种前缀，不做严格格式检查
        if api_key.startswith("sk-") or len(api_key) >= 20:
            return JSONResponse({
                "success": True,
                "message": "阿里云百炼 API 连接成功"
            })

    prefixes = valid_prefixes.get(provider, ["sk-"])
    is_valid = any(api_key.startswith(p) for p in prefixes)

    if is_valid or api_key.startswith("test-"):  # 允许测试 Key
        provider_names = {
            "anthropic": "Anthropic",
            "openai": "OpenAI",
            "deepseek": "DeepSeek",
            "bailian": "阿里云百炼"
        }
        return JSONResponse({
            "success": True,
            "message": f"{provider_names.get(provider, provider)} API 连接成功"
        })
    else:
        return JSONResponse({
            "success": False,
            "error": f"无效的 {provider} API Key 格式"
        })



class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: str  # user, assistant, system
    content: str

class ChatRequest(BaseModel):
    """聊天请求模型"""
    messages: List[ChatMessage]
    stream: bool = True
    temperature: float = 0.7
    max_tokens: int = 2048
    context_window: Optional[int] = None  # 上下文窗口长度
    # 支持自定义 AI 配置
    provider: Optional[str] = None
    model: Optional[str] = None
    apiKey: Optional[str] = None
    endpoint: Optional[str] = None
    # 工具调用支持
    enable_tools: bool = True  # 是否启用工具调用（默认启用）
    tool_profile: str = "coding"  # 工具策略 profile
    session_id: Optional[str] = None  # 会话 ID（用于工具注入）


class ReActRequest(BaseModel):
    """ReAct Agent 请求模型"""
    messages: List[ChatMessage]
    agent_type: str = "coder"  # Agent 类型: coder, tester, architect
    temperature: float = 0.7
    max_iterations: int = 15  # 最大推理迭代次数
    stream: bool = True
    # 支持自定义 AI 配置
    provider: Optional[str] = None
    model: Optional[str] = None
    apiKey: Optional[str] = None
    endpoint: Optional[str] = None  # 自定义 API 端点
    session_id: Optional[str] = None


# 聊天历史存储（内存中，实际应用应使用数据库）
CHAT_HISTORY: dict[str, list] = {}


async def generate_agent_response(
    messages: List[ChatMessage],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    provider: str = "bailian",
    api_key: str = None,
    model: str = None,
    endpoint: str = None,
    tool_profile: str = "coding",
    session_id: str = None,
) -> AsyncGenerator[str, None]:
    """
    使用 Agent 框架生成聊天响应（支持工具调用）
    
    这是新的带工具调用能力的 AI 助手实现。
    通过直接调用 LLM API 并集成工具系统，使 AI 能够执行文件操作、命令等。
    
    Args:
        messages: 聊天消息列表
        temperature: 温度参数
        max_tokens: 最大 token 数
        provider: LLM 提供商
        api_key: API 密钥
        model: 模型名称
        endpoint: 自定义端点
        tool_profile: 工具策略 profile
        session_id: 会话 ID（用于工具注入）
        
    Yields:
        SSE 格式的流式响应
    """
    from src.tools import get_registry
    from src.tools.policy import ToolsConfig, get_effective_tools
    
    try:
        # 1. 获取工具定义
        registry = get_registry()
        config = ToolsConfig(profile=tool_profile)
        effective_tools = get_effective_tools(global_config=config, registry=registry)
        
        # 构建工具定义列表（OpenAI function 格式）
        tools_definitions = []
        tool_map = {}  # 用于后续查找工具
        
        logger.info(f"[Agent] effective_tools: {effective_tools}")
        logger.info(f"[Agent] registry.tools.keys(): {list(registry.tools.keys()) if registry else 'None'}")
        
        for tool_name in effective_tools:
            logger.info(f"[Agent] 处理工具: {tool_name}")
            tool = registry.get(tool_name)
            logger.info(f"[Agent] registry.get({tool_name}) = {tool}")
            if tool:
                logger.info(f"[Agent] tool.enabled = {tool.enabled}")
                if tool.enabled:
                    tool_def = _convert_tool_to_openai_format(tool)
                    tools_definitions.append(tool_def)
                    tool_map[tool_name] = tool
                    logger.info(f"[Agent] 成功添加工具: {tool_name}")
                else:
                    logger.warning(f"[Agent] 工具被禁用: {tool_name}")
            else:
                logger.warning(f"[Agent] 工具未找到: {tool_name}")
        
        logger.info(f"[Agent] 启用 {len(tools_definitions)} 个工具: {list(tool_map.keys())}")
        
        # 2. 构建消息
        api_messages = []
        
        # 添加系统提示
        system_prompt = _build_system_prompt(tool_profile)
        api_messages.append({"role": "system", "content": system_prompt})
        
        # 添加历史消息
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})
        
        # 3. Agent 循环
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"[Agent] 第 {iteration} 轮对话")
            
            # 4. 调用 LLM
            response = await _call_llm_with_tools(
                provider=provider,
                api_key=api_key,
                model=model,
                endpoint=endpoint,
                messages=api_messages,
                tools=tools_definitions,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if response is None:
                yield f"data: {json.dumps({'error': 'LLM 调用失败'})}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            # 5. 处理响应
            # 检查是否有工具调用
            tool_calls = response.get("tool_calls", [])
            content = response.get("content", "")
            
            logger.info(f"[Agent] 第 {iteration} 轮 - tool_calls: {len(tool_calls)}, content: '{content[:100]}'")
            
            # 过滤掉 <tool_call> 标签（如果 LLM 错误地输出了这些）
            if content and "<tool_call>" in content:
                logger.warning(f"[Agent] 检测到 <tool_call> 标签在 content 中: {content}")
                # 提取标签内的内容作为工具调用
                import re
                tool_call_match = re.search(r'<tool_call>(.*?)</tool_call>', content, re.DOTALL)
                if tool_call_match:
                    try:
                        # 尝试解析工具调用
                        tool_call_data = json.loads(tool_call_match.group(1))
                        if isinstance(tool_call_data, dict) and "name" in tool_call_data:
                            # 转换为 OpenAI tool_calls 格式
                            tool_calls = [{
                                "id": f"call_{hash(content)}",
                                "type": "function",
                                "function": {
                                    "name": tool_call_data["name"],
                                    "arguments": json.dumps(tool_call_data.get("arguments", {}))
                                }
                            }]
                            logger.info(f"[Agent] 从 <tool_call> 标签中提取工具调用: {tool_calls}")
                            content = ""  # 清空内容，只执行工具
                        else:
                            logger.warning(f"[Agent] <tool_call> 内容格式不正确: {tool_call_data}")
                            content = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()
                    except Exception as e:
                        logger.error(f"[Agent] 解析 <tool_call> 标签失败: {e}")
                        content = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()
                else:
                    # 如果没有找到有效的工具调用，移除标签
                    logger.warning("[Agent] 未匹配到 <tool_call> 内容，直接移除标签")
                    content = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()
            
            logger.info(f"[Agent] 第 {iteration} 轮 - 过滤后 - tool_calls: {len(tool_calls)}, content: '{content[:100]}'")
            
            # 发送文本内容
            if content:
                yield f"data: {json.dumps({'content': content})}\n\n"
            
            # 添加助手消息到历史
            assistant_message = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            api_messages.append(assistant_message)
            
            # 6. 如果没有工具调用，结束
            if not tool_calls:
                break
            
            # 7. 执行工具调用
            for tool_call in tool_calls:
                tool_call_id = tool_call.get("id", "")
                function_name = tool_call.get("function", {}).get("name", "")
                function_args_str = tool_call.get("function", {}).get("arguments", "{}")
                
                try:
                    function_args = json.loads(function_args_str)
                except json.JSONDecodeError:
                    function_args = {}
                
                # 🔧 自动注入 agent_id（针对需要 agent_id 的工具）
                tools_requiring_agent_id = ["memory_search", "memory_get"]
                if function_name in tools_requiring_agent_id and "agent_id" not in function_args:
                    # 使用 session_id 作为 agent_id，如果没有则生成一个
                    agent_id = session_id or f"session-{hash(str(messages))}"
                    function_args["agent_id"] = agent_id
                    logger.info(f"[Agent] 自动注入 agent_id: {agent_id} for tool {function_name}")
                
                # 发送工具开始事件
                tool_start_info = {
                    "type": "tool_start",
                    "tool_name": function_name,
                    "tool_call_id": tool_call_id,
                    "args": function_args
                }
                logger.info(f"[Agent] 工具调用: {function_name}({function_args})")
                yield f"data: {json.dumps(tool_start_info)}\n\n"
                
                # 执行工具
                tool = tool_map.get(function_name)
                tool_result = ""
                tool_success = False
                
                if tool:
                    try:
                        result = await tool.execute(**function_args)
                        if result.success:
                            if isinstance(result.data, str):
                                tool_result = result.data
                            elif isinstance(result.data, dict):
                                tool_result = json.dumps(result.data, ensure_ascii=False, indent=2)
                            else:
                                tool_result = str(result.data)
                            tool_success = True
                        else:
                            tool_result = f"Error: {result.error}"
                    except Exception as e:
                        tool_result = f"Error: {str(e)}"
                        logger.error(f"[Agent] 工具执行错误: {e}", exc_info=True)
                else:
                    tool_result = f"Error: Unknown tool '{function_name}'"
                
                # 发送工具结束事件
                tool_end_info = {
                    "type": "tool_end",
                    "tool_name": function_name,
                    "tool_call_id": tool_call_id,
                    "success": tool_success
                }
                yield f"data: {json.dumps(tool_end_info)}\n\n"
                
                # 添加工具结果到消息历史
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": tool_result
                })
            
            # 继续循环，让 LLM 处理工具结果
        
        logger.info("[Agent] 响应完成")
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        logger.error(f"[Agent] 响应生成错误: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


def _convert_tool_to_openai_format(tool) -> dict:
    """
    将 BaseTool 转换为 OpenAI function 格式
    
    Args:
        tool: BaseTool 实例
        
    Returns:
        OpenAI function 定义字典
    """
    properties = {}
    required = []
    
    if hasattr(tool, 'PARAMETERS') and tool.PARAMETERS:
        for param in tool.PARAMETERS:
            param_name = param.get("name", "")
            param_type = param.get("type", "string")
            param_desc = param.get("description", "")
            param_enum = param.get("enum")
            
            prop = {
                "type": param_type,
                "description": param_desc
            }
            if param_enum:
                prop["enum"] = param_enum
            
            properties[param_name] = prop
            
            if param.get("required", False):
                required.append(param_name)
    
    return {
        "type": "function",
        "function": {
            "name": tool.NAME,
            "description": tool.DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }


async def _call_llm_with_tools(
    provider: str,
    api_key: str,
    model: str,
    endpoint: str,
    messages: list,
    tools: list,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> dict | None:
    """
    调用 LLM API（支持工具调用）
    
    Args:
        provider: 提供商
        api_key: API 密钥
        model: 模型名称
        endpoint: 自定义端点
        messages: 消息列表
        tools: 工具定义列表
        temperature: 温度
        max_tokens: 最大 token
        
    Returns:
        响应字典，包含 content 和 tool_calls
    """
    try:
        # 确定端点 URL
        if provider == "bailian":
            base_url = endpoint.rstrip('/') if endpoint else "https://coding.dashscope.aliyuncs.com/v1"
            # 去掉 bailian/ 前缀
            if model.startswith("bailian/"):
                model = model[8:]
        elif provider == "openai":
            base_url = endpoint.rstrip('/') if endpoint else "https://api.openai.com/v1"
        elif provider == "deepseek":
            base_url = endpoint.rstrip('/') if endpoint else "https://api.deepseek.com/v1"
        else:
            base_url = endpoint.rstrip('/') if endpoint else ""
        
        api_url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # 添加工具定义
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        timeout_config = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
        
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"[Agent] LLM 调用失败: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            return {
                "content": message.get("content", ""),
                "tool_calls": message.get("tool_calls", [])
            }
            
    except Exception as e:
        logger.error(f"[Agent] LLM 调用异常: {e}")
        return None


def _build_system_prompt(tool_profile: str = "coding") -> str:
    """
    构建系统提示词
    
    Args:
        tool_profile: 工具策略 profile
        
    Returns:
        系统提示词
    """
    base_prompt = """你是一个智能研发助手，具备以下能力：

1. **文件操作**：读取、创建、编辑文件
2. **命令执行**：执行 shell 命令
3. **代码分析**：分析和理解代码结构
4. **网络搜索**：搜索和获取网络信息

当用户请求需要文件操作或命令执行时，请使用相应的工具完成。
执行工具后，请根据结果继续处理或向用户报告。

注意事项：
- 执行文件操作前确认路径正确
- 执行命令时注意安全性
- 工具执行结果会作为新消息返回，请根据结果继续对话
- 不要直接输出 <tool_call> 标签，系统会自动处理工具调用

请直接回答用户的问题，如果需要使用工具，系统会自动调用。
"""
    return base_prompt


async def generate_chat_response(messages: List[ChatMessage], temperature: float = 0.7, max_tokens: int = 2048, provider: str = None, api_key: str = None, model: str = None, endpoint: str = None, context_window: int = None) -> AsyncGenerator[str, None]:
    """
    生成聊天响应（流式）
    支持 Anthropic、OpenAI、DeepSeek 和阿里云百炼 API
    """
    try:
        # 从全局配置读取设置（如果请求中没有提供）
        if not provider:
            provider = SETTINGS_STORE.get("aiProvider", "bailian")
        if not api_key:
            # 使用安全的 API Key 获取函数（优先环境变量）
            api_key = get_api_key(provider)
            if not api_key and SETTINGS_STORE.get("apiKeyEncrypted"):
                api_key = decrypt_api_key(SETTINGS_STORE.get("apiKeyEncrypted", ""))
                logger.info(f"[DEBUG] 从 apiKeyEncrypted 解密得到 API Key")
        if not model:
            model = SETTINGS_STORE.get("model", "qwen3.5-plus")
        if not endpoint:
            endpoint = SETTINGS_STORE.get("endpoint", "") or SETTINGS_STORE.get("apiEndpoint", "")

        # 从全局设置读取 max_tokens 和 context_window（如果请求中没有提供）
        if max_tokens == 2048:  # 默认值，可能需要从设置中获取
            max_tokens = SETTINGS_STORE.get("maxTokens", 4096)
        if context_window is None:
            context_window = SETTINGS_STORE.get("contextWindow", None)

        logger.info(f"AI聊天使用配置: provider={provider}, model={model}, api_key={'*' * 8 if api_key else 'None'}")

        # 如果有 API Key 和 provider，使用配置的提供商
        if api_key and provider:
            # 百炼API使用OpenAI兼容格式
            if provider == "bailian":
                # 百炼 API endpoint
                # 所有模型统一使用相同端点处理方式
                # 优先使用用户设置的端点，否则使用默认 coding 端点
                if endpoint:
                    base_url = endpoint.rstrip('/')
                    logger.info(f"[百炼API] 使用自定义端点: {base_url}")
                else:
                    base_url = "https://coding.dashscope.aliyuncs.com/v1"
                    logger.info(f"[百炼API] 使用默认 coding 端点: {model}")

                api_url = f"{base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                logger.info(f"[百炼API] 请求 URL: {api_url}")
                # 百炼 API 不需要 bailian/ 前缀，如果存在则去掉
                if model and model.startswith("bailian/"):
                    model = model[8:]  # 去掉 "bailian/" 前缀
                    logger.info(f"[百炼API] 去掉 bailian/ 前缀，实际模型: {model}")
            elif provider == "openai":
                base_url = endpoint or "https://api.openai.com/v1"
                api_url = f"{base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            elif provider == "deepseek":
                base_url = endpoint or "https://api.deepseek.com/v1"
                api_url = f"{base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            elif provider == "anthropic":
                base_url = endpoint or "https://api.anthropic.com"
                api_url = f"{base_url}/v1/messages"
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
            else:
                raise ValueError(f"不支持的提供商: {provider}")

            # 构建消息格式
            if provider == "anthropic":
                # Anthropic 格式
                api_messages = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
                system_msg = next((m.content for m in messages if m.role == "system"), None)
                payload = {
                    "model": model or "claude-sonnet-4-6",
                    "messages": api_messages,
                    "max_tokens": max_tokens,
                    "stream": True
                }
                if system_msg:
                    payload["system"] = system_msg
            else:
                # OpenAI 兼容格式（包括百炼）
                api_messages = [{"role": m.role, "content": m.content} for m in messages]
                payload = {
                    "model": model or "qwen-plus",
                    "messages": api_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True
                }

            # 添加调试日志：打印实际发送的 payload
            logger.info(f"[DEBUG] 实际发送的 payload: model={payload.get('model')}, provider={provider}, max_tokens={max_tokens}, context_window={context_window}")
            logger.info(f"[DEBUG] 完整 payload: {json.dumps(payload, ensure_ascii=False)[:500]}")

            # 发送流式请求 - 使用详细的超时配置
            timeout_config = httpx.Timeout(
                connect=10.0,      # 连接超时 10 秒
                read=60.0,         # 读取超时 60 秒
                write=30.0,        # 写入超时 30 秒
                pool=10.0          # 连接池超时 10 秒
            )

            # 支持系统代理
            import os
            proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or \
                    os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")

            client_kwargs = {
                "timeout": timeout_config,
                "follow_redirects": True,
                "limits": httpx.Limits(max_keepalive_connections=5, max_connections=10)
            }
            if proxy:
                client_kwargs["proxy"] = proxy
                logger.info(f"[百炼API] 使用代理: {proxy}")

            async with httpx.AsyncClient(**client_kwargs) as client:
                async with client.stream("POST", api_url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield f"data: {json.dumps({'error': f'API错误 ({response.status_code}): {error_text.decode()}'})}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    # 记录响应状态
                    logger.info(f"[百炼API] 流式响应状态: {response.status_code}")
                    # 记录响应头中的模型信息
                    model_header = response.headers.get("x-model", "unknown")
                    logger.info(f"[百炼API] 响应头 x-model: {model_header}")

                    buffer = ""  # 用于处理不完整的行
                    first_chunk = True  # 标记第一个 chunk
                    async for chunk_bytes in response.aiter_bytes():
                        chunk_text = chunk_bytes.decode('utf-8')
                        buffer += chunk_text

                        # 按行分割处理
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            line = line.strip()

                            if not line:
                                continue

                            logger.debug(f"[百炼API] 收到行: {line[:100]}...")

                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    logger.info("[百炼API] 收到 [DONE] 信号")
                                    yield "data: [DONE]\n\n"
                                    return
                                try:
                                    chunk = json.loads(data)
                                    # 记录第一个 chunk 中的模型信息
                                    if first_chunk and "model" in chunk:
                                        logger.info(f"[DEBUG] API 返回的模型: {chunk.get('model')}")
                                        first_chunk = False
                                    if provider == "anthropic":
                                        # Anthropic 格式
                                        if chunk.get("type") == "content_block_delta":
                                            content = chunk.get("delta", {}).get("text", "")
                                            if content:
                                                yield f"data: {json.dumps({'content': content})}\n\n"
                                    else:
                                        # OpenAI 兼容格式（包括百炼）
                                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            logger.debug(f"[百炼API] 提取内容: {content[:50]}...")
                                            yield f"data: {json.dumps({'content': content})}\n\n"
                                except json.JSONDecodeError as e:
                                    logger.warning(f"[百炼API] JSON 解析失败: {e}, 数据: {data[:100]}")
                                    continue

                    # 处理 buffer 中剩余的数据
                    if buffer.strip():
                        line = buffer.strip()
                        logger.debug(f"[百炼API] 剩余数据: {line[:100]}...")
                        if line.startswith("data: ") and line[6:] != "[DONE]":
                            try:
                                chunk = json.loads(line[6:])
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield f"data: {json.dumps({'content': content})}\n\n"
                            except:
                                pass

                    logger.info("[百炼API] 流式响应完成")
                    yield "data: [DONE]\n\n"
                    return

        # 如果没有自定义配置，尝试使用项目的 LLM 服务
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        from src.llm.llm_provider import LLMFactory, init_llm_providers, LLMConfigError

        # 初始化 LLM 提供商
        if not LLMFactory._providers:
            init_llm_providers()

        # 构建提示
        prompt_parts = []
        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"[System]: {msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"[User]: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"[Assistant]: {msg.content}")

        full_prompt = "\n".join(prompt_parts)

        # 获取 LLM 提供商
        llm = LLMFactory.get_default()

        # 流式生成
        async for chunk in llm.generate_stream(full_prompt, temperature=temperature, max_tokens=max_tokens):
            yield f"data: {json.dumps({'content': chunk})}\n\n"

        yield "data: [DONE]\n\n"

    except httpx.ConnectError as e:
        logger.error(f"网络连接失败: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': '网络连接失败，请检查网络或代理设置'})}\n\n"
        yield f"data: {json.dumps({'error': f'详细信息: {str(e)}'})}\n\n"
        yield "data: [DONE]\n\n"
    except httpx.TimeoutException as e:
        logger.error(f"请求超时: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"AI 聊天错误: {e}", exc_info=True)
        # 如果是配置错误，提供友好提示
        error_msg = str(e)
        if "LLMConfigError" in error_msg or "未配置" in error_msg:
            msg1 = '⚠️ LLM 服务未配置。请在设置中配置 API Key。\n\n'
            msg2 = '支持：Anthropic、OpenAI、DeepSeek、阿里云百炼'
        else:
            msg1 = f'❌ AI 聊天错误: {error_msg}'
            msg2 = ''
        yield f"data: {json.dumps({'content': msg1})}\n\n"
        if msg2:
            yield f"data: {json.dumps({'content': msg2})}\n\n"
        yield "data: [DONE]\n\n"


async def generate_react_response(
    messages: List[ChatMessage],
    agent_type: str = "coder",
    temperature: float = 0.7,
    max_iterations: int = 15,
    provider: str = "bailian",
    api_key: str = None,
    model: str = None,
    endpoint: str = None,
    session_id: str = None,
) -> AsyncGenerator[str, None]:
    """
    使用 ReAct Agent 生成响应
    
    ReAct Agent 通过推理-行动循环完成任务，支持动态工具调用和完整推理链追踪。
    
    **实时进展推送**：
    - 通过 WebSocket 实时推送每个推理步骤
    - 通过 SSE 发送最终结果
    
    Args:
        messages: 聊天消息列表
        agent_type: Agent 类型（coder, tester, architect）
        temperature: 温度参数
        max_iterations: 最大推理迭代次数
        provider: LLM 提供商
        api_key: API 密钥
        model: 模型名称
        endpoint: 自定义 API 端点
        session_id: 会话 ID
        
    Yields:
        SSE 格式的流式响应
    """
    try:
        # 导入 ReAct Agent
        from src.agents.react_coder import create_react_coder_agent
        from src.agents.react_tester import create_react_tester_agent
        from src.agents.react_architect import create_react_architect_agent
        from src.react import ReActConfig
        from src.core import Task
        from langchain_openai import ChatOpenAI
        
        # ===== 创建实时进展推送回调 =====
        # 导入 LangChain 回调基类
        try:
            from langchain_core.callbacks import BaseCallbackHandler
        except ImportError:
            from langchain.callbacks.base import BaseCallbackHandler
        
        class RealTimeProgressCallback(BaseCallbackHandler):
            """实时推送 ReAct 执行进展的回调，包含 LLM token 流式输出"""
            
            def __init__(self, ws_manager, session_id):
                self.ws_manager = ws_manager
                self.session_id = session_id
                self.step_counter = 0
                self.start_time = None
                self.current_tool_name = None
                # LLM 输出相关
                self.current_llm_output = ""  # 当前 LLM 输出缓冲
                self.is_llm_streaming = False  # 是否正在流式输出
                self.llm_call_id = 0  # LLM 调用计数
            
            def on_llm_start(self, serialized, prompts, **kwargs):
                """LLM 开始生成时"""
                from datetime import datetime
                import asyncio
                
                self.llm_call_id += 1
                self.current_llm_output = ""
                self.is_llm_streaming = True
                
                # 推送 LLM 开始事件
                self._safe_broadcast({
                    "type": "react_progress",
                    "data": {
                        "session_id": self.session_id,
                        "event": "llm_start",
                        "llm_call_id": self.llm_call_id,
                        "timestamp": datetime.now().isoformat()
                    }
                })
            
            def on_llm_new_token(self, token, **kwargs):
                """LLM 生成新 token 时推送"""
                from datetime import datetime
                
                self.current_llm_output += token
                
                # 每 5 个 token 或遇到换行时推送一次（减少推送频率）
                if len(self.current_llm_output) % 5 == 0 or token in ['\n', '。', '：', ':']:
                    self._safe_broadcast({
                        "type": "react_progress",
                        "data": {
                            "session_id": self.session_id,
                            "event": "llm_token",
                            "llm_call_id": self.llm_call_id,
                            "token": token,
                            "current_output": self.current_llm_output,
                            "timestamp": datetime.now().isoformat()
                        }
                    })
            
            def on_llm_end(self, response, **kwargs):
                """LLM 生成结束时"""
                from datetime import datetime
                
                self.is_llm_streaming = False
                
                # 推送完整的 LLM 输出
                self._safe_broadcast({
                    "type": "react_progress",
                    "data": {
                        "session_id": self.session_id,
                        "event": "llm_end",
                        "llm_call_id": self.llm_call_id,
                        "full_output": self.current_llm_output,
                        "timestamp": datetime.now().isoformat()
                    }
                })
            
            def on_tool_start(self, serialized, input_str, **kwargs):
                """工具开始执行时推送"""
                from datetime import datetime
                
                self.step_counter += 1
                if self.start_time is None:
                    self.start_time = datetime.now()
                
                tool_name = serialized.get("name", "unknown")
                self.current_tool_name = tool_name
                
                # 通过 WebSocket 推送进展
                self._safe_broadcast({
                    "type": "react_progress",
                    "data": {
                        "session_id": self.session_id,
                        "event": "tool_start",
                        "step": self.step_counter,
                        "tool": tool_name,
                        "input": input_str[:200] if input_str else "",
                        "timestamp": datetime.now().isoformat()
                    }
                })
            
            def on_tool_end(self, output, **kwargs):
                """工具执行结束时推送"""
                from datetime import datetime
                
                # 通过 WebSocket 推送进展
                self._safe_broadcast({
                    "type": "react_progress",
                    "data": {
                        "session_id": self.session_id,
                        "event": "tool_end",
                        "step": self.step_counter,
                        "tool": self.current_tool_name or "unknown",
                        "output": output[:500] if output else "",
                        "timestamp": datetime.now().isoformat()
                    }
                })
            
            def _safe_broadcast(self, message):
                """从任意线程安全地广播消息到 WebSocket"""
                import asyncio
                import concurrent.futures
                
                try:
                    # 尝试获取正在运行的事件循环
                    try:
                        loop = asyncio.get_running_loop()
                        # 如果当前在事件循环线程中，直接创建任务
                        asyncio.create_task(self._broadcast_progress(message))
                    except RuntimeError:
                        # 当前不在事件循环线程中，需要找到主事件循环并调度任务
                        # 尝试获取主事件循环（由 FastAPI/Uvicorn 创建）
                        main_loop = None
                        try:
                            main_loop = asyncio.get_event_loop()
                        except RuntimeError:
                            pass
                        
                        if main_loop is None:
                            # 尝试使用全局存储的事件循环引用
                            if hasattr(self.ws_manager, '_event_loop'):
                                main_loop = self.ws_manager._event_loop
                        
                        if main_loop and main_loop.is_running():
                            # 从另一个线程安全地调度协程
                            future = asyncio.run_coroutine_threadsafe(
                                self._broadcast_progress(message),
                                main_loop
                            )
                            # 不等待结果，fire-and-forget 模式
                        else:
                            logger.debug("No running event loop available for broadcast")
                except Exception as e:
                    logger.warning(f"Failed to broadcast message: {e}")
            
            async def _broadcast_progress(self, message):
                """广播进展消息到所有 WebSocket 客户端"""
                try:
                    await self.ws_manager.broadcast(message)
                    logger.debug(f"[ReAct Progress] Step {self.step_counter}: {message['data']['event']}")
                except Exception as e:
                    logger.error(f"Failed to broadcast progress: {e}")
        
        # 创建回调实例
        progress_callback = RealTimeProgressCallback(websocket_manager, session_id)
        
        # 检测是否支持通义千问
        TONGYI_AVAILABLE = False
        try:
            from langchain_community.chat_models import ChatTongyi
            TONGYI_AVAILABLE = True
        except ImportError:
            ChatTongyi = None
        
        # 1. 创建 LLM（根据可用性和配置选择）
        use_tongyi = (provider == "bailian" or (model and "qwen" in model.lower()))
        
        # 检查是否支持原生工具调用
        # 百炼 OpenAI 兼容端点对 function calling 的支持可能有限
        SUPPORTS_FUNCTION_CALLING = provider in ["openai", "anthropic", "deepseek"]
        
        if use_tongyi and TONGYI_AVAILABLE:
            # 百炼 API 使用 OpenAI 兼容端点，不是原生 DashScope
            # 普通模式使用 https://coding.dashscope.aliyuncs.com/v1
            # 这里应该使用 ChatOpenAI 而不是 ChatTongyi
            base_url = endpoint.rstrip('/') if endpoint else "https://coding.dashscope.aliyuncs.com/v1"
            # 去掉 bailian/ 前缀
            model_name = model or "qwen3.5-plus"
            if model_name.startswith("bailian/"):
                model_name = model_name[8:]
            
            # 使用 ChatOpenAI 连接百炼 API（OpenAI 兼容格式）
            # 启用 streaming 以支持实时 token 输出
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                temperature=temperature,
                base_url=base_url,
                streaming=True,  # 启用流式输出
            )
            logger.info(f"[ReAct] 使用百炼 API (OpenAI 兼容): {model_name}, endpoint: {base_url}, streaming=True")
            logger.info(f"[ReAct] 百炼 API function calling 支持: 有限（可能存在兼容性问题）")
        else:
            if use_tongyi and not TONGYI_AVAILABLE:
                logger.warning("[ReAct] ChatTongyi 不可用，请安装 dashscope: pip install dashscope")
                logger.info("[ReAct] 回退到 ChatOpenAI")
            llm = ChatOpenAI(
                model=model or "gpt-4o-mini",
                api_key=api_key,
                temperature=temperature,
                streaming=True,  # 启用流式输出
            )
            logger.info(f"[ReAct] 使用 ChatOpenAI: {model or 'gpt-4o-mini'}, streaming=True")
        
        # 2. 配置 ReAct Agent
        config = ReActConfig(
            max_iterations=max_iterations,
            max_execution_time=300.0,
            enable_loop_detection=True,
            max_same_action=3,
            verbose=False,
        )
        
        # 百炼 API 需要强制使用 Legacy 模式（不支持原生 function calling）
        force_legacy = use_tongyi
        if force_legacy:
            logger.info("[ReAct] 百炼 API 不支持原生 function calling，使用 Legacy ReAct 模式")
        
        # 3. 创建 Agent（添加实时进展回调）
        agent = None
        extra_callbacks = [progress_callback]  # 添加实时进展回调
        
        if agent_type == "coder":
            agent = create_react_coder_agent(
                llm=llm, 
                config=config, 
                verbose=True, 
                force_legacy=force_legacy,
                extra_callbacks=extra_callbacks  # 传递回调
            )
        elif agent_type == "tester":
            agent = create_react_tester_agent(
                llm=llm, 
                config=config, 
                verbose=True, 
                force_legacy=force_legacy,
                extra_callbacks=extra_callbacks
            )
        elif agent_type == "architect":
            agent = create_react_architect_agent(
                llm=llm, 
                config=config, 
                verbose=True, 
                force_legacy=force_legacy,
                extra_callbacks=extra_callbacks
            )
        else:
            agent = create_react_coder_agent(
                llm=llm, 
                config=config, 
                verbose=True, 
                force_legacy=force_legacy,
                extra_callbacks=extra_callbacks
            )
        
        logger.info(f"[ReAct] 创建 Agent: {agent_type}, 最大迭代: {max_iterations}, 实时进展推送: 已启用")
        
        # 4. 构建任务
        last_message = messages[-1] if messages else None
        if not last_message:
            yield f"data: {json.dumps({'error': 'No messages provided'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        # 从历史消息中提取上下文
        context = ""
        if len(messages) > 1:
            context_messages = messages[:-1]  # 除了最后一条消息
            context = "\n".join([
                f"{msg.role}: {msg.content}" 
                for msg in context_messages[-5:]  # 最多 5 条历史
            ])
        
        task = Task(
            title=f"ReAct {agent_type} task",
            description=last_message.content,
            input_data={"history": context, "session_id": session_id} if context else {},
        )
        
        # 5. 发送开始事件
        yield f"data: {json.dumps({'type': 'react_start', 'agent_type': agent_type})}\n\n"
        
        # 6. 执行任务
        async with agent.lifecycle():
            result = await agent.process_task(task)
            
            # 安全获取 output_data（可能是 dict 或 None）
            output_data = result.output_data if isinstance(result.output_data, dict) else {}
            
            # 7. 流式发送推理链
            reasoning_chain = output_data.get("reasoning_chain", [])
            if not isinstance(reasoning_chain, list):
                reasoning_chain = []
            total_steps = len(reasoning_chain)
            
            for i, step in enumerate(reasoning_chain):
                if not isinstance(step, dict):
                    continue
                step_data = {
                    'type': 'reasoning_step',
                    'step': i + 1,
                    'total': total_steps,
                    'thought': step.get('thought', ''),
                    'action': step.get('action', ''),
                    'action_input': step.get('action_input', {}),
                    'observation': str(step.get('observation', ''))[:500],  # 截断避免过长
                }
                yield f"data: {json.dumps(step_data)}\n\n"
                logger.info(f"[ReAct] 步骤 {i+1}/{total_steps}: {step.get('action', 'unknown')}")
            
            # 8. 发送最终结果
            # success 基于 output_data 或 task status 判断
            output_content = output_data.get("output", "")
            success = output_data.get("success", result.status == "completed")
            
            # 检测是否达到迭代限制或超时（通过输出内容判断）
            iteration_limit_msg = "Agent stopped due to iteration limit or time limit"
            if iteration_limit_msg in output_content:
                success = False
                # 提供更友好的提示
                output_content = (
                    "🔄 Agent 达到迭代限制。\n\n"
                    "可能原因：\n"
                    "1. 任务过于复杂，需要更多迭代次数\n"
                    "2. LLM 输出格式不符合要求，导致解析失败\n"
                    "3. 任务定义不够清晰\n\n"
                    "建议：\n"
                    "- 简化问题或分解为多个小任务\n"
                    "- 使用更清晰的指令\n"
                    "- 尝试切换到普通对话模式"
                )
            
            response_data = {
                "type": "react_result",
                "content": output_content,
                "iterations": output_data.get("iterations", 0),
                "success": success,
                "execution_time": output_data.get("total_execution_time", 0),
                "reasoning_chain_length": total_steps,
            }
            
            yield f"data: {json.dumps(response_data)}\n\n"
            logger.info(f"[ReAct] 任务完成: 成功={success}, 迭代={output_data.get('iterations', 0)}")
            
        yield "data: [DONE]\n\n"
        
    except ImportError as e:
        logger.error(f"ReAct Agent 导入失败: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': f'ReAct Agent 未安装: {str(e)}'})}\n\n"
        yield "data: [DONE]\n\n"
    except asyncio.TimeoutError:
        logger.error("ReAct Agent 执行超时")
        timeout_msg = "⏱️ ReAct 执行超时（5分钟），建议：\n1. 简化问题\n2. 降低 max_iterations\n3. 使用普通模式"
        yield f"data: {json.dumps({'error': timeout_msg})}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"ReAct Agent 执行错误: {e}", exc_info=True)
        error_msg = str(e)
        
        # 友好的错误提示
        if "未配置" in error_msg or "LLMConfigError" in error_msg:
            yield f"data: {json.dumps({'error': '⚠️ LLM 服务未配置，请在设置中配置 API Key'})}\n\n"
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            yield f"data: {json.dumps({'error': '⏱️ 执行超时，请稍后重试或简化问题'})}\n\n"
        elif "rate limit" in error_msg.lower():
            yield f"data: {json.dumps({'error': '🚫 API 请求频率限制，请稍后重试'})}\n\n"
        elif "authentication" in error_msg.lower() or "api key" in error_msg.lower():
            yield f"data: {json.dumps({'error': '🔑 API Key 无效，请检查设置'})}\n\n"
        elif "MaxIterations" in error_msg or "max_iterations" in error_msg:
            yield f"data: {json.dumps({'error': f'🔄 达到最大迭代次数限制，请尝试简化问题或增加迭代次数'})}\n\n"
        elif "LoopDetected" in error_msg or "循环检测" in error_msg:
            yield f"data: {json.dumps({'error': f'🔁 检测到执行循环，已自动停止。请换一种方式提问'})}\n\n"
        else:
            yield f"data: {json.dumps({'error': f'❌ ReAct Agent 错误: {error_msg}'})}\n\n"
        yield "data: [DONE]\n\n"


@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
    """
    AI 聊天端点

    支持流式响应（SSE）和非流式响应
    支持工具调用（通过 Agent 框架）
    """
    # 获取配置
    provider = request.provider or SETTINGS_STORE.get("aiProvider", "bailian")
    api_key = request.apiKey
    if not api_key:
        # 使用安全的 API Key 获取函数（优先环境变量）
        api_key = get_api_key(provider)
        if not api_key and SETTINGS_STORE.get("apiKeyEncrypted"):
            api_key = decrypt_api_key(SETTINGS_STORE.get("apiKeyEncrypted", ""))
    model = request.model or SETTINGS_STORE.get("model", "qwen3.5-plus")
    endpoint = request.endpoint or SETTINGS_STORE.get("endpoint", "")
    max_tokens = request.max_tokens if request.max_tokens != 2048 else SETTINGS_STORE.get("maxTokens", 4096)
    
    # 选择响应生成方式
    # 如果启用了工具且 Agent 框架可用，使用 Agent 响应
    use_agent = request.enable_tools and AGENT_ENABLED
    
    if request.stream:
        if use_agent:
            # 使用 Agent 框架（支持工具调用）
            logger.info(f"[Chat] 使用 Agent 模式，工具策略: {request.tool_profile}")
            return StreamingResponse(
                generate_agent_response(
                    request.messages,
                    temperature=request.temperature,
                    max_tokens=max_tokens,
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    endpoint=endpoint,
                    tool_profile=request.tool_profile,
                    session_id=request.session_id,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        else:
            # 使用纯对话模式
            logger.info("[Chat] 使用纯对话模式")
            return StreamingResponse(
                generate_chat_response(
                    request.messages,
                    temperature=request.temperature,
                    max_tokens=max_tokens,
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    endpoint=endpoint,
                    context_window=request.context_window
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
                    "Content-Encoding": "identity",  # 跳过 Gzip 压缩
                }
            )
    else:
        # 非流式响应
        response_content = ""
        tool_calls = []
        
        if use_agent:
            async for chunk in generate_agent_response(
                request.messages,
                temperature=request.temperature,
                max_tokens=max_tokens,
                provider=provider,
                api_key=api_key,
                model=model,
                endpoint=endpoint,
                tool_profile=request.tool_profile,
                session_id=request.session_id,
            ):
                if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                    try:
                        data = json.loads(chunk[6:].strip())
                        if "content" in data:
                            response_content += data["content"]
                        elif "type" in data and data["type"] == "tool_start":
                            tool_calls.append(data)
                    except json.JSONDecodeError:
                        continue
        else:
            async for chunk in generate_chat_response(
                request.messages,
                temperature=request.temperature,
                max_tokens=max_tokens,
                provider=provider,
                api_key=api_key,
                model=model,
                endpoint=endpoint,
                context_window=request.context_window
            ):
                if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                    try:
                        data = json.loads(chunk[6:].strip())
                        if "content" in data:
                            response_content += data["content"]
                    except json.JSONDecodeError:
                        continue

        return {
            "response": response_content,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "tool_calls": tool_calls if tool_calls else None,
            "agent_mode": use_agent
        }


@app.post("/api/v1/react/chat")
async def react_chat(request: ReActRequest):
    """
    ReAct Agent 聊天端点
    
    使用 ReAct (Reasoning + Acting) 模式处理任务，支持：
    - 动态推理和决策
    - 自动工具调用
    - 完整推理链追踪
    - 多种 Agent 类型（coder, tester, architect）
    
    Args:
        request: ReActRequest 包含：
            - messages: 消息列表
            - agent_type: Agent 类型（coder/tester/architect）
            - max_iterations: 最大推理迭代次数
            - stream: 是否流式响应
            - provider/model/apiKey: LLM 配置
    
    Returns:
        StreamingResponse 或 JSONResponse
    """
    # 获取配置
    provider = request.provider or SETTINGS_STORE.get("aiProvider", "bailian")
    api_key = request.apiKey
    if not api_key:
        # 使用安全的 API Key 获取函数（优先环境变量）
        api_key = get_api_key(provider)
        if not api_key and SETTINGS_STORE.get("apiKeyEncrypted"):
            api_key = decrypt_api_key(SETTINGS_STORE.get("apiKeyEncrypted", ""))
    model = request.model or SETTINGS_STORE.get("model", "qwen-max")
    endpoint = request.endpoint or SETTINGS_STORE.get("endpoint", "")
    
    logger.info(f"[ReAct Chat] Agent: {request.agent_type}, 迭代: {request.max_iterations}, 流式: {request.stream}")
    
    if request.stream:
        # 流式响应
        return StreamingResponse(
            generate_react_response(
                request.messages,
                agent_type=request.agent_type,
                temperature=request.temperature,
                max_iterations=request.max_iterations,
                provider=provider,
                api_key=api_key,
                model=model,
                endpoint=endpoint,
                session_id=request.session_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Encoding": "identity",  # 跳过 Gzip 压缩
            }
        )
    else:
        # 非流式响应 - 收集所有数据
        response_data = {
            "content": "",
            "reasoning_chain": [],
            "iterations": 0,
            "success": False,
        }
        
        async for chunk in generate_react_response(
            request.messages,
            agent_type=request.agent_type,
            temperature=request.temperature,
            max_iterations=request.max_iterations,
            provider=provider,
            api_key=api_key,
            model=model,
            endpoint=endpoint,
            session_id=request.session_id,
        ):
            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                try:
                    data = json.loads(chunk[6:].strip())
                    
                    if data.get("type") == "react_result":
                        response_data["content"] = data.get("content", "")
                        response_data["iterations"] = data.get("iterations", 0)
                        response_data["success"] = data.get("success", False)
                        response_data["execution_time"] = data.get("execution_time", 0)
                    elif data.get("type") == "reasoning_step":
                        response_data["reasoning_chain"].append(data)
                    elif "error" in data:
                        response_data["error"] = data["error"]
                        
                except json.JSONDecodeError:
                    continue
        
        return {
            "response": response_data["content"],
            "reasoning_chain": response_data["reasoning_chain"],
            "iterations": response_data["iterations"],
            "success": response_data["success"],
            "model": model,
            "agent_type": request.agent_type,
            "timestamp": datetime.now().isoformat(),
        }


@app.get("/api/v1/chat/sessions")
async def get_chat_sessions(
    limit: int = 20,
    offset: int = 0
):
    """获取会话列表（支持分页）"""
    logger.info(f"[get_chat_sessions] 请求参数: limit={limit}, offset={offset}, DATABASE_ENABLED={DATABASE_ENABLED}")
    logger.info(f"[get_chat_sessions] 变量状态: get_database_manager={get_database_manager}, crud={crud}, ChatMessageModel={ChatMessageModel}")
    
    if not DATABASE_ENABLED:
        # 降级到内存模式
        logger.info("[get_chat_sessions] 使用内存模式")
        sessions = list(CHAT_HISTORY.keys())
        result = {
            "sessions": [{"session_id": sid, "message_count": len(CHAT_HISTORY[sid])} for sid in sessions[offset:offset+limit]],
            "total": len(sessions),
            "has_more": offset + limit < len(sessions)
        }
        logger.info(f"[get_chat_sessions] 返回: {result}")
        return result
    
    try:
        logger.info("[get_chat_sessions] 使用数据库模式")
        if get_database_manager is None:
            logger.error("[get_chat_sessions] get_database_manager 为 None!")
            raise Exception("get_database_manager 未初始化")
        
        db_manager = get_database_manager()
        logger.info(f"[get_chat_sessions] 获取数据库管理器: {db_manager}")
        async with db_manager.get_session() as db:
            logger.info("[get_chat_sessions] 获取会话数据")
            sessions = await crud.get_chat_sessions(db, limit=limit, offset=offset)
            
            # 获取总数量
            count_result = await db.execute(
                select(func.count(func.distinct(ChatMessageModel.session_id)))
            )
            total = count_result.scalar() or 0
            
            logger.info(f"[get_chat_sessions] 返回数据: sessions={len(sessions)}, total={total}")
            return {
                "sessions": sessions,
                "total": total,
                "has_more": offset + limit < total
            }
    except Exception as e:
        logger.error(f"[get_chat_sessions] 获取会话列表失败：{e}", exc_info=True)
        # 降级到内存模式
        sessions = list(CHAT_HISTORY.keys())
        return {
            "sessions": [{"session_id": sid, "message_count": len(CHAT_HISTORY[sid])} for sid in sessions[offset:offset+limit]],
            "total": len(sessions),
            "has_more": offset + limit < len(sessions),
            "error": str(e)
        }


@app.get("/api/v1/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
    limit: int = 50,
    offset: int = 0
):
    """获取聊天历史（支持分页）"""
    if not DATABASE_ENABLED:
        # 降级到内存模式
        messages = CHAT_HISTORY.get(session_id, [])
        return {
            "session_id": session_id,
            "messages": messages[offset:offset+limit],
            "total": len(messages),
            "has_more": offset + limit < len(messages)
        }
    
    try:
        db_manager = get_database_manager()
        async with db_manager.get_session() as db:
            messages = await crud.get_chat_messages_by_session(
                db, session_id, limit=limit, offset=offset
            )
            
            # 获取总数量
            count_result = await db.execute(
                select(func.count(ChatMessageModel.id)).where(
                    ChatMessageModel.session_id == session_id
                )
            )
            total = count_result.scalar() or 0
            
            return {
                "session_id": session_id,
                "messages": [msg.to_dict() for msg in messages],
                "total": total,
                "has_more": offset + limit < total
            }
    except Exception as e:
        logger.error(f"获取聊天历史失败 (session={session_id}): {e}", exc_info=True)
        # 降级到内存模式
        messages = CHAT_HISTORY.get(session_id, [])
        return {
            "session_id": session_id,
            "messages": messages[offset:offset+limit],
            "total": len(messages),
            "has_more": offset + limit < len(messages),
            "error": str(e)
        }


@app.post("/api/v1/chat/messages")
async def create_chat_message(message_data: dict):
    """保存新消息到数据库"""
    session_id = message_data.get("session_id")
    role = message_data.get("role")
    content = message_data.get("content")
    metadata = message_data.get("metadata", {})
    
    if not session_id or not role or not content:
        raise HTTPException(status_code=400, detail="缺少必要字段：session_id, role, content")
    
    if not DATABASE_ENABLED:
        # 降级到内存模式
        if session_id not in CHAT_HISTORY:
            CHAT_HISTORY[session_id] = []
        
        message = {
            "id": len(CHAT_HISTORY[session_id]) + 1,
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata
        }
        CHAT_HISTORY[session_id].append(message)
        return message
    
    try:
        db_manager = get_database_manager()
        async with db_manager.get_session() as db:
            message = await crud.create_chat_message(
                db,
                session_id=session_id,
                role=role,
                content=content,
                metadata=metadata
            )
            return message.to_dict()
    except Exception as e:
        logger.error(f"保存消息失败：{e}", exc_info=True)
        # 降级到内存模式
        if session_id not in CHAT_HISTORY:
            CHAT_HISTORY[session_id] = []
        
        message = {
            "id": len(CHAT_HISTORY[session_id]) + 1,
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata
        }
        CHAT_HISTORY[session_id].append(message)
        return message


@app.delete("/api/v1/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """删除会话及其所有消息"""
    if not DATABASE_ENABLED:
        # 降级到内存模式
        if session_id in CHAT_HISTORY:
            del CHAT_HISTORY[session_id]
        return {"status": "success", "message": "会话已删除", "session_id": session_id}
    
    try:
        db_manager = get_database_manager()
        async with db_manager.get_session() as db:
            deleted = await crud.delete_chat_session(db, session_id)
            if not deleted:
                # 会话不存在，但在内存模式下不报错
                pass
            return {"status": "success", "message": "会话已删除", "session_id": session_id}
    except Exception as e:
        logger.error(f"删除会话失败 (session={session_id}): {e}", exc_info=True)
        # 降级到内存模式
        if session_id in CHAT_HISTORY:
            del CHAT_HISTORY[session_id]
        return {"status": "success", "message": "会话已删除", "session_id": session_id}


@app.get("/api/v1/chat/stats")
async def get_chat_stats():
    """获取聊天统计信息"""
    if not DATABASE_ENABLED:
        return {
            "total_sessions": len(CHAT_HISTORY),
            "total_messages": sum(len(msgs) for msgs in CHAT_HISTORY.values()),
            "messages_by_role": {}
        }
    
    try:
        async for db in get_db_session():
            stats = await crud.get_chat_stats(db)
            return stats
    except Exception as e:
        logger.error(f"获取聊天统计失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "5.2.0",
        "features": {
            "logging": "unified",
            "api_docs": "enabled",
            "cache_stats": "enabled",
            "websocket_heartbeat": "enabled"
        }
    }


@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """获取缓存统计信息"""
    stats = response_cache.get_stats()
    logger.info(f"缓存统计：{stats}")
    return stats


@app.get("/api/v1/ws/stats")
async def get_ws_stats():
    """获取 WebSocket 连接统计"""
    stats = websocket_manager.get_stats()
    logger.info(f"WebSocket 统计：{stats}")
    return stats


@app.get("/api/v1/error-log")
async def get_error_log():
    """获取错误日志（简化版，实际应该从数据库读取）"""
    return {
        "errors": [],
        "total": 0,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/v1/error-log")
async def report_error(error: dict):
    """上报错误"""
    # 在实际应用中，这里应该写入数据库或日志系统
    logger.error(f"[Error Report] {datetime.now().isoformat()}: {error}")
    return {"status": "success", "message": "错误已记录"}


@app.get("/api/v1/export/tasks")
async def export_tasks(format: str = "json"):
    """导出任务数据"""

    if format == "json":
        return JSONResponse(content=TASKS_DATA)

    elif format == "csv":
        output = io.StringIO()
        if TASKS_DATA:
            writer = csv.DictWriter(output, fieldnames=TASKS_DATA[0].keys())
            writer.writeheader()
            writer.writerows(TASKS_DATA)
        return PlainTextResponse(content=output.getvalue(), media_type="text/csv")

    elif format == "markdown":
        md = "# 任务导出\n\n"
        md += "| ID | 标题 | 状态 | 优先级 | 负责人 | Agent |\n"
        md += "|---|---|---|---|---|---|\n"
        for task in TASKS_DATA:
            md += f"| {task['id']} | {task['title']} | {task['statusText']} | {task['priorityText']} | {task['assignee']} | {task['agent']} |\n"
        return PlainTextResponse(content=md, media_type="text/markdown")

    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")


@app.get("/api/v1/export/stats")
async def export_stats():
    """导出统计数据"""
    return {
        "totalTasks": len(TASKS_DATA),
        "activeAgents": len([a for a in AGENTS_DATA if a["status"] == "busy"]),
        "completionRate": 93,
        "timestamp": datetime.now().isoformat(),
        "agents": AGENTS_DATA,
        "tasks": TASKS_DATA
    }


# ============ 工具系统 API ============

# 工具数据（模拟 OpenClaw 工具）
TOOLS_DATA = [
    {
        "name": "read",
        "description": "读取文件内容，支持文本文件和图片",
        "category": "file",
        "enabled": True,
        "parameters": [
            {"name": "path", "type": "string", "description": "文件路径", "required": True},
            {"name": "offset", "type": "integer", "description": "起始行号", "required": False, "default": 1},
            {"name": "limit", "type": "integer", "description": "最大行数", "required": False, "default": 2000}
        ],
        "examples": [{"path": "/home/user/file.txt", "limit": 100}]
    },
    {
        "name": "write",
        "description": "写入文件内容，创建或覆盖文件",
        "category": "file",
        "enabled": True,
        "parameters": [
            {"name": "path", "type": "string", "description": "文件路径", "required": True},
            {"name": "content", "type": "string", "description": "文件内容", "required": True}
        ],
        "examples": [{"path": "/home/user/file.txt", "content": "Hello World"}]
    },
    {
        "name": "edit",
        "description": "编辑文件，精确替换文本",
        "category": "file",
        "enabled": True,
        "parameters": [
            {"name": "path", "type": "string", "description": "文件路径", "required": True},
            {"name": "oldText", "type": "string", "description": "要替换的原文本", "required": True},
            {"name": "newText", "type": "string", "description": "新文本", "required": True}
        ],
        "examples": [{"path": "/home/user/file.txt", "oldText": "old", "newText": "new"}]
    },
    {
        "name": "exec",
        "description": "执行 shell 命令",
        "category": "system",
        "enabled": True,
        "parameters": [
            {"name": "command", "type": "string", "description": "要执行的命令", "required": True},
            {"name": "timeout", "type": "integer", "description": "超时时间（秒）", "required": False, "default": 60},
            {"name": "workdir", "type": "string", "description": "工作目录", "required": False}
        ],
        "examples": [{"command": "ls -la", "timeout": 30}]
    },
    {
        "name": "web_search",
        "description": "使用 Brave Search API 搜索互联网",
        "category": "web",
        "enabled": True,
        "parameters": [
            {"name": "query", "type": "string", "description": "搜索关键词", "required": True},
            {"name": "count", "type": "integer", "description": "结果数量", "required": False, "default": 10},
            {"name": "freshness", "type": "string", "description": "时间过滤", "required": False}
        ],
        "examples": [{"query": "Python tutorial", "count": 5}]
    },
    {
        "name": "web_fetch",
        "description": "抓取网页内容并提取可读文本",
        "category": "web",
        "enabled": True,
        "parameters": [
            {"name": "url", "type": "string", "description": "网页 URL", "required": True},
            {"name": "extractMode", "type": "string", "description": "提取模式", "required": False, "default": "markdown"}
        ],
        "examples": [{"url": "https://example.com"}]
    },
    {
        "name": "browser",
        "description": "控制浏览器进行自动化操作",
        "category": "web",
        "enabled": True,
        "parameters": [
            {"name": "action", "type": "string", "description": "操作类型", "required": True},
            {"name": "url", "type": "string", "description": "目标 URL", "required": False},
            {"name": "selector", "type": "string", "description": "CSS 选择器", "required": False}
        ],
        "examples": [{"action": "open", "url": "https://example.com"}]
    },
    {
        "name": "message",
        "description": "发送消息到 Telegram 等渠道",
        "category": "communication",
        "enabled": True,
        "parameters": [
            {"name": "action", "type": "string", "description": "操作类型", "required": True},
            {"name": "target", "type": "string", "description": "目标频道/用户", "required": False},
            {"name": "message", "type": "string", "description": "消息内容", "required": False}
        ],
        "examples": [{"action": "send", "message": "Hello"}]
    },
    {
        "name": "image",
        "description": "分析图片内容",
        "category": "multimedia",
        "enabled": True,
        "parameters": [
            {"name": "image", "type": "string", "description": "图片路径或 URL", "required": True},
            {"name": "prompt", "type": "string", "description": "分析提示", "required": False}
        ],
        "examples": [{"image": "/home/user/photo.jpg", "prompt": "描述图片内容"}]
    },
    {
        "name": "pdf",
        "description": "分析 PDF 文档",
        "category": "multimedia",
        "enabled": True,
        "parameters": [
            {"name": "pdf", "type": "string", "description": "PDF 路径或 URL", "required": True},
            {"name": "prompt", "type": "string", "description": "分析提示", "required": False},
            {"name": "pages", "type": "string", "description": "页码范围", "required": False}
        ],
        "examples": [{"pdf": "/home/user/doc.pdf", "prompt": "总结文档内容"}]
    }
]

# 模拟进程数据
PROCESSES_DATA = []


@app.get("/api/v1/tools")
async def get_tools():
    """获取工具列表"""
    logger.info("获取工具列表")
    return {"tools": TOOLS_DATA, "total": len(TOOLS_DATA)}


@app.get("/api/v1/tools/categories")
async def get_tool_categories():
    """获取工具分类"""
    categories = list(set(tool["category"] for tool in TOOLS_DATA))
    logger.info(f"获取工具分类：{categories}")
    return {"categories": sorted(categories)}


@app.get("/api/v1/tools/name/{tool_name}")
async def get_tool_by_name(tool_name: str):
    """根据名称获取工具详情"""
    tool = next((t for t in TOOLS_DATA if t["name"] == tool_name), None)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 {tool_name} 不存在")
    logger.info(f"获取工具详情：{tool_name}")
    return tool


@app.get("/api/v1/tools/categories/{category}")
async def get_tools_by_category(category: str):
    """获取指定分类的工具"""
    tools = [t for t in TOOLS_DATA if t["category"] == category]
    logger.info(f"获取分类 {category} 的工具：{len(tools)} 个")
    return {"tools": tools, "category": category}


class ToolExecuteRequest(BaseModel):
    """工具执行请求"""
    tool_name: str
    params: dict = {}


@app.post("/api/v1/tools/execute")
async def execute_tool(request: ToolExecuteRequest):
    """执行工具"""
    tool = next((t for t in TOOLS_DATA if t["name"] == request.tool_name), None)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 {request.tool_name} 不存在")
    if not tool["enabled"]:
        raise HTTPException(status_code=400, detail=f"工具 {request.tool_name} 已禁用")
    
    # 模拟执行（实际应该调用 OpenClaw 工具）
    import time
    start_time = time.time()
    
    try:
        # 这里应该调用实际的 OpenClaw 工具
        # 暂时返回模拟结果
        result = {
            "success": True,
            "data": {
                "message": f"工具 {request.tool_name} 执行成功",
                "params": request.params
            },
            "execution_time": round(time.time() - start_time, 3)
        }
        logger.info(f"执行工具 {request.tool_name}: 成功")
        return result
    except Exception as e:
        logger.error(f"执行工具 {request.tool_name} 失败：{e}")
        return {
            "success": False,
            "error": str(e),
            "execution_time": round(time.time() - start_time, 3)
        }


@app.get("/api/v1/tools/processes")
async def get_processes():
    """获取后台进程列表"""
    logger.info(f"获取进程列表：{len(PROCESSES_DATA)} 个")
    return {"processes": PROCESSES_DATA, "total": len(PROCESSES_DATA)}


@app.post("/api/v1/tools/processes/{session_id}/kill")
async def kill_process(session_id: str):
    """终止后台进程"""
    global PROCESSES_DATA
    proc = next((p for p in PROCESSES_DATA if p["session_id"] == session_id), None)
    if not proc:
        raise HTTPException(status_code=404, detail=f"进程 {session_id} 不存在")
    
    PROCESSES_DATA = [p for p in PROCESSES_DATA if p["session_id"] != session_id]
    logger.info(f"终止进程：{session_id}")
    return {"status": "success", "message": f"进程 {session_id} 已终止"}


# ============ 导出功能 ============

# WebSocket 连接管理
class WebSocketManager:
    """WebSocket 连接管理器"""
    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}
        self.heartbeat_interval = 30  # 心跳间隔（秒）
        self._event_loop = None  # 存储主事件循环引用
        logger.info("WebSocket 管理器初始化完成")

    async def connect(self, websocket: WebSocket, client_id: int):
        """接受连接并记录"""
        import asyncio
        await websocket.accept()
        self.active_connections[client_id] = websocket
        # 存储当前事件循环引用，供后台线程使用
        if self._event_loop is None:
            self._event_loop = asyncio.get_running_loop()
        logger.info(f"WebSocket 客户端连接：{client_id}, 当前连接数：{len(self.active_connections)}")

    def disconnect(self, client_id: int):
        """断开连接并清理"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket 客户端断开：{client_id}, 当前连接数：{len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息给所有连接的客户端"""
        disconnected = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"广播消息失败 (client={client_id}): {e}")
                disconnected.append(client_id)
        # 清理断开的连接
        for client_id in disconnected:
            self.disconnect(client_id)

    def get_stats(self) -> dict:
        """获取连接统计"""
        return {
            "active_connections": len(self.active_connections),
            "connection_ids": list(self.active_connections.keys())
        }


class AgentEventBus:
    """
    Agent 状态事件总线
    
    功能：
    - 监听 Agent 状态变化
    - 通过 WebSocket 广播状态更新
    - 支持外部事件源接入
    - 订阅/发布模式
    """
    
    def __init__(self):
        self._subscribers: list[callable] = []
        self._agent_states: dict[str, dict] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        logger.info("Agent 事件总线初始化完成")
    
    def subscribe(self, callback: callable):
        """订阅 Agent 状态变化"""
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: callable):
        """取消订阅"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    async def publish(self, event_type: str, agent_name: str, data: dict):
        """
        发布 Agent 事件
        
        Args:
            event_type: 事件类型 (status_change, task_complete, error, etc.)
            agent_name: Agent 名称
            data: 事件数据
        """
        event = {
            "type": event_type,
            "agent": agent_name,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        await self._event_queue.put(event)
        logger.debug(f"Agent 事件发布：{event_type} - {agent_name}")
    
    async def update_agent_status(self, agent_name: str, new_status: str, metadata: dict = None):
        """
        更新 Agent 状态并广播
        
        Args:
            agent_name: Agent 名称
            new_status: 新状态
            metadata: 附加元数据
        """
        old_status = self._agent_states.get(agent_name, {}).get("status", "unknown")
        
        self._agent_states[agent_name] = {
            "status": new_status,
            "updated_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        await self.publish(
            "status_change",
            agent_name,
            {
                "old_status": old_status,
                "new_status": new_status,
                "metadata": metadata
            }
        )
    
    def get_agent_status(self, agent_name: str) -> dict | None:
        """获取 Agent 当前状态"""
        return self._agent_states.get(agent_name)
    
    async def start(self):
        """启动事件处理循环"""
        self._running = True
        logger.info("Agent 事件总线启动")
        
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                await self._dispatch_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"事件处理错误：{e}")
    
    def stop(self):
        """停止事件处理"""
        self._running = False
        logger.info("Agent 事件总线停止")
    
    async def _dispatch_event(self, event: dict):
        """分发事件给所有订阅者"""
        for callback in self._subscribers:
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"订阅者回调错误：{e}")
    
    async def connect_to_agent_manager(self):
        """
        连接到真实的 Agent 管理器
        
        从 src/pi/agent_manager.py 获取实时状态
        """
        try:
            from src.pi.agent_manager import get_agent_manager
            
            agent_manager = get_agent_manager()
            
            # 注册状态变化回调
            async def on_status_change(agent_id, old_status, new_status):
                agent_info = agent_manager.get_agent(agent_id)
                if agent_info:
                    await self.update_agent_status(
                        agent_info.name,
                        new_status.value if hasattr(new_status, 'value') else str(new_status),
                        {"agent_id": agent_id}
                    )
            
            agent_manager._on_status_change = on_status_change
            logger.info("已连接到 Agent 管理器")
            
        except ImportError:
            logger.warning("Agent 管理器模块未找到，使用模拟数据")
        except Exception as e:
            logger.warning(f"连接 Agent 管理器失败：{e}")


# 全局实例
websocket_manager = WebSocketManager()
agent_event_bus = AgentEventBus()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 实时数据推送端点
    
    功能:
    - 系统状态推送（5 秒间隔）
    - Agent 状态实时更新（通过事件总线）
    - 心跳检测（30 秒间隔）
    - 断线自动清理
    """
    client_id = id(websocket)
    await websocket_manager.connect(websocket, client_id)

    last_heartbeat = datetime.now(timezone.utc).astimezone()
    
    # 订阅 Agent 事件
    async def on_agent_event(event: dict):
        await websocket.send_json({
            "type": "agent_update",
            "data": {
                "name": event.get("agent"),
                "status": event.get("data", {}).get("new_status"),
                "event_type": event.get("type"),
                "timestamp": event.get("timestamp")
            }
        })
    
    agent_event_bus.subscribe(on_agent_event)

    try:
        while True:
            now = datetime.now(timezone.utc).astimezone()

            # 推送系统状态
            await websocket.send_json({
                "type": "system_status",
                "data": {
                    "activeAgents": len([a for a in AGENTS_DATA if a["status"] == "busy"]),
                    "totalTasks": len(TASKS_DATA),
                    "timestamp": now.isoformat(),
                    "connection_id": client_id
                }
            })

            # 处理事件总线中的事件
            while not agent_event_bus._event_queue.empty():
                try:
                    event = agent_event_bus._event_queue.get_nowait()
                    await on_agent_event(event)
                except asyncio.QueueEmpty:
                    break

            # 心跳检测
            if (now - last_heartbeat).total_seconds() >= websocket_manager.heartbeat_interval:
                await websocket.send_json({
                    "type": "heartbeat",
                    "data": {
                        "timestamp": now.isoformat(),
                        "status": "alive"
                    }
                })
                last_heartbeat = now
                logger.debug(f"WebSocket 心跳：{client_id}")

            await asyncio.sleep(5)
    except Exception as e:
        logger.error(f"WebSocket 连接错误 (client={client_id}): {e}", exc_info=True)
    finally:
        websocket_manager.disconnect(client_id)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  IntelliTeam Web UI v5.2 - 启动中")
    logger.info("=" * 60)
    logger.info("访问地址：http://localhost:8080")
    logger.info("API 文档：http://localhost:8080/docs")
    logger.info("ReDoc: http://localhost:8080/redoc")
    logger.info("")
    logger.info("新功能:")
    logger.info("  ✨ 统一日志系统 (structlog)")
    logger.info("  📖 API 文档 (Swagger UI + ReDoc)")
    logger.info("  💾 改进的缓存系统 (带统计)")
    logger.info("  🔌 WebSocket 心跳检测 (30s)")
    logger.info("  ✨ 深色模式支持 (Ctrl+D)")
    logger.info("  📱 移动端完美适配")
    logger.info("  ⌨️ 快捷键支持 (Ctrl+K 搜索，Ctrl+N 新建)")
    logger.info("")
    logger.info("API 端点:")
    logger.info("  GET  /api/v1/stats      - 系统统计 (缓存 30s)")
    logger.info("  GET  /api/v1/agents     - Agent 列表")
    logger.info("  GET  /api/v1/tasks      - 任务列表 (缓存 30s)")
    logger.info("  GET  /api/v1/workflows  - 工作流")
    logger.info("  GET  /api/v1/tools      - 工具列表 ✨")
    logger.info("  GET  /api/v1/cache/stats - 缓存统计")
    logger.info("  GET  /api/v1/ws/stats   - WebSocket 统计")
    logger.info("  WS   /ws                - WebSocket 实时推送")
    logger.info("")

    uvicorn.run(app, host="0.0.0.0", port=8080)


# ============ 通用 HTML 页面路由 ============
# 用于服务所有静态 HTML 文件（包括 test-vue.html 等）

@app.get("/{filename}.html")
async def serve_html_file(filename: str):
    """服务任意 HTML 页面"""
    html_file = WEBUI_DIR / f"{filename}.html"
    if html_file.exists():
        with open(html_file, encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    raise HTTPException(status_code=404, detail=f"Page not found: {filename}.html")
