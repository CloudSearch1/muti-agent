"""
Agent 依赖注入容器

管理 Agent 的所有依赖，支持动态切换和测试 Mock

版本：2.0.0
更新时间：2026-03-12
增强功能：
- 支持 Agent 实例的注册和获取
- 支持 Agent 工厂函数注册
- 支持批量 Agent 创建
"""

import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable

from ..db.database import DatabaseManager, get_database_manager
from ..llm.cache import LLMCache, get_llm_cache
from ..llm.llm_provider import BaseProvider, get_llm
from ..llm.semantic_cache import SemanticCache, get_semantic_cache
from .models import AgentRole
from .state_store import StateStore, get_state_store

logger = logging.getLogger(__name__)

# Agent 类型别名（避免循环导入）
AgentFactory = Callable[[], Any]  # Agent 工厂函数类型


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
    _lock = threading.Lock()  # 类级别锁，保证单例创建的线程安全

    def __new__(cls, name: str = "default"):
        """
        单例模式，支持多实例（线程安全）
        
        使用双重检查锁定（Double-Checked Locking）模式：
        1. 第一次检查避免不必要的锁竞争
        2. 锁内第二次检查防止重复创建
        """
        if name not in cls._instances:
            with cls._lock:
                # 双重检查：防止在等待锁期间其他线程已创建实例
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
        self._llm_provider: BaseProvider | None = None
        self._llm_cache: LLMCache | None = None
        self._semantic_cache: SemanticCache | None = None
        self._db_manager: DatabaseManager | None = None
        self._state_store: StateStore | None = None

        # Agent 实例缓存
        self._agents: dict[str, Any] = {}

        # Agent 工厂函数注册表
        self._agent_factories: dict[str, AgentFactory] = {}

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

    def set_llm_provider(self, provider: BaseProvider):
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

    # ===========================================
    # Agent 管理（新增）
    # ===========================================

    def register_agent(self, name: str, agent: Any) -> "AgentContainer":
        """
        注册 Agent 实例

        Args:
            name: Agent 名称（如 "planner", "architect"）
            agent: Agent 实例

        Returns:
            self（支持链式调用）
        """
        self._agents[name] = agent
        logger.info(f"Agent registered: {name}")
        return self

    def register_agent_factory(self, name: str, factory: AgentFactory) -> "AgentContainer":
        """
        注册 Agent 工厂函数

        Args:
            name: Agent 名称
            factory: 创建 Agent 实例的工厂函数

        Returns:
            self（支持链式调用）

        使用示例:
            container.register_agent_factory("planner", lambda: PlannerAgent())
        """
        self._agent_factories[name] = factory
        logger.info(f"Agent factory registered: {name}")
        return self

    def get_agent(self, name: str) -> Any:
        """
        获取 Agent 实例

        优先级：
        1. 已注册的 Agent 实例
        2. 调用工厂函数创建并缓存

        Args:
            name: Agent 名称

        Returns:
            Agent 实例

        Raises:
            KeyError: Agent 未注册
        """
        # 1. 检查已缓存的实例
        if name in self._agents:
            return self._agents[name]

        # 2. 使用工厂函数创建
        if name in self._agent_factories:
            agent = self._agent_factories[name]()
            self._agents[name] = agent  # 缓存实例
            logger.info(f"Agent created via factory: {name}")
            return agent

        raise KeyError(f"Agent not found: {name}. Please register it first.")

    def has_agent(self, name: str) -> bool:
        """检查 Agent 是否已注册"""
        return name in self._agents or name in self._agent_factories

    def get_all_agents(self) -> dict[str, Any]:
        """
        获取所有 Agent 实例

        会触发所有已注册工厂函数的执行

        Returns:
            Agent 名称到实例的映射
        """
        # 确保所有工厂函数都被执行
        for name in self._agent_factories:
            if name not in self._agents:
                self._agents[name] = self._agent_factories[name]()

        return self._agents.copy()

    def clear_agents(self) -> "AgentContainer":
        """清除所有 Agent 实例（保留工厂函数）"""
        self._agents.clear()
        logger.info("All agent instances cleared")
        return self

    def create_agents_batch(self, agent_configs: dict[str, AgentFactory]) -> dict[str, Any]:
        """
        批量创建 Agent

        Args:
            agent_configs: Agent 名称到工厂函数的映射

        Returns:
            创建的 Agent 实例字典
        """
        agents = {}
        for name, factory in agent_configs.items():
            if name not in self._agents:
                self._agent_factories[name] = factory
                self._agents[name] = factory()
                agents[name] = self._agents[name]
                logger.info(f"Agent created: {name}")
        return agents

    def create_agent_by_role(
        self,
        role: AgentRole,
        name: str | None = None,
        **kwargs,
    ) -> Any:
        """
        根据角色创建 Agent 实例

        这是推荐的方式，使用 AgentRole 枚举自动映射到具体的 Agent 类。

        Args:
            role: Agent 角色枚举
            name: Agent 名称（可选，默认使用角色名称）
            **kwargs: 传递给 Agent 构造函数的额外参数

        Returns:
            Agent 实例

        Raises:
            ValueError: 角色未找到对应的 Agent 类

        使用示例:
            from src.core.models import AgentRole

            container = get_agent_container()
            planner = container.create_agent_by_role(AgentRole.PLANNER)
            coder = container.create_agent_by_role(AgentRole.CODER, name="code_assistant")
        """
        agent_class = AgentRole.get_agent_class(role)
        if agent_class is None:
            raise ValueError(f"No agent class found for role: {role}")

        # 使用角色值作为默认名称
        agent_name = name or role.value

        # 创建 Agent 实例
        agent = agent_class(name=agent_name, **kwargs)

        # 注册到容器
        self._agents[agent_name] = agent
        logger.info(f"Agent created by role: {role.value} -> {agent_class.__name__}")

        return agent

    def create_all_agents(self, **kwargs) -> dict[str, Any]:
        """
        创建所有角色的 Agent 实例

        Args:
            **kwargs: 传递给所有 Agent 构造函数的通用参数

        Returns:
            Agent 名称到实例的映射

        使用示例:
            container = get_agent_container()
            agents = container.create_all_agents()
            # 返回: {"planner": PlannerAgent, "architect": ArchitectAgent, ...}
        """
        agents = {}
        for role in AgentRole.get_all_roles():
            try:
                agent = self.create_agent_by_role(role, **kwargs)
                agents[role.value] = agent
            except Exception as e:
                logger.error(f"Failed to create agent for role {role.value}: {e}")

        logger.info(f"Created {len(agents)} agents for all roles")
        return agents

    def get_agent_by_role(self, role: AgentRole) -> Any:
        """
        根据角色获取 Agent 实例

        优先级：
        1. 已注册的同名 Agent 实例
        2. 已注册的同名工厂函数
        3. 自动创建并注册

        Args:
            role: Agent 角色枚举

        Returns:
            Agent 实例

        Raises:
            ValueError: 角色未找到对应的 Agent 类
        """
        # 1. 尝试使用角色值作为名称查找
        role_name = role.value
        if role_name in self._agents:
            return self._agents[role_name]

        # 2. 检查工厂函数
        if role_name in self._agent_factories:
            return self.get_agent(role_name)

        # 3. 自动创建
        return self.create_agent_by_role(role)

    def get_llm(self) -> BaseProvider:
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
            "agents": self._agents,
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
