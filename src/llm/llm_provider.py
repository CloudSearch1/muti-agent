"""
LLM API 统一封装层

提供统一的 LLM 调用接口，支持多提供商（OpenAI, Claude, 通义千问等）
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """LLM 提供商抽象基类"""
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        pass
    
    @abstractmethod
    async def generate_json(self, prompt: str, **kwargs) -> dict:
        """生成 JSON 格式响应"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT 提供商"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        logger.info(f"OpenAI Provider 初始化完成 (model={model})")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        # TODO: 实现真实的 OpenAI API 调用
        logger.info(f"[OpenAI] 生成文本：{prompt[:50]}...")
        return f"[OpenAI 响应] 处理完成：{prompt}"
    
    async def generate_json(self, prompt: str, **kwargs) -> dict:
        # TODO: 实现真实的 OpenAI API 调用
        logger.info(f"[OpenAI] 生成 JSON: {prompt[:50]}...")
        return {"status": "success", "message": "处理完成"}


class ClaudeProvider(LLMProvider):
    """Anthropic Claude 提供商"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        logger.info(f"Claude Provider 初始化完成 (model={model})")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        # TODO: 实现真实的 Claude API 调用
        logger.info(f"[Claude] 生成文本：{prompt[:50]}...")
        return f"[Claude 响应] 处理完成：{prompt}"
    
    async def generate_json(self, prompt: str, **kwargs) -> dict:
        # TODO: 实现真实的 Claude API 调用
        logger.info(f"[Claude] 生成 JSON: {prompt[:50]}...")
        return {"status": "success", "message": "处理完成"}


class BailianProvider(LLMProvider):
    """阿里云百炼（通义千问）提供商"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "qwen-plus"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.model = model
        logger.info(f"Bailian Provider 初始化完成 (model={model})")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        # TODO: 实现真实的百炼 API 调用
        logger.info(f"[百炼] 生成文本：{prompt[:50]}...")
        return f"[百炼响应] 处理完成：{prompt}"
    
    async def generate_json(self, prompt: str, **kwargs) -> dict:
        # TODO: 实现真实的百炼 API 调用
        logger.info(f"[百炼] 生成 JSON: {prompt[:50]}...")
        return {"status": "success", "message": "处理完成"}


class LLMFactory:
    """LLM 工厂类"""
    
    _providers: dict[str, LLMProvider] = {}
    
    @classmethod
    def register(cls, name: str, provider: LLMProvider):
        """注册提供商"""
        cls._providers[name] = provider
        logger.info(f"注册 LLM 提供商：{name}")
    
    @classmethod
    def get(cls, name: str) -> Optional[LLMProvider]:
        """获取提供商"""
        return cls._providers.get(name)
    
    @classmethod
    def get_default(cls) -> LLMProvider:
        """获取默认提供商"""
        # 优先使用环境变量配置的提供商
        provider_name = os.getenv("LLM_PROVIDER", "openai")
        provider = cls.get(provider_name)
        if not provider:
            # 如果没有配置，返回第一个注册的提供商
            if cls._providers:
                provider = list(cls._providers.values())[0]
            else:
                raise RuntimeError("没有可用的 LLM 提供商")
        return provider


# 初始化默认提供商
def init_llm_providers():
    """初始化 LLM 提供商"""
    # 根据环境变量自动注册可用的提供商
    if os.getenv("OPENAI_API_KEY"):
        LLMFactory.register("openai", OpenAIProvider())
    
    if os.getenv("ANTHROPIC_API_KEY"):
        LLMFactory.register("claude", ClaudeProvider())
    
    if os.getenv("DASHSCOPE_API_KEY"):
        LLMFactory.register("bailian", BailianProvider())
    
    # 如果没有自动注册，至少注册一个默认的（用于测试）
    if not LLMFactory._providers:
        logger.warning("未检测到 LLM API Key，使用模拟模式")
        LLMFactory.register("openai", OpenAIProvider())
    
    logger.info(f"LLM 提供商初始化完成，已注册：{list(LLMFactory._providers.keys())}")


def get_llm(provider_name: Optional[str] = None) -> LLMProvider:
    """获取 LLM 实例"""
    if provider_name:
        return LLMFactory.get(provider_name) or LLMFactory.get_default()
    return LLMFactory.get_default()


# 便捷的全局函数
async def llm_generate(prompt: str, provider: Optional[str] = None, **kwargs) -> str:
    """便捷函数：生成文本"""
    llm = get_llm(provider)
    return await llm.generate(prompt, **kwargs)


async def llm_generate_json(prompt: str, provider: Optional[str] = None, **kwargs) -> dict:
    """便捷函数：生成 JSON"""
    llm = get_llm(provider)
    return await llm.generate_json(prompt, **kwargs)
