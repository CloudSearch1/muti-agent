"""
PI-Python 交互式 REPL

提供交互式命令行会话功能
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Awaitable
from collections.abc import Coroutine

if TYPE_CHECKING:
    from rich.console import Console

from ...agent.events import AgentEvent, AgentEventType


# Type alias for event handlers that can be sync or async
EventHandler = Callable[[AgentEvent], None] | Callable[[AgentEvent], Awaitable[None]]


class ReplSession:
    """交互式 REPL 会话"""

    def __init__(
        self,
        agent: Any,
        console: Console,
        debug: bool = False,
        tracer: Any | None = None
    ):
        """
        初始化 REPL 会话

        Args:
            agent: Agent 实例
            console: Rich 控制台
            debug: 是否启用调试模式
            tracer: 追踪器实例
        """
        self.agent = agent
        self.console = console
        self.debug = debug
        self.tracer = tracer
        self.history: list[str] = []

        # 订阅 Agent 事件（只订阅一次）
        self._request_handler: EventHandler | None = None
        self.agent.subscribe(self._on_agent_event)
    
    async def run(self) -> None:
        """运行 REPL 循环"""
        
        # 显示帮助信息
        self._show_welcome()
        
        while True:
            try:
                # 读取用户输入
                user_input = await self._read_input()
                
                if not user_input.strip():
                    continue
                
                # 检查退出命令
                if user_input.lower() in ("exit", "quit", "q", "/exit", "/quit"):
                    break
                
                # 添加到历史
                self.history.append(user_input)
                
                # 处理特殊命令
                if await self._handle_command(user_input):
                    continue
                
                # 处理 Agent 请求
                await self._process_request(user_input)
                
            except KeyboardInterrupt:
                self.console.print("\n[yellow]按 Ctrl+D 或输入 'exit' 退出[/yellow]")
                continue
            except EOFError:
                break
        
        self.console.print("\n[green]感谢使用 PI-Python！[/green]")
    
    def _show_welcome(self) -> None:
        """显示欢迎信息"""
        from rich.markdown import Markdown
        
        help_text = """
## 欢迎使用 PI-Python REPL

### 可用命令：
- `/clear` - 清除会话历史
- `/history` - 显示会话历史
- `/tools` - 显示可用工具
- `/skills` - 显示可用技能
- `/debug` - 显示调试信息
- `/help` - 显示帮助信息
- `exit` / `quit` / `q` - 退出 REPL

### 使用提示：
- 直接输入问题，Agent 会帮你解答
- 使用 ↑ / ↓ 键浏览历史记录
- 使用 Tab 键自动补全（如支持）
- 调试模式下会记录详细的执行日志
        """
        
        self.console.print(Markdown(help_text))
    
    async def _read_input(self) -> str:
        """读取用户输入"""
        from rich.prompt import Prompt
        
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: Prompt.ask("\n[cyan]>>>[/cyan]")
        )
    
    async def _handle_command(self, command: str) -> bool:
        """
        处理 REPL 特殊命令
        
        Args:
            command: 用户输入的命令
            
        Returns:
            是否已处理（True 表示不再传递给 Agent）
        """
        
        if not command.startswith("/"):
            return False
        
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == "/clear":
            self.agent.clear_messages()
            self.console.print("[green]✓[/green] 会话已清除")
            return True
        
        elif cmd == "/history":
            self._show_history()
            return True
        
        elif cmd == "/tools":
            self._show_tools()
            return True
        
        elif cmd == "/skills":
            self._show_skills()
            return True
        
        elif cmd == "/debug":
            self._show_debug_info()
            return True
        
        elif cmd == "/help":
            self._show_welcome()
            return True
        
        return False
    
    def _show_history(self) -> None:
        """显示会话历史"""
        messages = self.agent.get_messages()
        
        if not messages:
            self.console.print("[yellow]暂无历史消息[/yellow]")
            return
        
        self.console.print("\n[bold]会话历史:[/bold]")
        
        for i, msg in enumerate(messages, 1):
            role = msg.role
            content_preview = str(msg.content)[:60]
            if len(str(msg.content)) > 60:
                content_preview += "..."
            
            # 根据角色显示不同颜色
            if role == "user":
                style = "cyan"
            elif role == "assistant":
                style = "green"
            else:
                style = "yellow"
            
            self.console.print(
                f"  [{style}]{i}. [{role}]{content_preview}[/{style}]"
            )
        
        self.console.print(f"\n总计 {len(messages)} 条消息")
    
    def _show_tools(self) -> None:
        """显示可用工具"""
        tools = self.agent.state.tools
        
        if not tools:
            self.console.print("[yellow]暂无可用工具[/yellow]")
            return
        
        self.console.print("\n[bold]可用工具:[/bold]")
        
        for tool in tools:
            self.console.print(
                f"  [blue]- {tool.name}:[/blue] {tool.description}"
            )
    
    def _show_skills(self) -> None:
        """显示可用技能"""
        registry = self.agent.state.skill_registry
        
        if not registry:
            self.console.print("[yellow]暂无可用技能[/yellow]")
            return
        
        skills = registry.list()
        
        if not skills:
            self.console.print("[yellow]暂无可用技能[/yellow]")
            return
        
        self.console.print("\n[bold]可用技能:[/bold]")
        
        for skill in skills:
            triggers = f" (触发: {', '.join(skill.triggers[:3])})" if skill.triggers else ""
            self.console.print(
                f"  [green]- {skill.name}:[/green] {skill.description}{triggers}"
            )
        
        self.console.print(f"\n总计 {len(skills)} 个技能")
    
    def _show_debug_info(self) -> None:
        """显示调试信息"""
        state = self.agent.state
        
        self.console.print("\n[bold]Agent 状态:[/bold]")
        self.console.print(f"  消息数: {len(state.messages)}")
        self.console.print(f"  工具数: {len(state.tools)}")
        self.console.print(f"  技能数: {len(state.active_skills) if state.active_skills else 0}")
        self.console.print(f"  模型: {state.model.id if state.model else 'None'}")
        self.console.print(f"  流式状态: {'正在流式' if state.is_streaming else '空闲'}")
        
        if state.error:
            self.console.print(f"  [red]错误: {state.error}[/red]")
        
        if self.debug:
            self.console.print("\n[yellow]调试模式已启用[/yellow]")
            if self.tracer:
                self.console.print(f"  追踪ID: {self.tracer.trace_id}")
                self.console.print(f"  事件数: {len(self.tracer.events)}")
    
    async def _process_request(self, user_input: str) -> None:
        """处理用户请求"""

        from rich.live import Live
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.spinner import Spinner

        # 显示思考中提示
        with Live(
            Spinner("dots", text="思考中..."),
            console=self.console,
            refresh_per_second=10,
            transient=True
        ) as live:

            response_parts = []

            def on_event(event: AgentEvent) -> None:
                """收集 Agent 输出"""
                if event.type == AgentEventType.MESSAGE_UPDATE:
                    if hasattr(event, 'delta') and event.delta:
                        response_parts.append(event.delta)

                        # 更新显示
                        content = "".join(response_parts)
                        live.update(
                            Panel(
                                Markdown(content),
                                title="AI 助手",
                                border_style="blue"
                            )
                        )

                elif event.type == AgentEventType.TOOL_EXECUTION_START:
                    tool_name = getattr(event, 'tool_name', 'unknown')
                    live.update(
                        Spinner("dots", text=f"正在执行 {tool_name}...")
                    )

                elif event.type == AgentEventType.ERROR:
                    error_msg = getattr(event, 'error', '未知错误')
                    live.update(
                        Panel(
                            f"[red]错误: {error_msg}[/red]",
                            title="错误",
                            border_style="red"
                        )
                    )

            # 设置临时请求处理器
            self._request_handler = on_event

            # 发送提示
            try:
                await self.agent.prompt(user_input)
            except Exception as e:
                self.console.print(f"\n[red]处理请求失败: {e}[/red]")
                return
            finally:
                # 清理请求处理器
                self._request_handler = None

            # 显示完成消息
            if response_parts:
                content = "".join(response_parts)
                live.update(
                    Panel(
                        Markdown(content),
                        title="AI 助手",
                        border_style="green"
                    )
                )
    
    async def _on_agent_event(self, event: AgentEvent) -> None:
        """处理 Agent 事件（会话级别）"""
        # 如果有请求处理器，转发事件
        if self._request_handler:
            self._request_handler(event)
