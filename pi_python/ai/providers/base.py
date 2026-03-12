"""
PI-Python 基础提供商

所有提供商的抽象基类
"""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..stream import AssistantMessageEventStream, StreamOptions
from ..types import Context, Model


class BaseProvider(ABC):
    """LLM 提供商抽象基类"""

    NAME: str = "base"
    DEFAULT_TIMEOUT: int = 60

    def __init__(self, timeout: int | None = None):
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageEventStream:
        """
        流式调用

        Args:
            model: 模型定义
            context: 调用上下文
            options: 调用选项

        Returns:
            AssistantMessageEventStream: 流式事件流
        """
        pass

    def _get_api_key(self, options: StreamOptions, env_var: str) -> str | None:
        """获取 API Key"""
        if options.api_key:
            return options.api_key
        return os.getenv(env_var)

    def _get_timeout(self, options: StreamOptions) -> int:
        """获取超时配置"""
        return options.timeout or self._timeout

    async def _retry_with_backoff(
        self,
        func: Any,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> Any:
        """带指数退避的重试"""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return await func()
            except Exception as e:
                last_exception = e

                # 检查是否应该重试
                if not self._should_retry(e):
                    raise

                # 最后一次尝试不再重试
                if attempt == max_retries:
                    raise

                # 计算延迟
                delay = min(base_delay * (2 ** attempt), max_delay)

                await asyncio.sleep(delay)

        raise last_exception

    def _should_retry(self, exception: Exception) -> bool:
        """判断是否应该重试"""
        if isinstance(exception, httpx.HTTPStatusError):
            # 429 速率限制
            if exception.response.status_code == 429:
                return True
            # 5xx 服务错误
            if exception.response.status_code >= 500:
                return True
        if isinstance(exception, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        return False
