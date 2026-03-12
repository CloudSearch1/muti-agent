"""
PI-Python Agent 类

有状态的 Agent 运行时，支持工具调用、事件流和技能集成
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..ai import (
    AssistantMessage,
    Context,
    Message,
    Model,
    TextContent,
    ToolCall,
    ToolResultMessage,
    complete,
    stream,
)
from ..ai.stream import AssistantMessageEventStream, StreamOptions
from ..skills import Skill, SkillLoader, SkillRegistry
from .events import AgentEvent, AgentEventType
from .session import Session
from .tools import AgentTool


@dataclass
class AgentState:
    """Agent 状态"""
    system_prompt: str
    model: Model
    thinking_level: str = "off"  # off, low, medium, high
    tools: list[AgentTool] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    is_streaming: bool = False
    stream_message: AssistantMessage | None = None
    pending_tool_calls: set[str] = field(default_factory=set)
    error: str | None = None
    session: Session | None = None
    # Skills 相关
    skill_registry: SkillRegistry | None = None
    active_skills: list[Skill] = field(default_factory=list)
    skills_injected: bool = False


class Agent:
    """
    有状态的 Agent

    特性:
    - 状态管理（消息、模型、工具）
    - 工具执行生命周期
    - 事件驱动架构
    - Steering/Follow-up 消息队列
    - Skills 集成（动态加载和注入）
    """

    def __init__(
        self,
        initial_state: AgentState,
        convert_to_llm: Callable[[list[Message]], list[Message]] | None = None,
        transform_context: Callable[[Context], Awaitable[Context]] | None = None,
        steering_mode: str = "one-at-a-time",
        follow_up_mode: str = "one-at-a-time",
        skill_registry: SkillRegistry | None = None,
        skills_dir: Path | None = None,
        auto_match_skills: bool = True,
    ):
        """
        初始化 Agent

        Args:
            initial_state: 初始状态
            convert_to_llm: 消息转换函数
            transform_context: 上下文转换函数（用于压缩、注入外部上下文）
            steering_mode: Steering 模式
            follow_up_mode: Follow-up 模式
            skill_registry: 技能注册表（可选，不提供则使用全局注册表）
            skills_dir: 技能目录（可选，用于加载技能文件）
            auto_match_skills: 是否自动匹配技能（默认 True）
        """
        self.state = initial_state
        self._convert_to_llm = convert_to_llm or self._default_convert_to_llm
        self._transform_context = transform_context
        self._steering_mode = steering_mode
        self._follow_up_mode = follow_up_mode
        self._subscribers: list[Callable[[AgentEvent], Awaitable[None]]] = []
        self._steering_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._follow_up_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._abort_controller = asyncio.Event()
        self._auto_match_skills = auto_match_skills

        # 初始化技能注册表
        if skill_registry:
            self.state.skill_registry = skill_registry
        else:
            from ..skills.registry import get_skill_registry
            self.state.skill_registry = get_skill_registry()

        # 从目录加载技能
        if skills_dir:
            self._load_skills_from_directory(skills_dir)

    def subscribe(self, callback: Callable[[AgentEvent], Awaitable[None]]) -> None:
        """订阅 Agent 事件"""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[AgentEvent], Awaitable[None]]) -> None:
        """取消订阅"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def _emit(self, event: AgentEvent) -> None:
        """发射事件"""
        for callback in self._subscribers:
            try:
                await callback(event)
            except Exception:
                pass  # 忽略订阅者错误

    def _default_convert_to_llm(self, messages: list[Message]) -> list[Message]:
        """默认消息转换"""
        return [m for m in messages if m.role in ("user", "assistant", "tool_result")]

    async def prompt(self, content: str | list[Any]) -> None:
        """
        发送提示

        Args:
            content: 用户输入（字符串或内容列表）
        """
        # 重置中止标志
        self._abort_controller.clear()

        await self._emit(AgentEvent(type=AgentEventType.AGENT_START))
        await self._emit(AgentEvent(type=AgentEventType.TURN_START))

        # 添加用户消息
        if isinstance(content, str):
            user_msg = AssistantMessage if False else None
            from ..ai.types import UserMessage
            user_msg = UserMessage.from_text(content)
        else:
            from ..ai.types import UserMessage
            user_msg = UserMessage(content=content)

        await self._emit(AgentEvent(
            type=AgentEventType.MESSAGE_START,
            message=user_msg
        ))

        self.state.messages.append(user_msg)

        await self._emit(AgentEvent(
            type=AgentEventType.MESSAGE_END,
            message=user_msg
        ))

        # 运行循环
        await self._run_loop()

        await self._emit(AgentEvent(type=AgentEventType.TURN_END))
        await self._emit(AgentEvent(type=AgentEventType.AGENT_END))

    async def _run_loop(self) -> None:
        """运行主循环"""
        max_iterations = 50  # 防止无限循环

        for _ in range(max_iterations):
            if self._abort_controller.is_set():
                break

            # 构建上下文
            context = await self._build_context()

            # 调用 LLM
            self.state.is_streaming = True

            try:
                event_stream = await stream(
                    self.state.model,
                    context,
                    StreamOptions(
                        reasoning=self.state.thinking_level,
                    )
                )

                # 处理流式事件
                assistant_msg = await self._process_stream(event_stream)

                if assistant_msg:
                    self.state.messages.append(assistant_msg)

                    # 检查是否有工具调用
                    tool_calls = [
                        c for c in assistant_msg.content
                        if isinstance(c, ToolCall)
                    ]

                    if tool_calls:
                        # 执行工具
                        should_continue = await self._execute_tools(tool_calls)
                        if should_continue:
                            continue  # 继续循环

                    # 没有工具调用，结束
                    break

            except Exception as e:
                self.state.error = str(e)
                await self._emit(AgentEvent(
                    type=AgentEventType.ERROR,
                    error=str(e)
                ))
                break

            finally:
                self.state.is_streaming = False

        # 处理 follow-up
        while not self._follow_up_queue.empty():
            follow_up = await self._follow_up_queue.get()
            if isinstance(follow_up.content, str):
                await self.prompt(follow_up.content)
            else:
                await self.prompt(follow_up.content)

    async def _build_context(self) -> Context:
        """构建上下文"""
        # 构建系统提示词，包含 Skills
        system_prompt = self.state.system_prompt

        # 如果有技能注册表且尚未注入，添加技能列表
        if self.state.skill_registry and not self.state.skills_injected:
            skills_prompt = self.format_skills_for_prompt()
            if skills_prompt:
                system_prompt = system_prompt + skills_prompt

        context = Context(
            system_prompt=system_prompt,
            messages=self._convert_to_llm(self.state.messages),
            tools=[t.to_tool() for t in self.state.tools]
        )

        # 应用上下文转换
        if self._transform_context:
            context = await self._transform_context(context)

        return context

    async def _process_stream(
        self,
        event_stream: AssistantMessageEventStream
    ) -> AssistantMessage | None:
        """处理流式事件"""
        content: list[Any] = []
        current_text = ""
        _usage = {}

        async for event in event_stream:
            if self._abort_controller.is_set():
                break

            if event.type == "text_delta":
                current_text += event.delta or ""
                await self._emit(AgentEvent(
                    type=AgentEventType.MESSAGE_UPDATE,
                    delta=event.delta
                ))

            elif event.type == "thinking_delta":
                from ..ai.types import ThinkingContent
                # 暂存思考内容
                content.append(ThinkingContent(thinking=event.delta or ""))

            elif event.type == "tool_call" and event.tool_call:
                content.append(event.tool_call)

            elif event.type == "done":
                if event.message:
                    return event.message

                # 构建消息
                if current_text:
                    content.insert(0, TextContent(text=current_text))

                if event.usage:
                    _usage = event.usage

                return AssistantMessage(content=content)

            elif event.type == "error":
                raise RuntimeError(event.error or "Unknown error")

        return None

    async def _execute_tools(self, tool_calls: list[ToolCall]) -> bool:
        """执行工具，返回是否应该继续"""
        for tool_call in tool_calls:
            # 检查 steering
            if not self._steering_queue.empty():
                steering = await self._steering_queue.get()
                self.state.messages.append(steering)
                return True  # 中断，继续循环

            await self._emit(AgentEvent(
                type=AgentEventType.TOOL_EXECUTION_START,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                args=tool_call.input
            ))

            # 查找工具
            tool = next(
                (t for t in self.state.tools if t.name == tool_call.name),
                None
            )

            if tool:
                try:
                    result = await tool.execute(
                        tool_call.id,
                        tool_call.input,
                        context={"agent": self}
                    )

                    # 添加工具结果
                    tool_result_msg = ToolResultMessage(
                        tool_call_id=tool_call.id,
                        content=result.content
                    )
                    self.state.messages.append(tool_result_msg)

                    await self._emit(AgentEvent(
                        type=AgentEventType.TOOL_EXECUTION_END,
                        tool_call_id=tool_call.id,
                        result=result
                    ))

                except Exception as e:
                    # 工具执行失败
                    error_result = ToolResultMessage(
                        tool_call_id=tool_call.id,
                        content=[TextContent(text=f"Error: {str(e)}")]
                    )
                    self.state.messages.append(error_result)

                    await self._emit(AgentEvent(
                        type=AgentEventType.ERROR,
                        error=f"Tool {tool_call.name} failed: {str(e)}"
                    ))
            else:
                # 工具不存在
                error_result = ToolResultMessage(
                    tool_call_id=tool_call.id,
                    content=[TextContent(text=f"Unknown tool: {tool_call.name}")]
                )
                self.state.messages.append(error_result)

        return True  # 继续循环

    def steer(self, message: Message) -> None:
        """
        发送 Steering 消息

        在工具执行过程中中断，跳过剩余工具
        """
        self._steering_queue.put_nowait(message)

    def follow_up(self, message: Message) -> None:
        """
        发送 Follow-up 消息

        在 Agent 完成后执行
        """
        self._follow_up_queue.put_nowait(message)

    def abort(self) -> None:
        """中止当前操作"""
        self._abort_controller.set()

    def set_tools(self, tools: list[AgentTool]) -> None:
        """设置工具列表"""
        self.state.tools = tools

    def add_tool(self, tool: AgentTool) -> None:
        """添加工具"""
        self.state.tools.append(tool)

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示"""
        self.state.system_prompt = prompt

    def set_model(self, model: Model) -> None:
        """设置模型"""
        self.state.model = model

    def clear_messages(self) -> None:
        """清除消息"""
        self.state.messages.clear()

    def get_messages(self) -> list[Message]:
        """获取所有消息"""
        return self.state.messages.copy()

    async def complete_simple(self, prompt: str) -> str:
        """简单完成调用，返回文本结果"""
        context = Context(system_prompt=self.state.system_prompt)
        context.add_user_message(prompt)

        message = await complete(self.state.model, context)
        return message.text

    # ===========================================
    # Skills 集成方法
    # ===========================================

    def _load_skills_from_directory(self, skills_dir: Path) -> int:
        """
        从目录加载技能

        Args:
            skills_dir: 技能目录

        Returns:
            加载的技能数量
        """
        if self.state.skill_registry:
            return self.state.skill_registry.load_from_directory(skills_dir)
        return 0

    def format_skills_for_prompt(self, skills: list[Skill] | None = None) -> str:
        """
        格式化技能为紧凑的提示词格式

        参考 OpenClaw 的紧凑格式，在系统提示词中显示为简洁列表

        Args:
            skills: 要格式化的技能列表（None 则使用所有已注册技能）

        Returns:
            格式化后的技能提示词
        """
        registry = self.state.skill_registry
        if not registry:
            return ""

        skills_to_format = skills if skills is not None else registry.list()
        if not skills_to_format:
            return ""

        lines = [
            "",
            "# Available Skills",
            "",
            "Skills provide specialized capabilities. Invoke with: skill: \"<name>\"",
            "",
        ]

        # 紧凑格式：每个技能一行
        for skill in skills_to_format:
            trigger_hint = f" - trigger: {', '.join(skill.triggers[:3])}" if skill.triggers else ""
            lines.append(f"- **{skill.name}**: {skill.description}{trigger_hint}")

        lines.append("")
        lines.append("When a skill matches the user's request, follow its guidance.")
        lines.append("")

        return "\n".join(lines)

    def match_skills(self, text: str) -> list[Skill]:
        """
        匹配用户输入与技能

        Args:
            text: 用户输入文本

        Returns:
            匹配的技能列表
        """
        if not self.state.skill_registry:
            return []

        return self.state.skill_registry.find_matching(text)

    def inject_skill_instructions(self, skills: list[Skill]) -> str:
        """
        注入技能详细指令

        当技能被触发时，动态加载完整的技能指令

        Args:
            skills: 要注入的技能列表

        Returns:
            完整的技能指令
        """
        if not skills:
            return ""

        lines = ["", "# Active Skill Instructions", ""]

        for skill in skills:
            lines.append(skill.to_prompt())
            lines.append("")

        return "\n".join(lines)

    def set_skill_registry(self, registry: SkillRegistry) -> None:
        """设置技能注册表"""
        self.state.skill_registry = registry

    def register_skill(self, skill: Skill) -> None:
        """注册单个技能"""
        if self.state.skill_registry:
            self.state.skill_registry.register(skill)

    def get_active_skills(self) -> list[Skill]:
        """获取当前激活的技能"""
        return self.state.active_skills.copy()

    def clear_active_skills(self) -> None:
        """清除激活的技能"""
        self.state.active_skills.clear()
        self.state.skills_injected = False

    async def prompt_with_skills(
        self,
        content: str | list[Any],
        inject_matched: bool = True
    ) -> None:
        """
        发送提示并自动处理技能

        Args:
            content: 用户输入
            inject_matched: 是否注入匹配的技能指令
        """
        # 匹配技能
        if self._auto_match_skills and inject_matched:
            text = content if isinstance(content, str) else str(content)
            matched = self.match_skills(text)

            if matched:
                self.state.active_skills = matched

                # 注入技能指令到系统提示词
                skill_instructions = self.inject_skill_instructions(matched)
                if skill_instructions:
                    original_prompt = self.state.system_prompt
                    self.state.system_prompt = original_prompt + skill_instructions
                    self.state.skills_injected = True

        # 调用原始 prompt 方法
        await self.prompt(content)
