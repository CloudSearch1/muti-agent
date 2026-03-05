"""
IntelliTeam Web UI Server v3.0

新增功能：
- WebSocket 实时推送
- 任务评论系统
- 文件上传功能
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import uvicorn
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import uuid
import os
import json

app = FastAPI(title="IntelliTeam Web UI API v3.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建上传目录
UPLOAD_DIR = "webui/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ===========================================
# WebSocket 连接管理器
# ===========================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"🔌 WebSocket 连接成功，当前连接数：{len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"🔌 WebSocket 断开连接，当前连接数：{len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息给所有连接的客户端"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        # 清理断开的连接
        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except:
            self.disconnect(websocket)

manager = ConnectionManager()

# ===========================================
# 数据模型
# ===========================================

class TaskCreate(BaseModel):
    title: str
    description: str
    priority: str = "normal"
    agent: str = "Coder"
    assignee: str = ""

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None

class CommentCreate(BaseModel):
    task_id: str
    content: str
    author: str = "用户"

class LogCreate(BaseModel):
    level: str
    agent: str
    message: str

# ===========================================
# 模拟数据库
# ===========================================

_tasks_db: Dict[str, dict] = {
    "1": {
        "id": "1",
        "title": "创建用户管理 API",
        "description": "实现用户注册、登录、权限管理等功能",
        "priority": "high",
        "status": "in_progress",
        "assignee": "张三",
        "agent": "Coder",
        "created_at": "2026-03-05 08:30:00",
        "updated_at": "2026-03-05 08:55:00",
        "progress": 65,
        "files": [],
        "comments": [
            {"id": "c1", "task_id": "1", "content": "这个任务很重要，优先处理", "author": "项目经理", "created_at": "2026-03-05 08:35:00"},
            {"id": "c2", "task_id": "1", "content": "收到，已经开始开发", "author": "张三", "created_at": "2026-03-05 08:40:00"}
        ]
    },
    "2": {
        "id": "2",
        "title": "数据库设计",
        "description": "设计用户表和权限表结构",
        "priority": "normal",
        "status": "completed",
        "assignee": "李四",
        "agent": "Architect",
        "created_at": "2026-03-05 07:15:00",
        "updated_at": "2026-03-05 08:00:00",
        "progress": 100,
        "files": [{"id": "f1", "name": "数据库设计文档.pdf", "size": 1024000, "uploaded_at": "2026-03-05 07:30:00"}],
        "comments": []
    }
}

_agents_db: Dict[str, dict] = {
    "Planner": {
        "name": "Planner",
        "role": "任务规划师",
        "icon": "fas fa-chess",
        "description": "负责任务分解和优先级排序",
        "status": "idle",
        "tasks_completed": 45,
        "avg_time": 2.3,
        "success_rate": 98,
        "current_load": 0,
        "max_load": 5
    },
    "Architect": {
        "name": "Architect",
        "role": "系统架构师",
        "icon": "fas fa-building",
        "description": "负责系统架构设计和技术选型",
        "status": "busy",
        "tasks_completed": 38,
        "avg_time": 5.7,
        "success_rate": 96,
        "current_load": 2,
        "max_load": 3
    },
    "Coder": {
        "name": "Coder",
        "role": "代码工程师",
        "icon": "fas fa-laptop-code",
        "description": "负责代码实现和功能开发",
        "status": "busy",
        "tasks_completed": 89,
        "avg_time": 8.2,
        "success_rate": 94,
        "current_load": 3,
        "max_load": 5
    },
    "Tester": {
        "name": "Tester",
        "role": "测试工程师",
        "icon": "fas fa-bug",
        "description": "负责测试用例和质量保障",
        "status": "idle",
        "tasks_completed": 67,
        "avg_time": 4.5,
        "success_rate": 97,
        "current_load": 1,
        "max_load": 5
    },
    "DocWriter": {
        "name": "DocWriter",
        "role": "文档工程师",
        "icon": "fas fa-file-alt",
        "description": "负责技术文档编写",
        "status": "idle",
        "tasks_completed": 52,
        "avg_time": 3.8,
        "success_rate": 99,
        "current_load": 0,
        "max_load": 4
    },
    "Reviewer": {
        "name": "Reviewer",
        "role": "代码审查员",
        "icon": "fas fa-search",
        "description": "负责代码审查和质量检查",
        "status": "idle",
        "tasks_completed": 34,
        "avg_time": 3.2,
        "success_rate": 95,
        "current_load": 0,
        "max_load": 4
    }
}

_logs_db: List[dict] = [
    {"id": "1", "time": "08:57:32", "level": "info", "agent": "Planner", "message": "开始分析新任务：用户管理 API"},
    {"id": "2", "time": "08:57:35", "level": "success", "agent": "Planner", "message": "任务分解完成，共 5 个子任务"},
    {"id": "3", "time": "08:57:40", "level": "info", "agent": "Architect", "message": "接收任务，开始架构设计"},
    {"id": "4", "time": "08:58:15", "level": "warning", "agent": "Architect", "message": "检测到潜在的数据库性能问题"},
    {"id": "5", "time": "08:58:30", "level": "info", "agent": "Coder", "message": "开始编写用户模型代码"},
    {"id": "6", "time": "08:59:00", "level": "success", "agent": "Coder", "message": "用户模型创建成功"},
    {"id": "7", "time": "08:59:15", "level": "info", "agent": "Coder", "message": "开始实现 API 接口"},
    {"id": "8", "time": "08:59:45", "level": "error", "agent": "Tester", "message": "测试环境连接失败，重试中..."}
]

# 模型配置
_available_models: List[dict] = [
    {"id": "qwen3.5-plus", "name": "通义千问 3.5 Plus", "provider": "阿里云", "speed": 3, "intelligence": 4, "cost": 2, "recommended": True},
    {"id": "qwen-max", "name": "通义千问 Max", "provider": "阿里云", "speed": 2, "intelligence": 5, "cost": 3, "recommended": False},
    {"id": "qwen-plus", "name": "通义千问 Plus", "provider": "阿里云", "speed": 3, "intelligence": 3, "cost": 2, "recommended": False},
    {"id": "qwen-turbo", "name": "通义千问 Turbo", "provider": "阿里云", "speed": 4, "intelligence": 2, "cost": 1, "recommended": False},
    {"id": "gpt-4", "name": "GPT-4", "provider": "OpenAI", "speed": 2, "intelligence": 5, "cost": 4, "recommended": False},
    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "OpenAI", "speed": 3, "intelligence": 4, "cost": 3, "recommended": False},
    {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "provider": "OpenAI", "speed": 4, "intelligence": 3, "cost": 2, "recommended": False}
]

_current_model: str = "qwen3.5-plus"

_start_time = datetime.now() - timedelta(hours=2, minutes=35)

# ===========================================
# WebSocket 端点
# ===========================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接"""
    await manager.connect(websocket)
    try:
        while True:
            # 接收客户端消息（心跳等）
            data = await websocket.receive_text()
            # 可以处理客户端消息
            if data == "ping":
                await manager.send_personal(websocket, {"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({"type": "user_left", "message": "有用户断开连接"})

# ===========================================
# 系统 API
# ===========================================

@app.get("/api/v1/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime": str(datetime.now() - _start_time),
        "websocket_connections": len(manager.active_connections),
        "current_model": _current_model
    }

# ===========================================
# 模型管理 API
# ===========================================

@app.get("/api/v1/models")
async def get_models():
    """获取可用模型列表"""
    return {
        "models": _available_models,
        "current_model": _current_model
    }

@app.get("/api/v1/models/current")
async def get_current_model():
    """获取当前使用的模型"""
    return {
        "model": _current_model,
        "model_info": next((m for m in _available_models if m["id"] == _current_model), None)
    }

@app.post("/api/v1/models/switch")
async def switch_model(model_id: str):
    """切换模型"""
    global _current_model
    
    model = next((m for m in _available_models if m["id"] == model_id), None)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    old_model = _current_model
    _current_model = model_id
    
    # 添加日志
    add_log("info", "System", f"模型切换：{old_model} -> {model_id}")
    
    # WebSocket 广播
    await manager.broadcast({
        "type": "model_switched",
        "old_model": old_model,
        "new_model": model_id,
        "model_info": model
    })
    
    return {
        "success": True,
        "old_model": old_model,
        "new_model": model_id,
        "model_info": model
    }

@app.get("/api/v1/stats")
async def get_stats():
    """获取系统统计"""
    total_tasks = len(_tasks_db)
    completed_tasks = len([t for t in _tasks_db.values() if t["status"] == "completed"])
    completion_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0)
    
    active_agents = len([a for a in _agents_db.values() if a["status"] == "busy"])
    
    uptime = datetime.now() - _start_time
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    
    return {
        "totalTasks": total_tasks,
        "activeAgents": active_agents,
        "completionRate": completion_rate,
        "uptime": f"{hours} 小时 {minutes} 分",
        "timestamp": datetime.now().isoformat(),
        "websocketConnections": len(manager.active_connections)
    }

# ===========================================
# 任务 API
# ===========================================

@app.get("/api/v1/tasks")
async def get_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
):
    """获取任务列表"""
    tasks = list(_tasks_db.values())
    
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    
    if priority:
        tasks = [t for t in tasks if t["priority"] == priority]
    
    if search:
        search_lower = search.lower()
        tasks = [t for t in tasks if search_lower in t["title"].lower() or search_lower in t["description"].lower()]
    
    tasks = tasks[:limit]
    
    return [
        {
            "id": t["id"],
            "title": t["title"],
            "description": t["description"],
            "priority": t["priority"],
            "priorityText": get_priority_text(t["priority"]),
            "status": t["status"],
            "statusText": get_status_text(t["status"]),
            "assignee": t["assignee"],
            "agent": t["agent"],
            "createdAt": t["created_at"],
            "progress": t.get("progress", 0),
            "filesCount": len(t.get("files", [])),
            "commentsCount": len(t.get("comments", []))
        }
        for t in tasks
    ]

@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    task = _tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task

@app.post("/api/v1/tasks")
async def create_task(task: TaskCreate):
    """创建新任务"""
    task_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    new_task = {
        "id": task_id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "status": "pending",
        "assignee": task.assignee or "未分配",
        "agent": task.agent,
        "created_at": now,
        "updated_at": now,
        "progress": 0,
        "logs": [],
        "files": [],
        "comments": []
    }
    
    _tasks_db[task_id] = new_task
    
    # 添加日志
    add_log("info", "System", f"创建新任务：{task.title}")
    
    # WebSocket 广播
    await manager.broadcast({
        "type": "task_created",
        "task": new_task
    })
    
    return new_task

@app.put("/api/v1/tasks/{task_id}")
async def update_task(task_id: str, update: TaskUpdate):
    """更新任务"""
    task = _tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    old_status = task["status"]
    
    if update.title:
        task["title"] = update.title
    if update.description:
        task["description"] = update.description
    if update.priority:
        task["priority"] = update.priority
    if update.status:
        task["status"] = update.status
    if update.progress is not None:
        task["progress"] = update.progress
    
    task["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # WebSocket 广播
    await manager.broadcast({
        "type": "task_updated",
        "task": task
    })
    
    return task

@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    if task_id not in _tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = _tasks_db[task_id]
    del _tasks_db[task_id]
    
    add_log("warning", "System", f"删除任务：{task['title']}")
    
    await manager.broadcast({
        "type": "task_deleted",
        "task_id": task_id
    })
    
    return {"status": "deleted", "task_id": task_id}

@app.get("/api/v1/tasks/recent")
async def get_recent_tasks(limit: int = 10):
    """获取最近任务"""
    tasks = sorted(_tasks_db.values(), key=lambda x: x["created_at"], reverse=True)[:limit]
    
    return [
        {
            "id": t["id"],
            "title": t["title"],
            "description": t["description"][:50] + "..." if len(t["description"]) > 50 else t["description"],
            "status": t["status"],
            "agent": t["agent"],
            "time": get_relative_time(t["created_at"])
        }
        for t in tasks
    ]

# ===========================================
# 评论系统 API
# ===========================================

@app.get("/api/v1/tasks/{task_id}/comments")
async def get_comments(task_id: str):
    """获取任务评论列表"""
    task = _tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task.get("comments", [])

@app.post("/api/v1/tasks/{task_id}/comments")
async def create_comment(task_id: str, comment: CommentCreate):
    """创建任务评论"""
    task = _tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    comment_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    new_comment = {
        "id": comment_id,
        "task_id": task_id,
        "content": comment.content,
        "author": comment.author,
        "created_at": now
    }
    
    if "comments" not in task:
        task["comments"] = []
    
    task["comments"].append(new_comment)
    task["updated_at"] = now
    
    # WebSocket 广播
    await manager.broadcast({
        "type": "comment_created",
        "task_id": task_id,
        "comment": new_comment
    })
    
    return new_comment

@app.delete("/api/v1/comments/{comment_id}")
async def delete_comment(comment_id: str, task_id: str):
    """删除评论"""
    task = _tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    comments = task.get("comments", [])
    task["comments"] = [c for c in comments if c["id"] != comment_id]
    
    await manager.broadcast({
        "type": "comment_deleted",
        "task_id": task_id,
        "comment_id": comment_id
    })
    
    return {"status": "deleted", "comment_id": comment_id}

# ===========================================
# 文件上传 API
# ===========================================

@app.post("/api/v1/tasks/{task_id}/files")
async def upload_file(task_id: str, file: UploadFile = File(...)):
    """上传任务附件"""
    task = _tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 生成唯一文件名
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
    saved_filename = f"{file_id}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)
    
    # 保存文件
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 记录文件信息
    file_info = {
        "id": file_id,
        "name": file.filename,
        "size": len(content),
        "type": file.content_type or "application/octet-stream",
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "uploaded_by": "用户"
    }
    
    if "files" not in task:
        task["files"] = []
    
    task["files"].append(file_info)
    task["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # WebSocket 广播
    await manager.broadcast({
        "type": "file_uploaded",
        "task_id": task_id,
        "file": file_info
    })
    
    return file_info

@app.get("/api/v1/tasks/{task_id}/files")
async def get_files(task_id: str):
    """获取任务文件列表"""
    task = _tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task.get("files", [])

@app.get("/api/v1/files/{file_id}")
async def download_file(file_id: str):
    """下载文件"""
    file_path = os.path.join(UPLOAD_DIR, file_id)
    
    # 查找文件信息
    for task in _tasks_db.values():
        for file_info in task.get("files", []):
            if file_info["id"] == file_id:
                return FileResponse(
                    file_path,
                    filename=file_info["name"],
                    media_type=file_info.get("type", "application/octet-stream")
                )
    
    raise HTTPException(status_code=404, detail="File not found")

@app.delete("/api/v1/files/{file_id}")
async def delete_file(file_id: str, task_id: str):
    """删除文件"""
    task = _tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    files = task.get("files", [])
    file_info = next((f for f in files if f["id"] == file_id), None)
    
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")
    
    # 删除物理文件
    file_path = os.path.join(UPLOAD_DIR, file_id)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # 删除记录
    task["files"] = [f for f in files if f["id"] != file_id]
    
    await manager.broadcast({
        "type": "file_deleted",
        "task_id": task_id,
        "file_id": file_id
    })
    
    return {"status": "deleted", "file_id": file_id}

# ===========================================
# Agent API
# ===========================================

@app.get("/api/v1/agents")
async def get_agents():
    """获取 Agent 列表"""
    return list(_agents_db.values())

@app.get("/api/v1/agents/{agent_name}")
async def get_agent(agent_name: str):
    """获取 Agent 详情"""
    agent = _agents_db.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

# ===========================================
# 日志 API
# ===========================================

@app.get("/api/v1/logs")
async def get_logs(
    level: Optional[str] = None,
    agent: Optional[str] = None,
    limit: int = 100
):
    """获取日志列表"""
    logs = _logs_db.copy()
    
    if level:
        logs = [l for l in logs if l["level"] == level]
    
    if agent:
        logs = [l for l in logs if l["agent"] == agent]
    
    logs = logs[-limit:]
    
    return logs

@app.post("/api/v1/logs")
async def create_log(log: LogCreate):
    """创建日志"""
    log_entry = {
        "id": str(uuid.uuid4()),
        "time": datetime.now().strftime("%H:%M:%S"),
        "level": log.level,
        "agent": log.agent,
        "message": log.message
    }
    
    _logs_db.append(log_entry)
    
    # WebSocket 广播
    await manager.broadcast({
        "type": "log_created",
        "log": log_entry
    })
    
    return log_entry

@app.get("/api/v1/logs/stats")
async def get_logs_stats():
    """获取日志统计"""
    return {
        "total": len(_logs_db),
        "info": len([l for l in _logs_db if l["level"] == "info"]),
        "success": len([l for l in _logs_db if l["level"] == "success"]),
        "warning": len([l for l in _logs_db if l["level"] == "warning"]),
        "error": len([l for l in _logs_db if l["level"] == "error"])
    }

@app.delete("/api/v1/logs")
async def clear_logs():
    """清空日志"""
    _logs_db.clear()
    return {"status": "cleared"}

# ===========================================
# 工作流 API
# ===========================================

@app.get("/api/v1/workflows")
async def get_workflows():
    """获取工作流列表"""
    return [
        {"id": "standard", "name": "标准研发流程", "steps": 5},
        {"id": "quick", "name": "快速迭代流程", "steps": 3},
        {"id": "hotfix", "name": "紧急修复流程", "steps": 4}
    ]

@app.get("/api/v1/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """获取工作流详情"""
    workflows = {
        "standard": [
            {"name": "需求分析", "agent": "Planner", "icon": "fas fa-clipboard-list", "color": "bg-blue-500"},
            {"name": "架构设计", "agent": "Architect", "icon": "fas fa-sitemap", "color": "bg-purple-500"},
            {"name": "代码开发", "agent": "Coder", "icon": "fas fa-code", "color": "bg-green-500"},
            {"name": "测试", "agent": "Tester", "icon": "fas fa-vial", "color": "bg-yellow-500"},
            {"name": "文档", "agent": "DocWriter", "icon": "fas fa-file-alt", "color": "bg-red-500"}
        ],
        "quick": [
            {"name": "快速设计", "agent": "Architect", "icon": "fas fa-bolt", "color": "bg-purple-500"},
            {"name": "快速开发", "agent": "Coder", "icon": "fas fa-code", "color": "bg-green-500"},
            {"name": "快速测试", "agent": "Tester", "icon": "fas fa-vial", "color": "bg-yellow-500"}
        ],
        "hotfix": [
            {"name": "问题分析", "agent": "Planner", "icon": "fas fa-bug", "color": "bg-red-500"},
            {"name": "紧急修复", "agent": "Coder", "icon": "fas fa-code", "color": "bg-orange-500"},
            {"name": "快速测试", "agent": "Tester", "icon": "fas fa-vial", "color": "bg-yellow-500"},
            {"name": "部署上线", "agent": "Architect", "icon": "fas fa-rocket", "color": "bg-blue-500"}
        ]
    }
    
    steps = workflows.get(workflow_id, workflows["standard"])
    
    return {
        "id": workflow_id,
        "name": {"standard": "标准研发流程", "quick": "快速迭代流程", "hotfix": "紧急修复流程"}.get(workflow_id, "标准研发流程"),
        "steps": steps
    }

@app.get("/api/v1/workflows/history")
async def get_workflow_history():
    """获取工作流历史"""
    return [
        {"id": "1", "taskTitle": "用户登录功能", "steps": 5, "duration": "2.5 小时", "status": "success", "time": "2 小时前"},
        {"id": "2", "taskTitle": "数据库优化", "steps": 4, "duration": "1.8 小时", "status": "success", "time": "5 小时前"},
        {"id": "3", "taskTitle": "API 接口开发", "steps": 5, "duration": "3.2 小时", "status": "success", "time": "昨天"}
    ]

# ===========================================
# 辅助函数
# ===========================================

def get_priority_text(priority: str) -> str:
    texts = {
        "low": "低优先级",
        "normal": "中优先级",
        "high": "高优先级",
        "critical": "紧急"
    }
    return texts.get(priority, priority)

def get_status_text(status: str) -> str:
    texts = {
        "pending": "待处理",
        "in_progress": "进行中",
        "completed": "已完成",
        "failed": "失败"
    }
    return texts.get(status, status)

def get_relative_time(time_str: str) -> str:
    try:
        task_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        diff = now - task_time
        
        seconds = diff.total_seconds()
        if seconds < 60:
            return "刚刚"
        elif seconds < 3600:
            return f"{int(seconds // 60)} 分钟前"
        elif seconds < 86400:
            return f"{int(seconds // 3600)} 小时前"
        else:
            return f"{int(seconds // 86400)} 天前"
    except:
        return time_str

def add_log(level: str, agent: str, message: str):
    log_entry = {
        "id": str(uuid.uuid4()),
        "time": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "agent": agent,
        "message": message
    }
    _logs_db.append(log_entry)

# ===========================================
# 页面路由
# ===========================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回 v3.0 UI"""
    return FileResponse("webui/index_v3.html")

@app.get("/v2")
async def v2():
    """返回 v2.0 UI"""
    return FileResponse("webui/index_v2.html")

@app.get("/classic")
async def classic():
    """返回经典版 UI"""
    return FileResponse("webui/index.html")

# ===========================================
# 启动
# ===========================================

if __name__ == "__main__":
    print("🚀 Starting IntelliTeam Web UI Server v3.0...")
    print("🌐 Dashboard: http://localhost:3000")
    print("📚 API Docs: http://localhost:3000/docs")
    print("💚 Health: http://localhost:3000/api/v1/health")
    print("🔌 WebSocket: ws://localhost:3000/ws")
    print("\n✨ New Features:")
    print("   - WebSocket Real-time Push")
    print("   - Task Comment System")
    print("   - File Upload Support")
    uvicorn.run(app, host="0.0.0.0", port=3000)
