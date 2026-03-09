"""
本地 LLM 测试

测试 Ollama, vLLM, LM Studio 等本地 LLM 提供商
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.llm.local import (
    LocalLLMService,
    LMStudioProvider,
    OllamaProvider,
    VLLMProvider,
    get_local_llm,
    local_llm_generate,
)
from src.llm.llm_provider import LLMConfigError, LLMError


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
        assert provider.base_url == "http://localhost:11434"
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
        provider = OllamaProvider(base_url="")
        with pytest.raises(LLMConfigError):
            provider._validate_config()

    def test_clean_json_response(self):
        """测试 JSON 响应清理"""
        provider = OllamaProvider()

        # Test with markdown code block
        result = provider._clean_json_response('```json\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

        # Test without code block
        result = provider._clean_json_response('{"key": "value"}')
        assert result == '{"key": "value"}'


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
        assert provider.base_url == "http://localhost:8000"
        assert provider.api_key == "EMPTY"

    def test_clean_json_response(self):
        """测试 JSON 响应清理"""
        provider = VLLMProvider()
        result = provider._clean_json_response('```json\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'


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
        assert provider.base_url == "http://localhost:1234"


# ============ LocalLLMService 测试 ============

class TestLocalLLMService:
    """本地 LLM 服务测试"""

    def test_create_ollama_service(self):
        """测试创建 Ollama 服务"""
        service = LocalLLMService(provider_type="ollama")
        assert service._provider_type == "ollama"
        assert isinstance(service.provider, OllamaProvider)

    def test_create_vllm_service(self):
        """测试创建 vLLM 服务"""
        service = LocalLLMService(provider_type="vllm")
        assert service._provider_type == "vllm"
        assert isinstance(service.provider, VLLMProvider)

    def test_create_lmstudio_service(self):
        """测试创建 LM Studio 服务"""
        service = LocalLLMService(provider_type="lmstudio")
        assert service._provider_type == "lmstudio"
        assert isinstance(service.provider, LMStudioProvider)

    def test_invalid_provider_type(self):
        """测试无效的提供商类型"""
        with pytest.raises(ValueError) as excinfo:
            LocalLLMService(provider_type="invalid")
        assert "不支持" in str(excinfo.value)

    def test_create_with_custom_config(self):
        """测试使用自定义配置创建服务"""
        service = LocalLLMService(
            provider_type="ollama",
            base_url="http://custom:11434",
            model="codellama",
        )
        assert service.provider.base_url == "http://custom:11434"
        assert service.provider.model == "codellama"

    def test_provider_property(self):
        """测试提供商属性"""
        service = LocalLLMService(provider_type="ollama")
        assert service.provider is not None
        assert isinstance(service.provider, OllamaProvider)


# ============ 便捷函数测试 ============

class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_get_local_llm(self):
        """测试获取本地 LLM"""
        service1 = get_local_llm("ollama")
        assert isinstance(service1, LocalLLMService)

        # 同样参数应该返回缓存的服务
        service2 = get_local_llm("ollama")
        assert service1 is service2

    def test_get_local_llm_different_params(self):
        """测试不同参数获取不同服务"""
        service1 = get_local_llm("ollama", model="llama2")
        service2 = get_local_llm("ollama", model="codellama")
        assert service1 is not service2

    @pytest.mark.asyncio
    async def test_local_llm_generate(self):
        """测试本地 LLM 生成便捷函数"""
        mock_service = MagicMock()
        mock_service.generate = AsyncMock(return_value="Test response")

        with patch('src.llm.local._local_services', {}):
            with patch('src.llm.local.LocalLLMService', return_value=mock_service):
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


# ============ 运行测试 ============

if __name__ == "__main__":
    pytest.main([__file__, "-v"])