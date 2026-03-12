"""
LLM API 统一封装层

提供统一的 LLM 调用接口，支持多提供商（OpenAI, Claude, Azure, 通义千问等）

功能:
- 统一的异常处理
- 自动重试机制（指数退避）
- 流式调用支持
- 超时配置统一管理
"""

from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import structlog

from ..config.settings import get_llm_settings
from ..utils.text import clean_json_from_markdown

logger = structlog.get_logger(__name__)


# ============ 异常类 ============

class LLMError(Exception):
    """LLM 调用基础异常"""

    def __init__(self, message: str, provider: str | None = None, original_error: Exception | None = None):
        self.provider = provider
        self.original_error = original_error
        super().__init__(message)


class LLMConfigError(LLMError):
    """配置错误（如 API Key 缺失）"""
    pass


class LLMRateLimitError(LLMError):
    """速率限制错误（429）"""

    def __init__(self, message: str, retry_after: int | None = None, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, **kwargs)


class LLMTimeoutError(LLMError):
    """超时错误"""
    pass


class LLMAPIError(LLMError):
    """API 调用错误"""
    pass


class LLMJSONError(LLMError):
    """JSON 解析错误"""
    pass


# ============ 重试机制 ============

def _should_retry(exception: Exception) -> bool:
    """判断是否应该重试"""
    if isinstance(exception, LLMRateLimitError):
        return True
    if isinstance(exception, LLMAPIError):
        return True
    if isinstance(exception, LLMTimeoutError):
        return True
    # 网络错误
    if isinstance(exception, (ConnectionError, TimeoutError)):
        return True
    return False


async def _retry_with_backoff(
    func,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    **kwargs,
):
    """
    带指数退避的重试机制

    Args:
        func: 要执行的异步函数
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            # 检查是否应该重试
            if not _should_retry(e):
                raise

            # 最后一次尝试不再重试
            if attempt == max_retries:
                raise

            # 计算延迟（指数退避）
            delay = min(base_delay * (2 ** attempt), max_delay)

            # 如果是速率限制，使用 retry_after
            if isinstance(e, LLMRateLimitError) and e.retry_after:
                delay = max(delay, e.retry_after)

            logger.warning(
                "LLM call failed, retrying",
                attempt=attempt + 1,
                max_retries=max_retries,
                delay=delay,
                error=str(e),
            )

            await asyncio.sleep(delay)

    raise last_exception


# ============ 基础类 ============

class LLMResponse:
    """LLM 响应"""

    def __init__(
        self,
        content: str,
        model: str,
        usage: dict[str, int] | None = None,
        finish_reason: str | None = None,
    ):
        self.content = content
        self.model = model
        self.usage = usage or {}
        self.finish_reason = finish_reason

    def __repr__(self) -> str:
        return f"LLMResponse(model={self.model}, content_len={len(self.content)})"


class BaseProvider(ABC):
    """LLM 提供商抽象基类"""

    NAME: str = "base"
    DEFAULT_TIMEOUT: int = 60

    def __init__(self, timeout: int | None = None):
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._httpx_module = None
        self._client: httpx.AsyncClient | None = None

    @property
    def httpx(self):
        """延迟导入 httpx 模块"""
        if self._httpx_module is None:
            import httpx
            self._httpx_module = httpx
        return self._httpx_module

    async def get_client(self) -> httpx.AsyncClient:
        """
        获取共享的 HTTP 客户端实例
        
        使用连接池和 keep-alive 连接复用，避免每次请求都创建新的 TCP 连接
        
        Returns:
            共享的 AsyncClient 实例
        """
        if self._client is None:
            self._client = self.httpx.AsyncClient(
                timeout=120.0,
                limits=self.httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30.0
                )
            )
            logger.debug("创建新的 HTTP 客户端连接池")
        return self._client

    async def close(self):
        """
        关闭 HTTP 客户端并释放资源
        
        应在应用关闭或不再使用 provider 时调用
        """
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("HTTP 客户端连接池已关闭")

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """生成文本"""
        pass

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> dict[str, Any]:
        """
        生成 JSON 格式响应（通用实现）

        子类可以重写此方法以提供特定实现。
        """
        json_prompt = f"{prompt}\n\n请以严格的 JSON 格式回复，不要包含其他文字。"
        content = await self.generate(json_prompt, temperature, max_tokens, **kwargs)

        try:
            cleaned = self._clean_json_response(content)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise LLMJSONError(
                f"JSON 解析失败: {e}",
                provider=self.NAME,
                original_error=e,
            ) from e

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式生成"""
        pass

    def _clean_json_response(self, content: str) -> str:
        """
        清理 JSON 响应中的 markdown 标记

        Args:
            content: 原始响应内容

        Returns:
            清理后的 JSON 字符串
        """
        return clean_json_from_markdown(content)

    def _get_timeout(self, timeout: int | None = None) -> int:
        """获取超时配置"""
        if timeout:
            return timeout
        try:
            settings = get_llm_settings()
            return settings.timeout
        except Exception:
            return self._timeout

    def _handle_api_error(self, response, provider_name: str) -> None:
        """
        处理 API 响应错误（公共方法）

        Args:
            response: httpx 响应对象
            provider_name: 提供商名称

        Raises:
            LLMRateLimitError: 速率限制错误
            LLMAPIError: API 服务错误
        """
        if response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            raise LLMRateLimitError(
                f"{provider_name} API 速率限制",
                provider=provider_name,
                retry_after=int(retry_after) if retry_after else None,
            )

        if response.status_code >= 500:
            raise LLMAPIError(
                f"{provider_name} API 服务错误: {response.status_code}",
                provider=provider_name,
            )

        try:
            response.raise_for_status()
        except Exception as e:
            raise LLMAPIError(
                f"{provider_name} API 调用失败: {e}",
                provider=provider_name,
                original_error=e,
            ) from e

    async def _make_request(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        provider_name: str,
    ) -> dict[str, Any]:
        """
        发送 API 请求（公共方法）

        Args:
            url: 请求 URL
            headers: 请求头
            payload: 请求体
            provider_name: 提供商名称

        Returns:
            JSON 响应数据

        Raises:
            LLMError: API 调用错误
        """
        client = await self.get_client()
        response = await client.post(
            url,
            headers=headers,
            json=payload,
            timeout=self._get_timeout(),
        )
        self._handle_api_error(response, provider_name)
        return response.json()

    async def _stream_request(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> AsyncIterator[str]:
        """
        流式请求（公共方法 - OpenAI 风格）

        Args:
            url: 请求 URL
            headers: 请求头
            payload: 请求体

        Yields:
            内容片段
        """
        client = await self.get_client()
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
                        choice = chunk["choices"][0]
                        delta = choice.get("delta", {})
                        content = delta.get("content", "")

                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


# ============ OpenAI Provider ============

class OpenAIProvider(BaseProvider):
    """OpenAI GPT 提供商"""

    NAME = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-3.5-turbo",
        base_url: str = "https://api.openai.com/v1",
        timeout: int | None = None,
    ):
        super().__init__(timeout=timeout)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url

        if not self.api_key:
            logger.warning("OpenAI API Key 未配置")

        logger.info("OpenAI Provider 初始化完成", model=model, base_url=base_url)

    def _validate_config(self) -> None:
        """验证配置"""
        if not self.api_key:
            raise LLMConfigError(
                "OpenAI API Key 未配置",
                provider=self.NAME,
            )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """实现真实的 OpenAI API 调用"""

        async def _call():
            self._validate_config()

            url = f"{self.base_url}/chat/completions"
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

            logger.debug("调用 OpenAI API", model=self.model)

            data = await self._make_request(url, headers, payload, self.NAME)
            content = data["choices"][0]["message"]["content"]
            logger.debug("OpenAI API 调用成功", usage=data.get("usage", {}))
            return content

        return await _retry_with_backoff(_call)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式调用 OpenAI API"""
        self._validate_config()

        url = f"{self.base_url}/chat/completions"
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

        logger.debug("流式调用 OpenAI API", model=self.model)

        async for content in self._stream_request(url, headers, payload):
            yield content


# ============ Claude Provider ============

class ClaudeProvider(BaseProvider):
    """Anthropic Claude 提供商"""

    NAME = "claude"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-sonnet-20240229",
        timeout: int | None = None,
    ):
        super().__init__(timeout=timeout)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.base_url = "https://api.anthropic.com"

        if not self.api_key:
            logger.warning("Claude API Key 未配置")

        logger.info("Claude Provider 初始化完成", model=model)

    def _validate_config(self) -> None:
        """验证配置"""
        if not self.api_key:
            raise LLMConfigError(
                "Claude API Key 未配置",
                provider=self.NAME,
            )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """实现真实的 Claude API 调用"""

        async def _call():
            self._validate_config()

            url = f"{self.base_url}/v1/messages"
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            payload = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }

            logger.debug("调用 Claude API", model=self.model)

            data = await self._make_request(url, headers, payload, self.NAME)
            content = data["content"][0]["text"]
            logger.debug("Claude API 调用成功")
            return content

        return await _retry_with_backoff(_call)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式调用 Claude API"""
        self._validate_config()

        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }

        logger.debug("流式调用 Claude API", model=self.model)

        client = await self.get_client()
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

                    try:
                        event = json.loads(data)
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                yield text
                    except json.JSONDecodeError:
                        continue


# ============ Azure OpenAI Provider ============

class AzureOpenAIProvider(BaseProvider):
    """Azure OpenAI 提供商"""

    NAME = "azure"

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        deployment: str | None = None,
        api_version: str = "2024-02-15-preview",
        timeout: int | None = None,
    ):
        super().__init__(timeout=timeout)
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment = deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.api_version = api_version

        if not self.api_key or not self.endpoint or not self.deployment:
            logger.warning("Azure OpenAI 配置不完整")

        logger.info(
            "Azure OpenAI Provider 初始化完成",
            deployment=self.deployment,
            endpoint=self.endpoint,
        )

    def _validate_config(self) -> None:
        """验证配置"""
        if not self.api_key:
            raise LLMConfigError(
                "Azure OpenAI API Key 未配置",
                provider=self.NAME,
            )
        if not self.endpoint:
            raise LLMConfigError(
                "Azure OpenAI Endpoint 未配置",
                provider=self.NAME,
            )
        if not self.deployment:
            raise LLMConfigError(
                "Azure OpenAI Deployment 未配置",
                provider=self.NAME,
            )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """调用 Azure OpenAI API"""

        async def _call():
            self._validate_config()

            url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
            headers = {
                "api-key": self.api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            logger.debug("调用 Azure OpenAI API", deployment=self.deployment)

            data = await self._make_request(url, headers, payload, self.NAME)
            content = data["choices"][0]["message"]["content"]
            logger.debug("Azure OpenAI API 调用成功", usage=data.get("usage", {}))
            return content

        return await _retry_with_backoff(_call)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式调用 Azure OpenAI API"""
        self._validate_config()

        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        logger.debug("流式调用 Azure OpenAI API", deployment=self.deployment)

        async for content in self._stream_request(url, headers, payload):
            yield content


# ============ 百炼（通义千问）Provider ============

class BailianProvider(BaseProvider):
    """阿里云百炼（通义千问）提供商"""

    NAME = "bailian"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "qwen-plus",
        timeout: int | None = None,
    ):
        super().__init__(timeout=timeout)
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.model = model

        if not self.api_key:
            logger.warning("百炼 API Key 未配置")

        logger.info("百炼 Provider 初始化完成", model=model)

    def _validate_config(self) -> None:
        """验证配置"""
        if not self.api_key:
            raise LLMConfigError(
                "百炼 API Key 未配置",
                provider=self.NAME,
            )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """实现真实的百炼 API 调用"""

        async def _call():
            self._validate_config()

            url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model,
                "input": {
                    "messages": [{"role": "user", "content": prompt}],
                },
                "parameters": {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            }

            logger.debug("调用百炼 API", model=self.model)

            data = await self._make_request(url, headers, payload, self.NAME)
            content = data["output"]["text"]
            logger.debug("百炼 API 调用成功")
            return content

        return await _retry_with_backoff(_call)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式调用百炼 API（暂不支持）"""
        # 百炼流式 API 格式不同，暂时 fallback 到普通调用
        content = await self.generate(prompt, temperature, max_tokens, **kwargs)
        yield content


# ============ 工厂类 ============

class LLMFactory:
    """LLM 工厂类"""

    _providers: dict[str, BaseProvider] = {}

    @classmethod
    def register(cls, name: str, provider: BaseProvider) -> None:
        """注册提供商"""
        cls._providers[name] = provider
        logger.info("注册 LLM 提供商", name=name)

    @classmethod
    def get(cls, name: str) -> BaseProvider | None:
        """获取提供商"""
        return cls._providers.get(name)

    @classmethod
    def get_default(cls) -> BaseProvider:
        """获取默认提供商"""
        provider_name = os.getenv("LLM_PROVIDER", "openai")
        provider = cls.get(provider_name)
        if not provider:
            if cls._providers:
                provider = list(cls._providers.values())[0]
            else:
                raise LLMConfigError("没有可用的 LLM 提供商")
        return provider

    @classmethod
    def list_providers(cls) -> list[str]:
        """列出所有已注册的提供商"""
        return list(cls._providers.keys())

    @classmethod
    async def clear(cls) -> None:
        """
        清除所有已注册的提供商并释放资源
        
        应在应用关闭时调用，以正确关闭所有 HTTP 连接
        """
        for provider in cls._providers.values():
            try:
                await provider.close()
            except Exception as e:
                logger.warning("关闭 provider 失败", provider=provider.NAME, error=str(e))
        cls._providers.clear()
        logger.info("所有 LLM 提供商已清除")


# ============ 初始化函数 ============

def init_llm_providers() -> None:
    """初始化 LLM 提供商"""
    # 根据环境变量自动注册可用的提供商
    if os.getenv("OPENAI_API_KEY"):
        LLMFactory.register("openai", OpenAIProvider())

    if os.getenv("ANTHROPIC_API_KEY"):
        LLMFactory.register("claude", ClaudeProvider())

    if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
        LLMFactory.register("azure", AzureOpenAIProvider())

    if os.getenv("DASHSCOPE_API_KEY"):
        LLMFactory.register("bailian", BailianProvider())

    # 如果没有自动注册，至少注册一个默认的（用于测试）
    if not LLMFactory._providers:
        logger.warning("未检测到 LLM API Key，使用默认配置")
        LLMFactory.register("openai", OpenAIProvider())

    logger.info("LLM 提供商初始化完成", providers=list(LLMFactory._providers.keys()))


def get_llm(provider_name: str | None = None) -> BaseProvider:
    """获取 LLM 实例"""
    if provider_name:
        provider = LLMFactory.get(provider_name)
        if provider:
            return provider
    return LLMFactory.get_default()


# ============ 便捷函数 ============

async def llm_generate(prompt: str, provider: str | None = None, **kwargs) -> str:
    """便捷函数：生成文本"""
    llm = get_llm(provider)
    return await llm.generate(prompt, **kwargs)


async def llm_generate_json(prompt: str, provider: str | None = None, **kwargs) -> dict[str, Any]:
    """便捷函数：生成 JSON"""
    llm = get_llm(provider)
    return await llm.generate_json(prompt, **kwargs)


async def llm_generate_stream(prompt: str, provider: str | None = None, **kwargs) -> AsyncIterator[str]:
    """便捷函数：流式生成"""
    llm = get_llm(provider)
    async for chunk in llm.generate_stream(prompt, **kwargs):
        yield chunk


async def cleanup_llm_providers() -> None:
    """
    清理所有 LLM 提供商资源
    
    应在应用关闭时调用，以正确关闭所有 HTTP 连接池
    """
    await LLMFactory.clear()
