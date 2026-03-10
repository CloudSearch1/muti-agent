"""
本地 LLM 支持

支持多种本地部署方案：
- Ollama: 简单部署，开箱即用
- vLLM: 高性能推理引擎
- LM Studio: 图形化界面

特性:
- 连接池复用 HTTP 客户端
- 自动重试机制
- 流式响应支持
- 完善的错误处理
"""

from __future__ import annotations

import json
import re
from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Final
from urllib.parse import urlparse

import structlog

from .llm_provider import (
    BaseProvider,
    LLMConfigError,
    LLMError,
    LLMJSONError,
    LLMAPIError,
    LLMTimeoutError,
    _retry_with_backoff,
)

logger = structlog.get_logger(__name__)


# ============ 常量定义 ============

DEFAULT_OLLAMA_URL: Final[str] = "http://localhost:11434"
DEFAULT_VLLM_URL: Final[str] = "http://localhost:8000"
DEFAULT_LMSTUDIO_URL: Final[str] = "http://localhost:1234"
DEFAULT_MODEL_OLLAMA: Final[str] = "llama2"
DEFAULT_MODEL_VLLM: Final[str] = "meta-llama/Llama-2-7b-hf"
DEFAULT_MODEL_LMSTUDIO: Final[str] = "local-model"
DEFAULT_TIMEOUT: Final[int] = 120
HEALTH_CHECK_TIMEOUT: Final[int] = 10
MAX_RETRIES: Final[int] = 2


# ============ 工具函数 ============

def _validate_url(url: str, provider_name: str) -> None:
    """
    验证 URL 格式

    Args:
        url: 要验证的 URL
        provider_name: 提供商名称（用于错误信息）

    Raises:
        LLMConfigError: URL 格式无效时抛出
    """
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            raise LLMConfigError(
                f"{provider_name} URL 格式无效: {url}",
                provider=provider_name,
            )
        if result.scheme not in ("http", "https"):
            raise LLMConfigError(
                f"{provider_name} URL 必须使用 http 或 https 协议: {url}",
                provider=provider_name,
            )
    except Exception as e:
        if isinstance(e, LLMConfigError):
            raise
        raise LLMConfigError(
            f"{provider_name} URL 解析失败: {url}",
            provider=provider_name,
        ) from e


def _clean_json_response(content: str) -> str:
    """
    清理 JSON 响应中的 markdown 标记

    Args:
        content: 原始响应内容

    Returns:
        清理后的 JSON 字符串
    """
    if not content:
        return content

    cleaned = content.strip()

    # 移除 markdown 代码块标记
    patterns = [
        (r'^```json\s*', ''),
        (r'^```\s*', ''),
        (r'\s*```$', ''),
    ]

    for pattern, replacement in patterns:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.MULTILINE)

    return cleaned.strip()


def _extract_stream_content(line: str, provider: str) -> str | None:
    """
    从流式响应行中提取内容

    Args:
        line: 原始响应行
        provider: 提供商名称

    Returns:
        提取的内容，如果没有则返回 None
    """
    if not line or not line.strip():
        return None

    line = line.strip()

    # OpenAI 兼容格式 (vLLM, LM Studio)
    if line.startswith("data: "):
        data = line[6:]
        if data == "[DONE]":
            return None
        try:
            chunk = json.loads(data)
            choice = chunk.get("choices", [{}])[0]
            delta = choice.get("delta", {})
            return delta.get("content", "")
        except (json.JSONDecodeError, KeyError, IndexError):
            return None

    # Ollama 格式
    try:
        data = json.loads(line)
        return data.get("response", "")
    except json.JSONDecodeError:
        return None


# ============ 本地 LLM 基类 ============

class LocalLLMProvider(BaseProvider):
    """
    本地 LLM 提供商基类

    提供本地 LLM 的通用功能:
    - 配置验证
    - 健康检查
    - 连接池管理
    """

    NAME: Final[str] = "local"
    DEFAULT_TIMEOUT = DEFAULT_TIMEOUT

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """
        初始化本地 LLM 提供商

        Args:
            base_url: 服务地址
            model: 模型名称
            timeout: 请求超时时间（秒）

        Raises:
            LLMConfigError: 配置无效时抛出
        """
        super().__init__(timeout=timeout)
        self.base_url = base_url.rstrip("/")
        self.model = model

        # 验证配置
        self._validate_config()

        logger.info(
            f"{self.NAME} Provider 初始化完成",
            model=model,
            base_url=self.base_url,
            timeout=timeout,
        )

    def _validate_config(self) -> None:
        """验证配置"""
        if not self.base_url:
            raise LLMConfigError(
                f"{self.NAME} base_url 未配置",
                provider=self.NAME,
            )
        _validate_url(self.base_url, self.NAME)

    @abstractmethod
    async def check_health(self) -> dict[str, Any]:
        """
        检查服务健康状态

        Returns:
            包含状态信息的字典:
            - status: healthy/unhealthy/unreachable
            - models: 可用模型列表
            - error: 错误信息（如有）
            - provider: 提供商名称
        """
        pass

    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        """
        列出可用模型

        Returns:
            模型信息列表
        """
        pass

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        生成 JSON 格式响应

        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            解析后的 JSON 对象

        Raises:
            LLMJSONError: JSON 解析失败时抛出
        """
        json_prompt = f"{prompt}\n\n请以严格的 JSON 格式回复，不要包含其他文字。"
        content = await self.generate(json_prompt, temperature, max_tokens, **kwargs)

        try:
            cleaned = _clean_json_response(content)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(
                "JSON 解析失败",
                provider=self.NAME,
                error=str(e),
                content_preview=content[:200] if content else "",
            )
            raise LLMJSONError(
                f"JSON 解析失败: {e}",
                provider=self.NAME,
                original_error=e,
            ) from e

    async def _retry_with_backoff(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """
        本地 LLM 的重试机制

        Args:
            func: 要执行的异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果
        """
        return await _retry_with_backoff(
            func,
            *args,
            max_retries=MAX_RETRIES,
            **kwargs,
        )


# ============ Ollama Provider ============

class OllamaProvider(LocalLLMProvider):
    """
    Ollama 本地 LLM 提供商

    使用方法:
        1. 安装 Ollama: https://ollama.ai
        2. 拉取模型: ollama pull llama2
        3. 使用: provider = OllamaProvider(model="llama2")

    支持的功能:
        - 文本生成
        - 流式输出
        - 对话模式
        - 模型管理（下载、列表）
    """

    NAME: Final[str] = "ollama"

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_MODEL_OLLAMA,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """
        初始化 Ollama 提供商

        Args:
            base_url: Ollama 服务地址
            model: 模型名称
            timeout: 请求超时时间
        """
        super().__init__(base_url=base_url, model=model, timeout=timeout)

    async def check_health(self) -> dict[str, Any]:
        """检查 Ollama 服务状态"""
        try:
            async with self.httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=HEALTH_CHECK_TIMEOUT,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "healthy",
                        "models": [m.get("name", "unknown") for m in data.get("models", [])],
                        "provider": self.NAME,
                    }
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "provider": self.NAME,
                }
        except Exception as e:
            logger.warning("Ollama 健康检查失败", error=str(e))
            return {
                "status": "unreachable",
                "error": str(e),
                "provider": self.NAME,
            }

    async def list_models(self) -> list[dict[str, Any]]:
        """列出可用模型"""
        async with self.httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/tags",
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])

    async def pull_model(self, model_name: str) -> dict[str, Any]:
        """
        下载模型

        Args:
            model_name: 模型名称，如 "llama2", "codellama:7b"

        Returns:
            下载结果

        Raises:
            LLMAPIError: 下载失败时抛出
        """
        if not model_name or not model_name.strip():
            raise LLMAPIError(
                "模型名称不能为空",
                provider=self.NAME,
            )

        logger.info("开始下载模型", model=model_name)

        async with self.httpx.AsyncClient(timeout=600) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name.strip(), "stream": False},
                )
                response.raise_for_status()
                result = response.json()
                logger.info("模型下载完成", model=model_name)
                return result
            except Exception as e:
                logger.error("模型下载失败", model=model_name, error=str(e))
                raise LLMAPIError(
                    f"模型下载失败: {e}",
                    provider=self.NAME,
                    original_error=e,
                ) from e

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """
        调用 Ollama 生成 API

        Args:
            prompt: 输入提示
            temperature: 温度参数 (0.0 - 2.0)
            max_tokens: 最大输出 token 数

        Returns:
            生成的文本

        Raises:
            LLMAPIError: API 调用失败时抛出
        """
        # 参数验证
        if not prompt:
            raise LLMAPIError("提示不能为空", provider=self.NAME)
        if not 0.0 <= temperature <= 2.0:
            raise LLMAPIError(
                f"temperature 必须在 0.0 到 2.0 之间，当前值: {temperature}",
                provider=self.NAME,
            )

        async def _call() -> str:
            self._validate_config()

            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            # 添加额外参数
            extra_options = {}
            if "stop" in kwargs:
                extra_options["stop"] = kwargs["stop"]
            if "top_p" in kwargs:
                extra_options["top_p"] = kwargs["top_p"]
            if "top_k" in kwargs:
                extra_options["top_k"] = kwargs["top_k"]
            payload["options"].update(extra_options)

            logger.debug("调用 Ollama API", model=self.model, temperature=temperature)

            async with self.httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=self._get_timeout(),
                )

                if response.status_code >= 500:
                    raise LLMAPIError(
                        f"Ollama 服务错误: {response.status_code}",
                        provider=self.NAME,
                    )

                try:
                    response.raise_for_status()
                except Exception as e:
                    raise LLMAPIError(
                        f"Ollama API 调用失败: {e}",
                        provider=self.NAME,
                        original_error=e,
                    ) from e

                data = response.json()
                content = data.get("response", "")
                logger.debug(
                    "Ollama API 调用成功",
                    eval_count=data.get("eval_count", 0),
                )
                return content

        return await self._retry_with_backoff(_call)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        流式调用 Ollama API

        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Yields:
            生成的文本片段
        """
        if not prompt:
            raise LLMAPIError("提示不能为空", provider=self.NAME)

        self._validate_config()

        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        logger.debug("流式调用 Ollama API", model=self.model)

        async with self.httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                json=payload,
                timeout=self._get_timeout(),
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    content = _extract_stream_content(line, self.NAME)
                    if content:
                        yield content

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """
        对话模式（使用 Ollama Chat API）

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            生成的回复
        """
        if not messages:
            raise LLMAPIError("消息列表不能为空", provider=self.NAME)

        async def _call() -> str:
            self._validate_config()

            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            logger.debug("调用 Ollama Chat API", model=self.model, messages=len(messages))

            async with self.httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=self._get_timeout(),
                )

                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")

        return await self._retry_with_backoff(_call)


# ============ vLLM Provider ============

class VLLMProvider(LocalLLMProvider):
    """
    vLLM 高性能推理提供商

    vLLM 提供 OpenAI 兼容的 API 接口

    使用方法:
        1. 安装 vLLM: pip install vllm
        2. 启动服务: python -m vllm.entrypoints.openai.api_server --model <model_name>
        3. 使用: provider = VLLMProvider(model="meta-llama/Llama-2-7b-hf")
    """

    NAME: Final[str] = "vllm"

    def __init__(
        self,
        base_url: str = DEFAULT_VLLM_URL,
        model: str = DEFAULT_MODEL_VLLM,
        api_key: str = "EMPTY",  # vLLM 默认不需要 API Key
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """
        初始化 vLLM 提供商

        Args:
            base_url: vLLM 服务地址
            model: 模型名称
            api_key: API Key（通常不需要）
            timeout: 请求超时时间
        """
        super().__init__(base_url=base_url, model=model, timeout=timeout)
        self.api_key = api_key

    async def check_health(self) -> dict[str, Any]:
        """检查 vLLM 服务状态"""
        try:
            async with self.httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    timeout=HEALTH_CHECK_TIMEOUT,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "healthy",
                        "models": [m.get("id", "unknown") for m in data.get("data", [])],
                        "provider": self.NAME,
                    }
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "provider": self.NAME,
                }
        except Exception as e:
            logger.warning("vLLM 健康检查失败", error=str(e))
            return {
                "status": "unreachable",
                "error": str(e),
                "provider": self.NAME,
            }

    async def list_models(self) -> list[dict[str, Any]]:
        """列出可用模型"""
        async with self.httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """
        调用 vLLM 生成 API (OpenAI 兼容)

        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            生成的文本
        """
        if not prompt:
            raise LLMAPIError("提示不能为空", provider=self.NAME)

        async def _call() -> str:
            self._validate_config()

            url = f"{self.base_url}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # vLLM 特有参数
            vllm_params = ["top_p", "top_k", "repetition_penalty"]
            for param in vllm_params:
                if param in kwargs:
                    payload[param] = kwargs[param]

            logger.debug("调用 vLLM API", model=self.model)

            async with self.httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._get_timeout(),
                )

                if response.status_code >= 500:
                    raise LLMAPIError(
                        f"vLLM 服务错误: {response.status_code}",
                        provider=self.NAME,
                    )

                try:
                    response.raise_for_status()
                except Exception as e:
                    raise LLMAPIError(
                        f"vLLM API 调用失败: {e}",
                        provider=self.NAME,
                        original_error=e,
                    ) from e

                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.debug("vLLM API 调用成功", usage=data.get("usage", {}))
                return content

        return await self._retry_with_backoff(_call)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        流式调用 vLLM API

        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Yields:
            生成的文本片段
        """
        if not prompt:
            raise LLMAPIError("提示不能为空", provider=self.NAME)

        self._validate_config()

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        logger.debug("流式调用 vLLM API", model=self.model)

        async with self.httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
                timeout=self._get_timeout(),
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            choice = chunk.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue


# ============ LM Studio Provider ============

class LMStudioProvider(LocalLLMProvider):
    """
    LM Studio 本地 LLM 提供商

    LM Studio 提供 OpenAI 兼容的 API 接口

    使用方法:
        1. 下载安装 LM Studio: https://lmstudio.ai
        2. 在 LM Studio 中加载模型
        3. 启动本地服务器 (默认端口 1234)
        4. 使用: provider = LMStudioProvider(model="local-model")
    """

    NAME: Final[str] = "lmstudio"

    def __init__(
        self,
        base_url: str = DEFAULT_LMSTUDIO_URL,
        model: str = DEFAULT_MODEL_LMSTUDIO,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """
        初始化 LM Studio 提供商

        Args:
            base_url: LM Studio 服务地址
            model: 模型名称
            timeout: 请求超时时间
        """
        super().__init__(base_url=base_url, model=model, timeout=timeout)

    async def check_health(self) -> dict[str, Any]:
        """检查 LM Studio 服务状态"""
        try:
            async with self.httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    timeout=HEALTH_CHECK_TIMEOUT,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "healthy",
                        "models": [m.get("id", "unknown") for m in data.get("data", [])],
                        "provider": self.NAME,
                    }
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "provider": self.NAME,
                }
        except Exception as e:
            logger.warning("LM Studio 健康检查失败", error=str(e))
            return {
                "status": "unreachable",
                "error": str(e),
                "provider": self.NAME,
            }

    async def list_models(self) -> list[dict[str, Any]]:
        """列出可用模型"""
        async with self.httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/models",
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """
        调用 LM Studio 生成 API (OpenAI 兼容)

        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            生成的文本
        """
        if not prompt:
            raise LLMAPIError("提示不能为空", provider=self.NAME)

        async def _call() -> str:
            self._validate_config()

            url = f"{self.base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            logger.debug("调用 LM Studio API")

            async with self.httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._get_timeout(),
                )

                if response.status_code >= 500:
                    raise LLMAPIError(
                        f"LM Studio 服务错误: {response.status_code}",
                        provider=self.NAME,
                    )

                try:
                    response.raise_for_status()
                except Exception as e:
                    raise LLMAPIError(
                        f"LM Studio API 调用失败: {e}",
                        provider=self.NAME,
                        original_error=e,
                    ) from e

                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.debug("LM Studio API 调用成功")
                return content

        return await self._retry_with_backoff(_call)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        流式调用 LM Studio API

        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Yields:
            生成的文本片段
        """
        if not prompt:
            raise LLMAPIError("提示不能为空", provider=self.NAME)

        self._validate_config()

        url = f"{self.base_url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        logger.debug("流式调用 LM Studio API")

        async with self.httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
                timeout=self._get_timeout(),
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            choice = chunk.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue


# ============ 本地 LLM 服务 ============

class LocalLLMService:
    """
    本地 LLM 服务

    统一管理 Ollama/vLLM/LM Studio 等本地 LLM

    使用示例:
        service = LocalLLMService(provider_type="ollama", model="llama2")
        response = await service.generate("你好")
    """

    PROVIDER_TYPES: Final[dict[str, type[LocalLLMProvider]]] = {
        "ollama": OllamaProvider,
        "vllm": VLLMProvider,
        "lmstudio": LMStudioProvider,
    }

    def __init__(
        self,
        provider_type: str = "ollama",
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """
        初始化本地 LLM 服务

        Args:
            provider_type: 提供商类型 (ollama/vllm/lmstudio)
            base_url: 服务地址
            model: 模型名称
            timeout: 请求超时时间

        Raises:
            ValueError: 不支持的提供商类型时抛出
        """
        self._provider_type = provider_type
        self._provider: LocalLLMProvider | None = None

        # 获取提供商类
        provider_class = self.PROVIDER_TYPES.get(provider_type)
        if not provider_class:
            supported = ", ".join(self.PROVIDER_TYPES.keys())
            raise ValueError(
                f"不支持的本地 LLM 类型: {provider_type}。支持的类型: {supported}"
            )

        # 创建提供商实例
        provider_kwargs = {"timeout": timeout}
        if base_url:
            provider_kwargs["base_url"] = base_url
        if model:
            provider_kwargs["model"] = model

        self._provider = provider_class(**provider_kwargs)

        logger.info(
            "本地 LLM 服务初始化完成",
            provider=provider_type,
            model=model or "default",
        )

    @property
    def provider(self) -> LocalLLMProvider | None:
        """获取提供商"""
        return self._provider

    @property
    def provider_type(self) -> str:
        """获取提供商类型"""
        return self._provider_type

    async def health_check(self) -> dict[str, Any]:
        """
        检查服务健康状态

        Returns:
            健康状态信息
        """
        if not self._provider:
            return {
                "status": "not_configured",
                "provider": self._provider_type,
            }
        return await self._provider.check_health()

    async def list_models(self) -> list[dict[str, Any]]:
        """
        列出可用模型

        Returns:
            模型信息列表
        """
        if not self._provider:
            return []
        return await self._provider.list_models()

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """
        生成文本

        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            生成的文本
        """
        if not self._provider:
            raise LLMConfigError("本地 LLM 提供商未配置")
        return await self._provider.generate(prompt, temperature, max_tokens, **kwargs)

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        生成 JSON

        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            解析后的 JSON 对象
        """
        if not self._provider:
            raise LLMConfigError("本地 LLM 提供商未配置")
        return await self._provider.generate_json(prompt, temperature, max_tokens, **kwargs)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        流式生成

        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Yields:
            生成的文本片段
        """
        if not self._provider:
            raise LLMConfigError("本地 LLM 提供商未配置")
        async for chunk in self._provider.generate_stream(
            prompt, temperature, max_tokens, **kwargs
        ):
            yield chunk


# ============ 便捷函数 ============

_local_services: dict[str, LocalLLMService] = {}


def get_local_llm(
    provider_type: str = "ollama",
    base_url: str | None = None,
    model: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> LocalLLMService:
    """
    获取本地 LLM 服务（带缓存）

    Args:
        provider_type: 提供商类型 (ollama/vllm/lmstudio)
        base_url: 服务地址
        model: 模型名称
        timeout: 请求超时时间

    Returns:
        本地 LLM 服务实例
    """
    key = f"{provider_type}:{base_url}:{model}:{timeout}"

    if key not in _local_services:
        _local_services[key] = LocalLLMService(
            provider_type=provider_type,
            base_url=base_url,
            model=model,
            timeout=timeout,
        )

    return _local_services[key]


def clear_local_llm_cache() -> None:
    """清除本地 LLM 服务缓存"""
    global _local_services
    _local_services = {}
    logger.info("本地 LLM 服务缓存已清除")


async def local_llm_generate(
    prompt: str,
    provider_type: str = "ollama",
    model: str | None = None,
    **kwargs: Any,
) -> str:
    """
    便捷函数：本地 LLM 生成

    Args:
        prompt: 输入提示
        provider_type: 提供商类型
        model: 模型名称

    Returns:
        生成的文本
    """
    service = get_local_llm(provider_type=provider_type, model=model)
    return await service.generate(prompt, **kwargs)