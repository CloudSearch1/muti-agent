"""
LLM 服务

职责：提供统一的 LLM 调用接口，支持多提供商
"""

from typing import Any, Optional, AsyncIterator
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
import structlog

from ..config.settings import Settings, get_settings


logger = structlog.get_logger(__name__)


class LLMMessage(BaseModel):
    """LLM 消息"""
    role: str = Field(..., description="角色 (system/user/assistant)")
    content: str = Field(..., description="消息内容")


class LLMResponse(BaseModel):
    """LLM 响应"""
    content: str = Field(..., description="响应内容")
    model: str = Field(..., description="使用的模型")
    usage: dict[str, int] = Field(default_factory=dict, description="Token 使用量")
    finish_reason: Optional[str] = Field(default=None, description="结束原因")


class BaseProvider(ABC):
    """LLM 提供商抽象基类"""
    
    NAME: str = None
    
    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """生成响应"""
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式生成"""
        pass


class OpenAIProvider(BaseProvider):
    """OpenAI 提供商"""
    
    NAME = "openai"
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4",
        **kwargs,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        
        # 延迟导入 httpx
        self._httpx = None
        
        logger.info(
            "OpenAIProvider initialized",
            model=model,
            base_url=base_url,
        )
    
    @property
    def httpx(self):
        """延迟导入 httpx"""
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx
    
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """调用 OpenAI API 生成响应"""
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [m.dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        
        logger.debug(
            "Calling OpenAI API",
            model=self.model,
            messages_count=len(messages),
        )
        
        async with self.httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            choice = data["choices"][0]
            
            return LLMResponse(
                content=choice["message"]["content"],
                model=data["model"],
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason"),
            )
    
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式调用 OpenAI API"""
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [m.dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }
        
        async with self.httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        
                        import json
                        try:
                            chunk = json.loads(data)
                            choice = chunk["choices"][0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue


class AzureOpenAIProvider(BaseProvider):
    """Azure OpenAI 提供商"""
    
    NAME = "azure"
    
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str = "2024-02-15-preview",
        **kwargs,
    ):
        self.api_key = api_key
        self.endpoint = endpoint
        self.deployment = deployment
        self.api_version = api_version
        
        self._httpx = None
        
        logger.info(
            "AzureOpenAIProvider initialized",
            deployment=deployment,
            endpoint=endpoint,
        )
    
    @property
    def httpx(self):
        if self._httpx is None:
            import httpx
            self._httpx = httpx
        return self._httpx
    
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """调用 Azure OpenAI API"""
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
        
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }
        
        payload = {
            "messages": [m.dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        
        async with self.httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            choice = data["choices"][0]
            
            return LLMResponse(
                content=choice["message"]["content"],
                model=self.deployment,
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason"),
            )
    
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式调用 Azure OpenAI"""
        # TODO: 实现流式调用
        response = await self.generate(messages, temperature, max_tokens, **kwargs)
        yield response.content


class LLMService:
    """
    LLM 服务
    
    统一管理 LLM 调用，支持多提供商切换
    """
    
    def __init__(self, settings: Settings = None):
        self.settings = settings or get_settings()
        self._provider: Optional[BaseProvider] = None
        self._initialize_provider()
        
        logger.info(
            "LLMService initialized",
            provider=self.settings.openai_model if self.settings.openai_api_key else "none",
        )
    
    def _initialize_provider(self) -> None:
        """初始化提供商"""
        if self.settings.azure_openai_api_key:
            self._provider = AzureOpenAIProvider(
                api_key=self.settings.azure_openai_api_key,
                endpoint=self.settings.azure_openai_endpoint,
                deployment=self.settings.azure_openai_deployment,
            )
        elif self.settings.openai_api_key:
            self._provider = OpenAIProvider(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_api_base,
                model=self.settings.openai_model,
            )
        else:
            logger.warning("No LLM API key configured")
    
    @property
    def provider(self) -> Optional[BaseProvider]:
        """获取当前提供商"""
        return self._provider
    
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return self._provider is not None
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        生成响应
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度
            max_tokens: 最大 token 数
            
        Returns:
            LLM 响应
        """
        if not self._provider:
            raise RuntimeError("LLM provider not configured")
        
        messages = []
        
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        
        messages.append(LLMMessage(role="user", content=prompt))
        
        return await self._provider.generate(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式生成"""
        if not self._provider:
            raise RuntimeError("LLM provider not configured")
        
        messages = []
        
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        
        messages.append(LLMMessage(role="user", content=prompt))
        
        async for chunk in self._provider.generate_stream(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ):
            yield chunk
    
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        对话
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            
        Returns:
            LLM 响应
        """
        if not self._provider:
            raise RuntimeError("LLM provider not configured")
        
        llm_messages = [
            LLMMessage(role=m["role"], content=m["content"])
            for m in messages
        ]
        
        return await self._provider.generate(
            llm_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


# 全局单例
_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """获取 LLM 服务单例"""
    global _service
    if _service is None:
        _service = LLMService()
    return _service


def reset_llm_service() -> LLMService:
    """重置 LLM 服务"""
    global _service
    _service = LLMService()
    return _service
