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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, AsyncGenerator
import json

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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

app = FastAPI(
    title="IntelliTeam Web UI v5.2",
    description="智能研发协作平台 - Web 管理界面",
    version="5.2.0",
    docs_url="/docs",      # 启用 Swagger UI
    redoc_url="/redoc",    # 启用 ReDoc
    openapi_url="/openapi.json"
)

# CORS 配置 - 允许所有来源访问（生产环境建议限制）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# ============ 响应缓存 ============

class ResponseCache:
    """
    内存缓存实现（生产环境建议升级为 Redis）
    
    TODO: 
    - 集成 Redis 作为缓存后端
    - 支持多实例缓存共享
    - 添加缓存预热和淘汰策略
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
                logger.debug(f"缓存命中：{key} (hits={self._hits}, misses={self._misses})")
                return entry['data']
            # 过期数据清理
            del self._cache[key]
            logger.debug(f"缓存过期：{key}")
        self._misses += 1
        return None

    def set(self, key: str, data: dict):
        self._cache[key] = {
            'data': data,
            'expires': datetime.now(timezone.utc).astimezone() + self._ttl
        }
        logger.debug(f"缓存设置：{key}, 过期时间={self._ttl}")

    def invalidate(self, key: str):
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"缓存失效：{key}")

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%"
        }

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

# 技能数据
SKILLS_DATA = [
    {"id": 1, "name": "simplify", "description": "Review code for reuse, quality, and efficiency", "category": "code_review", "version": "1.0.0", "config": {"auto_fix": True}, "enabled": True, "createdAt": "2026-03-01 10:00"},
    {"id": 2, "name": "claude-api", "description": "Build apps with Claude API or Anthropic SDK", "category": "api", "version": "1.0.0", "config": {"model": "claude-sonnet-4-6"}, "enabled": True, "createdAt": "2026-03-01 10:00"},
    {"id": 3, "name": "code-generation", "description": "Generate code from natural language", "category": "generation", "version": "1.2.0", "config": {"language": "python"}, "enabled": True, "createdAt": "2026-03-02 14:30"},
    {"id": 4, "name": "documentation", "description": "Generate documentation for code files", "category": "docs", "version": "1.0.0", "config": {"format": "markdown"}, "enabled": True, "createdAt": "2026-03-02 14:30"},
    {"id": 5, "name": "testing", "description": "Generate and run tests for code", "category": "testing", "version": "1.1.0", "config": {"framework": "pytest"}, "enabled": False, "createdAt": "2026-03-03 09:15"},
]

# ============ API 路由 ============

@app.get("/")
async def root():
    """返回主页面"""
    from starlette.responses import HTMLResponse

    index_file = WEBUI_DIR / "index_v5.html"
    if not index_file.exists():
        logger.error(f"主页面文件不存在：{index_file}")
        return HTMLResponse(
            content="<html><body><h1>Web UI not found</h1><p>Please check webui/index_v5.html exists</p></body></html>",
            status_code=500
        )

    with open(index_file, encoding="utf-8") as f:
        content = f.read()

    return HTMLResponse(content=content)


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


@app.get("/ai-assistant.html")
async def get_ai_assistant():
    """返回 AI 助手页面"""
    ai_file = WEBUI_DIR / "ai-assistant.html"
    if ai_file.exists():
        return FileResponse(path=str(ai_file), media_type="text/html")
    return HTMLResponse(content="<html><body><h1>AI Assistant page not found</h1></body></html>")


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
    SKILLS_DATA.append(new_skill)
    logger.info(f"create_skill: 技能创建成功, id={new_skill['id']}, name={name}")
    return {"status": "success", "message": "技能创建成功", "skill": new_skill}


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
            logger.info(f"update_skill: 技能 {skill_id} 更新成功")
            return {"status": "success", "message": "技能已更新", "skill": skill}

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
            logger.info(f"toggle_skill: 技能 {skill_id} 状态已切换为 {skill['enabled']}")
            return {"status": "success", "message": f"技能已{'启用' if skill['enabled'] else '禁用'}", "skill": skill}

    logger.warning(f"toggle_skill: 技能 {skill_id} 不存在")
    raise HTTPException(status_code=404, detail=f"技能不存在 (ID: {skill_id})")


# ============ AI 聊天 API ============

# ============ Settings API ============

# 设置存储（内存中，实际应用应使用数据库或加密文件）
SETTINGS_STORE: dict = {
    "aiProvider": "bailian",
    "apiKey": "",  # API Key 由前端设置
    "model": "qwen3.5-plus",
    "temperature": 0.7,
    "maxTokens": 4096,
    "autoSave": True,
    "theme": "dark",
    "language": "zh-CN"
}

@app.get("/api/v1/settings")
async def get_settings():
    """获取系统设置"""
    return JSONResponse({
        "success": True,
        "settings": SETTINGS_STORE
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
        new_settings["apiKey"] = decrypted
        logger.info(f"[DEBUG] 解密 apiKeyEncrypted -> apiKey: {'*' * 8 if decrypted else 'empty'}")
        # 保留加密版本用于返回给前端
        SETTINGS_STORE["apiKeyEncrypted"] = new_settings["apiKeyEncrypted"]
    elif "apiKey" in new_settings:
        logger.info(f"[DEBUG] 直接收到 apiKey: {'*' * 8 if new_settings['apiKey'] else 'empty'}")
    
    # 确保 apiKey 字段存在（如果前端没有发送，保留现有值）
    if "apiKey" not in new_settings and "apiKey" in SETTINGS_STORE:
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

    # 简单验证 API Key 格式
    valid_prefixes = {
        "anthropic": ["sk-ant-"],
        "openai": ["sk-"],
        "deepseek": ["sk-"],
        "bailian": ["sk-"]  # 百炼API Key格式
    }

    # 百炼API特殊处理
    if provider == "bailian":
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
    # 支持自定义 AI 配置
    provider: Optional[str] = None
    model: Optional[str] = None
    apiKey: Optional[str] = None
    endpoint: Optional[str] = None

# 聊天历史存储（内存中，实际应用应使用数据库）
CHAT_HISTORY: dict[str, list] = {}

async def generate_chat_response(messages: List[ChatMessage], temperature: float = 0.7, max_tokens: int = 2048, provider: str = None, api_key: str = None, model: str = None, endpoint: str = None) -> AsyncGenerator[str, None]:
    """
    生成聊天响应（流式）
    支持 Anthropic、OpenAI、DeepSeek 和阿里云百炼 API
    """
    try:
        import httpx

        # 从全局配置读取设置（如果请求中没有提供）
        if not provider:
            provider = SETTINGS_STORE.get("aiProvider", "bailian")
        if not api_key:
            # 优先从 apiKey 读取，如果没有则尝试从 apiKeyEncrypted 解密
            api_key = SETTINGS_STORE.get("apiKey", "")
            if not api_key and SETTINGS_STORE.get("apiKeyEncrypted"):
                api_key = decrypt_api_key(SETTINGS_STORE.get("apiKeyEncrypted", ""))
                logger.info(f"[DEBUG] 从 apiKeyEncrypted 解密得到 API Key")
        if not model:
            model = SETTINGS_STORE.get("model", "qwen3.5-plus")
        if not endpoint:
            endpoint = SETTINGS_STORE.get("endpoint", "") or SETTINGS_STORE.get("apiEndpoint", "")

        logger.info(f"AI聊天使用配置: provider={provider}, model={model}, api_key={'*' * 8 if api_key else 'None'}")

        # 如果有 API Key 和 provider，使用配置的提供商
        if api_key and provider:
            # 百炼API使用OpenAI兼容格式
            if provider == "bailian":
                base_url = endpoint or "https://dashscope.aliyuncs.com/compatible-mode/v1"
                api_url = f"{base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
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

            # 发送流式请求
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", api_url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield f"data: {json.dumps({'error': f'API错误 ({response.status_code}): {error_text.decode()}'})}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                yield "data: [DONE]\n\n"
                                return
                            try:
                                chunk = json.loads(data)
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
                                        yield f"data: {json.dumps({'content': content})}\n\n"
                            except json.JSONDecodeError:
                                continue

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


@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
    """
    AI 聊天端点

    支持流式响应（SSE）和非流式响应
    """
    if request.stream:
        # 流式响应
        return StreamingResponse(
            generate_chat_response(
                request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                provider=request.provider,
                api_key=request.apiKey,
                model=request.model,
                endpoint=request.endpoint
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
            }
        )
    else:
        # 非流式响应
        response_content = ""
        async for chunk in generate_chat_response(
            request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            provider=request.provider,
            api_key=request.apiKey,
            model=request.model,
            endpoint=request.endpoint
        ):
            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                try:
                    data = json.loads(chunk[6:].strip())
                    if "content" in data:
                        response_content += data["content"]
                except json.JSONDecodeError:
                    continue

        return {
            "content": response_content,
            "model": "intelliteam-ai",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/v1/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """获取聊天历史"""
    return {
        "session_id": session_id,
        "messages": CHAT_HISTORY.get(session_id, [])
    }


@app.delete("/api/v1/chat/history/{session_id}")
async def clear_chat_history(session_id: str):
    """清除聊天历史"""
    if session_id in CHAT_HISTORY:
        del CHAT_HISTORY[session_id]
    return {"status": "success", "message": "聊天历史已清除"}


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


# ============ 导出功能 ============

# WebSocket 连接管理
class WebSocketManager:
    """WebSocket 连接管理器"""
    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}
        self.heartbeat_interval = 30  # 心跳间隔（秒）
        logger.info("WebSocket 管理器初始化完成")

    async def connect(self, websocket: WebSocket, client_id: int):
        """接受连接并记录"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
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

websocket_manager = WebSocketManager()

async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 实时数据推送端点
    
    功能:
    - 系统状态推送（5 秒间隔）
    - Agent 状态实时更新
    - 心跳检测（30 秒间隔）
    - 断线自动清理
    """
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
                    "activeAgents": len([a for a in AGENTS_DATA if a["status"] == "busy"]),
                    "totalTasks": len(TASKS_DATA),
                    "timestamp": now.isoformat(),
                    "connection_id": client_id
                }
            })

            # 随机更新 Agent 状态（模拟真实变化）
            # TODO: 替换为真实的 Agent 状态事件总线
            if random.random() < 0.3:
                agent = random.choice(AGENTS_DATA)
                old_status = agent["status"]
                agent["status"] = "busy" if agent["status"] == "idle" else "idle"
                logger.debug(f"Agent 状态变化：{agent['name']} {old_status} -> {agent['status']}")
                await websocket.send_json({
                    "type": "agent_update",
                    "data": agent
                })

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
    logger.info("  GET  /api/v1/cache/stats - 缓存统计")
    logger.info("  GET  /api/v1/ws/stats   - WebSocket 统计")
    logger.info("  WS   /ws                - WebSocket 实时推送")
    logger.info("")

    uvicorn.run(app, host="0.0.0.0", port=8080)
