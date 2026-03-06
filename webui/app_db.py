"""
IntelliTeam Web UI - v6.0 (数据库版本)

基于 FastAPI + Vue 3 + SQLAlchemy 的 Web 管理界面
支持真实数据库持久化
"""

import asyncio
import csv
import io
import logging
import random
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_database_manager, get_db_session, init_database
from src.db import crud
from src.db.models import TaskModel, AgentModel

# 配置结构化日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============ 生命周期管理 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    logger.info("应用启动中，初始化数据库...")
    await init_database()
    logger.info("数据库初始化完成")
    
    # 初始化示例数据（如果数据库为空）
    db_manager = get_database_manager()
    async with db_manager.async_session_maker() as session:
        agents = await crud.get_all_agents(session)
        if not agents:
            logger.info("数据库为空，初始化默认数据...")
            await crud.init_default_agents(session)
            await crud.init_sample_data(session)
            logger.info("默认数据初始化完成")
    
    yield
    
    # 关闭时清理资源
    logger.info("应用关闭中...")
    await db_manager.disconnect()
    logger.info("应用已关闭")


app = FastAPI(
    title="IntelliTeam Web UI v6.0",
    description="智能研发协作平台 - Web 管理界面（数据库版本）",
    version="6.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
try:
    app.mount("/static", StaticFiles(directory="webui/static"), name="static")
    logger.info("静态文件挂载成功：webui/static")
except Exception as e:
    logger.error(f"静态文件挂载失败：{e}", exc_info=True)


# ============ 依赖注入 ============

async def get_db() -> AsyncSession:
    """获取数据库会话（依赖注入）"""
    async for session in get_db_session():
        yield session


# ============ 响应缓存 ============

class ResponseCache:
    """
    内存缓存实现（生产环境建议升级为 Redis）
    """
    def __init__(self, ttl_seconds: int = 60):
        self._cache: dict[str, dict] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._hits = 0
        self._misses = 0
        logger.info(f"响应缓存初始化完成，TTL={ttl_seconds}秒")

    def get(self, key: str) -> dict | None:
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now(timezone.utc).astimezone() < entry['expires']:
                self._hits += 1
                return entry['data']
            del self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, data: dict):
        self._cache[key] = {
            'data': data,
            'expires': datetime.now(timezone.utc).astimezone() + self._ttl
        }

    def invalidate(self, key: str):
        if key in self._cache:
            del self._cache[key]

    def get_stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%"
        }

response_cache = ResponseCache(ttl_seconds=30)


# ============ WebSocket 管理 ============

class WebSocketManager:
    """WebSocket 连接管理器"""
    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}
        self.heartbeat_interval = 30
        logger.info("WebSocket 管理器初始化完成")
    
    async def connect(self, websocket: WebSocket, client_id: int):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket 客户端连接：{client_id}")
    
    def disconnect(self, client_id: int):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket 客户端断开：{client_id}")
    
    async def broadcast(self, message: dict):
        disconnected = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"广播消息失败 (client={client_id}): {e}")
                disconnected.append(client_id)
        for client_id in disconnected:
            self.disconnect(client_id)
    
    def get_stats(self) -> dict:
        return {
            "active_connections": len(self.active_connections),
            "connection_ids": list(self.active_connections.keys())
        }

websocket_manager = WebSocketManager()


# ============ 辅助函数 ============

def task_to_dict(task: TaskModel) -> dict:
    """将 TaskModel 转换为字典"""
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "priorityText": {
            "low": "低优先级",
            "normal": "中优先级",
            "high": "高优先级",
            "critical": "紧急"
        }.get(task.priority, "中优先级"),
        "status": task.status,
        "statusText": {
            "pending": "待处理",
            "in_progress": "进行中",
            "completed": "已完成"
        }.get(task.status, "待处理"),
        "assignee": task.assignee or "",
        "agent": task.agent or "",
        "createdAt": task.created_at.strftime("%Y-%m-%d %H:%M") if task.created_at else "",
        "time": "刚刚",
    }


def agent_to_dict(agent: AgentModel) -> dict:
    """将 AgentModel 转换为字典"""
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "icon": "fas fa-robot",
        "description": agent.description or "",
        "status": agent.status,
        "tasksCompleted": agent.tasks_completed,
        "avgTime": round(agent.avg_time, 1),
        "successRate": round(agent.success_rate, 1),
    }


# ============ API 路由 ============

@app.get("/")
async def root():
    """返回主页面"""
    from starlette.responses import HTMLResponse
    with open("webui/index_v5.html", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content, media_type="text/html; charset=utf-8")


@app.get("/manifest.json")
async def get_manifest():
    return FileResponse(path="webui/manifest.json", media_type="application/json")


@app.get("/offline.html")
async def get_offline():
    return FileResponse(path="webui/offline.html", media_type="text/html")


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "6.0.0",
        "database": "sqlite",
        "features": {
            "logging": "unified",
            "api_docs": "enabled",
            "cache_stats": "enabled",
            "websocket_heartbeat": "enabled",
            "database": "enabled"
        }
    }


@app.get("/api/v1/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """获取系统统计"""
    cache_key = "stats"
    cached = response_cache.get(cache_key)
    if cached:
        return cached

    stats = await crud.get_task_stats(db)
    agents = await crud.get_all_agents(db)
    active_agents = len([a for a in agents if a.status == "busy"])
    
    data = {
        "totalTasks": stats["total"],
        "completedTasks": stats["completed"],
        "inProgressTasks": stats["in_progress"],
        "pendingTasks": stats["pending"],
        "activeAgents": active_agents,
        "totalAgents": len(agents),
        "completionRate": round(stats["completed"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0,
        "timestamp": datetime.now().isoformat()
    }
    response_cache.set(cache_key, data)
    return data


@app.get("/api/v1/agents")
async def get_agents(db: AsyncSession = Depends(get_db)):
    """获取 Agent 列表"""
    agents = await crud.get_all_agents(db)
    return [agent_to_dict(agent) for agent in agents]


@app.get("/api/v1/tasks")
async def get_tasks(
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
):
    """获取任务列表"""
    cache_key = f"tasks_{limit}_{offset}"
    cached = response_cache.get(cache_key)
    if cached:
        return cached

    tasks = await crud.get_all_tasks(db, limit=limit, offset=offset)
    data = [task_to_dict(task) for task in tasks]
    response_cache.set(cache_key, data)
    return data


@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个任务"""
    task = await crud.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task_to_dict(task)


@app.post("/api/v1/tasks")
async def create_task(
    task_data: dict,
    db: AsyncSession = Depends(get_db),
):
    """创建新任务"""
    new_task = await crud.create_task(
        db,
        title=task_data.get("title", "新任务"),
        description=task_data.get("description", ""),
        priority=task_data.get("priority", "normal"),
        status=task_data.get("status", "pending"),
        assignee=task_data.get("assignee", ""),
        agent=task_data.get("agent", ""),
    )
    
    # 清除缓存
    response_cache.invalidate("stats")
    response_cache.invalidate(f"tasks_100_0")
    
    return {
        "status": "success",
        "message": "任务创建成功",
        "taskId": new_task.id,
        "task": task_to_dict(new_task)
    }


@app.put("/api/v1/tasks/{task_id}")
async def update_task(
    task_id: int,
    task_update: dict,
    db: AsyncSession = Depends(get_db),
):
    """更新任务"""
    updated_task = await crud.update_task(
        db,
        task_id,
        title=task_update.get("title"),
        description=task_update.get("description"),
        priority=task_update.get("priority"),
        status=task_update.get("status"),
        assignee=task_update.get("assignee"),
        agent=task_update.get("agent"),
    )
    
    if not updated_task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 清除缓存
    response_cache.invalidate("stats")
    response_cache.invalidate(f"tasks_100_0")
    
    return {
        "status": "success",
        "message": "任务已更新",
        "task": task_to_dict(updated_task)
    }


@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """删除任务"""
    deleted = await crud.delete_task(db, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 清除缓存
    response_cache.invalidate("stats")
    response_cache.invalidate(f"tasks_100_0")
    
    return {"status": "success", "message": "任务已删除"}


@app.get("/api/v1/workflows")
async def get_workflows(db: AsyncSession = Depends(get_db)):
    """获取工作流列表"""
    workflows = await crud.get_all_workflows(db)
    return [
        {
            "id": wf.id,
            "name": wf.name,
            "state": wf.state,
            "createdAt": wf.created_at.strftime("%Y-%m-%d %H:%M") if wf.created_at else "",
        }
        for wf in workflows
    ]


@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """获取缓存统计"""
    return response_cache.get_stats()


@app.get("/api/v1/ws/stats")
async def get_ws_stats():
    """获取 WebSocket 统计"""
    return websocket_manager.get_stats()


@app.get("/api/v1/error-log")
async def get_error_log():
    return {"errors": [], "total": 0, "timestamp": datetime.now().isoformat()}


@app.post("/api/v1/error-log")
async def report_error(error: dict):
    logger.error(f"[Error Report] {datetime.now().isoformat()}: {error}")
    return {"status": "success", "message": "错误已记录"}


@app.get("/api/v1/export/tasks")
async def export_tasks(
    format: str = "json",
    db: AsyncSession = Depends(get_db),
):
    """导出任务数据"""
    tasks = await crud.get_all_tasks(db)
    task_data = [task_to_dict(task) for task in tasks]
    
    if format == "json":
        return JSONResponse(content=task_data)
    elif format == "csv":
        output = io.StringIO()
        if task_data:
            writer = csv.DictWriter(output, fieldnames=task_data[0].keys())
            writer.writeheader()
            writer.writerows(task_data)
        return PlainTextResponse(content=output.getvalue(), media_type="text/csv")
    elif format == "markdown":
        md = "# 任务导出\n\n"
        md += "| ID | 标题 | 状态 | 优先级 | 负责人 | Agent |\n"
        md += "|---|---|---|---|---|---|\n"
        for task in task_data:
            md += f"| {task['id']} | {task['title']} | {task['statusText']} | {task['priorityText']} | {task['assignee']} | {task['agent']} |\n"
        return PlainTextResponse(content=md, media_type="text/markdown")
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")


# ============ WebSocket 端点 ============

async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时数据推送"""
    client_id = id(websocket)
    await websocket_manager.connect(websocket, client_id)
    
    last_heartbeat = datetime.now(timezone.utc).astimezone()
    
    try:
        while True:
            now = datetime.now(timezone.utc).astimezone()
            
            # 推送系统状态
            await websocket.send_json({
                "type": "system_status",
                "data": {
                    "activeAgents": 0,  # 从数据库获取
                    "totalTasks": 0,
                    "timestamp": now.isoformat(),
                    "connection_id": client_id
                }
            })
            
            # 心跳检测
            if (now - last_heartbeat).total_seconds() >= websocket_manager.heartbeat_interval:
                await websocket.send_json({
                    "type": "heartbeat",
                    "data": {"timestamp": now.isoformat(), "status": "alive"}
                })
                last_heartbeat = now
            
            await asyncio.sleep(5)
    except Exception as e:
        logger.error(f"WebSocket 连接错误 (client={client_id}): {e}", exc_info=True)
    finally:
        websocket_manager.disconnect(client_id)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  IntelliTeam Web UI v6.0 - 数据库版本")
    logger.info("=" * 60)
    logger.info("访问地址：http://localhost:8080")
    logger.info("API 文档：http://localhost:8080/docs")
    logger.info("ReDoc: http://localhost:8080/redoc")
    logger.info("")
    logger.info="新功能:")
    logger.info("  🗄️ SQLAlchemy 数据库支持")
    logger.info("  ✅ 真实数据持久化")
    logger.info("  📊 CRUD 操作完整实现")
    logger.info("  🔄 自动初始化示例数据")
    logger.info("  ✨ 统一日志系统")
    logger.info("  📖 API 文档 (Swagger + ReDoc)")
    logger.info("")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)
