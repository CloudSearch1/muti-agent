"""
Agent 依赖注入容器

管理 Agent 的所有依赖，支持动态切换和测试 Mock
"""

import logging
from dataclasses import dataclass
from typing import Any

from ..db.database import DatabaseManager, get_database_manager
from ..llm.cache import LLMCache, get_llm_cache
from ..llm.llm_provider import LLMProvider, get_llm
from ..llm.semantic_cache import SemanticCache, get_semantic_cache
from .state_store import StateStore, get_state_store

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent 配置"""
    # LLM 配置
    llm_provider: str = "openai"
    llm_model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 2048
    
    # 缓存配置
    use_cache: bool = True
    cache_ttl: int = 3600
    semantic_cache_threshold: float = 0.9
    
    # Agent 特定配置
    preferred_language: str = "python"
    code_style: str = "pep8"
    testing_framework: str = "pytest"
    doc_format: str = "markdown"
    
    # 执行配置
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 日志配置
    log_level: str = "INFO"
    verbose: bool = False


class AgentContainer:
    """
    Agent 依赖注入容器

    功能:
    - 集中管理所有依赖
    - 支持动态配置
    - 便于测试 Mock
    - 生命周期管理
    """

    _instance: "AgentContainer | None" = None
    _instances: dict[str, "AgentContainer"] = {}

    def __new__(cls, name: str = "default"):
        """单例模式，支持多实例"""
        if name not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name: str = "default"):
        if self._initialized:
            return

        self.name = name
        self.config = AgentConfig()

        # 依赖项
        self._llm_provider: LLMProvider | None = None
        self._llm_cache: LLMCache | None = None
        self._semantic_cache: SemanticCache | None = None
        self._db_manager: DatabaseManager | None = None
        self._state_store: StateStore | None = None

        # 自定义依赖
        self._custom_deps: dict[str, Any] = {}

        self._initialized = True
        logger.info(f"AgentContainer '{name}' initialized")

    @classmethod
    def get_container(cls, name: str = "default") -> "AgentContainer":
        """获取容器实例"""
        return cls(name)
    
    @classmethod
    def reset(cls, name: str = "default"):
        """重置容器（用于测试）"""
        if name in cls._instances:
            del cls._instances[name]
    
    def configure(self, **kwargs):
        """配置 Agent"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        logger.info(f"AgentContainer '{self.name}' configured: {kwargs}")
        return self
    
    def set_llm_provider(self, provider: LLMProvider):
        """设置 LLM 提供商"""
        self._llm_provider = provider
        logger.info(f"LLM provider set: {provider.__class__.__name__}")
        return self
    
    def set_llm_cache(self, cache: LLMCache):
        """设置 LLM 缓存"""
        self._llm_cache = cache
        logger.info("LLM cache set")
        return self
    
    def set_semantic_cache(self, cache: SemanticCache):
        """设置语义缓存"""
        self._semantic_cache = cache
        logger.info("Semantic cache set")
        return self
    
    def set_db_manager(self, db_manager: DatabaseManager):
        """设置数据库管理器"""
        self._db_manager = db_manager
        logger.info("Database manager set")
        return self
    
    def set_state_store(self, state_store: StateStore):
        """设置状态存储"""
        self._state_store = state_store
        logger.info("State store set")
        return self
    
    def register_dependency(self, name: str, dependency: Any):
        """注册自定义依赖"""
        self._custom_deps[name] = dependency
        logger.info(f"Custom dependency registered: {name}")
        return self
    
    def get_llm(self) -> LLMProvider:
        """获取 LLM 提供商"""
        if self._llm_provider:
            return self._llm_provider
        
        # 使用默认配置
        self._llm_provider = get_llm(self.config.llm_provider)
        return self._llm_provider
    
    def get_llm_cache(self) -> LLMCache:
        """获取 LLM 缓存"""
        if self._llm_cache:
            return self._llm_cache
        
        self._llm_cache = get_llm_cache()
        return self._llm_cache
    
    def get_semantic_cache(self) -> SemanticCache:
        """获取语义缓存"""
        if self._semantic_cache:
            return self._semantic_cache
        
        self._semantic_cache = get_semantic_cache(
            similarity_threshold=self.config.semantic_cache_threshold,
        )
        return self._semantic_cache
    
    def get_db_manager(self) -> DatabaseManager:
        """获取数据库管理器"""
        if self._db_manager:
            return self._db_manager
        
        self._db_manager = get_database_manager()
        return self._db_manager
    
    def get_state_store(self) -> StateStore:
        """获取状态存储"""
        if self._state_store:
            return self._state_store
        
        self._state_store = get_state_store()
        return self._state_store
    
    def get_dependency(self, name: str) -> Any:
        """获取自定义依赖"""
        if name in self._custom_deps:
            return self._custom_deps[name]
        
        raise KeyError(f"Dependency not found: {name}")
    
    def get_all_dependencies(self) -> dict[str, Any]:
        """获取所有依赖"""
        return {
            "llm_provider": self._llm_provider,
            "llm_cache": self._llm_cache,
            "semantic_cache": self._semantic_cache,
            "db_manager": self._db_manager,
            "state_store": self._state_store,
            **self._custom_deps,
        }
    
    async def initialize(self):
        """初始化所有依赖"""
        logger.info(f"Initializing AgentContainer '{self.name}'")
        
        # 初始化缓存
        if self.config.use_cache:
            await self.get_llm_cache()
            await self.get_semantic_cache()
        
        # 初始化数据库
        self.get_db_manager()
        
        # 初始化状态存储
        self.get_state_store()
        
        logger.info(f"AgentContainer '{self.name}' initialized")
    
    async def shutdown(self):
        """关闭所有依赖"""
        logger.info(f"Shutting down AgentContainer '{self.name}'")
        
        # 关闭数据库
        if self._db_manager:
            await self._db_manager.disconnect()
        
        # 关闭缓存
        if self._llm_cache:
            await self._llm_cache.close()
        
        logger.info(f"AgentContainer '{self.name}' shut down")


# 全局容器实例
_default_container: AgentContainer | None = None


def get_agent_container(name: str = "default") -> AgentContainer:
    """获取 Agent 容器"""
    global _default_container
    if _default_container is None:
        _default_container = AgentContainer(name)
    return _default_container


async def init_agent_container(
    name: str = "default",
    **config_kwargs,
) -> AgentContainer:
    """初始化 Agent 容器"""
    container = AgentContainer(name)
    container.configure(**config_kwargs)
    await container.initialize()
    return container


# 装饰器：自动注入依赖
def inject_dependencies(*dep_names: str):
    """
    装饰器：自动注入依赖
    
    用法:
        @inject_dependencies("llm_provider", "llm_cache")
        async def generate(self, llm_provider, llm_cache, prompt: str) -> str:
            ...
    """
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            container = get_agent_container()
            
            # 注入依赖
            for dep_name in dep_names:
                if dep_name not in kwargs:
                    kwargs[dep_name] = getattr(container, f"get_{dep_name}")()
            
            return await func(self, *args, **kwargs)
        
        return wrapper
    return decorator
