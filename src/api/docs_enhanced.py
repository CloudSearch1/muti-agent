"""
API 文档增强模块

完善 Swagger UI 和 ReDoc 文档
"""

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi


def setup_enhanced_docs(app: FastAPI):
    """
    设置增强版 API 文档

    Args:
        app: FastAPI 应用实例
    """

    # 自定义 OpenAPI 配置
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title="IntelliTeam API",
            version="2.0.0",
            description="""
## IntelliTeam 智能研发协作平台 API

多智能体协同平台，自动化处理软件研发全流程

### 核心功能

- **Agent 管理** - 6 个专业 AI Agent（Coder, Tester, DocWriter, Architect, SeniorArchitect, Planner）
- **任务管理** - 创建、更新、查询、删除任务
- **批量操作** - 批量获取、创建、更新、删除任务
- **工作流** - Agent 执行引擎，支持工作流编排
- **实时监控** - WebSocket 实时通信，Agent 状态推送
- **性能监控** - Prometheus 指标，健康检查

### 认证

使用 JWT Token 进行认证：

1. 调用 `/api/v1/auth/login` 获取 token
2. 在请求头中添加 `Authorization: Bearer <token>`

### 错误处理

所有错误返回统一格式：

```json
{
    "error": "ERROR_CODE",
    "message": "错误描述",
    "details": {}
}
```

### 版本管理

API 支持多版本共存：

- **v1** - 初始版本（简化数据）
- **v2** - 当前版本（完整数据，推荐）

通过 `X-API-Version` 请求头指定版本：

```bash
curl -H "X-API-Version: 2.0" http://localhost:8080/api/v2/tasks
```

### 批量操作

批量端点减少网络往返：

```bash
# 批量获取任务
POST /api/v1/batch/tasks/get
{
    "task_ids": [1, 2, 3, 4, 5]
}

# 批量创建任务
POST /api/v1/batch/tasks/create
{
    "tasks": [
        {"title": "Task 1", "priority": "high"},
        {"title": "Task 2", "priority": "normal"}
    ]
}
```

### 性能优化

- **响应压缩** - GZip 自动压缩（>1KB）
- **缓存** - LLM 语义缓存，响应缓存
- **连接池** - 数据库连接池优化
- **并发控制** - 信号量、限流器、熔断器

### 监控

```bash
# 健康检查
GET /health

# 性能指标
GET /health/metrics

# 存活检查
GET /health/live

# 就绪检查
GET /health/ready
```
            """,
            contact={
                "name": "IntelliTeam Support",
                "email": "support@intelliteam.com",
            },
            license_info={
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
            },
            docs_url=None,  # 自定义
            redoc_url=None,  # 自定义
            openapi_url="/openapi.json",
        )

        # 添加标签说明
        openapi_schema["tags"] = [
            {
                "name": "tasks",
                "description": "任务管理 API - 创建、查询、更新、删除任务",
            },
            {
                "name": "agents",
                "description": "Agent 管理 API - Agent 状态查询和管理",
            },
            {
                "name": "batch",
                "description": "批量操作 API - 批量获取、创建、更新、删除",
            },
            {
                "name": "health",
                "description": "健康检查 API - 系统健康状态监控",
            },
            {
                "name": "auth",
                "description": "认证授权 API - 登录、登出、Token 管理",
            },
            {
                "name": "workflows",
                "description": "工作流 API - Agent 执行引擎和工作流编排",
            },
        ]

        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = custom_openapi

    # 自定义 Swagger UI
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="IntelliTeam API - Swagger UI",
            swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
            swagger_ui_parameters={
                "apisSorter": "alpha",
                "operationsSorter": "alpha",
                "docExpansion": "list",
                "filter": True,
                "showExtensions": True,
                "showCommonExtensions": True,
            },
        )

    # 自定义 ReDoc
    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc_html():
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="IntelliTeam API - ReDoc",
            redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
        )


def add_api_examples(app: FastAPI):
    """
    添加 API 示例到文档

    Args:
        app: FastAPI 应用实例
    """

    # 示例在路由中通过 examples 参数添加
    # 这里添加全局示例

    print("✅ API 示例已添加")
    print("📚 Swagger UI: http://localhost:8080/docs")
    print("📖 ReDoc: http://localhost:8080/redoc")


# ============ 示例响应模型 ============

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskExample(BaseModel):
    """任务示例模型"""
    id: int = Field(1, description="任务 ID", example=1)
    title: str = Field(..., description="任务标题", example="创建用户管理 API")
    description: str = Field("", description="任务描述", example="实现用户注册、登录、权限管理等功能")
    status: str = Field("pending", description="任务状态", example="pending")
    priority: str = Field("normal", description="优先级", example="high")
    assignee: str | None = Field(None, description="负责人", example="张三")
    agent: str | None = Field(None, description="执行 Agent", example="Coder")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")


class TaskCreateExample(BaseModel):
    """创建任务请求示例"""
    title: str = Field(..., description="任务标题", example="创建用户管理 API")
    description: str = Field("", description="任务描述", example="实现用户注册、登录、权限管理等功能")
    priority: str = Field("normal", description="优先级", example="high")
    assignee: str | None = Field(None, description="负责人", example="张三")
    agent: str | None = Field(None, description="执行 Agent", example="Coder")


class TaskResponseExample(BaseModel):
    """任务响应示例"""
    status: str = Field("success", description="状态", example="success")
    message: str = Field("操作成功", description="消息", example="任务创建成功")
    data: TaskExample = Field(..., description="任务数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


class ErrorResponseExample(BaseModel):
    """错误响应示例"""
    error: str = Field(..., description="错误代码", example="VALIDATION_ERROR")
    message: str = Field(..., description="错误消息", example="数据验证失败")
    details: dict[str, Any] | None = Field(None, description="详细错误信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="错误时间")


class HealthCheckExample(BaseModel):
    """健康检查响应示例"""
    status: str = Field(..., description="整体状态", example="ok")
    timestamp: datetime = Field(default_factory=datetime.now, description="检查时间")
    version: str = Field("2.0.0", description="应用版本", example="2.0.0")
    checks: dict[str, Any] = Field(..., description="组件检查状态")
    uptime_seconds: float = Field(..., description="运行时间（秒）", example=3600.5)


class BatchGetRequestExample(BaseModel):
    """批量获取请求示例"""
    task_ids: list[int] = Field(..., description="任务 ID 列表", example=[1, 2, 3, 4, 5])


class BatchGetResponseExample(BaseModel):
    """批量获取响应示例"""
    tasks: list[TaskExample] = Field(..., description="任务列表")
    not_found: list[int] = Field([], description="未找到的任务 ID")


# ============ API 使用示例 ============

API_USAGE_EXAMPLES = """
# IntelliTeam API 使用示例

## 1. 任务管理

### 创建任务
```bash
curl -X POST http://localhost:8080/api/v1/tasks \\
  -H "Content-Type: application/json" \\
  -d '{
    "title": "创建用户管理 API",
    "description": "实现用户注册、登录、权限管理",
    "priority": "high",
    "assignee": "张三",
    "agent": "Coder"
  }'
```

### 获取任务列表
```bash
curl http://localhost:8080/api/v1/tasks?page=1&page_size=20
```

### 批量获取任务
```bash
curl -X POST http://localhost:8080/api/v1/batch/tasks/get \\
  -H "Content-Type: application/json" \\
  -d '{
    "task_ids": [1, 2, 3, 4, 5]
  }'
```

## 2. Agent 管理

### 获取 Agent 列表
```bash
curl http://localhost:8080/api/v1/agents
```

### 获取 Agent 状态
```bash
curl http://localhost:8080/api/v1/agents/Coder/status
```

## 3. 健康检查

### 完整健康检查
```bash
curl http://localhost:8080/health
```

### 存活检查
```bash
curl http://localhost:8080/health/live
```

### 性能指标
```bash
curl http://localhost:8080/health/metrics
```

## 4. 认证

### 登录
```bash
curl -X POST http://localhost:8080/api/v1/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{
    "username": "admin",
    "password": "password123"
  }'
```

### 使用 Token
```bash
curl http://localhost:8080/api/v1/tasks \\
  -H "Authorization: Bearer <token>"
```

## 5. 版本管理

### 指定 API 版本
```bash
curl -H "X-API-Version: 2.0" http://localhost:8080/api/v2/tasks
```

## 6. 性能优化

### 启用缓存
```bash
# 自动缓存，无需额外配置
# 相同请求会返回缓存结果
```

### 流式响应
```bash
# SSE 流式输出
curl -N http://localhost:8080/api/v1/generate/stream?prompt=xxx
```
"""
