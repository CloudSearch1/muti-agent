# PI-Python: Python 版 AI Agent 工具包设计文档

> 基于 pi-mono 架构设计，为 IntelliTeam 项目提供统一的 LLM API 和 Agent 运行时

---

## 1. 概述

### 1.1 目标

PI-Python 是一个 Python 版本的 AI Agent 工具包，借鉴 pi-mono 的优秀设计，为 IntelliTeam 项目提供：

- 统一的多提供商 LLM API
- 有状态的 Agent 运行时
- 工具调用生命周期管理
- 会话持久化和分支
- 扩展系统和技能系统

### 1.2 与 pi-mono 的对应关系

| pi-mono 包 | PI-Python 模块 | 说明 |
|-----------|---------------|------|
| @mariozechner/pi-ai | pi_python.ai | 统一 LLM API |
| @mariozechner/pi-agent-core | pi_python.agent | Agent 运行时 |
| @mariozechner/pi-coding-agent | pi_python.coding_agent | 编程助手 CLI |
| @mariozechner/pi-tui | pi_python.tui | 终端 UI 库 |
| @mariozechner/pi-web-ui | pi_python.web_ui | Web UI 组件 |
| - | pi_python.extensions | 扩展系统 |
| - | pi_python.skills | 技能系统 |

---

## 2. 包结构

```
pi_python/
├── __init__.py                 # 包入口
├── ai/                         # 统一 LLM API
│   ├── __init__.py
│   ├── types.py               # 核心类型定义
│   ├── stream.py              # 流式响应处理
│   ├── model.py               # 模型注册和发现
│   ├── context.py             # 上下文管理
│   └── providers/             # 提供商实现
│       ├── __init__.py
│       ├── base.py            # 基础提供商类
│       ├── openai.py          # OpenAI
│       ├── anthropic.py       # Anthropic Claude
│       ├── google.py          # Google Gemini
│       ├── azure.py           # Azure OpenAI
│       ├── bedrock.py         # AWS Bedrock
│       ├── mistral.py         # Mistral
│       ├── groq.py            # Groq
│       ├── openrouter.py      # OpenRouter
│       ├── bailian.py         # 阿里百炼
│       ├── ollama.py          # Ollama
│       ├── vllm.py            # vLLM
│       └── local.py           # 本地模型
├── agent/                      # Agent 运行时
│   ├── __init__.py
│   ├── agent.py               # Agent 类
│   ├── state.py               # 状态管理
│   ├── events.py              # 事件系统
│   ├── tools.py               # 工具定义
│   ├── executor.py            # 工具执行器
│   └── session.py             # 会话管理
├── coding_agent/               # 编程助手 CLI
│   ├── __init__.py
│   ├── cli.py                 # CLI 入口
│   ├── session.py             # 会话管理
│   └── commands.py            # 命令处理
├── tui/                        # 终端 UI 库
│   ├── __init__.py
│   ├── app.py                 # TUI 应用
│   ├── components/            # UI 组件
│   └── theme.py               # 主题配置
├── web_ui/                     # Web UI 组件
│   ├── __init__.py
│   ├── chat.py                # 聊天组件
│   └── storage.py             # 存储后端
├── extensions/                 # 扩展系统
│   ├── __init__.py
│   ├── api.py                 # 扩展 API
│   ├── loader.py              # 扩展加载器
│   └── builtin/               # 内置扩展
├── skills/                     # 技能系统
│   ├── __init__.py
│   ├── loader.py              # 技能加载器
│   └── registry.py            # 技能注册表
└── utils/                      # 工具函数
    ├── __init__.py
    ├── jsonl.py               # JSONL 持久化
    └── compression.py         # 上下文压缩
```

---

## 3. 核心模块设计

### 3.1 pi_python.ai - 统一 LLM API

#### 3.1.1 核心类型 (types.py)

```python
from __future__ import annotations
from typing import Literal, Union, Optional
from pydantic import BaseModel, Field
from enum import Enum

class ApiType(str, Enum):
    """已知 API 类型"""
    OPENAI_COMPLETIONS = "openai-completions"
    OPENAI_RESPONSES = "openai-responses"
    ANTHROPIC_MESSAGES = "anthropic-messages"
    GOOGLE_GENERATIVE_AI = "google-generative-ai"
    GOOGLE_VERTEX = "google-vertex"
    MISTRAL_CONVERSATIONS = "mistral-conversations"
    BEDROCK_CONVERSE_STREAM = "bedrock-converse-stream"
    CUSTOM = "custom"

class StopReason(str, Enum):
    """停止原因"""
    STOP = "stop"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    ABORTED = "aborted"

# 内容类型
class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ImageContent(BaseModel):
    type: Literal["image"] = "image"
    source: dict  # {type: "url"|"base64", media_type, data}

class ThinkingContent(BaseModel):
    type: Literal["thinking"] = "thinking"
    thinking: str

class ToolCall(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    input: dict

Content = Union[TextContent, ImageContent, ThinkingContent, ToolCall]

# 消息类型
class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: list[Content]
    timestamp: float = Field(default_factory=lambda: time.time())

class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: list[Content]
    timestamp: float = Field(default_factory=lambda: time.time())

class ToolResultMessage(BaseModel):
    role: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    content: list[Content]
    timestamp: float = Field(default_factory=lambda: time.time())

Message = Union[UserMessage, AssistantMessage, ToolResultMessage]

# 模型定义
class ModelCost(BaseModel):
    input: float = 0.0       # $/million tokens
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0

class Model(BaseModel):
    id: str
    name: str
    api: ApiType
    provider: str
    base_url: str
    reasoning: bool = False
    input_types: list[Literal["text", "image"]] = ["text"]
    cost: ModelCost = Field(default_factory=ModelCost)
    context_window: int = 4096
    max_tokens: int = 2048

# 工具定义
class ToolParameter(BaseModel):
    type: str
    description: Optional[str] = None
    enum: Optional[list[str]] = None

class Tool(BaseModel):
    name: str
    description: str
    parameters: dict[str, ToolParameter]
```

#### 3.1.2 流式 API (stream.py)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Optional
from asyncio import Queue
import asyncio

@dataclass
class AssistantMessageEvent:
    """流式事件类型"""
    type: str
    # text_delta
    content_index: Optional[int] = None
    delta: Optional[str] = None
    # tool_call
    tool_call: Optional[ToolCall] = None
    # done/error
    reason: Optional[StopReason] = None
    message: Optional[AssistantMessage] = None
    error: Optional[str] = None

class AssistantMessageEventStream:
    """流式事件流"""

    def __init__(self):
        self._queue: Queue[AssistantMessageEvent] = Queue()
        self._closed = False

    async def emit(self, event: AssistantMessageEvent) -> None:
        await self._queue.put(event)

    async def __aiter__(self) -> AsyncIterator[AssistantMessageEvent]:
        while True:
            event = await self._queue.get()
            yield event
            if event.type in ("done", "error"):
                break

    def close(self) -> None:
        self._closed = True

async def stream(
    model: Model,
    context: Context,
    options: Optional[StreamOptions] = None,
) -> AssistantMessageEventStream:
    """流式调用 LLM"""
    provider = get_provider(model.provider)
    return await provider.stream(model, context, options)

async def stream_simple(
    model: Model,
    context: Context,
    options: Optional[StreamOptions] = None,
    reasoning: str = "off",
    thinking_budgets: Optional[dict[str, int]] = None,
) -> AssistantMessageEventStream:
    """简化流式调用（带推理支持）"""
    # 处理 reasoning/thinking 配置
    ...
```

#### 3.1.3 上下文管理 (context.py)

```python
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional

class Context(BaseModel):
    """LLM 调用上下文"""
    system_prompt: Optional[str] = None
    messages: list[Message] = []
    tools: list[Tool] = []

    class Config:
        arbitrary_types_allowed = True

    def add_user_message(self, content: str | list[Content]) -> None:
        """添加用户消息"""
        if isinstance(content, str):
            content = [TextContent(text=content)]
        self.messages.append(UserMessage(content=content))

    def add_assistant_message(self, content: list[Content]) -> None:
        """添加助手消息"""
        self.messages.append(AssistantMessage(content=content))

    def add_tool_result(self, tool_call_id: str, content: list[Content]) -> None:
        """添加工具结果"""
        self.messages.append(ToolResultMessage(
            tool_call_id=tool_call_id,
            content=content
        ))

    def to_provider_format(self, api_type: ApiType) -> dict:
        """转换为提供商特定格式"""
        ...
```

### 3.2 pi_python.agent - Agent 运行时

#### 3.2.1 Agent 类 (agent.py)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional, Awaitable
from asyncio import Queue
import asyncio

@dataclass
class AgentState:
    """Agent 状态"""
    system_prompt: str
    model: Model
    thinking_level: str = "off"  # off, low, medium, high
    tools: list[AgentTool] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    is_streaming: bool = False
    stream_message: Optional[AssistantMessage] = None
    pending_tool_calls: set[str] = field(default_factory=set)
    error: Optional[str] = None

class Agent:
    """有状态的 Agent"""

    def __init__(
        self,
        initial_state: AgentState,
        convert_to_llm: Optional[Callable] = None,
        transform_context: Optional[Callable] = None,
        steering_mode: str = "one-at-a-time",
        follow_up_mode: str = "one-at-a-time",
    ):
        self.state = initial_state
        self._convert_to_llm = convert_to_llm
        self._transform_context = transform_context
        self._steering_mode = steering_mode
        self._follow_up_mode = follow_up_mode
        self._subscribers: list[Callable] = []
        self._steering_queue: Queue[UserMessage] = Queue()
        self._follow_up_queue: Queue[UserMessage] = Queue()

    def subscribe(self, callback: Callable[[AgentEvent], Awaitable[None]]) -> None:
        """订阅 Agent 事件"""
        self._subscribers.append(callback)

    async def _emit(self, event: AgentEvent) -> None:
        """发射事件"""
        for callback in self._subscribers:
            await callback(event)

    async def prompt(self, content: str | list[Content]) -> None:
        """发送提示"""
        await self._emit(AgentEvent(type="agent_start"))

        # 添加用户消息
        user_msg = UserMessage(
            content=content if isinstance(content, list) else [TextContent(text=content)]
        )

        await self._emit(AgentEvent(type="turn_start"))
        await self._emit(AgentEvent(type="message_start", message=user_msg))

        # 添加到状态
        self.state.messages.append(user_msg)

        # 构建上下文
        context = Context(
            system_prompt=self.state.system_prompt,
            messages=self._convert_messages(),
            tools=[t.to_tool() for t in self.state.tools]
        )

        # 调用 LLM
        stream = await stream_simple(
            self.state.model,
            context,
            reasoning=self.state.thinking_level
        )

        async for event in stream:
            await self._handle_stream_event(event)

        await self._emit(AgentEvent(type="turn_end"))
        await self._emit(AgentEvent(type="agent_end"))

    async def steer(self, message: UserMessage) -> None:
        """发送 Steering 消息（中断工具执行）"""
        await self._steering_queue.put(message)

    async def follow_up(self, message: UserMessage) -> None:
        """发送 Follow-up 消息（Agent 完成后执行）"""
        await self._follow_up_queue.put(message)

    def set_tools(self, tools: list[AgentTool]) -> None:
        """设置工具"""
        self.state.tools = tools

    async def _handle_stream_event(self, event: AssistantMessageEvent) -> None:
        """处理流式事件"""
        if event.type == "tool_call":
            await self._execute_tool(event.tool_call)
        elif event.type == "text_delta":
            await self._emit(AgentEvent(
                type="message_update",
                delta=event.delta
            ))
        elif event.type == "done":
            # 检查是否有 follow-up
            if not self._follow_up_queue.empty():
                follow_up = await self._follow_up_queue.get()
                await self.prompt(follow_up.content)

    async def _execute_tool(self, tool_call: ToolCall) -> None:
        """执行工具"""
        tool = next((t for t in self.state.tools if t.name == tool_call.name), None)
        if not tool:
            return

        await self._emit(AgentEvent(
            type="tool_execution_start",
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            args=tool_call.input
        ))

        result = await tool.execute(tool_call.id, tool_call.input)

        await self._emit(AgentEvent(
            type="tool_execution_end",
            tool_call_id=tool_call.id,
            result=result
        ))
```

#### 3.2.2 工具定义 (tools.py)

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Optional, Awaitable
from pydantic import BaseModel
import asyncio

class ToolResult(BaseModel):
    """工具执行结果"""
    content: list[Content]
    details: dict = {}

class AgentTool(ABC):
    """Agent 工具基类"""

    name: str
    label: str
    description: str
    parameters: dict

    @abstractmethod
    async def execute(
        self,
        tool_call_id: str,
        params: dict,
        signal: Optional[asyncio.CancelledError] = None,
        on_update: Optional[Callable] = None,
        context: Optional[dict] = None,
    ) -> ToolResult:
        """执行工具"""
        pass

    def to_tool(self) -> Tool:
        """转换为 LLM 工具定义"""
        return Tool(
            name=self.name,
            description=self.description,
            parameters=self.parameters
        )

# 便捷函数
def tool(
    name: str,
    description: str,
    parameters: dict,
):
    """装饰器：将函数转换为工具"""
    def decorator(func: Callable) -> AgentTool:
        class FunctionTool(AgentTool):
            def __init__(self):
                self.name = name
                self.label = name
                self.description = description
                self.parameters = parameters

            async def execute(self, tool_call_id, params, signal=None, on_update=None, context=None):
                result = await func(**params)
                if isinstance(result, ToolResult):
                    return result
                return ToolResult(content=[TextContent(text=str(result))])

        return FunctionTool()
    return decorator

# 示例：Bash 工具
class BashTool(AgentTool):
    name = "bash"
    label = "Bash"
    description = "Execute a bash command"
    parameters = {
        "command": {"type": "string", "description": "Command to execute"},
        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
    }

    async def execute(self, tool_call_id, params, signal=None, on_update=None, context=None):
        import asyncio

        command = params["command"]
        timeout = params.get("timeout", 30)

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode() + stderr.decode()

            return ToolResult(
                content=[TextContent(text=output)],
                details={"exit_code": proc.returncode}
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ToolResult(
                content=[TextContent(text=f"Command timed out after {timeout}s")],
                details={"exit_code": -1, "timeout": True}
            )
```

#### 3.2.3 事件系统 (events.py)

```python
from dataclasses import dataclass
from typing import Optional, Union
from enum import Enum

class AgentEventType(str, Enum):
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    MESSAGE_START = "message_start"
    MESSAGE_UPDATE = "message_update"
    MESSAGE_END = "message_end"
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_END = "tool_execution_end"
    ERROR = "error"

@dataclass
class AgentEvent:
    """Agent 事件"""
    type: AgentEventType
    message: Optional[Message] = None
    delta: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    args: Optional[dict] = None
    result: Optional[ToolResult] = None
    error: Optional[str] = None
```

#### 3.2.4 会话管理 (session.py)

```python
from __future__ import annotations
from pathlib import Path
from typing import Optional, Iterator
from datetime import datetime
import json

class Session:
    """Agent 会话"""

    def __init__(self, path: Optional[Path] = None):
        self.path = path
        self.messages: list[Message] = []
        self.metadata: dict = {}
        self._branches: dict[str, Session] = {}

    def save(self) -> None:
        """保存会话到 JSONL 文件"""
        if not self.path:
            return

        with open(self.path, "w") as f:
            # 写入元数据
            f.write(json.dumps({"type": "metadata", "data": self.metadata}) + "\n")
            # 写入消息
            for msg in self.messages:
                f.write(json.dumps({"type": "message", "data": msg.dict()}) + "\n")

    @classmethod
    def load(cls, path: Path) -> Session:
        """从 JSONL 文件加载会话"""
        session = cls(path)

        with open(path, "r") as f:
            for line in f:
                entry = json.loads(line)
                if entry["type"] == "metadata":
                    session.metadata = entry["data"]
                elif entry["type"] == "message":
                    session.messages.append(parse_message(entry["data"]))

        return session

    def branch(self, from_index: int, name: str) -> Session:
        """从指定点创建分支"""
        branch = Session()
        branch.messages = self.messages[:from_index].copy()
        branch.metadata = {"parent": str(self.path), "branch_point": from_index, "name": name}
        self._branches[name] = branch
        return branch

    def compress(self, max_messages: int = 50) -> None:
        """压缩旧消息"""
        if len(self.messages) <= max_messages:
            return

        # 保留系统消息和最近的 N 条消息
        system_messages = [m for m in self.messages if m.role == "system"]
        recent_messages = self.messages[-(max_messages - len(system_messages)):]

        self.messages = system_messages + recent_messages
```

### 3.3 pi_python.extensions - 扩展系统

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Optional, Any
from dataclasses import dataclass
import importlib.util
from pathlib import Path

@dataclass
class ExtensionContext:
    """扩展上下文"""
    ui: Any  # UI 接口
    agent: Agent
    session: Session

class ExtensionAPI:
    """扩展 API"""

    def __init__(self, agent: Agent, context: ExtensionContext):
        self._agent = agent
        self._context = context
        self._handlers: dict[str, list[Callable]] = {}

    def on(self, event: str, handler: Callable) -> None:
        """注册事件处理器"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    async def emit(self, event: str, data: Any) -> list[Any]:
        """发射事件"""
        results = []
        for handler in self._handlers.get(event, []):
            result = await handler(data, self._context)
            results.append(result)
        return results

    def register_tool(self, tool: AgentTool) -> None:
        """注册工具"""
        self._agent.state.tools.append(tool)

    def register_command(self, name: str, handler: Callable) -> None:
        """注册命令"""
        ...

class ExtensionLoader:
    """扩展加载器"""

    def __init__(self, extensions_dir: Path):
        self.extensions_dir = extensions_dir

    def discover(self) -> list[Path]:
        """发现扩展"""
        return list(self.extensions_dir.glob("*.py"))

    def load(self, path: Path, api: ExtensionAPI) -> None:
        """加载扩展"""
        spec = importlib.util.spec_from_file_location("extension", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 调用扩展入口函数
        if hasattr(module, "extension"):
            module.extension(api)
```

### 3.4 pi_python.skills - 技能系统

```python
from __future__ import annotations
from pathlib import Path
from typing import Optional
import re

@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str
    triggers: list[str]
    steps: list[str]
    examples: list[str]
    path: Path

class SkillLoader:
    """技能加载器 - 支持 Agent Skills 标准"""

    @classmethod
    def load(cls, path: Path) -> Skill:
        """从 Markdown 文件加载技能"""
        content = path.read_text()

        # 解析 Markdown
        name = cls._extract_title(content)
        description = cls._extract_section(content, "描述") or cls._extract_section(content, "Description")
        triggers = cls._extract_list(content, "触发") or cls._extract_list(content, "Triggers")
        steps = cls._extract_list(content, "步骤") or cls._extract_list(content, "Steps")
        examples = cls._extract_list(content, "示例") or cls._extract_list(content, "Examples")

        return Skill(
            name=name,
            description=description,
            triggers=triggers,
            steps=steps,
            examples=examples,
            path=path
        )

    @staticmethod
    def _extract_title(content: str) -> str:
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return match.group(1) if match else "Unknown"

    @staticmethod
    def _extract_section(content: str, heading: str) -> Optional[str]:
        pattern = rf"^##\s+{heading}\s*\n(.+?)(?=\n##|\Z)"
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_list(content: str, heading: str) -> list[str]:
        section = SkillLoader._extract_section(content, heading)
        if not section:
            return []

        items = []
        for line in section.split("\n"):
            match = re.match(r"^\d+\.\s+(.+)$", line)
            if match:
                items.append(match.group(1))
        return items

class SkillRegistry:
    """技能注册表"""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def find_matching(self, text: str) -> list[Skill]:
        """查找匹配的技能"""
        matches = []
        for skill in self._skills.values():
            for trigger in skill.triggers:
                if trigger.lower() in text.lower():
                    matches.append(skill)
                    break
        return matches

    def to_system_prompt(self) -> str:
        """生成技能系统提示"""
        if not self._skills:
            return ""

        prompt = "你可以使用以下技能:\n\n"
        for skill in self._skills.values():
            prompt += f"### {skill.name}\n"
            prompt += f"{skill.description}\n\n"
            if skill.steps:
                prompt += "步骤:\n"
                for i, step in enumerate(skill.steps, 1):
                    prompt += f"{i}. {step}\n"
                prompt += "\n"

        return prompt
```

---

## 4. 与现有系统集成

### 4.1 迁移路径

```
Phase 1: 替换 LLM 层
├── 保留 src/llm/ 的接口
├── 使用 pi_python.ai 作为底层实现
└── 适配器模式保持向后兼容

Phase 2: 增强 Agent 层
├── 使用 pi_python.agent 替换 src/agents/
├── 保留任务调度逻辑
└── 集成工具系统

Phase 3: 添加扩展能力
├── 实现 pi_python.extensions
├── 实现 pi_python.skills
└── 提供配置化扩展点
```

### 4.2 适配器示例

```python
# src/llm/llm_provider.py 适配器

from pi_python.ai import stream, Context, TextContent, get_model
from pi_python.ai.types import AssistantMessageEvent

class LLMProviderAdapter(BaseProvider):
    """适配器：将 pi_python.ai 适配到现有接口"""

    def __init__(self, provider: str, model: str):
        self.model = get_model(provider, model)

    async def generate(self, prompt: str, **kwargs) -> str:
        context = Context()
        context.add_user_message(prompt)

        result = []
        async for event in stream(self.model, context):
            if event.type == "text_delta":
                result.append(event.delta)
            elif event.type == "done":
                return "".join(result)

        return "".join(result)

    async def generate_stream(self, prompt: str, **kwargs):
        context = Context()
        context.add_user_message(prompt)

        async for event in stream(self.model, context):
            if event.type == "text_delta":
                yield event.delta
```

### 4.3 配置集成

```yaml
# config/llm.yaml
pi_python:
  providers:
    - name: openai
      api_key: ${OPENAI_API_KEY}
      models:
        - id: gpt-4o
          name: GPT-4o
          context_window: 128000
          max_tokens: 4096
          cost:
            input: 2.5
            output: 10.0

    - name: anthropic
      api_key: ${ANTHROPIC_API_KEY}
      models:
        - id: claude-sonnet-4-20250514
          name: Claude Sonnet 4
          context_window: 200000
          max_tokens: 8192
          reasoning: true

  default: openai/gpt-4o

  extensions:
    enabled: true
    path: ./extensions

  skills:
    enabled: true
    path: ./skills
```

---

## 5. API 示例

### 5.1 基础 LLM 调用

```python
from pi_python.ai import get_model, stream, Context

# 获取模型
model = get_model("anthropic", "claude-sonnet-4-20250514")

# 创建上下文
context = Context(
    system_prompt="You are a helpful assistant."
)
context.add_user_message("Hello!")

# 流式调用
async for event in stream(model, context):
    if event.type == "text_delta":
        print(event.delta, end="", flush=True)
    elif event.type == "done":
        print()  # newline
```

### 5.2 使用 Agent

```python
from pi_python.agent import Agent, AgentState
from pi_python.agent.tools import BashTool
from pi_python.ai import get_model

# 创建 Agent
agent = Agent(
    initial_state=AgentState(
        system_prompt="You are a coding assistant.",
        model=get_model("anthropic", "claude-sonnet-4-20250514"),
        tools=[BashTool()],
        messages=[]
    )
)

# 订阅事件
async def on_event(event):
    if event.type == "message_update":
        print(event.delta, end="", flush=True)
    elif event.type == "tool_execution_start":
        print(f"\n[Tool: {event.tool_name}]")

agent.subscribe(on_event)

# 发送提示
await agent.prompt("List files in current directory")
```

### 5.3 创建扩展

```python
# extensions/permission.py

def extension(pi):
    """权限控制扩展"""

    protected_paths = [".env", "credentials.json"]

    @pi.on("tool_call")
    async def on_tool_call(event, ctx):
        if event.tool_name in ("write", "edit"):
            path = event.args.get("path", "")
            for protected in protected_paths:
                if protected in path:
                    ok = await ctx.ui.confirm(
                        "Protected File",
                        f"Allow write to {path}?"
                    )
                    if not ok:
                        return {"block": True, "reason": "Protected path"}

    @pi.register_tool
    class GreetTool(AgentTool):
        name = "greet"
        description = "Greet someone"
        parameters = {
            "name": {"type": "string", "description": "Name to greet"}
        }

        async def execute(self, tool_call_id, params, **kwargs):
            return ToolResult(
                content=[TextContent(text=f"Hello, {params['name']}!")]
            )
```

### 5.4 创建技能

```markdown
# skills/code-review/SKILL.md

# Code Review

代码审查技能，用于审查代码变更并提供反馈。

## 触发

- 当用户请求代码审查
- 当用户说 "review this code"
- 当用户提供代码片段

## 步骤

1. 阅读提供的代码变更
2. 分析代码质量和潜在问题
3. 检查是否有安全漏洞
4. 提供改进建议
5. 生成审查报告

## 示例

- 用户: "请审查这段代码..."
- 用户: "Review PR #123"
```

---

## 6. 实现计划

### Phase 1: 核心框架 (1-2 周)

- [ ] 实现 `pi_python.ai.types` 核心类型
- [ ] 实现 `pi_python.ai.context` 上下文管理
- [ ] 实现 `pi_python.ai.stream` 流式 API
- [ ] 实现 OpenAI 和 Anthropic 提供商
- [ ] 单元测试

### Phase 2: Agent 运行时 (1-2 周)

- [ ] 实现 `pi_python.agent.agent` Agent 类
- [ ] 实现 `pi_python.agent.events` 事件系统
- [ ] 实现 `pi_python.agent.tools` 工具系统
- [ ] 实现 `pi_python.agent.session` 会话管理
- [ ] 集成测试

### Phase 3: 扩展系统 (1 周)

- [ ] 实现 `pi_python.extensions` 扩展 API
- [ ] 实现 `pi_python.skills` 技能系统
- [ ] 实现内置扩展
- [ ] 文档

### Phase 4: 集成迁移 (1 周)

- [ ] 实现 LLM 层适配器
- [ ] 迁移现有提供商
- [ ] 性能测试
- [ ] 文档完善

---

## 7. 技术栈

| 组件 | 技术选型 |
|-----|---------|
| 异步运行时 | asyncio |
| HTTP 客户端 | httpx (异步) |
| 数据验证 | pydantic v2 |
| CLI | typer + rich |
| 配置 | pyyaml + pydantic-settings |
| 测试 | pytest + pytest-asyncio |
| 日志 | structlog |

---

## 8. 参考资料

- [pi-mono 仓库](https://github.com/badlogic/pi-mono)
- [Agent Skills 标准](https://agentskills.io)
- [Anthropic API 文档](https://docs.anthropic.com)
- [OpenAI API 文档](https://platform.openai.com/docs)

---

*文档版本: 1.0.0*
*创建时间: 2026-03-11*
*作者: OpenClaw Team*