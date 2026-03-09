"""
本地 LLM 支持

支持多种本地部署方案：
- Ollama: 简单部署，开箱即用
- vLLM: 高性能推理引擎
- LM Studio: 图形化界面
"""

from __future__ import annotations

import json
from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import structlog

from .llm_provider import BaseProvider, LLMConfigError, LLMError, LLMJSONError, LLMAPIError

logger = structlog.get_logger(__name__)


# ============ 本地 LLM 基类 ============

class LocalLLMProvider(BaseProvider):
    """本地 LLM 提供商基类"""

    NAME = "local"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama2",
        timeout: int = 120,  # 本地模型可能需要更长超时
    ):
        super().__init__(timeout=timeout)
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _validate_config(self) -> None:
        """验证配置"""
        if not self.base_url:
            raise LLMConfigError(
                "本地 LLM base_url 未配置",
                provider=self.NAME,
            )

    async def check_health(self) -> dict[str, Any]:
        """检查服务健康状态"""
        raise NotImplementedError


# ============ Ollama Provider ============

class OllamaProvider(LocalLLMProvider):
    """
    Ollama 本地 LLM 提供商

    使用方法:
        1. 安装 Ollama: https://ollama.ai
        2. 拉取模型: ollama pull llama2
        3. 使用: provider = OllamaProvider(model="llama2")
    """

    NAME = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama2",
        timeout: int = 120,
    ):
        super().__init__(base_url=base_url, model=model, timeout=timeout)
        logger.info("Ollama Provider 初始化完成", model=model, base_url=base_url)

    async def check_health(self) -> dict[str, Any]:
        """检查 Ollama 服务状态"""
        try:
            async with self.httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "healthy",
                        "models": [m["name"] for m in data.get("models", [])],
                        "provider": self.NAME,
                    }
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "provider": self.NAME,
                }
        except Exception as e:
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
        """
        logger.info("开始下载模型", model=model_name)

        async with self.httpx.AsyncClient(timeout=600) as client:
            response = await client.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": False},
            )
            response.raise_for_status()
            return response.json()

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """调用 Ollama 生成 API"""

        async def _call():
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
            if "stop" in kwargs:
                payload["options"]["stop"] = kwargs["stop"]
            if "top_p" in kwargs:
                payload["options"]["top_p"] = kwargs["top_p"]
            if "top_k" in kwargs:
                payload["options"]["top_k"] = kwargs["top_k"]

            logger.debug("调用 Ollama API", model=self.model)

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
                    )

                data = response.json()
                content = data.get("response", "")
                logger.debug(
                    "Ollama API 调用成功",
                    eval_count=data.get("eval_count", 0),
                )
                return content

        return await self._retry_with_backoff(_call)

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> dict[str, Any]:
        """生成 JSON 格式响应"""
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
            )

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式调用 Ollama API"""
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
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """
        对话模式（使用 Ollama Chat API）

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
        """
        async def _call():
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

            logger.debug("调用 Ollama Chat API", model=self.model)

            async with self.httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=self._get_timeout(),
                )

                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]

        return await self._retry_with_backoff(_call)

    def _clean_json_response(self, content: str) -> str:
        """清理 JSON 响应中的 markdown 标记"""
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """本地 LLM 的重试机制（更长的超时）"""
        from .llm_provider import _retry_with_backoff
        return await _retry_with_backoff(func, *args, max_retries=2, **kwargs)


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

    NAME = "vllm"

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model: str = "meta-llama/Llama-2-7b-hf",
        api_key: str = "EMPTY",  # vLLM 默认不需要 API Key
        timeout: int = 120,
    ):
        super().__init__(base_url=base_url, model=model, timeout=timeout)
        self.api_key = api_key
        logger.info("vLLM Provider 初始化完成", model=model, base_url=base_url)

    async def check_health(self) -> dict[str, Any]:
        """检查 vLLM 服务状态"""
        try:
            async with self.httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "healthy",
                        "models": [m["id"] for m in data.get("data", [])],
                        "provider": self.NAME,
                    }
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "provider": self.NAME,
                }
        except Exception as e:
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
        **kwargs,
    ) -> str:
        """调用 vLLM 生成 API (OpenAI 兼容)"""

        async def _call():
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
            if "top_p" in kwargs:
                payload["top_p"] = kwargs["top_p"]
            if "top_k" in kwargs:
                payload["top_k"] = kwargs["top_k"]
            if "repetition_penalty" in kwargs:
                payload["repetition_penalty"] = kwargs["repetition_penalty"]

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
                    )

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.debug("vLLM API 调用成功", usage=data.get("usage", {}))
                return content

        return await self._retry_with_backoff(_call)

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> dict[str, Any]:
        """生成 JSON 格式响应"""
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
            )

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式调用 vLLM API"""
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
                            choice = chunk["choices"][0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

    def _clean_json_response(self, content: str) -> str:
        """清理 JSON 响应"""
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """本地 LLM 的重试机制"""
        from .llm_provider import _retry_with_backoff
        return await _retry_with_backoff(func, *args, max_retries=2, **kwargs)


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

    NAME = "lmstudio"

    def __init__(
        self,
        base_url: str = "http://localhost:1234",
        model: str = "local-model",
        timeout: int = 120,
    ):
        super().__init__(base_url=base_url, model=model, timeout=timeout)
        logger.info("LM Studio Provider 初始化完成", base_url=base_url)

    async def check_health(self) -> dict[str, Any]:
        """检查 LM Studio 服务状态"""
        try:
            async with self.httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "healthy",
                        "models": [m["id"] for m in data.get("data", [])],
                        "provider": self.NAME,
                    }
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "provider": self.NAME,
                }
        except Exception as e:
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
        **kwargs,
    ) -> str:
        """调用 LM Studio 生成 API (OpenAI 兼容)"""

        async def _call():
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
                    )

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.debug("LM Studio API 调用成功")
                return content

        return await self._retry_with_backoff(_call)

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> dict[str, Any]:
        """生成 JSON 格式响应"""
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
            )

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式调用 LM Studio API"""
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
                            choice = chunk["choices"][0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

    def _clean_json_response(self, content: str) -> str:
        """清理 JSON 响应"""
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """本地 LLM 的重试机制"""
        from .llm_provider import _retry_with_backoff
        return await _retry_with_backoff(func, *args, max_retries=2, **kwargs)


# ============ 本地 LLM 服务 ============

class LocalLLMService:
    """
    本地 LLM 服务

    统一管理 Ollama/vLLM/LM Studio 等本地 LLM
    """

    def __init__(
        self,
        provider_type: str = "ollama",
        base_url: str | None = None,
        model: str | None = None,
    ):
        self._provider_type = provider_type
        self._provider: LocalLLMProvider | None = None

        # 根据类型创建提供商
        if provider_type == "ollama":
            self._provider = OllamaProvider(
                base_url=base_url or "http://localhost:11434",
                model=model or "llama2",
            )
        elif provider_type == "vllm":
            self._provider = VLLMProvider(
                base_url=base_url or "http://localhost:8000",
                model=model or "meta-llama/Llama-2-7b-hf",
            )
        elif provider_type == "lmstudio":
            self._provider = LMStudioProvider(
                base_url=base_url or "http://localhost:1234",
                model=model or "local-model",
            )
        else:
            raise ValueError(f"不支持的本地 LLM 类型: {provider_type}")

        logger.info(
            "本地 LLM 服务初始化完成",
            provider=provider_type,
            model=model,
        )

    @property
    def provider(self) -> LocalLLMProvider | None:
        """获取提供商"""
        return self._provider

    async def health_check(self) -> dict[str, Any]:
        """检查服务健康状态"""
        if not self._provider:
            return {
                "status": "not_configured",
                "provider": self._provider_type,
            }
        return await self._provider.check_health()

    async def list_models(self) -> list[dict[str, Any]]:
        """列出可用模型"""
        if not self._provider:
            return []
        return await self._provider.list_models()

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """生成文本"""
        if not self._provider:
            raise LLMConfigError("本地 LLM 提供商未配置")
        return await self._provider.generate(prompt, temperature, max_tokens, **kwargs)

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> dict[str, Any]:
        """生成 JSON"""
        if not self._provider:
            raise LLMConfigError("本地 LLM 提供商未配置")
        return await self._provider.generate_json(prompt, temperature, max_tokens, **kwargs)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式生成"""
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
) -> LocalLLMService:
    """
    获取本地 LLM 服务

    Args:
        provider_type: 提供商类型 (ollama/vllm/lmstudio)
        base_url: 服务地址
        model: 模型名称

    Returns:
        本地 LLM 服务实例
    """
    key = f"{provider_type}:{base_url}:{model}"

    if key not in _local_services:
        _local_services[key] = LocalLLMService(
            provider_type=provider_type,
            base_url=base_url,
            model=model,
        )

    return _local_services[key]


async def local_llm_generate(
    prompt: str,
    provider_type: str = "ollama",
    model: str | None = None,
    **kwargs,
) -> str:
    """便捷函数：本地 LLM 生成"""
    service = get_local_llm(provider_type=provider_type, model=model)
    return await service.generate(prompt, **kwargs)