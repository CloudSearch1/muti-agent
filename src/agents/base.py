"""
Agent 基类

职责：定义所有 Agent 的通用接口和基础功能
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog

from ..core.exceptions import (
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


class BaseAgent(ABC):
    """Agent 抽象基类 - 所有具体 Agent 必须继承此类并实现核心方法"""
    
    ROLE: AgentRole = None

    def __init__(
        self,
        agent_id: str | None = None,
        name: str | None = None,
        blackboard: Blackboard | None = None,
        **kwargs,
    ):
        """
        初始化 Agent

        Args:
            agent_id: Agent ID (可选，默认自动生成)
            name: Agent 名称 (可选，默认使用类名)
            blackboard: 共享黑板实例
            **kwargs: 其他配置参数
        """
        # 创建 Agent 模型实例
        self.agent = Agent(
            id=agent_id,
            name=name or self.__class__.__name__,
            role=self.ROLE,
            description=self.__doc__ or "",
            **kwargs,
        )

        # 共享黑板
        self.blackboard = blackboard

        # 回调函数
        self._on_task_start: Callable | None = None
        self._on_task_complete: Callable | None = None
        self._on_task_error: Callable | None = None

        # 日志上下文
        self.logger = logger.bind(
            agent_id=self.agent.id,
            agent_name=self.agent.name,
            agent_role=self.ROLE.value if self.ROLE else None,
        )

        self.logger.info("Agent initialized")

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

            if self._on_task_error:
                await self._on_task_error(task, TimeoutError(error_msg))

            self.logger.error("Task timeout", task_id=task.id)
            raise AgentTimeoutError(self.agent.name, self.agent.timeout_seconds)

        except Exception as e:
            error_msg = str(e)
            task.fail(error_msg)
            self.agent.fail_task()

            if self._on_task_error:
                await self._on_task_error(task, e)

            self.logger.error(
                "Task failed",
                task_id=task.id,
                error=error_msg,
            )
            raise AgentExecutionError(self.agent.name, error_msg) from e

        finally:
            # 更新最后活跃时间
            self.agent.last_active_at = datetime.now()

        return task

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
    ) -> Message:
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

    # ===========================================
    # 状态查询
    # ===========================================

    def get_state(self) -> AgentState:
        """获取 Agent 状态"""
        return self.agent.state

    def is_available(self) -> bool:
        """检查是否可用"""
        return self.agent.is_available()

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return self.agent.get_statistics()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.agent.id,
            "name": self.agent.name,
            "role": self.ROLE.value if self.ROLE else None,
            "state": self.agent.state.value,
            "enabled": self.agent.enabled,
            "current_task_id": self.agent.current_task_id,
            "statistics": self.get_statistics(),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.agent.id}, name={self.agent.name}, role={self.ROLE.value})"
