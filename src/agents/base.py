"""
Agent 基类

职责：定义所有 Agent 的通用接口和基础功能

设计原则：
1. 生命周期管理：init -> start -> execute -> stop -> destroy
2. 错误隔离：单个 Agent 失败不影响其他 Agent
3. 可观测性：完整的日志、指标、追踪支持
4. 异步优先：所有 I/O 操作均支持 async/await

版本：2.0.0
更新时间：2026-03-08
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from ..core.exceptions import (
    AgentAlreadyRunningError,
    AgentExecutionError,
    AgentTimeoutError,
)
from ..core.models import (
    Agent,
    AgentRole,
    AgentState,
    Blackboard,
    Message,
    MessageType,
    Task,
)

logger = structlog.get_logger(__name__)


# ===========================================
# 数据类定义
# ===========================================


class AgentLifecycleState(Enum):
    """Agent 生命周期状态"""
    CREATED = "created"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    DESTROYED = "destroyed"


@dataclass
class AgentMetrics:
    """Agent 性能指标"""
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_execution_time: float = 0.0
    total_tokens_used: int = 0
    total_cost: float = 0.0
    avg_response_time: float = 0.0
    last_execution_time: float | None = None

    def record_success(self, execution_time: float, tokens: int = 0, cost: float = 0.0) -> None:
        """记录成功执行"""
        self.total_tasks += 1
        self.successful_tasks += 1
        self.total_execution_time += execution_time
        self.total_tokens_used += tokens
        self.total_cost += cost
        self.avg_response_time = self.total_execution_time / self.successful_tasks
        self.last_execution_time = execution_time

    def record_failure(self) -> None:
        """记录失败执行"""
        self.total_tasks += 1
        self.failed_tasks += 1

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": self.successful_tasks / self.total_tasks if self.total_tasks > 0 else 0,
            "total_execution_time": round(self.total_execution_time, 3),
            "total_tokens_used": self.total_tokens_used,
            "total_cost": round(self.total_cost, 4),
            "avg_response_time": round(self.avg_response_time, 3),
            "last_execution_time": self.last_execution_time,
        }


class BaseAgent(ABC):
    """
    Agent 抽象基类 - 所有具体 Agent 必须继承此类并实现核心方法

    生命周期：
        CREATED -> init() -> INITIALIZED -> start() -> STARTED
        -> execute() -> stop() -> STOPPED -> destroy() -> DESTROYED

    使用方式：
        async with agent.lifecycle() as a:
            result = await a.process_task(task)

    或者手动管理：
        await agent.init()
        await agent.start()
        result = await agent.process_task(task)
        await agent.stop()
        await agent.destroy()
    """

    ROLE: AgentRole = None

    def __init__(
        self,
        agent_id: str | None = None,
        name: str | None = None,
        blackboard: Blackboard | None = None,
        trace_id: str | None = None,
        **kwargs,
    ):
        """
        初始化 Agent

        Args:
            agent_id: Agent ID (可选，默认自动生成)
            name: Agent 名称 (可选，默认使用类名)
            blackboard: 共享黑板实例
            trace_id: 追踪 ID (可选，用于分布式追踪)
            **kwargs: 其他配置参数
        """
        # 创建 Agent 模型实例
        agent_kwargs = {
            "name": name or self.__class__.__name__,
            "role": self.ROLE,
            "description": self.__doc__ or "",
        }
        # 只有当 agent_id 不为 None 时才设置 id，否则使用默认生成的 UUID
        if agent_id is not None:
            agent_kwargs["id"] = agent_id
        agent_kwargs.update(kwargs)
        self.agent = Agent(**agent_kwargs)

        # 共享黑板
        self.blackboard = blackboard

        # 生命周期状态
        self._lifecycle_state = AgentLifecycleState.CREATED

        # 追踪 ID
        self._trace_id = trace_id or str(uuid.uuid4())

        # 性能指标
        self._metrics = AgentMetrics()

        # 回调函数
        self._on_task_start: Callable | None = None
        self._on_task_complete: Callable | None = None
        self._on_task_error: Callable | None = None
        self._on_lifecycle_change: Callable | None = None

        # 日志上下文
        self.logger = logger.bind(
            agent_id=self.agent.id,
            agent_name=self.agent.name,
            agent_role=self.ROLE.value if self.ROLE else None,
            trace_id=self._trace_id,
        )

    # ===========================================
    # 生命周期管理
    # ===========================================

    async def init(self) -> None:
        """
        初始化 Agent

        子类可以重写此方法进行自定义初始化
        """
        if self._lifecycle_state != AgentLifecycleState.CREATED:
            raise AgentAlreadyRunningError(
                self.agent.name,
                f"Cannot init: current state is {self._lifecycle_state.value}",
            )

        self.logger.info("Agent initializing...")
        await self._do_init()
        self._set_lifecycle_state(AgentLifecycleState.INITIALIZED)
        self.logger.info("Agent initialized")

    async def _do_init(self) -> None:
        """子类重写此方法实现自定义初始化逻辑"""
        pass

    async def start(self) -> None:
        """
        启动 Agent

        子类可以重写此方法进行自定义启动逻辑
        """
        if self._lifecycle_state == AgentLifecycleState.CREATED:
            await self.init()
        elif self._lifecycle_state not in (
            AgentLifecycleState.INITIALIZED,
            AgentLifecycleState.STOPPED,
        ):
            raise AgentAlreadyRunningError(
                self.agent.name,
                f"Cannot start: current state is {self._lifecycle_state.value}",
            )

        self.logger.info("Agent starting...")
        await self._do_start()
        self._set_lifecycle_state(AgentLifecycleState.STARTED)
        self.logger.info("Agent started")

    async def _do_start(self) -> None:
        """子类重写此方法实现自定义启动逻辑"""
        pass

    async def stop(self) -> None:
        """
        停止 Agent

        子类可以重写此方法进行自定义停止逻辑
        """
        if self._lifecycle_state not in (
            AgentLifecycleState.STARTED,
            AgentLifecycleState.INITIALIZED,
        ):
            return  # 已经停止或未启动

        self.logger.info("Agent stopping...")
        await self._do_stop()
        self._set_lifecycle_state(AgentLifecycleState.STOPPED)
        self.logger.info("Agent stopped")

    async def _do_stop(self) -> None:
        """子类重写此方法实现自定义停止逻辑"""
        pass

    async def destroy(self) -> None:
        """
        销毁 Agent

        释放所有资源，Agent 将无法再使用
        """
        if self._lifecycle_state == AgentLifecycleState.DESTROYED:
            return

        if self._lifecycle_state == AgentLifecycleState.STARTED:
            await self.stop()

        self.logger.info("Agent destroying...")
        await self._do_destroy()
        self._set_lifecycle_state(AgentLifecycleState.DESTROYED)
        self.logger.info("Agent destroyed")

    async def _do_destroy(self) -> None:
        """子类重写此方法实现自定义销毁逻辑"""
        pass

    def _set_lifecycle_state(self, state: AgentLifecycleState) -> None:
        """设置生命周期状态"""
        old_state = self._lifecycle_state
        self._lifecycle_state = state
        if self._on_lifecycle_change:
            self._on_lifecycle_change(old_state, state)

    @asynccontextmanager
    async def lifecycle(self) -> AsyncIterator["BaseAgent"]:
        """
        生命周期上下文管理器

        使用方式：
            async with agent.lifecycle() as a:
                result = await a.process_task(task)
        """
        await self.init()
        await self.start()
        try:
            yield self
        finally:
            await self.stop()
            await self.destroy()

    def get_lifecycle_state(self) -> AgentLifecycleState:
        """获取生命周期状态"""
        return self._lifecycle_state

    def is_running(self) -> bool:
        """检查 Agent 是否正在运行"""
        return self._lifecycle_state == AgentLifecycleState.STARTED

    # ===========================================
    # 抽象方法 - 必须由子类实现
    # ===========================================

    @abstractmethod
    async def execute(self, task: Task) -> dict[str, Any]:
        """
        执行任务

        Args:
            task: 要执行的任务

        Returns:
            执行结果字典
        """
        pass

    @abstractmethod
    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        思考/推理过程

        Args:
            context: 上下文信息

        Returns:
            思考结果
        """
        pass

    # ===========================================
    # 任务执行
    # ===========================================

    async def process_task(self, task: Task) -> Task:
        """
        处理任务

        Args:
            task: 任务对象

        Returns:
            更新后的任务对象
        """
        # 检查 Agent 状态
        if not self.agent.is_available():
            raise AgentExecutionError(
                self.agent.name,
                f"Agent is not available. Current state: {self.agent.state}",
            )

        # 分配任务
        self.agent.assign_task(task.id)
        task.assigned_to = self.agent.id

        # 通知任务开始
        if self._on_task_start:
            await self._on_task_start(task)

        self.logger.info(
            "Task started",
            task_id=task.id,
            task_title=task.title,
        )

        try:
            # 开始任务
            task.start()
            start_time = datetime.now()

            # 执行任务 (带超时控制)
            if self.agent.timeout_seconds:
                result = await asyncio.wait_for(
                    self.execute(task),
                    timeout=self.agent.timeout_seconds,
                )
            else:
                result = await self.execute(task)

            # 计算执行时间
            execution_time = (datetime.now() - start_time).total_seconds()

            # 完成任务
            task.complete(output_data=result)
            self.agent.complete_task(success=True, execution_time=execution_time)

            # 通知任务完成
            if self._on_task_complete:
                await self._on_task_complete(task, result)

            self.logger.info(
                "Task completed",
                task_id=task.id,
                execution_time=execution_time,
            )

        except TimeoutError:
            error_msg = f"Task execution timed out after {self.agent.timeout_seconds}s"
            task.fail(error_msg)
            self.agent.fail_task()
            self._metrics.record_failure()

            if self._on_task_error:
                await self._on_task_error(task, TimeoutError(error_msg))

            self.logger.error(
                "Task timeout",
                task_id=task.id,
                timeout_seconds=self.agent.timeout_seconds,
            )
            raise AgentTimeoutError(self.agent.name, self.agent.timeout_seconds) from None

        except Exception as e:
            error_msg = str(e)
            task.fail(error_msg)
            self.agent.fail_task()
            self._metrics.record_failure()

            if self._on_task_error:
                await self._on_task_error(task, e)

            self.logger.error(
                "Task failed",
                task_id=task.id,
                error=error_msg,
                error_type=type(e).__name__,
            )
            raise AgentExecutionError(self.agent.name, error_msg) from e

        finally:
            # 更新最后活跃时间
            self.agent.last_active_at = datetime.now()

        return task

    def record_metrics(
        self,
        execution_time: float,
        tokens_used: int = 0,
        cost: float = 0.0,
    ) -> None:
        """
        记录执行指标（供子类调用）

        Args:
            execution_time: 执行时间（秒）
            tokens_used: 使用的 token 数
            cost: 成本（美元）
        """
        self._metrics.record_success(execution_time, tokens_used, cost)

        self.logger.debug(
            "Metrics recorded",
            execution_time=round(execution_time, 3),
            tokens_used=tokens_used,
            cost=round(cost, 4),
        )

    # ===========================================
    # 黑板通信
    # ===========================================

    def post_message(
        self,
        subject: str,
        content: Any,
        message_type: MessageType = MessageType.NOTIFICATION,
        recipient_id: str | None = None,
        recipient_role: str | None = None,
        priority: str = "normal",
        task_id: str | None = None,
    ) -> Message | None:
        """
        发送消息到黑板

        Args:
            subject: 消息主题
            content: 消息内容
            message_type: 消息类型
            recipient_id: 目标接收者 ID
            recipient_role: 目标接收者角色
            priority: 优先级
            task_id: 关联任务 ID

        Returns:
            发送的消息对象
        """
        if not self.blackboard:
            self.logger.warning("Cannot post message: blackboard not initialized")
            return None

        message = Message(
            type=message_type,
            priority=priority,
            subject=subject,
            content=content,
            sender_id=self.agent.id,
            sender_role=self.ROLE.value if self.ROLE else None,
            recipient_id=recipient_id,
            recipient_role=recipient_role,
            task_id=task_id,
        )

        self.blackboard.post_message(message)

        self.logger.debug(
            "Message posted",
            message_id=message.id,
            subject=subject,
            recipient=recipient_id or recipient_role or "broadcast",
        )

        return message

    def get_messages(
        self,
        message_type: MessageType | None = None,
        unread_only: bool = True,
    ) -> list[Message]:
        """
        获取消息

        Args:
            message_type: 消息类型过滤
            unread_only: 是否只获取未读消息

        Returns:
            消息列表
        """
        if not self.blackboard:
            return []

        messages = self.blackboard.get_messages(
            recipient_id=self.agent.id,
            recipient_role=self.ROLE.value if self.ROLE else None,
            message_type=message_type,
            unread_only=unread_only,
        )

        # 标记为已读
        for msg in messages:
            self.blackboard.mark_message_read(msg.id, self.agent.id)

        return messages

    def put_to_blackboard(
        self,
        key: str,
        value: Any,
        **kwargs,
    ) -> None:
        """
        写入黑板数据

        Args:
            key: 键名
            value: 值
            **kwargs: 其他参数
        """
        if not self.blackboard:
            self.logger.warning("Cannot put to blackboard: not initialized")
            return

        self.blackboard.put(
            key,
            value,
            owner_id=self.agent.id,
            **kwargs,
        )

        self.logger.debug("Data written to blackboard", key=key)

    def get_from_blackboard(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        从黑板读取数据

        Args:
            key: 键名
            default: 默认值

        Returns:
            值
        """
        if not self.blackboard:
            return default

        return self.blackboard.get(key, default)

    # ===========================================
    # 回调注册
    # ===========================================

    def on_task_start(self, callback: Callable) -> None:
        """注册任务开始回调"""
        self._on_task_start = callback

    def on_task_complete(self, callback: Callable) -> None:
        """注册任务完成回调"""
        self._on_task_complete = callback

    def on_task_error(self, callback: Callable) -> None:
        """注册任务错误回调"""
        self._on_task_error = callback

    def on_lifecycle_change(self, callback: Callable) -> None:
        """注册生命周期状态变化回调"""
        self._on_lifecycle_change = callback

    # ===========================================
    # 状态查询
    # ===========================================

    def get_state(self) -> AgentState:
        """获取 Agent 状态"""
        return self.agent.state

    def is_available(self) -> bool:
        """检查是否可用"""
        return self.agent.is_available() and self._lifecycle_state == AgentLifecycleState.STARTED

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return self.agent.get_statistics()

    def get_metrics(self) -> dict[str, Any]:
        """获取性能指标"""
        return self._metrics.to_dict()

    def get_trace_id(self) -> str:
        """获取追踪 ID"""
        return self._trace_id

    def set_trace_id(self, trace_id: str) -> None:
        """设置追踪 ID"""
        self._trace_id = trace_id
        self.logger = self.logger.bind(trace_id=trace_id)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.agent.id,
            "name": self.agent.name,
            "role": self.ROLE.value if self.ROLE else None,
            "state": self.agent.state.value,
            "lifecycle_state": self._lifecycle_state.value,
            "enabled": self.agent.enabled,
            "current_task_id": self.agent.current_task_id,
            "trace_id": self._trace_id,
            "statistics": self.get_statistics(),
            "metrics": self._metrics.to_dict(),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.agent.id}, name={self.agent.name}, role={self.ROLE.value})"
