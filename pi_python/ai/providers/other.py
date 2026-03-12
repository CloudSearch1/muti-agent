"""
其他 LLM 提供商的简化实现
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from ..stream import AssistantMessageEventStream, EventBuilder, StreamOptions
from ..types import AssistantMessage, Context, Model, StopReason, TextContent
from .base import BaseProvider


class GoogleProvider(BaseProvider):
    """
    Google Gemini 提供商。

    支持 Google Gemini 系列模型的流式生成。

    Attributes:
        NAME: 提供商名称标识符
    """

    NAME = "google"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """
        流式生成消息。

        Args:
            model: 模型配置信息
            context: 对话上下文，包含消息历史
            options: 流式生成选项

        Returns:
            AssistantMessageEventStream: 异步事件流

        Raises:
            ValueError: 当 API Key 未配置时返回错误事件流
        """
        stream = AssistantMessageEventStream()
        api_key = self._get_api_key(options, "GOOGLE_API_KEY")

        if not api_key:
            stream.emit_sync(EventBuilder.error("Google API Key 未配置"))
            return stream

        url = f"{model.base_url}/models/{model.id}:streamGenerateContent?key={api_key}"

        # 简化的 Gemini 请求格式
        contents = []
        for msg in context.messages:
            role = "user" if msg.role == "user" else "model"
            text = getattr(msg, "text", "") or ""
            contents.append({"role": role, "parts": [{"text": text}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": options.temperature,
                "maxOutputTokens": options.max_tokens,
            }
        }

        asyncio.create_task(self._process_stream(stream, url, payload))
        return stream

    async def _process_stream(
        self,
        stream: AssistantMessageEventStream,
        url: str,
        payload: dict[str, Any],
    ) -> None:
        """
        处理 Google Gemini API 的流式响应。

        Args:
            stream: 事件流对象，用于发射事件
            url: API 请求 URL
            payload: 请求体数据

        Note:
            此方法在后台任务中执行，解析 Gemini API 的 SSE 响应。
        """
        try:
            stream.emit_sync(EventBuilder.start())

            async with self.client.stream(
                "POST",
                url,
                json=payload,
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()

                content_parts = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if "candidates" in data:
                            for part in data["candidates"][0].get("content", {}).get("parts", []):
                                if "text" in part:
                                    content_parts.append(part["text"])
                                    stream.emit_sync(EventBuilder.text_delta(0, part["text"]))

                message = AssistantMessage(content=[TextContent(text="".join(content_parts))])
                stream.emit_sync(EventBuilder.done(StopReason.STOP, message))

        except Exception as e:
            stream.emit_sync(EventBuilder.error(str(e)))


class AzureProvider(BaseProvider):
    """
    Azure OpenAI 提供商。

    通过 Azure OpenAI Service 调用 OpenAI 模型。

    Attributes:
        NAME: 提供商名称标识符
    """

    NAME = "azure"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """
        流式生成消息。

        Args:
            model: 模型配置信息
            context: 对话上下文
            options: 流式生成选项

        Returns:
            AssistantMessageEventStream: 异步事件流

        Note:
            复用 OpenAI 提供商的实现，通过 Azure 端点调用。
        """
        stream = AssistantMessageEventStream()
        api_key = self._get_api_key(options, "AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", model.base_url)
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", model.id)

        if not api_key:
            stream.emit_sync(EventBuilder.error("Azure OpenAI API Key 未配置"))
            return stream

        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-15-preview"

        # 复用 OpenAI 格式
        from .openai import OpenAIProvider
        openai_provider = OpenAIProvider(api_key=api_key, base_url=url)
        return await openai_provider.stream(model, context, options)


class BedrockProvider(BaseProvider):
    """
    AWS Bedrock 提供商。

    支持 AWS Bedrock 平台上的各种基础模型。

    Attributes:
        NAME: 提供商名称标识符

    Note:
        当前尚未实现，调用时返回错误事件流。
    """

    NAME = "bedrock"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """
        流式生成消息。

        Args:
            model: 模型配置信息
            context: 对话上下文
            options: 流式生成选项

        Returns:
            AssistantMessageEventStream: 异步事件流（当前返回未实现错误）
        """
        stream = AssistantMessageEventStream()
        stream.emit_sync(EventBuilder.error("Bedrock 提供商尚未实现"))
        return stream


class MistralProvider(BaseProvider):
    """
    Mistral AI 提供商。

    支持 Mistral 系列模型，通过 OpenAI 兼容 API 调用。

    Attributes:
        NAME: 提供商名称标识符
    """

    NAME = "mistral"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """
        流式生成消息。

        Args:
            model: 模型配置信息
            context: 对话上下文
            options: 流式生成选项

        Returns:
            AssistantMessageEventStream: 异步事件流

        Note:
            使用 OpenAI 兼容 API 端点 https://api.mistral.ai/v1
        """
        stream = AssistantMessageEventStream()
        api_key = self._get_api_key(options, "MISTRAL_API_KEY")

        if not api_key:
            stream.emit_sync(EventBuilder.error("Mistral API Key 未配置"))
            return stream

        # 使用 OpenAI 兼容 API
        from .openai import OpenAIProvider
        openai_provider = OpenAIProvider(
            api_key=api_key,
            base_url="https://api.mistral.ai/v1"
        )
        return await openai_provider.stream(model, context, options)


class GroqProvider(BaseProvider):
    """
    Groq 提供商。

    支持 Groq 平台上的高速推理模型，通过 OpenAI 兼容 API 调用。

    Attributes:
        NAME: 提供商名称标识符
    """

    NAME = "groq"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """
        流式生成消息。

        Args:
            model: 模型配置信息
            context: 对话上下文
            options: 流式生成选项

        Returns:
            AssistantMessageEventStream: 异步事件流

        Note:
            使用 OpenAI 兼容 API 端点 https://api.groq.com/openai/v1
        """
        stream = AssistantMessageEventStream()
        api_key = self._get_api_key(options, "GROQ_API_KEY")

        if not api_key:
            stream.emit_sync(EventBuilder.error("Groq API Key 未配置"))
            return stream

        # 使用 OpenAI 兼容 API
        from .openai import OpenAIProvider
        openai_provider = OpenAIProvider(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        return await openai_provider.stream(model, context, options)


class OpenRouterProvider(BaseProvider):
    """
    OpenRouter 提供商。

    OpenRouter 是一个统一的 LLM API 网关，支持多种模型提供商。
    通过 OpenAI 兼容 API 调用。

    Attributes:
        NAME: 提供商名称标识符
    """

    NAME = "openrouter"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """
        流式生成消息。

        Args:
            model: 模型配置信息
            context: 对话上下文
            options: 流式生成选项

        Returns:
            AssistantMessageEventStream: 异步事件流

        Note:
            使用 OpenAI 兼容 API 端点 https://openrouter.ai/api/v1
        """
        stream = AssistantMessageEventStream()
        api_key = self._get_api_key(options, "OPENROUTER_API_KEY")

        if not api_key:
            stream.emit_sync(EventBuilder.error("OpenRouter API Key 未配置"))
            return stream

        # 使用 OpenAI 兼容 API
        from .openai import OpenAIProvider
        openai_provider = OpenAIProvider(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        return await openai_provider.stream(model, context, options)


class OllamaProvider(BaseProvider):
    """
    Ollama 本地提供商。

    支持 Ollama 运行的本地开源模型，无需外部 API 调用。

    Attributes:
        NAME: 提供商名称标识符
    """

    NAME = "ollama"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """
        流式生成消息。

        Args:
            model: 模型配置信息（base_url 默认为 http://localhost:11434）
            context: 对话上下文
            options: 流式生成选项

        Returns:
            AssistantMessageEventStream: 异步事件流

        Note:
            需要本地运行 Ollama 服务。
        """
        stream = AssistantMessageEventStream()
        base_url = model.base_url or "http://localhost:11434"

        url = f"{base_url}/api/chat"

        messages = []
        if context.system_prompt:
            messages.append({"role": "system", "content": context.system_prompt})

        for msg in context.messages:
            if hasattr(msg, "text"):
                messages.append({"role": msg.role, "content": msg.text})

        payload = {
            "model": model.id,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": options.temperature,
                "num_predict": options.max_tokens,
            }
        }

        asyncio.create_task(self._process_stream(stream, url, payload))
        return stream

    async def _process_stream(
        self,
        stream: AssistantMessageEventStream,
        url: str,
        payload: dict[str, Any],
    ) -> None:
        """
        处理 Ollama API 的流式响应。

        Args:
            stream: 事件流对象，用于发射事件
            url: Ollama API URL（默认 http://localhost:11434/api/chat）
            payload: 请求体数据

        Note:
            此方法在后台任务中执行，解析 Ollama 的 JSON 行响应。
        """
        try:
            stream.emit_sync(EventBuilder.start())

            async with self.client.stream(
                "POST",
                url,
                json=payload,
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()

                content_parts = []
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "message" in data:
                            content = data["message"].get("content", "")
                            if content:
                                content_parts.append(content)
                                stream.emit_sync(EventBuilder.text_delta(0, content))
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

                message = AssistantMessage(content=[TextContent(text="".join(content_parts))])
                stream.emit_sync(EventBuilder.done(StopReason.STOP, message))

        except Exception as e:
            stream.emit_sync(EventBuilder.error(str(e)))


class VLLMProvider(BaseProvider):
    """
    vLLM 提供商。

    支持 vLLM 部署的高性能推理服务，通过 OpenAI 兼容 API 调用。

    Attributes:
        NAME: 提供商名称标识符
    """

    NAME = "vllm"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """
        流式生成消息。

        Args:
            model: 模型配置信息（base_url 默认为 http://localhost:8000/v1）
            context: 对话上下文
            options: 流式生成选项

        Returns:
            AssistantMessageEventStream: 异步事件流

        Note:
            使用 OpenAI 兼容 API，需要本地或远程运行 vLLM 服务。
        """
        # vLLM 使用 OpenAI 兼容 API
        from .openai import OpenAIProvider
        base_url = model.base_url or "http://localhost:8000/v1"
        openai_provider = OpenAIProvider(base_url=base_url)
        return await openai_provider.stream(model, context, options)


# 注册所有提供商
from ..model import register_provider


async def google_stream(
    model: Model,
    context: Context,
    options: StreamOptions
) -> AssistantMessageEventStream:
    """
    Google Gemini 流式生成便捷函数。

    Args:
        model: 模型配置信息
        context: 对话上下文
        options: 流式生成选项

    Returns:
        AssistantMessageEventStream: 异步事件流
    """
    return await GoogleProvider().stream(model, context, options)


async def azure_stream(
    model: Model,
    context: Context,
    options: StreamOptions
) -> AssistantMessageEventStream:
    """
    Azure OpenAI 流式生成便捷函数。

    Args:
        model: 模型配置信息
        context: 对话上下文
        options: 流式生成选项

    Returns:
        AssistantMessageEventStream: 异步事件流
    """
    return await AzureProvider().stream(model, context, options)


async def bedrock_stream(
    model: Model,
    context: Context,
    options: StreamOptions
) -> AssistantMessageEventStream:
    """
    AWS Bedrock 流式生成便捷函数。

    Args:
        model: 模型配置信息
        context: 对话上下文
        options: 流式生成选项

    Returns:
        AssistantMessageEventStream: 异步事件流（当前返回未实现错误）
    """
    return await BedrockProvider().stream(model, context, options)


async def mistral_stream(
    model: Model,
    context: Context,
    options: StreamOptions
) -> AssistantMessageEventStream:
    """
    Mistral AI 流式生成便捷函数。

    Args:
        model: 模型配置信息
        context: 对话上下文
        options: 流式生成选项

    Returns:
        AssistantMessageEventStream: 异步事件流
    """
    return await MistralProvider().stream(model, context, options)


async def groq_stream(
    model: Model,
    context: Context,
    options: StreamOptions
) -> AssistantMessageEventStream:
    """
    Groq 流式生成便捷函数。

    Args:
        model: 模型配置信息
        context: 对话上下文
        options: 流式生成选项

    Returns:
        AssistantMessageEventStream: 异步事件流
    """
    return await GroqProvider().stream(model, context, options)


async def openrouter_stream(
    model: Model,
    context: Context,
    options: StreamOptions
) -> AssistantMessageEventStream:
    """
    OpenRouter 流式生成便捷函数。

    Args:
        model: 模型配置信息
        context: 对话上下文
        options: 流式生成选项

    Returns:
        AssistantMessageEventStream: 异步事件流
    """
    return await OpenRouterProvider().stream(model, context, options)


async def ollama_stream(
    model: Model,
    context: Context,
    options: StreamOptions
) -> AssistantMessageEventStream:
    """
    Ollama 本地流式生成便捷函数。

    Args:
        model: 模型配置信息
        context: 对话上下文
        options: 流式生成选项

    Returns:
        AssistantMessageEventStream: 异步事件流
    """
    return await OllamaProvider().stream(model, context, options)


async def vllm_stream(
    model: Model,
    context: Context,
    options: StreamOptions
) -> AssistantMessageEventStream:
    """
    vLLM 流式生成便捷函数。

    Args:
        model: 模型配置信息
        context: 对话上下文
        options: 流式生成选项

    Returns:
        AssistantMessageEventStream: 异步事件流
    """
    return await VLLMProvider().stream(model, context, options)


# 注册所有提供商
register_provider("google", google_stream)
register_provider("azure", azure_stream)
register_provider("bedrock", bedrock_stream)
register_provider("mistral", mistral_stream)
register_provider("groq", groq_stream)
register_provider("openrouter", openrouter_stream)
register_provider("ollama", ollama_stream)
register_provider("vllm", vllm_stream)
