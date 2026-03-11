"""
PI-Python 模型注册测试

测试 ai/model.py 模块
"""

import pytest
from pi_python.ai.model import (
    ModelRegistry,
    register_model,
    register_provider,
    get_model,
    get_provider,
    list_models,
    register_builtin_models,
    OPENAI_MODELS,
    ANTHROPIC_MODELS,
    BAILIAN_MODELS,
)
from pi_python.ai.types import ApiType, Model, ModelCost


class TestModelRegistry:
    """模型注册表测试"""

    def setup_method(self):
        """每个测试前清除注册表"""
        ModelRegistry.clear()
        register_builtin_models()

    def test_register_model(self):
        """测试注册模型"""
        model = Model(
            id="test-model",
            name="Test Model",
            api=ApiType.CUSTOM,
            provider="test",
            base_url=""
        )
        register_model(model)

        retrieved = get_model("test", "test-model")
        assert retrieved is not None
        assert retrieved.id == "test-model"

    def test_get_unknown_model(self):
        """测试获取未知模型"""
        with pytest.raises(ValueError, match="Unknown model"):
            get_model("unknown", "model")

    def test_list_models(self):
        """测试列出模型"""
        models = list_models()
        assert len(models) > 0

    def test_list_models_by_provider(self):
        """测试按提供商列出模型"""
        openai_models = list_models(provider="openai")
        assert len(openai_models) > 0
        for model in openai_models:
            assert model.provider == "openai"

    def test_list_providers(self):
        """测试列出提供商"""
        # 注册一个测试提供商
        async def mock_provider(model, context, options):
            pass
        register_provider("test_provider_for_list", mock_provider)

        providers = ModelRegistry.list_providers()
        assert "test_provider_for_list" in providers

    def test_register_provider(self):
        """测试注册提供商"""
        async def mock_provider(model, context, options):
            pass

        register_provider("test_provider", mock_provider)
        provider = get_provider("test_provider")
        assert provider == mock_provider


class TestBuiltinModels:
    """内置模型测试"""

    def setup_method(self):
        """每个测试前清除注册表"""
        ModelRegistry.clear()
        register_builtin_models()

    def test_openai_models_registered(self):
        """测试 OpenAI 模型已注册"""
        model = get_model("openai", "gpt-4o")
        assert model is not None
        assert model.provider == "openai"
        assert model.context_window == 128000

    def test_anthropic_models_registered(self):
        """测试 Anthropic 模型已注册"""
        model = get_model("anthropic", "claude-sonnet-4-20250514")
        assert model is not None
        assert model.provider == "anthropic"
        assert model.reasoning is True

    def test_bailian_models_registered(self):
        """测试百炼模型已注册"""
        model = get_model("bailian", "qwen-max")
        assert model is not None
        assert model.provider == "bailian"

    def test_openai_models_list(self):
        """测试 OpenAI 模型列表"""
        assert len(OPENAI_MODELS) >= 4
        model_ids = [m.id for m in OPENAI_MODELS]
        assert "gpt-4o" in model_ids
        assert "gpt-4o-mini" in model_ids

    def test_anthropic_models_list(self):
        """测试 Anthropic 模型列表"""
        assert len(ANTHROPIC_MODELS) >= 3
        model_ids = [m.id for m in ANTHROPIC_MODELS]
        assert "claude-sonnet-4-20250514" in model_ids

    def test_bailian_models_list(self):
        """测试百炼模型列表"""
        assert len(BAILIAN_MODELS) >= 3
        model_ids = [m.id for m in BAILIAN_MODELS]
        assert "qwen-max" in model_ids
        assert "qwen-plus" in model_ids

    def test_model_cost(self):
        """测试模型成本"""
        model = get_model("openai", "gpt-4o")
        assert model.cost.input > 0
        assert model.cost.output > 0


class TestModelRegistryClear:
    """模型注册表清除测试"""

    def test_clear(self):
        """测试清除注册表"""
        register_builtin_models()
        assert len(ModelRegistry._models) > 0

        ModelRegistry.clear()
        assert len(ModelRegistry._models) == 0
        assert len(ModelRegistry._providers) == 0