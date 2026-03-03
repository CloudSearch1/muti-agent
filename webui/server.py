"""
Web UI 服务器

提供静态文件服务和 API 代理
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pathlib import Path


app = FastAPI(title="IntelliTeam Web UI")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件目录
static_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """返回主页面"""
    index_path = static_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    
    return FileResponse(index_path)


@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    return {
        "totalTasks": 156,
        "activeAgents": 6,
        "completionRate": 93,
        "systemStatus": "running"
    }


@app.get("/api/agents")
async def get_agents():
    """获取 Agent 列表"""
    return [
        {
            "name": "Planner",
            "role": "任务规划师",
            "icon": "fas fa-chess",
            "description": "负责任务分解和优先级排序",
            "status": "idle",
            "tasksCompleted": 45,
            "avgTime": 2.3,
            "successRate": 98
        },
        {
            "name": "Architect",
            "role": "系统架构师",
            "icon": "fas fa-building",
            "description": "负责系统架构设计和技术选型",
            "status": "busy",
            "tasksCompleted": 38,
            "avgTime": 5.7,
            "successRate": 96
        },
        {
            "name": "Coder",
            "role": "代码工程师",
            "icon": "fas fa-laptop-code",
            "description": "负责代码实现和功能开发",
            "status": "busy",
            "tasksCompleted": 89,
            "avgTime": 8.2,
            "successRate": 94
        },
        {
            "name": "Tester",
            "role": "测试工程师",
            "icon": "fas fa-bug",
            "description": "负责测试用例和质量保障",
            "status": "idle",
            "tasksCompleted": 67,
            "avgTime": 4.5,
            "successRate": 97
        },
        {
            "name": "DocWriter",
            "role": "文档工程师",
            "icon": "fas fa-file-alt",
            "description": "负责技术文档编写",
            "status": "idle",
            "tasksCompleted": 52,
            "avgTime": 3.8,
            "successRate": 99
        }
    ]


@app.get("/api/tasks")
async def get_tasks():
    """获取任务列表"""
    return [
        {
            "id": 1,
            "title": "创建用户管理 API",
            "description": "实现用户注册、登录、权限管理等功能",
            "priority": "high",
            "status": "in_progress",
            "assignee": "张三",
            "agent": "Coder",
            "createdAt": "2026-03-03 10:30"
        },
        {
            "id": 2,
            "title": "数据库设计",
            "description": "设计用户表和权限表结构",
            "priority": "normal",
            "status": "completed",
            "assignee": "李四",
            "agent": "Architect",
            "createdAt": "2026-03-03 09:15"
        }
    ]


@app.post("/api/tasks")
async def create_task(request: Request):
    """创建新任务"""
    data = await request.json()
    
    # TODO: 实际调用后端 API 创建任务
    print(f"创建任务：{data}")
    
    return {
        "success": True,
        "message": "任务创建成功",
        "taskId": "task-" + str(hash(str(data)))[-8:]
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "IntelliTeam Web UI"
    }


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("  IntelliTeam Web UI 服务器")
    print("=" * 60)
    print()
    print("访问地址：http://localhost:3000")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=3000)
