"""
LLM API 统一封装层

提供统一的 LLM 调用接口，支持多提供商（OpenAI, Claude, 通义千问等）

已实现真实 API 调用：
- OpenAI GPT
- Anthropic Claude  
- 阿里云百炼（通义千问）
"""

import json
import logging
import os
from abc import ABC, abstractmethod

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

    def __init__(self, api_key: str | None = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = "https://api.openai.com/v1"
        self._httpx = None
        logger.info(f"OpenAI Provider 初始化完成 (model={model})")

    @property
    def httpx(self):
        """延迟导入 httpx"""
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx

    async def generate(self, prompt: str, **kwargs) -> str:
        """实现真实的 OpenAI API 调用"""
        if not self.api_key:
            logger.warning("OpenAI API Key 未配置，使用模拟响应")
            return f"[OpenAI 模拟响应] {prompt[:100]}..."

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }

        logger.info(f"[OpenAI] 调用 API: {self.model}")

        try:
            async with self.httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.info(f"[OpenAI] API 调用成功，tokens={data.get('usage', {})}")
                return content
        except Exception as e:
            logger.error(f"[OpenAI] API 调用失败：{e}")
            return f"[OpenAI 错误] {str(e)}"

    async def generate_json(self, prompt: str, **kwargs) -> dict:
        """实现真实的 OpenAI API JSON 调用"""
        # 添加 JSON 格式要求
        json_prompt = f"{prompt}\n\n请以严格的 JSON 格式回复，不要包含其他文字。"
        content = await self.generate(json_prompt, **kwargs)

        try:
            # 清理可能的 markdown 标记
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"[OpenAI] JSON 解析失败：{e}")
            return {"error": "JSON 解析失败", "content": content[:200]}


class ClaudeProvider(LLMProvider):
    """Anthropic Claude 提供商"""

    def __init__(self, api_key: str | None = None, model: str = "claude-3-sonnet-20240229"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.base_url = "https://api.anthropic.com"
        self._httpx = None
        logger.info(f"Claude Provider 初始化完成 (model={model})")

    @property
    def httpx(self):
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx

    async def generate(self, prompt: str, **kwargs) -> str:
        """实现真实的 Claude API 调用"""
        if not self.api_key:
            logger.warning("Claude API Key 未配置，使用模拟响应")
            return f"[Claude 模拟响应] {prompt[:100]}..."

        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", 2048),
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        logger.info(f"[Claude] 调用 API: {self.model}")

        try:
            async with self.httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                content = data["content"][0]["text"]
                logger.info("[Claude] API 调用成功")
                return content
        except Exception as e:
            logger.error(f"[Claude] API 调用失败：{e}")
            return f"[Claude 错误] {str(e)}"

    async def generate_json(self, prompt: str, **kwargs) -> dict:
        """实现真实的 Claude API JSON 调用"""
        json_prompt = f"{prompt}\n\n请以严格的 JSON 格式回复，不要包含其他文字。"
        content = await self.generate(json_prompt, **kwargs)

        try:
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"[Claude] JSON 解析失败：{e}")
            return {"error": "JSON 解析失败", "content": content[:200]}


class BailianProvider(LLMProvider):
    """阿里云百炼（通义千问）提供商"""

    def __init__(self, api_key: str | None = None, model: str = "qwen-plus"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.model = model
        self._httpx = None
        logger.info(f"Bailian Provider 初始化完成 (model={model})")

    @property
    def httpx(self):
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx

    async def generate(self, prompt: str, **kwargs) -> str:
        """实现真实的百炼 API 调用"""
        if not self.api_key:
            logger.warning("百炼 API Key 未配置，使用模拟响应")
            return f"[百炼模拟响应] {prompt[:100]}..."

        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            "parameters": {
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2048),
            }
        }

        logger.info(f"[百炼] 调用 API: {self.model}")

        try:
            async with self.httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                content = data["output"]["text"]
                logger.info("[百炼] API 调用成功")
                return content
        except Exception as e:
            logger.error(f"[百炼] API 调用失败：{e}")
            return f"[百炼错误] {str(e)}"

    async def generate_json(self, prompt: str, **kwargs) -> dict:
        """实现真实的百炼 API JSON 调用"""
        json_prompt = f"{prompt}\n\n请以严格的 JSON 格式回复，不要包含其他文字。"
        content = await self.generate(json_prompt, **kwargs)

        try:
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"[百炼] JSON 解析失败：{e}")
            return {"error": "JSON 解析失败", "content": content[:200]}


class LLMFactory:
    """LLM 工厂类"""

    _providers: dict[str, LLMProvider] = {}

    @classmethod
    def register(cls, name: str, provider: LLMProvider):
        """注册提供商"""
        cls._providers[name] = provider
        logger.info(f"注册 LLM 提供商：{name}")

    @classmethod
    def get(cls, name: str) -> LLMProvider | None:
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


def get_llm(provider_name: str | None = None) -> LLMProvider:
    """获取 LLM 实例"""
    if provider_name:
        return LLMFactory.get(provider_name) or LLMFactory.get_default()
    return LLMFactory.get_default()


# 便捷的全局函数
async def llm_generate(prompt: str, provider: str | None = None, **kwargs) -> str:
    """便捷函数：生成文本"""
    llm = get_llm(provider)
    return await llm.generate(prompt, **kwargs)


async def llm_generate_json(prompt: str, provider: str | None = None, **kwargs) -> dict:
    """便捷函数：生成 JSON"""
    llm = get_llm(provider)
    return await llm.generate_json(prompt, **kwargs)
