"""
本地 LLM API 端点

提供本地 LLM 管理和调用接口
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...llm.llm_provider import LLMConfigError, LLMError
from ...llm.local import (
    LocalLLMService,
    OllamaProvider,
    get_local_llm,
)

router = APIRouter(prefix="/local", tags=["Local LLM"])


# ============ 请求模型 ============

class LocalChatRequest(BaseModel):
    """本地 LLM 对话请求"""

    prompt: str = Field(..., description="用户提示")
    model: str | None = Field(default=None, description="模型名称")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=8192)
    stream: bool = Field(default=False, description="是否流式输出")


class LocalPullRequest(BaseModel):
    """模型下载请求"""

    model_name: str = Field(..., description="模型名称")


class LocalProviderConfig(BaseModel):
    """本地 LLM 配置"""

    provider_type: str = Field(
        default="ollama",
        description="提供商类型 (ollama/vllm/lmstudio)"
    )
    base_url: str | None = Field(default=None, description="服务地址")
    model: str | None = Field(default=None, description="模型名称")


# ============ 响应模型 ============

class LocalModelResponse(BaseModel):
    """本地模型响应"""

    name: str
    size: str | None = None
    modified_at: str | None = None
    details: dict[str, Any] | None = None


class LocalHealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    provider: str
    models: list[str] | None = None
    error: str | None = None


class LocalChatResponse(BaseModel):
    """本地对话响应"""

    content: str
    model: str
    provider: str
    timestamp: str


# ============ 服务缓存 ============

_local_services: dict[str, LocalLLMService] = {}


def _get_service(
    provider_type: str = "ollama",
    base_url: str | None = None,
    model: str | None = None,
) -> LocalLLMService:
    """获取本地 LLM 服务（带缓存）"""
    key = f"{provider_type}:{base_url}:{model}"

    if key not in _local_services:
        _local_services[key] = get_local_llm(
            provider_type=provider_type,
            base_url=base_url,
            model=model,
        )

    return _local_services[key]


# ============ API 端点 ============

@router.get("/health", response_model=LocalHealthResponse)
async def check_local_health(
    provider: str = Query(default="ollama", description="提供商类型"),
    base_url: str | None = Query(default=None, description="服务地址"),
):
    """
    检查本地 LLM 服务健康状态

    - **provider**: 提供商类型 (ollama/vllm/lmstudio)
    - **base_url**: 服务地址（可选）
    """
    try:
        service = _get_service(provider_type=provider, base_url=base_url)
        result = await service.health_check()
        return LocalHealthResponse(**result)
    except Exception as e:
        return LocalHealthResponse(
            status="error",
            provider=provider,
            error=str(e),
        )


@router.get("/models", response_model=list[LocalModelResponse])
async def list_local_models(
    provider: str = Query(default="ollama", description="提供商类型"),
    base_url: str | None = Query(default=None, description="服务地址"),
):
    """
    列出本地可用模型

    - **provider**: 提供商类型
    - **base_url**: 服务地址（可选）
    """
    try:
        service = _get_service(provider_type=provider, base_url=base_url)
        models = await service.list_models()

        # 格式化响应
        result = []
        for m in models:
            if isinstance(m, dict):
                result.append(LocalModelResponse(
                    name=m.get("name", m.get("id", "unknown")),
                    size=m.get("size"),
                    modified_at=m.get("modified_at"),
                    details=m.get("details"),
                ))
            else:
                result.append(LocalModelResponse(name=str(m)))

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/pull")
async def pull_local_model(
    request: LocalPullRequest,
    provider: str = Query(default="ollama", description="提供商类型"),
    base_url: str | None = Query(default=None, description="服务地址"),
):
    """
    下载本地模型（仅支持 Ollama）

    - **provider**: 提供商类型
    - **base_url**: 服务地址（可选）
    - **model_name**: 要下载的模型名称
    """
    if provider != "ollama":
        raise HTTPException(
            status_code=400,
            detail="模型下载仅支持 Ollama 提供商"
        )

    try:
        service = _get_service(provider_type=provider, base_url=base_url)
        ollama_provider = service.provider

        if not isinstance(ollama_provider, OllamaProvider):
            raise HTTPException(
                status_code=500,
                detail="提供商类型错误"
            )

        result = await ollama_provider.pull_model(request.model_name)
        return {
            "status": "success",
            "model": request.model_name,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/chat", response_model=LocalChatResponse)
async def local_chat(
    request: LocalChatRequest,
    provider: str = Query(default="ollama", description="提供商类型"),
    base_url: str | None = Query(default=None, description="服务地址"),
):
    """
    本地 LLM 对话

    - **provider**: 提供商类型 (ollama/vllm/lmstudio)
    - **base_url**: 服务地址（可选）
    - **prompt**: 用户提示
    - **model**: 模型名称（可选，使用默认模型）
    - **temperature**: 温度参数
    - **max_tokens**: 最大输出 token 数
    """
    try:
        service = _get_service(
            provider_type=provider,
            base_url=base_url,
            model=request.model,
        )

        content = await service.generate(
            prompt=request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        return LocalChatResponse(
            content=content,
            model=request.model or service.provider.model if service.provider else "unknown",
            provider=provider,
            timestamp=datetime.now().isoformat(),
        )
    except LLMConfigError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LLMError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/chat/stream")
async def local_chat_stream(
    request: LocalChatRequest,
    provider: str = Query(default="ollama", description="提供商类型"),
    base_url: str | None = Query(default=None, description="服务地址"),
):
    """
    本地 LLM 流式对话

    返回 Server-Sent Events (SSE) 格式的流式响应
    """
    import json

    from fastapi.responses import StreamingResponse

    async def generate_stream():
        try:
            service = _get_service(
                provider_type=provider,
                base_url=base_url,
                model=request.model,
            )

            async for chunk in service.generate_stream(
                prompt=request.prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
    )


@router.get("/providers")
async def list_local_providers():
    """
    列出支持的本地 LLM 提供商
    """
    return {
        "providers": [
            {
                "type": "ollama",
                "name": "Ollama",
                "description": "简单部署，开箱即用的本地 LLM 运行环境",
                "default_url": "http://localhost:11434",
                "default_model": "llama2",
                "features": ["chat", "stream", "pull_model", "list_models"],
            },
            {
                "type": "vllm",
                "name": "vLLM",
                "description": "高性能推理引擎，OpenAI 兼容 API",
                "default_url": "http://localhost:8000",
                "default_model": "meta-llama/Llama-2-7b-hf",
                "features": ["chat", "stream", "list_models"],
            },
            {
                "type": "lmstudio",
                "name": "LM Studio",
                "description": "图形化界面的本地 LLM 运行环境",
                "default_url": "http://localhost:1234",
                "default_model": "local-model",
                "features": ["chat", "stream", "list_models"],
            },
        ],
    }


@router.post("/configure")
async def configure_local_provider(config: LocalProviderConfig):
    """
    配置本地 LLM 提供商

    - **provider_type**: 提供商类型
    - **base_url**: 服务地址
    - **model**: 模型名称
    """
    try:
        # 清除旧的服务缓存
        key = f"{config.provider_type}:{config.base_url}:{config.model}"
        if key in _local_services:
            del _local_services[key]

        # 创建新服务
        service = _get_service(
            provider_type=config.provider_type,
            base_url=config.base_url,
            model=config.model,
        )

        # 检查健康状态
        health = await service.health_check()

        return {
            "status": "configured",
            "provider": config.provider_type,
            "base_url": config.base_url,
            "model": config.model,
            "health": health,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
