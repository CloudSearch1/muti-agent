"""
LLM 服务模块

提供统一的 LLM 调用接口，支持多提供商
"""

from .llm_provider import (
    AzureOpenAIProvider,
    BailianProvider,
    BaseProvider,
    ClaudeProvider,
    LLMConfigError,
    LLMError,
    LLMFactory,
    LLMJSONError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
    OpenAIProvider,
    get_llm,
    init_llm_providers,
    llm_generate,
    llm_generate_json,
    llm_generate_stream,
)
from .local import (
    LMStudioProvider,
    LocalLLMProvider,
    LocalLLMService,
    OllamaProvider,
    VLLMProvider,
    get_local_llm,
    local_llm_generate,
)
from .service import LLMService, get_llm_service

__all__ = [
    # 异常类
    "LLMError",
    "LLMConfigError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMAPIError",
    "LLMJSONError",
    # 基础类
    "BaseProvider",
    "LLMResponse",
    "LLMFactory",
    # 云端提供商
    "OpenAIProvider",
    "ClaudeProvider",
    "AzureOpenAIProvider",
    "BailianProvider",
    # 本地 LLM 提供商
    "LocalLLMProvider",
    "OllamaProvider",
    "VLLMProvider",
    "LMStudioProvider",
    # 服务
    "LLMService",
    "get_llm_service",
    "LocalLLMService",
    "get_local_llm",
    # 便捷函数
    "get_llm",
    "init_llm_providers",
    "llm_generate",
    "llm_generate_json",
    "llm_generate_stream",
    "local_llm_generate",
]

# 定义模块级别的异常别名
LLMAPIError = LLMError
