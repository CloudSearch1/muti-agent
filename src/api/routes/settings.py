"""
Settings API 路由

提供前端设置存储和加载功能
"""

import json
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["settings"])

# 设置文件路径
SETTINGS_PATH = Path("config/settings.json")


class SettingsRequest(BaseModel):
    """设置请求"""

    settings: dict[str, Any]


class SettingsResponse(BaseModel):
    """设置响应"""

    status: str = "success"
    message: str = "设置已保存"
    settings: dict[str, Any] | None = None


def load_settings() -> dict[str, Any]:
    """加载设置"""
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error("设置文件 JSON 解析失败", error=str(e))
    return {}


def save_settings(settings: dict[str, Any]) -> None:
    """保存设置"""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


@router.get(
    "/settings",
    response_model=SettingsResponse,
    summary="获取设置",
)
async def get_settings() -> SettingsResponse:
    """
    获取用户设置

    Returns:
        设置信息
    """
    settings = load_settings()
    logger.info("获取设置")
    return SettingsResponse(settings=settings)


@router.post(
    "/settings",
    response_model=SettingsResponse,
    summary="保存设置",
)
async def save_settings_endpoint(request: SettingsRequest) -> SettingsResponse:
    """
    保存用户设置

    Args:
        request: 设置请求

    Returns:
        保存结果
    """
    save_settings(request.settings)
    logger.info("设置已保存")
    return SettingsResponse(message="设置已保存", settings=request.settings)
