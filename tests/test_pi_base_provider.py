"""
PI-Python Base Provider 测试

测试 BaseProvider 抽象类
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pi_python.ai.providers.base import BaseProvider
from pi_python.ai import Model, Context, StreamOptions, ApiType


# ===========================================
# Fixtures
# ===========================================


@pytest.fixture
def model():
    """创建测试模型"""
    return Model(
        id="test-model",
        name="Test Model",
        api=ApiType.OPENAI_COMPLETIONS,
        provider="test",
        base_url="https://api.test.com/v1",
        context_window=4096,
        max_tokens=1024,
    )


@pytest.fixture
def context():
    """创建测试上下文"""
    ctx = Context(system_prompt="Test prompt")
    ctx.add_user_message("Hello")
    return ctx


@pytest.fixture
def options():
    """创建测试选项"""
    return StreamOptions(
        api_key="test-key",
        timeout=30,
        temperature=0.7,
        max_tokens=100,
    )


# ===========================================
# Concrete Provider for Testing
# ===========================================


class ConcreteProvider(BaseProvider):
    """用于测试的具体提供商实现"""

    NAME = "concrete"

    async def stream(self, model, context, options):
        """实现抽象方法"""
        from pi_python.ai.stream import AssistantMessageEventStream, AssistantMessageEvent
        from pi_python.ai import AssistantMessage, TextContent

        event_stream = AssistantMessageEventStream()
        event_stream._queue.put_nowait(
            AssistantMessageEvent(type="text_delta", delta="Test ")
        )
        event_stream._queue.put_nowait(
            AssistantMessageEvent(type="text_delta", delta="Response")
        )
        event_stream._queue.put_nowait(
            AssistantMessageEvent(
                type="done",
                message=AssistantMessage(content=[TextContent(text="Test Response")])
            )
        )
        return event_stream


# ===========================================
# BaseProvider Tests
# ===========================================


class TestBaseProvider:
    """BaseProvider 测试"""

    def test_init(self):
        """测试初始化"""
        provider = ConcreteProvider()

        assert provider._timeout == 60  # DEFAULT_TIMEOUT
        assert provider._client is None

    def test_init_with_custom_timeout(self):
        """测试自定义超时初始化"""
        provider = ConcreteProvider(timeout=120)

        assert provider._timeout == 120

    def test_client_property(self):
        """测试客户端属性"""
        import os
        # 清除代理环境变量以避免代理错误
        env_backup = {}
        proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']
        for var in proxy_vars:
            if var in os.environ:
                env_backup[var] = os.environ[var]
                del os.environ[var]

        try:
            provider = ConcreteProvider()

            client = provider.client

            assert client is not None
            assert isinstance(client, httpx.AsyncClient)

            # 第二次访问返回同一个实例
            client2 = provider.client
            assert client2 is client
        finally:
            # 恢复环境变量
            for var, val in env_backup.items():
                os.environ[var] = val

    @pytest.mark.asyncio
    async def test_close(self):
        """测试关闭客户端"""
        import os
        # 清除代理环境变量以避免代理错误
        env_backup = {}
        proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']
        for var in proxy_vars:
            if var in os.environ:
                env_backup[var] = os.environ[var]
                del os.environ[var]

        try:
            provider = ConcreteProvider()

            # 先获取客户端
            _ = provider.client

            await provider.close()

            assert provider._client is None
        finally:
            # 恢复环境变量
            for var, val in env_backup.items():
                os.environ[var] = val

    @pytest.mark.asyncio
    async def test_close_without_client(self):
        """测试没有客户端时关闭"""
        provider = ConcreteProvider()

        # 不应该抛出异常
        await provider.close()

    def test_get_api_key_from_options(self, options):
        """测试从选项获取 API Key"""
        provider = ConcreteProvider()

        key = provider._get_api_key(options, "TEST_API_KEY")

        assert key == "test-key"

    def test_get_api_key_from_env(self):
        """测试从环境变量获取 API Key"""
        import os

        provider = ConcreteProvider()
        options = StreamOptions()

        with patch.dict(os.environ, {"TEST_API_KEY": "env-key"}):
            key = provider._get_api_key(options, "TEST_API_KEY")

        assert key == "env-key"

    def test_get_api_key_options_priority(self):
        """测试选项优先于环境变量"""
        import os

        provider = ConcreteProvider()
        options = StreamOptions(api_key="options-key")

        with patch.dict(os.environ, {"TEST_API_KEY": "env-key"}):
            key = provider._get_api_key(options, "TEST_API_KEY")

        assert key == "options-key"

    def test_get_timeout_from_options(self, options):
        """测试从选项获取超时"""
        provider = ConcreteProvider()

        timeout = provider._get_timeout(options)

        assert timeout == 30

    def test_get_timeout_default(self):
        """测试默认超时"""
        provider = ConcreteProvider(timeout=90)
        # StreamOptions 有默认 timeout=60
        options = StreamOptions()

        timeout = provider._get_timeout(options)

        # StreamOptions 的默认值优先
        assert timeout == 60

    def test_get_timeout_options_priority(self):
        """测试选项超时优先"""
        provider = ConcreteProvider(timeout=90)
        options = StreamOptions(timeout=30)

        timeout = provider._get_timeout(options)

        assert timeout == 30

    @pytest.mark.asyncio
    async def test_stream(self, model, context, options):
        """测试流式调用"""
        provider = ConcreteProvider()

        event_stream = await provider.stream(model, context, options)

        chunks = []
        async for event in event_stream:
            if event.type == "text_delta":
                chunks.append(event.delta)

        assert chunks == ["Test ", "Response"]


# ===========================================
# Retry Logic Tests
# ===========================================


class TestRetryLogic:
    """重试逻辑测试"""

    @pytest.mark.asyncio
    async def test_retry_success_first_try(self):
        """测试第一次成功"""
        provider = ConcreteProvider()

        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await provider._retry_with_backoff(func, max_retries=3)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_after_failure(self):
        """测试失败后重试成功"""
        provider = ConcreteProvider()

        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "Error",
                    request=MagicMock(),
                    response=MagicMock(status_code=429)
                )
            return "success"

        result = await provider._retry_with_backoff(func, max_retries=3, base_delay=0.01)

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_max_retries_exceeded(self):
        """测试超过最大重试次数"""
        provider = ConcreteProvider()

        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            raise httpx.HTTPStatusError(
                "Error",
                request=MagicMock(),
                response=MagicMock(status_code=429)
            )

        with pytest.raises(httpx.HTTPStatusError):
            await provider._retry_with_backoff(func, max_retries=2, base_delay=0.01)

        assert call_count == 3  # 初始 + 2 次重试

    @pytest.mark.asyncio
    async def test_retry_non_retryable_error(self):
        """测试不可重试的错误"""
        provider = ConcreteProvider()

        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError, match="Not retryable"):
            await provider._retry_with_backoff(func, max_retries=3)

        assert call_count == 1  # 不重试

    def test_should_retry_429(self):
        """测试 429 状态码应该重试"""
        provider = ConcreteProvider()

        response = MagicMock(status_code=429)
        error = httpx.HTTPStatusError("Error", request=MagicMock(), response=response)

        assert provider._should_retry(error) is True

    def test_should_retry_5xx(self):
        """测试 5xx 状态码应该重试"""
        provider = ConcreteProvider()

        for status_code in [500, 502, 503, 504]:
            response = MagicMock(status_code=status_code)
            error = httpx.HTTPStatusError("Error", request=MagicMock(), response=response)

            assert provider._should_retry(error) is True

    def test_should_retry_timeout(self):
        """测试超时错误应该重试"""
        provider = ConcreteProvider()

        error = httpx.TimeoutException("Timeout")

        assert provider._should_retry(error) is True

    def test_should_retry_network_error(self):
        """测试网络错误应该重试"""
        provider = ConcreteProvider()

        error = httpx.NetworkError("Network error")

        assert provider._should_retry(error) is True

    def test_should_not_retry_4xx(self):
        """测试 4xx 状态码不应该重试（除了 429）"""
        provider = ConcreteProvider()

        for status_code in [400, 401, 403, 404]:
            response = MagicMock(status_code=status_code)
            error = httpx.HTTPStatusError("Error", request=MagicMock(), response=response)

            assert provider._should_retry(error) is False

    def test_should_not_retry_other_errors(self):
        """测试其他错误不应该重试"""
        provider = ConcreteProvider()

        error = ValueError("Some error")

        assert provider._should_retry(error) is False


# ===========================================
# Backoff Timing Tests
# ===========================================


class TestBackoffTiming:
    """退避时间测试"""

    @pytest.mark.asyncio
    async def test_backoff_timing(self):
        """测试退避时间计算"""
        provider = ConcreteProvider()

        delays = []
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise httpx.HTTPStatusError(
                    "Error",
                    request=MagicMock(),
                    response=MagicMock(status_code=429)
                )
            return "success"

        import time

        start = time.time()
        result = await provider._retry_with_backoff(
            func,
            max_retries=3,
            base_delay=0.1,
            max_delay=10.0
        )
        elapsed = time.time() - start

        assert result == "success"
        # 应该有延迟：0.1 + 0.2 + 0.4 = 0.7
        assert elapsed >= 0.3  # 给一些容差

    @pytest.mark.asyncio
    async def test_max_delay(self):
        """测试最大延迟限制"""
        provider = ConcreteProvider()

        delays = []
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise httpx.HTTPStatusError(
                    "Error",
                    request=MagicMock(),
                    response=MagicMock(status_code=429)
                )
            return "success"

        import time

        start = time.time()
        result = await provider._retry_with_backoff(
            func,
            max_retries=5,
            base_delay=1.0,
            max_delay=0.5  # 限制最大延迟
        )
        elapsed = time.time() - start

        assert result == "success"
        # 即使 base_delay * 2^n 会更大，也被 max_delay 限制
        assert elapsed < 2.0  # 应该远小于无限制的情况


if __name__ == "__main__":
    pytest.main([__file__, "-v"])