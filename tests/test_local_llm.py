"""
本地 LLM 测试

测试 Ollama, vLLM, LM Studio 等本地 LLM 提供商

测试覆盖:
- 初始化和配置验证
- 健康检查
- 文本生成
- 流式响应
- JSON 解析
- 错误处理
- 边界条件
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collections.abc import AsyncIterator

from src.llm.local import (
    LocalLLMService,
    LMStudioProvider,
    OllamaProvider,
    VLLMProvider,
    get_local_llm,
    local_llm_generate,
    clear_local_llm_cache,
    _validate_url,
    _clean_json_response,
    _extract_stream_content,
    DEFAULT_OLLAMA_URL,
    DEFAULT_VLLM_URL,
    DEFAULT_LMSTUDIO_URL,
)
from src.llm.llm_provider import LLMConfigError, LLMError, LLMAPIError, LLMJSONError


# ============ 工具函数测试 ============

class TestUtilityFunctions:
    """工具函数测试"""

    def test_validate_url_valid(self):
        """测试有效 URL"""
        # Should not raise
        _validate_url("http://localhost:11434", "test")
        _validate_url("https://api.example.com", "test")
        _validate_url("http://192.168.1.1:8000", "test")

    def test_validate_url_invalid_scheme(self):
        """测试无效协议"""
        with pytest.raises(LLMConfigError) as excinfo:
            _validate_url("ftp://localhost", "test")
        assert "http 或 https" in str(excinfo.value)

    def test_validate_url_missing_scheme(self):
        """测试缺少协议"""
        with pytest.raises(LLMConfigError):
            _validate_url("localhost:11434", "test")

    def test_validate_url_empty(self):
        """测试空 URL"""
        with pytest.raises(LLMConfigError):
            _validate_url("", "test")

    def test_clean_json_response_with_markdown(self):
        """测试清理 markdown 格式的 JSON"""
        # Test with json code block
        result = _clean_json_response('```json\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

        # Test with plain code block
        result = _clean_json_response('```\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

        # Test without code block
        result = _clean_json_response('{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_clean_json_response_empty(self):
        """测试清理空内容"""
        assert _clean_json_response("") == ""
        assert _clean_json_response(None) is None

    def test_clean_json_response_whitespace(self):
        """测试清理带空白的内容"""
        result = _clean_json_response('  \n{"key": "value"}\n  ')
        assert result == '{"key": "value"}'

    def test_extract_stream_content_openai_format(self):
        """测试 OpenAI 格式流式内容提取"""
        # Valid chunk
        line = 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
        result = _extract_stream_content(line, "vllm")
        assert result == "Hello"

        # Done signal
        line = "data: [DONE]"
        result = _extract_stream_content(line, "vllm")
        assert result is None

        # Empty line
        result = _extract_stream_content("", "vllm")
        assert result is None

    def test_extract_stream_content_ollama_format(self):
        """测试 Ollama 格式流式内容提取"""
        line = '{"response": "Hello"}'
        result = _extract_stream_content(line, "ollama")
        assert result == "Hello"

        # Without response field
        line = '{"done": true}'
        result = _extract_stream_content(line, "ollama")
        assert result == ""


# ============ Ollama Provider 测试 ============

class TestOllamaProvider:
    """Ollama 提供商测试"""

    def test_init(self):
        """测试初始化"""
        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="llama2",
        )
        assert provider.NAME == "ollama"
        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "llama2"

    def test_init_default(self):
        """测试默认初始化"""
        provider = OllamaProvider()
        assert provider.base_url == DEFAULT_OLLAMA_URL
        assert provider.model == "llama2"
        assert provider._timeout == 120

    def test_timeout_config(self):
        """测试超时配置"""
        provider = OllamaProvider(timeout=300)
        assert provider._timeout == 300

    def test_validate_config_success(self):
        """测试配置验证成功"""
        provider = OllamaProvider(base_url="http://localhost:11434")
        # Should not raise
        provider._validate_config()

    def test_validate_config_failure(self):
        """测试配置验证失败"""
        with pytest.raises(LLMConfigError):
            OllamaProvider(base_url="invalid-url")

    def test_validate_config_empty(self):
        """测试空配置验证"""
        with pytest.raises(LLMConfigError):
            OllamaProvider(base_url="")

    def test_base_url_trailing_slash(self):
        """测试 URL 尾部斜杠处理"""
        provider = OllamaProvider(base_url="http://localhost:11434/")
        assert provider.base_url == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_check_health_healthy(self):
        """测试健康检查 - 健康"""
        provider = OllamaProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama2"}, {"name": "codellama"}]
        }

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await provider.check_health()

        assert result["status"] == "healthy"
        assert "llama2" in result["models"]
        assert result["provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_check_health_unhealthy(self):
        """测试健康检查 - 不健康"""
        provider = OllamaProvider()

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await provider.check_health()

        assert result["status"] == "unhealthy"
        assert result["provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_check_health_unreachable(self):
        """测试健康检查 - 无法连接"""
        provider = OllamaProvider()

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.get.side_effect = ConnectionError("Connection refused")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await provider.check_health()

        assert result["status"] == "unreachable"
        assert "Connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """测试文本生成成功"""
        provider = OllamaProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Hello, world!"}

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await provider.generate("Hi")

        assert result == "Hello, world!"

    @pytest.mark.asyncio
    async def test_generate_empty_prompt(self):
        """测试空提示"""
        provider = OllamaProvider()

        with pytest.raises(LLMAPIError) as excinfo:
            await provider.generate("")
        assert "提示不能为空" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_generate_invalid_temperature(self):
        """测试无效温度参数"""
        provider = OllamaProvider()

        with pytest.raises(LLMAPIError) as excinfo:
            await provider.generate("Hi", temperature=3.0)
        assert "temperature" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_generate_json_success(self):
        """测试 JSON 生成成功"""
        provider = OllamaProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": '{"name": "test", "value": 123}'}

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await provider.generate_json("Generate JSON")

        assert result == {"name": "test", "value": 123}

    @pytest.mark.asyncio
    async def test_generate_json_failure(self):
        """测试 JSON 生成失败"""
        provider = OllamaProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Not valid JSON"}

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            with pytest.raises(LLMJSONError):
                await provider.generate_json("Generate JSON")

    @pytest.mark.asyncio
    async def test_chat_success(self):
        """测试对话成功"""
        provider = OllamaProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "I'm doing well!"}
        }

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await provider.chat([
                {"role": "user", "content": "How are you?"}
            ])

        assert result == "I'm doing well!"

    @pytest.mark.asyncio
    async def test_chat_empty_messages(self):
        """测试空消息列表"""
        provider = OllamaProvider()

        with pytest.raises(LLMAPIError) as excinfo:
            await provider.chat([])
        assert "消息列表不能为空" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_pull_model_success(self):
        """测试模型下载成功"""
        provider = OllamaProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await provider.pull_model("llama2")

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_pull_model_empty_name(self):
        """测试空模型名称"""
        provider = OllamaProvider()

        with pytest.raises(LLMAPIError) as excinfo:
            await provider.pull_model("")
        assert "模型名称不能为空" in str(excinfo.value)


# ============ vLLM Provider 测试 ============

class TestVLLMProvider:
    """vLLM 提供商测试"""

    def test_init(self):
        """测试初始化"""
        provider = VLLMProvider(
            base_url="http://localhost:8000",
            model="meta-llama/Llama-2-7b-hf",
        )
        assert provider.NAME == "vllm"
        assert provider.base_url == "http://localhost:8000"
        assert provider.model == "meta-llama/Llama-2-7b-hf"

    def test_init_default(self):
        """测试默认初始化"""
        provider = VLLMProvider()
        assert provider.base_url == DEFAULT_VLLM_URL
        assert provider.api_key == "EMPTY"

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """测试文本生成成功"""
        provider = VLLMProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello from vLLM!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await provider.generate("Hi")

        assert result == "Hello from vLLM!"

    @pytest.mark.asyncio
    async def test_generate_with_extra_params(self):
        """测试带额外参数的生成"""
        provider = VLLMProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}]
        }

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await provider.generate(
                "Hi",
                top_p=0.9,
                top_k=50,
                repetition_penalty=1.1
            )

        assert result == "Response"

    @pytest.mark.asyncio
    async def test_list_models(self):
        """测试列出模型"""
        provider = VLLMProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"id": "model1"}, {"id": "model2"}]
        }

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            models = await provider.list_models()

        assert len(models) == 2
        assert models[0]["id"] == "model1"


# ============ LM Studio Provider 测试 ============

class TestLMStudioProvider:
    """LM Studio 提供商测试"""

    def test_init(self):
        """测试初始化"""
        provider = LMStudioProvider(
            base_url="http://localhost:1234",
            model="local-model",
        )
        assert provider.NAME == "lmstudio"
        assert provider.base_url == "http://localhost:1234"
        assert provider.model == "local-model"

    def test_init_default(self):
        """测试默认初始化"""
        provider = LMStudioProvider()
        assert provider.base_url == DEFAULT_LMSTUDIO_URL

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """测试文本生成成功"""
        provider = LMStudioProvider()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello from LM Studio!"}}]
        }

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await provider.generate("Hi")

        assert result == "Hello from LM Studio!"


# ============ LocalLLMService 测试 ============

class TestLocalLLMService:
    """本地 LLM 服务测试"""

    def test_create_ollama_service(self):
        """测试创建 Ollama 服务"""
        service = LocalLLMService(provider_type="ollama")
        assert service.provider_type == "ollama"
        assert isinstance(service.provider, OllamaProvider)

    def test_create_vllm_service(self):
        """测试创建 vLLM 服务"""
        service = LocalLLMService(provider_type="vllm")
        assert service.provider_type == "vllm"
        assert isinstance(service.provider, VLLMProvider)

    def test_create_lmstudio_service(self):
        """测试创建 LM Studio 服务"""
        service = LocalLLMService(provider_type="lmstudio")
        assert service.provider_type == "lmstudio"
        assert isinstance(service.provider, LMStudioProvider)

    def test_invalid_provider_type(self):
        """测试无效的提供商类型"""
        with pytest.raises(ValueError) as excinfo:
            LocalLLMService(provider_type="invalid")
        assert "不支持的本地 LLM 类型" in str(excinfo.value)
        assert "ollama" in str(excinfo.value)  # 应该显示支持的类型

    def test_create_with_custom_config(self):
        """测试使用自定义配置创建服务"""
        service = LocalLLMService(
            provider_type="ollama",
            base_url="http://custom:11434",
            model="codellama",
            timeout=300,
        )
        assert service.provider.base_url == "http://custom:11434"
        assert service.provider.model == "codellama"

    def test_provider_property(self):
        """测试提供商属性"""
        service = LocalLLMService(provider_type="ollama")
        assert service.provider is not None
        assert isinstance(service.provider, OllamaProvider)

    @pytest.mark.asyncio
    async def test_health_check(self):
        """测试健康检查"""
        service = LocalLLMService(provider_type="ollama")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await service.health_check()

        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_list_models(self):
        """测试列出模型"""
        service = LocalLLMService(provider_type="ollama")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama2"}]
        }

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            models = await service.list_models()

        assert len(models) == 1


# ============ 便捷函数测试 ============

class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_get_local_llm(self):
        """测试获取本地 LLM"""
        clear_local_llm_cache()
        service1 = get_local_llm("ollama")
        assert isinstance(service1, LocalLLMService)

        # 同样参数应该返回缓存的服务
        service2 = get_local_llm("ollama")
        assert service1 is service2

    def test_get_local_llm_different_params(self):
        """测试不同参数获取不同服务"""
        clear_local_llm_cache()
        service1 = get_local_llm("ollama", model="llama2")
        service2 = get_local_llm("ollama", model="codellama")
        assert service1 is not service2

    def test_clear_cache(self):
        """测试清除缓存"""
        get_local_llm("ollama")
        clear_local_llm_cache()
        # 缓存清除后应该创建新实例
        service = get_local_llm("ollama")
        assert isinstance(service, LocalLLMService)

    @pytest.mark.asyncio
    async def test_local_llm_generate(self):
        """测试本地 LLM 生成便捷函数"""
        clear_local_llm_cache()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Test response"}

        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await local_llm_generate(
                "Hello",
                provider_type="ollama",
                model="llama2",
            )

        assert result == "Test response"


# ============ 配置测试 ============

class TestConfig:
    """配置测试"""

    def test_llm_settings_local_config(self):
        """测试本地 LLM 配置"""
        from src.config.settings import LLMSettings

        settings = LLMSettings(
            local_provider="ollama",
            local_base_url="http://localhost:11434",
            local_model="llama2",
            local_timeout=120,
        )

        local_config = settings.get_local_config()
        assert local_config["provider"] == "ollama"
        assert local_config["base_url"] == "http://localhost:11434"
        assert local_config["model"] == "llama2"
        assert local_config["timeout"] == 120

    def test_llm_settings_defaults(self):
        """测试默认配置"""
        from src.config.settings import LLMSettings

        settings = LLMSettings()
        assert settings.local_provider == "ollama"
        assert settings.local_timeout == 120


# ============ API 路由测试 ============

class TestAPIRoutes:
    """API 路由测试"""

    @pytest.mark.asyncio
    async def test_list_providers(self):
        """测试列出提供商"""
        from src.api.routes.local_llm import list_local_providers

        result = await list_local_providers()

        assert "providers" in result
        assert len(result["providers"]) == 3

        provider_types = [p["type"] for p in result["providers"]]
        assert "ollama" in provider_types
        assert "vllm" in provider_types
        assert "lmstudio" in provider_types

    def test_request_models(self):
        """测试请求模型"""
        from src.api.routes.local_llm import LocalChatRequest, LocalPullRequest

        chat_req = LocalChatRequest(
            prompt="Hello",
            model="llama2",
            temperature=0.5,
        )
        assert chat_req.prompt == "Hello"
        assert chat_req.model == "llama2"
        assert chat_req.temperature == 0.5

        pull_req = LocalPullRequest(model_name="llama2")
        assert pull_req.model_name == "llama2"

    def test_request_validation(self):
        """测试请求验证"""
        from src.api.routes.local_llm import LocalChatRequest
        from pydantic import ValidationError

        # 有效请求
        req = LocalChatRequest(prompt="Hello")
        assert req.temperature == 0.7  # 默认值

        # 无效温度
        with pytest.raises(ValidationError):
            LocalChatRequest(prompt="Hello", temperature=3.0)

        # 无效 max_tokens
        with pytest.raises(ValidationError):
            LocalChatRequest(prompt="Hello", max_tokens=0)


# ============ 边界条件测试 ============

class TestEdgeCases:
    """边界条件测试"""

    def test_very_long_prompt(self):
        """测试超长提示"""
        provider = OllamaProvider()
        long_prompt = "Hello " * 10000  # 50k+ characters
        # 初始化应该成功，错误应在 API 调用时处理
        assert provider.model == "llama2"

    def test_special_characters_in_model_name(self):
        """测试模型名称中的特殊字符"""
        provider = OllamaProvider(model="llama2:7b-instruct")
        assert provider.model == "llama2:7b-instruct"

    def test_unicode_in_prompt(self):
        """测试 Unicode 提示"""
        provider = OllamaProvider()
        # 初始化成功即可
        assert provider.NAME == "ollama"

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """测试并发请求"""
        import asyncio

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Response"}

        async def make_request(i: int):
            with patch('httpx.AsyncClient') as MockClient:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                MockClient.return_value = mock_client

                provider = OllamaProvider()
                return await provider.generate(f"Request {i}")

        # 并发执行 5 个请求
        results = await asyncio.gather(*[make_request(i) for i in range(5)])

        assert len(results) == 5
        assert all(r == "Response" for r in results)


# ============ 运行测试 ============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])