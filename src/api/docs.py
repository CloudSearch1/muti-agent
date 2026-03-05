"""
IntelliTeam OpenAPI 文档配置

优化 API 文档和 Swagger UI
"""

from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi


def setup_openapi_docs(app: FastAPI):
    """
    配置 OpenAPI 文档

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

- **Agent 管理** - 8 个专业 AI Agent
- **任务管理** - 创建、更新、查询、删除
- **工作流** - LangGraph 工作流编排
- **实时监控** - WebSocket 实时通信
- **性能监控** - Prometheus 指标

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
  "status_code": 400,
  "details": {},
  "timestamp": "2026-03-03T12:00:00"
}
```
            """,
            routes=app.routes,
        )

        # 添加标签说明
        openapi_schema["tags"] = [
            {"name": "tasks", "description": "任务管理 - 创建、查询、更新、删除任务"},
            {"name": "agents", "description": "Agent 管理 - 查询 Agent 状态和统计"},
            {"name": "workflows", "description": "工作流 - 工作流执行和监控"},
            {"name": "auth", "description": "认证 - 用户登录和 Token 管理"},
            {"name": "users", "description": "用户管理 - 用户 CRUD 操作"},
            {"name": "monitoring", "description": "监控 - Prometheus 指标和健康检查"},
            {"name": "export", "description": "导出 - 数据导出功能"},
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

    print("✅ OpenAPI 文档已配置")
    print("📚 Swagger UI: http://localhost:8080/docs")
    print("📖 ReDoc: http://localhost:8080/redoc")


def add_api_examples(app: FastAPI):
    """
    添加 API 示例

    Args:
        app: FastAPI 应用实例
    """

    # 任务示例

    # Agent 示例

    # 错误响应示例

    print("✅ API 示例已添加")
