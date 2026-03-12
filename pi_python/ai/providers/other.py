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
    """Google Gemini 提供商"""

    NAME = "google"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
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
    """Azure OpenAI 提供商"""

    NAME = "azure"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
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
    """AWS Bedrock 提供商"""

    NAME = "bedrock"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        stream = AssistantMessageEventStream()
        stream.emit_sync(EventBuilder.error("Bedrock 提供商尚未实现"))
        return stream


class MistralProvider(BaseProvider):
    """Mistral 提供商"""

    NAME = "mistral"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
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
    """Groq 提供商"""

    NAME = "groq"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
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
    """OpenRouter 提供商"""

    NAME = "openrouter"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
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
    """Ollama 本地提供商"""

    NAME = "ollama"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
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
    """vLLM 提供商"""

    NAME = "vllm"

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        # vLLM 使用 OpenAI 兼容 API
        from .openai import OpenAIProvider
        base_url = model.base_url or "http://localhost:8000/v1"
        openai_provider = OpenAIProvider(base_url=base_url)
        return await openai_provider.stream(model, context, options)


# 注册所有提供商
from ..model import register_provider


async def google_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    return await GoogleProvider().stream(model, context, options)

async def azure_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    return await AzureProvider().stream(model, context, options)

async def bedrock_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    return await BedrockProvider().stream(model, context, options)

async def mistral_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    return await MistralProvider().stream(model, context, options)

async def groq_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    return await GroqProvider().stream(model, context, options)

async def openrouter_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    return await OpenRouterProvider().stream(model, context, options)

async def ollama_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    return await OllamaProvider().stream(model, context, options)

async def vllm_stream(model: Model, context: Context, options: StreamOptions) -> AssistantMessageEventStream:
    return await VLLMProvider().stream(model, context, options)

# 注册
register_provider("google", google_stream)
register_provider("azure", azure_stream)
register_provider("bedrock", bedrock_stream)
register_provider("mistral", mistral_stream)
register_provider("groq", groq_stream)
register_provider("openrouter", openrouter_stream)
register_provider("ollama", ollama_stream)
register_provider("vllm", vllm_stream)
