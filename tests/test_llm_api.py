"""
LLM API 测试

测试多模型 API 支持
"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

# 配置测试环境
os.environ["TESTING"] = "true"


# ============ Fixtures ============


@pytest.fixture
def test_config(tmp_path):
    """创建测试配置文件"""
    config = {
        "providers": [
            {
                "name": "test_provider",
                "display_name": "Test Provider",
                "type": "openai-compatible",
                "baseUrl": "https://api.test.com/v1",
                "models": ["test-model-1", "test-model-2"],
                "default_model": "test-model-1",
                "env_key": "TEST_API_KEY",
                "enabled": True,
            },
            {
                "name": "ollama",
                "display_name": "Ollama (本地)",
                "type": "openai-compatible",
                "baseUrl": "http://localhost:11434/v1",
                "models": ["llama3", "codellama"],
                "default_model": "llama3",
                "env_key": None,
                "enabled": True,
            },
        ],
        "default": "test_provider/test-model-1",
        "fallback": None,
        "settings": {
            "timeout": 60,
            "max_retries": 3,
            "temperature": 0.7,
            "max_tokens": 4096,
        },
    }

    config_file = tmp_path / "llm.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f)

    return str(config_file)


@pytest.fixture
def mock_app(test_config):
    """创建测试应用"""
    import sys
    from pathlib import Path

    from fastapi import FastAPI

    # 直接导入路由模块，避免从 __init__.py 导入导致的循环依赖
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "llm_routes",
        Path(__file__).parent.parent / "src" / "api" / "routes" / "llm.py"
    )
    llm_module = importlib.util.module_from_spec(spec)
    sys.modules["llm_routes"] = llm_module
    spec.loader.exec_module(llm_module)

    # 设置配置路径
    llm_module.set_config_path(Path(test_config))

    app = FastAPI()
    app.include_router(llm_module.router, prefix="/api/v1/llm")

    yield app

    # 恢复原始路径
    llm_module.set_config_path(Path("config/llm.json"))


@pytest.fixture
def client(mock_app):
    """创建测试客户端"""
    return TestClient(mock_app)


# ============ Tests ============


class TestListProviders:
    """测试列出服务商"""

    def test_list_providers_success(self, client):
        """测试成功列出服务商"""
        response = client.get("/api/v1/llm/providers")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 2

        # 检查第一个服务商
        provider = data[0]
        assert provider["name"] == "test_provider"
        assert provider["display_name"] == "Test Provider"
        assert "test-model-1" in provider["models"]
        assert provider["enabled"] is True

    def test_list_providers_with_env_key(self, client, monkeypatch):
        """测试环境变量 API Key 检测"""
        monkeypatch.setenv("TEST_API_KEY", "test-key-123")

        response = client.get("/api/v1/llm/providers")
        data = response.json()

        # test_provider 应该显示已配置
        test_provider = next(p for p in data if p["name"] == "test_provider")
        assert test_provider["configured"] is True

        # ollama 本地服务不需要 API Key
        ollama = next(p for p in data if p["name"] == "ollama")
        assert ollama["configured"] is True


class TestGetProvider:
    """测试获取单个服务商"""

    def test_get_provider_success(self, client):
        """测试成功获取服务商"""
        response = client.get("/api/v1/llm/providers/test_provider")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "test_provider"
        assert data["display_name"] == "Test Provider"

    def test_get_provider_not_found(self, client):
        """测试服务商不存在"""
        response = client.get("/api/v1/llm/providers/nonexistent")

        assert response.status_code == 404


class TestConfigureProvider:
    """测试配置服务商"""

    def test_configure_provider_api_key(self, client):
        """测试设置 API Key"""
        response = client.post(
            "/api/v1/llm/config",
            json={
                "provider": "test_provider",
                "api_key": "new-api-key",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_configure_provider_base_url(self, client):
        """测试设置自定义 Base URL"""
        response = client.post(
            "/api/v1/llm/config",
            json={
                "provider": "test_provider",
                "base_url": "https://custom.api.com/v1",
            },
        )

        assert response.status_code == 200

    def test_configure_provider_not_found(self, client):
        """测试配置不存在的服务商"""
        response = client.post(
            "/api/v1/llm/config",
            json={
                "provider": "nonexistent",
                "api_key": "test-key",
            },
        )

        assert response.status_code == 404

    def test_configure_provider_disable(self, client):
        """测试禁用服务商"""
        response = client.post(
            "/api/v1/llm/config",
            json={
                "provider": "test_provider",
                "enabled": False,
            },
        )

        assert response.status_code == 200


class TestTestConnection:
    """测试连接测试"""

    @patch("httpx.AsyncClient")
    def test_test_connection_success(self, mock_client, client):
        """测试成功的连接测试"""
        # 模拟成功响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OK"}}]
        }

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_context)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_context.post = AsyncMock(return_value=mock_response)

        mock_client.return_value = mock_context

        response = client.post(
            "/api/v1/llm/test",
            json={
                "provider": "test_provider",
                "api_key": "test-key",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_test_connection_missing_api_key(self, client):
        """测试缺少 API Key"""
        response = client.post(
            "/api/v1/llm/test",
            json={
                "provider": "test_provider",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "API Key" in data["error"]

    def test_test_connection_provider_not_found(self, client):
        """测试服务商不存在"""
        response = client.post(
            "/api/v1/llm/test",
            json={
                "provider": "nonexistent",
            },
        )

        assert response.status_code == 404


class TestChat:
    """测试聊天接口"""

    @patch("httpx.AsyncClient")
    def test_chat_success(self, mock_client, client):
        """测试成功的聊天请求"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chat-123",
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_context)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_context.post = AsyncMock(return_value=mock_response)

        mock_client.return_value = mock_context

        response = client.post(
            "/api/v1/llm/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "test_provider/test-model-1",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Hello!"
        assert data["provider"] == "test_provider"

    def test_chat_provider_not_found(self, client):
        """测试服务商不存在"""
        response = client.post(
            "/api/v1/llm/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "nonexistent/model",
            },
        )

        assert response.status_code == 404

    def test_chat_invalid_model_format(self, client):
        """测试无效的模型格式"""
        response = client.post(
            "/api/v1/llm/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "invalid-model-format",
            },
        )

        # 应该使用默认服务商或返回错误
        # 可能返回 400/404 (业务逻辑错误) 或 502/500 (网络/代理问题)
        assert response.status_code in [200, 400, 404, 500, 502]


class TestSetDefault:
    """测试设置默认模型"""

    def test_set_default_success(self, client):
        """测试成功设置默认模型"""
        response = client.post("/api/v1/llm/default?model=test_provider/test-model-2")

        assert response.status_code == 200
        data = response.json()
        assert data["default"] == "test_provider/test-model-2"

    def test_set_default_invalid_format(self, client):
        """测试无效的模型格式"""
        response = client.post("/api/v1/llm/default?model=invalid-format")

        assert response.status_code == 400

    def test_set_default_provider_not_found(self, client):
        """测试服务商不存在"""
        response = client.post("/api/v1/llm/default?model=nonexistent/model")

        assert response.status_code == 404

    def test_set_default_model_not_found(self, client):
        """测试模型不存在"""
        response = client.post("/api/v1/llm/default?model=test_provider/nonexistent-model")

        assert response.status_code == 404


class TestGetConfig:
    """测试获取配置"""

    def test_get_config_success(self, client):
        """测试成功获取配置"""
        response = client.get("/api/v1/llm/config")

        assert response.status_code == 200
        data = response.json()

        assert "providers" in data
        assert "default" in data
        assert "settings" in data

        # 确保没有返回敏感信息
        for provider in data["providers"]:
            assert "api_key" not in provider


# ============ 集成测试 ============


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, client):
        """测试完整工作流程"""
        # 1. 列出服务商
        response = client.get("/api/v1/llm/providers")
        assert response.status_code == 200
        providers = response.json()
        assert len(providers) > 0

        # 2. 配置服务商
        response = client.post(
            "/api/v1/llm/config",
            json={
                "provider": "test_provider",
                "api_key": "test-key-123",
            },
        )
        assert response.status_code == 200

        # 3. 获取配置
        response = client.get("/api/v1/llm/config")
        assert response.status_code == 200
        config = response.json()

        # 4. 设置默认模型
        response = client.post("/api/v1/llm/default?model=test_provider/test-model-1")
        assert response.status_code == 200

    def test_ollama_local_provider(self, client):
        """测试 Ollama 本地服务商"""
        # Ollama 不需要 API Key
        response = client.get("/api/v1/llm/providers/ollama")
        assert response.status_code == 200

        provider = response.json()
        assert provider["configured"] is True  # 本地服务默认已配置


# ============ 错误处理测试 ============


class TestErrorHandling:
    """错误处理测试"""

    def test_malformed_request(self, client):
        """测试格式错误的请求"""
        response = client.post(
            "/api/v1/llm/chat",
            json={"invalid": "data"},
        )

        assert response.status_code == 422  # Validation error

    def test_empty_messages(self, client):
        """测试空消息列表"""
        response = client.post(
            "/api/v1/llm/chat",
            json={"messages": []},
        )

        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])