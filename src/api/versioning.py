"""
API 版本管理模块

支持多版本 API 共存，平滑升级
"""

from functools import wraps

from fastapi import APIRouter, Header, HTTPException, Request

# 版本路由器
v1_router = APIRouter(prefix="/api/v1", tags=["v1"])
v2_router = APIRouter(prefix="/api/v2", tags=["v2"])


# ============ 版本装饰器 ============

def api_version(min_version: str = "1.0", max_version: str | None = None):
    """
    API 版本控制装饰器

    Args:
        min_version: 最低支持版本
        max_version: 最高支持版本（None 表示无上限）

    用法:
        @api_version(min_version="1.0", max_version="2.0")
        async def api_handler():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(
            request: Request,
            x_api_version: str | None = Header(default="1.0"),
            *args,
            **kwargs
        ):
            # 解析版本号
            try:
                version_parts = [int(x) for x in x_api_version.split(".")]
                min_version_parts = [int(x) for x in min_version.split(".")]

                # 检查最低版本
                if version_parts < min_version_parts:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "VERSION_TOO_OLD",
                            "message": f"API version {x_api_version} is too old. Minimum supported version is {min_version}",
                            "min_version": min_version,
                            "current_version": x_api_version,
                        },
                    )

                # 检查最高版本
                if max_version:
                    max_version_parts = [int(x) for x in max_version.split(".")]
                    if version_parts > max_version_parts:
                        raise HTTPException(
                            status_code=400,
                            detail={
                                "error": "VERSION_TOO_NEW",
                                "message": f"API version {x_api_version} is not yet supported. Maximum supported version is {max_version}",
                                "max_version": max_version,
                                "current_version": x_api_version,
                            },
                        )

            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_VERSION_FORMAT",
                        "message": "API version must be in format X.Y (e.g., 1.0)",
                    },
                ) from None

            return await func(request, *args, **kwargs)

        return wrapper
    return decorator


# ============ 版本化端点示例 ============

@v1_router.get("/tasks")
@api_version(min_version="1.0")
async def get_tasks_v1(request: Request):
    """
    V1 版本：获取任务列表（旧版）

    返回简化版任务数据
    """
    return {
        "version": "1.0",
        "tasks": [
            {"id": 1, "title": "Task 1"},
            {"id": 2, "title": "Task 2"},
        ],
    }


@v2_router.get("/tasks")
@api_version(min_version="2.0")
async def get_tasks_v2(request: Request):
    """
    V2 版本：获取任务列表（新版）

    返回完整版任务数据，包含更多字段
    """
    return {
        "version": "2.0",
        "tasks": [
            {
                "id": 1,
                "title": "Task 1",
                "description": "Full description",
                "status": "pending",
                "priority": "high",
                "assignee": "user1",
                "created_at": "2026-03-06T12:00:00Z",
            },
            {
                "id": 2,
                "title": "Task 2",
                "description": "Full description",
                "status": "completed",
                "priority": "normal",
                "assignee": "user2",
                "created_at": "2026-03-06T12:00:00Z",
            },
        ],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total": 2,
        },
    }


# ============ 版本中间件 ============

class VersionMiddleware:
    """
    API 版本中间件

    自动处理版本兼容性和迁移
    """

    def __init__(self, app, default_version: str = "1.0"):
        self.app = app
        self.default_version = default_version
        self.supported_versions = ["1.0", "2.0"]

    async def __call__(self, scope, receive, send):
        # 添加版本信息到请求
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            version = headers.get(b"x-api-version", b"").decode() or self.default_version

            # 存储版本信息到请求 scope
            scope["api_version"] = version

        await self.app(scope, receive, send)


# ============ 版本迁移工具 ============

class VersionMigrator:
    """
    版本迁移工具

    在不同版本间转换数据格式
    """

    @staticmethod
    def migrate_v1_to_v2(v1_data: dict) -> dict:
        """
        将 V1 数据格式迁移到 V2

        Args:
            v1_data: V1 格式数据

        Returns:
            V2 格式数据
        """
        return {
            "id": v1_data.get("id"),
            "title": v1_data.get("title"),
            "description": v1_data.get("description", ""),
            "status": v1_data.get("status", "pending"),
            "priority": v1_data.get("priority", "normal"),
            "assignee": v1_data.get("assignee", ""),
            "created_at": v1_data.get("created_at", ""),
        }

    @staticmethod
    def migrate_v2_to_v1(v2_data: dict) -> dict:
        """
        将 V2 数据格式迁移到 V1（降级）

        Args:
            v2_data: V2 格式数据

        Returns:
            V1 格式数据（简化版）
        """
        return {
            "id": v2_data.get("id"),
            "title": v2_data.get("title"),
        }


# ============ 版本信息端点 ============

from fastapi import FastAPI


def add_version_endpoints(app: FastAPI):
    """
    添加版本信息端点

    Args:
        app: FastAPI 应用实例
    """

    @app.get("/api/version")
    async def get_api_version():
        """获取 API 版本信息"""
        return {
            "current_version": "2.0",
            "supported_versions": ["1.0", "2.0"],
            "deprecated_versions": [],
            "latest_stable": "2.0",
            "changelog": {
                "2.0": [
                    "添加完整任务数据",
                    "添加分页支持",
                    "改进错误响应格式",
                ],
                "1.0": [
                    "初始版本",
                    "基础任务管理",
                ],
            },
        }

    @app.get("/api/version/check")
    async def check_version_compatibility(
        client_version: str,
    ):
        """
        检查客户端版本兼容性

        Args:
            client_version: 客户端版本号

        Returns:
            兼容性信息
        """
        supported = ["1.0", "2.0"]
        deprecated = []

        is_supported = client_version in supported
        is_deprecated = client_version in deprecated

        return {
            "client_version": client_version,
            "is_supported": is_supported,
            "is_deprecated": is_deprecated,
            "recommended_version": "2.0",
            "message": "Version is supported" if is_supported else "Version is not supported",
        }
