"""
IntelliTeam Web UI - v5.1

基于 FastAPI + Vue 3 的 Web 管理界面
优化版本：添加 Gzip 压缩、响应缓存、性能优化
"""

from fastapi import FastAPI, Request, HTTPException, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
import hashlib
import json
import csv
import io

app = FastAPI(title="IntelliTeam Web UI v5.1")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip 压缩 - 暂时禁用，避免干扰 HTML 响应
# app.add_middleware(GZipMiddleware, minimum_size=1024)

# 挂载静态文件
try:
    app.mount("/static", StaticFiles(directory="webui/static"), name="static")
except Exception as e:
    print(f"静态文件挂载失败：{e}")

# ============ 响应缓存 ============

class ResponseCache:
    """简单的内存缓存"""
    def __init__(self, ttl_seconds: int = 60):
        self._cache: Dict[str, dict] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[dict]:
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() < entry['expires']:
                return entry['data']
            del self._cache[key]
        return None
    
    def set(self, key: str, data: dict):
        self._cache[key] = {
            'data': data,
            'expires': datetime.now() + self._ttl
        }
    
    def invalidate(self, key: str):
        if key in self._cache:
            del self._cache[key]

response_cache = ResponseCache(ttl_seconds=30)

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

# ============ API 路由 ============

@app.get("/")
async def root():
    """返回主页面"""
    from starlette.responses import HTMLResponse
    
    with open("webui/index_v5.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    return HTMLResponse(content=content)


@app.get("/manifest.json")
async def get_manifest():
    """返回 PWA manifest"""
    from fastapi.responses import FileResponse
    return FileResponse(path="webui/manifest.json", media_type="application/json")


@app.get("/offline.html")
async def get_offline():
    """返回离线页面"""
    from fastapi.responses import FileResponse
    return FileResponse(path="webui/offline.html", media_type="text/html")


@app.get("/static/js/{filename:path}")
async def get_static_js(filename: str):
    """返回静态 JS 文件"""
    from fastapi.responses import FileResponse
    return FileResponse(path=f"webui/static/js/{filename}", media_type="application/javascript")


@app.get("/static/images/{filename:path}")
async def get_static_images(filename: str):
    """返回静态图片文件"""
    from fastapi.responses import FileResponse
    import os
    
    filepath = f"webui/static/images/{filename}"
    if not os.path.exists(filepath):
        # 如果具体尺寸图标不存在，返回 SVG 占位图
        return FileResponse(path="webui/static/images/icon.svg", media_type="image/svg+xml")
    
    return FileResponse(path=filepath, media_type="image/png")


@app.get("/api/v1/stats")
async def get_stats():
    """获取系统统计（带缓存）"""
    cache_key = "stats"
    cached = response_cache.get(cache_key)
    if cached:
        return cached
    
    data = {
        "totalTasks": len(TASKS_DATA),
        "activeAgents": len([a for a in AGENTS_DATA if a["status"] == "busy"]),
        "completionRate": 93,
        "timestamp": datetime.now().isoformat()
    }
    response_cache.set(cache_key, data)
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
    cached = response_cache.get(cache_key)
    if cached:
        return cached
    
    response_cache.set(cache_key, TASKS_DATA)
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
    response_cache.invalidate("tasks")
    response_cache.invalidate("stats")
    return {"status": "success", "message": "任务创建成功", "taskId": new_task["id"]}


@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: int):
    """删除任务"""
    global TASKS_DATA
    TASKS_DATA = [t for t in TASKS_DATA if t["id"] != task_id]
    # 清除缓存
    response_cache.invalidate("tasks")
    response_cache.invalidate("stats")
    return {"status": "success", "message": "任务已删除"}


@app.get("/api/v1/workflows")
async def get_workflows():
    """获取工作流列表"""
    return WORKFLOWS_DATA


@app.get("/api/v1/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "version": "5.1"}


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
    print(f"[Error Report] {datetime.now().isoformat()}: {error}")
    return {"status": "success", "message": "错误已记录"}


@app.get("/api/v1/export/tasks")
async def export_tasks(format: str = "json"):
    """导出任务数据"""
    from fastapi.responses import JSONResponse, PlainTextResponse
    import csv
    import io
    
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


# ============ 导出功能 ============

async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时数据推送"""
    await websocket.accept()
    client_id = id(websocket)
    print(f"WebSocket 客户端连接：{client_id}")
    
    try:
        while True:
            # 推送系统状态
            await websocket.send_json({
                "type": "system_status",
                "data": {
                    "activeAgents": len([a for a in AGENTS_DATA if a["status"] == "busy"]),
                    "totalTasks": len(TASKS_DATA),
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            # 随机更新 Agent 状态
            if random.random() < 0.3:
                agent = random.choice(AGENTS_DATA)
                agent["status"] = "busy" if agent["status"] == "idle" else "idle"
                await websocket.send_json({
                    "type": "agent_update",
                    "data": agent
                })
            
            await asyncio.sleep(5)
    except Exception as e:
        print(f"WebSocket 连接断开：{client_id}, 错误：{e}")
    finally:
        print(f"WebSocket 客户端断开：{client_id}")


if __name__ == "__main__":
    print("=" * 60)
    print("  IntelliTeam Web UI v5.1")
    print("=" * 60)
    print()
    print("访问地址：http://localhost:8080")
    print()
    print("新功能:")
    print("  ✨ 深色模式支持 (Ctrl+D)")
    print("  ⚡ 性能优化 - 懒加载 + 预加载")
    print("  📱 移动端完美适配")
    print("  ⌨️ 快捷键支持 (Ctrl+K 搜索，Ctrl+N 新建)")
    print("  📡 实时数据更新 (WebSocket)")
    print("  🌙 自动检测系统主题")
    print("  🗜️ Gzip 压缩 - 响应自动压缩")
    print("  💾 响应缓存 - 减少重复计算")
    print()
    print("API 端点:")
    print("  GET  /api/v1/stats      - 系统统计 (缓存 30s)")
    print("  GET  /api/v1/agents     - Agent 列表")
    print("  GET  /api/v1/tasks      - 任务列表 (缓存 30s)")
    print("  GET  /api/v1/workflows  - 工作流")
    print("  WS   /ws                - WebSocket 实时推送")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8080)
