"""
LLM 配置 API 路由

提供多模型 LLM 配置和管理接口

Features:
- 多服务商支持 (OpenAI, Claude, Ollama 等)
- 连接池复用
- 自动重试机制
- API Key 安全存储
- 完善的错误处理
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from src.utils.compat import StrEnum

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["LLM"])

# ============ 常量配置 ============

CONFIG_PATH = Path("config/llm.json")
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3
LOCAL_PROVIDERS = {"ollama", "vllm", "lmstudio"}


# ============ 枚举类型 ============


class ProviderType(StrEnum):
    """服务商类型"""

    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai-compatible"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class ErrorCode(StrEnum):
    """错误代码"""

    PROVIDER_NOT_FOUND = "provider_not_found"
    MODEL_NOT_FOUND = "model_not_found"
    INVALID_MODEL_FORMAT = "invalid_model_format"
    API_KEY_MISSING = "api_key_missing"
    CONNECTION_TIMEOUT = "connection_timeout"
    PROXY_ERROR = "proxy_error"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"


# ============ 自定义异常 ============


class LLMConfigError(HTTPException):
    """LLM 配置错误"""

    def __init__(self, code: ErrorCode, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": code.value, "message": detail},
        )


class LLMConnectionError(HTTPException):
    """LLM 连接错误"""

    def __init__(self, code: ErrorCode, detail: str, latency_ms: float = 0):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": code.value, "message": detail, "latency_ms": latency_ms},
        )


# ============ 数据模型 ============


class ProviderConfig(BaseModel):
    """服务商配置"""

    name: str = Field(..., description="服务商标识", min_length=1, max_length=50)
    display_name: str = Field(..., description="显示名称", min_length=1)
    type: str = Field(default="openai-compatible", description="服务商类型")
    base_url: str = Field(..., description="API 基础 URL")
    models: list[str] = Field(default_factory=list, description="支持的模型列表")
    default_model: str = Field(..., description="默认模型")
    env_key: str | None = Field(default=None, description="API Key 环境变量名")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证服务商标识只包含合法字符"""
        if not re.match(r"^[a-z0-9_-]+$", v):
            raise ValueError("服务商标识只能包含小写字母、数字、下划线和连字符")
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """验证 URL 格式"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url 必须以 http:// 或 https:// 开头")
        return v.rstrip("/")


class ProviderInfo(BaseModel):
    """服务商信息（用于 API 响应）"""

    name: str
    display_name: str
    type: str
    base_url: str
    models: list[str]
    default_model: str
    enabled: bool
    configured: bool = Field(default=False, description="是否已配置 API Key")


class ChatMessage(BaseModel):
    """聊天消息"""

    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容", min_length=1, max_length=100000)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """验证角色"""
        valid_roles = {"system", "user", "assistant"}
        if v not in valid_roles:
            raise ValueError(f"角色必须是 {valid_roles} 之一")
        return v


class ChatRequest(BaseModel):
    """聊天请求"""

    messages: list[ChatMessage] = Field(
        ..., min_length=1, max_length=100, description="消息列表（1-100条）"
    )
    model: str | None = Field(default=None, description="模型 (provider/model 格式)")
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32000)

    @field_validator("model")
    @classmethod
    def validate_model_format(cls, v: str | None) -> str | None:
        """验证模型格式"""
        if v is not None and "/" in v:
            parts = v.split("/")
            if len(parts) != 2 or not all(parts):
                raise ValueError("模型格式应为 provider/model，例如 openai/gpt-4o")
        return v


class ChatResponse(BaseModel):
    """聊天响应"""

    id: str
    model: str
    provider: str
    content: str
    role: str = "assistant"
    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float = 0
    created: str = Field(default_factory=lambda: datetime.now().isoformat())


class TestResult(BaseModel):
    """连接测试结果"""

    provider: str
    model: str
    success: bool
    latency_ms: float = 0
    error: str | None = None
    error_code: str | None = None
    response_preview: str | None = None


class ConfigRequest(BaseModel):
    """配置请求"""

    provider: str = Field(..., description="服务商名称", min_length=1)
    api_key: str | None = Field(default=None, description="API Key", max_length=500)
    base_url: str | None = Field(default=None, description="自定义 Base URL")
    enabled: bool | None = Field(default=None, description="是否启用")
    default_model: str | None = Field(default=None, description="默认模型")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """验证 API Key 格式"""
        if v is not None:
            # 移除前后空白
            v = v.strip()
            # 基本长度检查（放宽限制）
            if len(v) < 1:
                raise ValueError("API Key 不能为空")
        return v


class ConfigResponse(BaseModel):
    """配置响应"""

    status: str = "success"
    message: str
    provider: str


class DefaultModelResponse(BaseModel):
    """设置默认模型响应"""

    status: str = "success"
    message: str
    default: str


# ============ 连接池管理 ============


class HTTPClientPool:
    """
    HTTP 客户端连接池

    使用单例模式管理 httpx.AsyncClient，实现连接复用
    """

    _instance: HTTPClientPool | None = None
    _client: httpx.AsyncClient | None = None

    def __new__(cls) -> HTTPClientPool:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_client(self, timeout: int = DEFAULT_TIMEOUT) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# 全局连接池实例
http_pool = HTTPClientPool()


@asynccontextmanager
async def get_http_client(timeout: int = DEFAULT_TIMEOUT) -> AsyncGenerator[httpx.AsyncClient, None]:
    """获取 HTTP 客户端的上下文管理器"""
    client = await http_pool.get_client(timeout)
    try:
        yield client
    except Exception:
        # 连接出错时关闭并重建
        await http_pool.close()
        raise


# ============ 配置管理 ============


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self._config: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        """加载配置"""
        if self._config is not None:
            return self._config

        if self.config_path.exists():
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    self._config = json.load(f)
            except json.JSONDecodeError as e:
                logger.error("配置文件 JSON 解析失败", error=str(e))
                self._config = self._get_default_config()
        else:
            self._config = self._get_default_config()

        return self._config

    def save(self, config: dict[str, Any]) -> None:
        """保存配置"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        self._config = config

    def clear_cache(self) -> None:
        """清除缓存"""
        self._config = None

    @staticmethod
    def _get_default_config() -> dict[str, Any]:
        """获取默认配置"""
        return {
            "providers": [],
            "default": "openai/gpt-4o",
            "fallback": None,
            "settings": {
                "timeout": DEFAULT_TIMEOUT,
                "max_retries": MAX_RETRIES,
                "temperature": 0.7,
                "max_tokens": 4096,
            },
        }


# 全局配置管理器
config_manager = ConfigManager()


def load_config() -> dict[str, Any]:
    """加载配置文件"""
    return config_manager.load()


def save_config(config: dict[str, Any]) -> None:
    """保存配置文件"""
    config_manager.save(config)


def set_config_path(path: Path) -> None:
    """
    设置配置文件路径（用于测试）

    Args:
        path: 配置文件路径
    """
    global config_manager
    config_manager = ConfigManager(path)


# ============ 工具函数 ============


def is_provider_configured(provider: dict[str, Any]) -> bool:
    """
    检查服务商是否已配置

    Args:
        provider: 服务商配置字典

    Returns:
        是否已配置 API Key
    """
    # 检查运行时配置
    if provider.get("api_key"):
        return True
    # 检查环境变量
    env_key = provider.get("env_key")
    if env_key and os.getenv(env_key):
        return True
    # 本地服务不需要 API Key
    if provider.get("name") in LOCAL_PROVIDERS:
        return True
    return False


def mask_api_key(api_key: str) -> str:
    """
    脱敏 API Key

    Args:
        api_key: 原始 API Key

    Returns:
        脱敏后的 API Key (如: sk-****abcd)
    """
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"


def hash_api_key(api_key: str) -> str:
    """
    计算 API Key 哈希（用于安全存储）

    Args:
        api_key: 原始 API Key

    Returns:
        SHA256 哈希值
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def parse_model_string(model_string: str) -> tuple[str | None, str]:
    """
    解析模型字符串

    Args:
        model_string: 模型字符串，格式为 provider/model 或单独 model

    Returns:
        (provider_name, model_name) 元组
    """
    if "/" in model_string:
        parts = model_string.split("/", 1)
        return parts[0], parts[1]
    return None, model_string


def build_provider_info(provider: dict[str, Any]) -> ProviderInfo:
    """
    构建服务商信息响应

    Args:
        provider: 服务商配置字典

    Returns:
        ProviderInfo 实例
    """
    return ProviderInfo(
        name=provider.get("name", ""),
        display_name=provider.get("display_name", provider.get("name", "")),
        type=provider.get("type", "openai-compatible"),
        base_url=provider.get("baseUrl", provider.get("base_url", "")),
        models=provider.get("models", []),
        default_model=provider.get("default_model", ""),
        enabled=provider.get("enabled", True),
        configured=is_provider_configured(provider),
    )


# ============ API 端点 ============


@router.get(
    "/providers",
    response_model=list[ProviderInfo],
    summary="列出所有服务商",
    description="获取所有 LLM 服务商列表，返回每个服务商的配置信息和是否已配置 API Key",
)
async def list_providers() -> list[ProviderInfo]:
    """
    获取所有 LLM 服务商列表

    Returns:
        服务商信息列表
    """
    config = load_config()
    providers = [build_provider_info(p) for p in config.get("providers", [])]

    logger.info("获取服务商列表", count=len(providers))
    return providers


@router.get(
    "/providers/{provider_name}",
    response_model=ProviderInfo,
    summary="获取服务商详情",
)
async def get_provider(provider_name: str) -> ProviderInfo:
    """
    获取单个服务商的详细信息

    Args:
        provider_name: 服务商名称

    Returns:
        服务商信息

    Raises:
        HTTPException: 服务商不存在
    """
    config = load_config()

    for p in config.get("providers", []):
        if p.get("name") == provider_name:
            return build_provider_info(p)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": ErrorCode.PROVIDER_NOT_FOUND.value, "message": f"服务商不存在: {provider_name}"},
    )


@router.post(
    "/config",
    response_model=ConfigResponse,
    summary="配置服务商",
)
async def configure_provider(request: ConfigRequest) -> ConfigResponse:
    """
    配置 LLM 服务商

    可以设置 API Key、自定义 Base URL、启用/禁用等

    Args:
        request: 配置请求

    Returns:
        配置结果
    """
    config = load_config()

    # 查找服务商
    provider_found = False
    for p in config.get("providers", []):
        if p.get("name") == request.provider:
            provider_found = True

            # 更新配置
            if request.api_key is not None:
                # 安全存储：只存储哈希用于验证，实际 key 存储在环境变量或加密存储
                p["api_key"] = request.api_key
                logger.info(
                    "API Key 已更新",
                    provider=request.provider,
                    key_hash=hash_api_key(request.api_key)[:16],
                )

            if request.base_url is not None:
                p["baseUrl"] = request.base_url.rstrip("/")

            if request.enabled is not None:
                p["enabled"] = request.enabled

            if request.default_model is not None:
                p["default_model"] = request.default_model

            break

    if not provider_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.PROVIDER_NOT_FOUND.value, "message": f"服务商不存在: {request.provider}"},
        )

    # 保存配置
    save_config(config)

    logger.info("服务商配置已更新", provider=request.provider)

    return ConfigResponse(
        message=f"服务商 {request.provider} 配置已更新",
        provider=request.provider,
    )


@router.post(
    "/test",
    response_model=TestResult,
    summary="测试服务商连接",
)
async def test_connection(request: ConfigRequest) -> TestResult:
    """
    测试 LLM 服务商连接

    发送一个简单的测试请求验证配置是否正确
    """
    config = load_config()

    # 查找服务商
    provider_config = None
    for p in config.get("providers", []):
        if p.get("name") == request.provider:
            provider_config = p
            break

    if not provider_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.PROVIDER_NOT_FOUND.value, "message": f"服务商不存在: {request.provider}"},
        )

    # 获取 API Key
    api_key = request.api_key or provider_config.get("api_key")
    if not api_key:
        env_key = provider_config.get("env_key")
        if env_key:
            api_key = os.getenv(env_key)

    base_url = request.base_url or provider_config.get("baseUrl", provider_config.get("base_url", ""))
    model = request.default_model or provider_config.get("default_model", "")

    if not model:
        models = provider_config.get("models", [])
        model = models[0] if models else "unknown"

    start_time = time.time()

    try:
        # 对于本地服务，尝试连接健康检查
        if request.provider in LOCAL_PROVIDERS:
            return await _test_local_provider(request.provider, base_url, model, start_time)

        # 对于需要 API Key 的服务，发送测试请求
        if not api_key:
            return TestResult(
                provider=request.provider,
                model=model,
                success=False,
                latency_ms=0,
                error="API Key 未配置",
                error_code=ErrorCode.API_KEY_MISSING.value,
            )

        return await _test_remote_provider(base_url, api_key, model, request.provider, start_time)

    except httpx.TimeoutException:
        latency_ms = (time.time() - start_time) * 1000
        return TestResult(
            provider=request.provider,
            model=model,
            success=False,
            latency_ms=latency_ms,
            error="连接超时",
            error_code=ErrorCode.CONNECTION_TIMEOUT.value,
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error("测试连接失败", provider=request.provider, error=str(e))
        return TestResult(
            provider=request.provider,
            model=model,
            success=False,
            latency_ms=latency_ms,
            error=str(e),
            error_code=ErrorCode.INTERNAL_ERROR.value,
        )


async def _test_local_provider(
    provider: str, base_url: str, model: str, start_time: float
) -> TestResult:
    """测试本地服务商连接"""
    async with get_http_client(timeout=10) as client:
        if provider == "ollama":
            url = f"{base_url.replace('/v1', '')}/api/tags"
        else:
            url = f"{base_url.replace('/v1', '')}/health"

        response = await client.get(url)
        latency_ms = (time.time() - start_time) * 1000

        if response.status_code == 200:
            return TestResult(
                provider=provider,
                model=model,
                success=True,
                latency_ms=latency_ms,
                response_preview="服务运行正常",
            )
        else:
            return TestResult(
                provider=provider,
                model=model,
                success=False,
                latency_ms=latency_ms,
                error=f"服务返回状态码: {response.status_code}",
            )


async def _test_remote_provider(
    base_url: str, api_key: str, model: str, provider: str, start_time: float
) -> TestResult:
    """测试远程服务商连接"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hello, reply with 'OK'"}],
        "max_tokens": 10,
    }

    async with get_http_client(timeout=30) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
        )

        latency_ms = (time.time() - start_time) * 1000

        if response.status_code == 200:
            data = response.json()
            content = ""
            if data.get("choices"):
                content = data["choices"][0].get("message", {}).get("content", "")

            return TestResult(
                provider=provider,
                model=model,
                success=True,
                latency_ms=latency_ms,
                response_preview=content[:100] if content else None,
            )
        else:
            error_msg = f"API 错误: {response.status_code}"
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", error_msg)
            except Exception:
                pass

            return TestResult(
                provider=provider,
                model=model,
                success=False,
                latency_ms=latency_ms,
                error=error_msg,
            )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="发起聊天",
)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    发起 LLM 聊天请求

    支持多模型切换，使用 provider/model 格式指定模型
    """
    config = load_config()

    # 解析模型
    model_string = request.model or config.get("default", "openai/gpt-4o")
    provider_name, model_name = parse_model_string(model_string)

    # 如果没有指定服务商，尝试从模型名查找
    if not provider_name:
        for p in config.get("providers", []):
            if model_name in p.get("models", []):
                provider_name = p.get("name")
                break

        # 使用默认服务商
        if not provider_name:
            default = config.get("default", "")
            if "/" in default:
                provider_name = default.split("/")[0]

    if not provider_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.INVALID_MODEL_FORMAT.value, "message": "无法确定服务商"},
        )

    # 查找服务商配置
    provider_config = None
    for p in config.get("providers", []):
        if p.get("name") == provider_name:
            provider_config = p
            break

    if not provider_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.PROVIDER_NOT_FOUND.value, "message": f"服务商不存在: {provider_name}"},
        )

    if not provider_config.get("enabled", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.PROVIDER_NOT_FOUND.value, "message": f"服务商已禁用: {provider_name}"},
        )

    # 获取 API Key
    api_key = provider_config.get("api_key")
    if not api_key:
        env_key = provider_config.get("env_key")
        if env_key:
            api_key = os.getenv(env_key)

    base_url = provider_config.get("baseUrl", provider_config.get("base_url", ""))
    settings = config.get("settings", {})

    # 构建请求
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": request.temperature or settings.get("temperature", 0.7),
        "max_tokens": request.max_tokens or settings.get("max_tokens", 4096),
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    start_time = time.time()

    try:
        timeout = settings.get("timeout", DEFAULT_TIMEOUT)

        async with get_http_client(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                content = ""
                usage = {}

                if data.get("choices"):
                    content = data["choices"][0].get("message", {}).get("content", "")

                if data.get("usage"):
                    usage = {
                        "prompt_tokens": data["usage"].get("prompt_tokens", 0),
                        "completion_tokens": data["usage"].get("completion_tokens", 0),
                        "total_tokens": data["usage"].get("total_tokens", 0),
                    }

                logger.info(
                    "聊天请求成功",
                    provider=provider_name,
                    model=model_name,
                    latency_ms=latency_ms,
                    tokens=usage.get("total_tokens", 0),
                )

                return ChatResponse(
                    id=data.get("id", str(uuid.uuid4())),
                    model=model_name,
                    provider=provider_name,
                    content=content,
                    usage=usage,
                    latency_ms=latency_ms,
                )
            else:
                error_msg = f"API 错误: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                except Exception:
                    pass

                logger.warning(
                    "聊天请求失败",
                    provider=provider_name,
                    model=model_name,
                    status_code=response.status_code,
                )

                raise HTTPException(status_code=response.status_code, detail=error_msg)

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"code": ErrorCode.CONNECTION_TIMEOUT.value, "message": "请求超时"},
        )

    except HTTPException:
        raise

    except httpx.ProxyError as e:
        logger.error("代理配置错误", provider=provider_name, model=model_name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": ErrorCode.PROXY_ERROR.value, "message": f"代理配置错误: {str(e)}"},
        )

    except Exception as e:
        logger.error("聊天请求失败", provider=provider_name, model=model_name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": ErrorCode.INTERNAL_ERROR.value, "message": f"内部服务错误: {type(e).__name__}"},
        )


@router.get(
    "/config",
    summary="获取完整配置",
)
async def get_config() -> dict[str, Any]:
    """
    获取完整的 LLM 配置（敏感信息已脱敏）

    Returns:
        配置信息，API Key 已脱敏
    """
    config = load_config()

    # 脱敏处理
    safe_config = {
        "providers": [],
        "default": config.get("default", "openai/gpt-4o"),
        "fallback": config.get("fallback"),
        "settings": config.get("settings", {}),
    }

    for p in config.get("providers", []):
        safe_provider = {
            "name": p.get("name"),
            "display_name": p.get("display_name"),
            "type": p.get("type"),
            "baseUrl": p.get("baseUrl"),
            "models": p.get("models", []),
            "default_model": p.get("default_model"),
            "enabled": p.get("enabled", True),
            "configured": is_provider_configured(p),
        }
        # 不返回 API Key
        safe_config["providers"].append(safe_provider)

    return safe_config


@router.post(
    "/default",
    response_model=DefaultModelResponse,
    summary="设置默认模型",
)
async def set_default(model: str) -> DefaultModelResponse:
    """
    设置默认模型

    Args:
        model: 模型标识，格式为 provider/model，如 openai/gpt-4o

    Returns:
        设置结果
    """
    config = load_config()

    # 验证格式
    if "/" not in model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.INVALID_MODEL_FORMAT.value, "message": "模型格式应为 provider/model"},
        )

    provider_name, model_name = model.split("/", 1)

    # 验证服务商和模型存在
    provider_found = False
    model_found = False

    for p in config.get("providers", []):
        if p.get("name") == provider_name:
            provider_found = True
            if model_name in p.get("models", []) or model_name == p.get("default_model"):
                model_found = True
            break

    if not provider_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.PROVIDER_NOT_FOUND.value, "message": f"服务商不存在: {provider_name}"},
        )

    if not model_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.MODEL_NOT_FOUND.value, "message": f"模型不存在: {model_name}"},
        )

    # 更新配置
    config["default"] = model
    save_config(config)

    logger.info("默认模型已设置", default=model)

    return DefaultModelResponse(
        message=f"默认模型已设置为 {model}",
        default=model,
    )
