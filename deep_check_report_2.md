# 深度代码逻辑检查报告 - 第二回合

**检查日期**: 2026-03-15
**检查范围**: 消息处理、资源管理、并发机制、异常处理、数据一致性、边界条件、安全性
**代码版本**: 基于 main 分支最新提交

---

## 目录

1. [消息处理与事件流](#1-消息处理与事件流)
2. [资源管理与清理](#2-资源管理与清理)
3. [并发与锁机制](#3-并发与锁机制)
4. [异常传播与恢复](#4-异常传播与恢复)
5. [数据一致性](#5-数据一致性)
6. [边界条件](#6-边界条件)
7. [安全性](#7-安全性)
8. [总结与优先级](#8-总结与优先级)

---

## 1. 消息处理与事件流

### 问题 1.1: Agent 事件订阅者错误被静默忽略

**文件**: `pi_python/agent/agent.py:121-125`

**问题描述**:
事件发射时，如果订阅者回调抛出异常，异常被静默忽略，没有任何日志记录。这可能导致问题难以调试。

```python
async def _emit(self, event: AgentEvent) -> None:
    """发射事件"""
    for callback in self._subscribers:
        try:
            await callback(event)
        except Exception:
            pass  # 忽略订阅者错误
```

**触发条件**: 订阅者回调函数内部抛出异常

**可能的影响**:
- 关键错误被隐藏
- 调试困难
- 订阅者失败不影响其他订阅者，但也无法追踪问题

**修复建议**:
```python
async def _emit(self, event: AgentEvent) -> None:
    """发射事件"""
    for callback in self._subscribers:
        try:
            await callback(event)
        except Exception as e:
            logger.warning(
                "Event callback failed",
                callback=callback.__name__,
                event_type=event.type.value,
                error=str(e),
            )
```

**优先级**: 中

---

### 问题 1.2: EventBus 取消订阅时竞态条件

**文件**: `webui/event_bus.py:86-98`

**问题描述**:
取消订阅时，先获取锁再移除回调，但如果回调正在执行中，可能导致问题。`remove()` 操作在回调不存在时静默失败。

```python
async def unsubscribe(
    self,
    event_type: str,
    callback: Callable,
):
    """取消订阅"""
    async with self._lock:
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from {event_type}")
            except ValueError:
                pass
```

**触发条件**:
- 高并发场景下，回调正在执行时取消订阅
- 多个协程同时订阅/取消订阅同一事件类型

**可能的影响**:
- 回调在取消后仍可能被调用
- 潜在的内存泄漏（回调未被正确移除）

**修复建议**:
```python
async def unsubscribe(
    self,
    event_type: str,
    callback: Callable,
):
    """取消订阅"""
    async with self._lock:
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]
                logger.debug(f"Unsubscribed from {event_type}")
            except ValueError:
                logger.debug(f"Callback not found for {event_type}")
```

**优先级**: 低

---

### 问题 1.3: Steering Queue 非阻塞 put 可能导致消息丢失

**文件**: `pi_python/agent/agent.py:374`

**问题描述**:
`steer()` 方法使用 `put_nowait()` 向队列添加消息，如果队列已满（默认无界，但用户可能设置大小限制），消息将被静默丢弃。

```python
def steer(self, message: Message) -> None:
    """
    发送 Steering 消息
    """
    self._steering_queue.put_nowait(message)
```

**触发条件**:
- 队列设置了最大大小
- 高频率 steering 消息场景

**可能的影响**:
- 关键 steering 指令丢失
- Agent 行为不符合预期

**修复建议**:
```python
def steer(self, message: Message) -> bool:
    """
    发送 Steering 消息

    Returns:
        是否成功添加到队列
    """
    try:
        self._steering_queue.put_nowait(message)
        return True
    except asyncio.QueueFull:
        logger.warning("Steering queue full, message dropped")
        return False
```

**优先级**: 中

---

## 2. 资源管理与清理

### 问题 2.1: 进程会话管理器内存泄漏风险

**文件**: `src/tools/builtin/exec.py:111-117`

**问题描述**:
`ProcessSessionManager` 使用单例模式，`_sessions` 字典持续增长。如果后台进程完成但会话未被清理，会导致内存泄漏。

```python
class ProcessSessionManager:
    _instance: Optional["ProcessSessionManager"] = None
    _sessions: dict[str, ProcessSession] = {}

    def __new__(cls) -> "ProcessSessionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

**触发条件**:
- 大量后台进程执行
- 进程完成后未调用 `remove_session`
- Agent 销毁时未清理其会话

**可能的影响**:
- 内存持续增长
- 进程对象无法被垃圾回收

**修复建议**:
1. 添加自动清理机制：
```python
async def _cleanup_finished_sessions(self):
    """定期清理已完成的会话"""
    while True:
        await asyncio.sleep(300)  # 每5分钟清理一次
        finished = [
            sid for sid, s in self._sessions.items()
            if s.status in ("completed", "failed")
        ]
        for sid in finished:
            await self.remove_session(sid)
```

2. 添加会话过期机制：
```python
class ProcessSession(BaseModel):
    # ... 现有字段
    expires_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now() + timedelta(hours=24)
    )
```

**优先级**: 高

---

### 问题 2.2: Redis 连接未正确关闭

**文件**: `webui/app.py:373-376`

**问题描述**:
`ResponseCache.close()` 方法中，Redis 连接关闭时未处理可能的异常。

```python
async def close(self):
    """关闭连接"""
    if self._redis:
        await self._redis.close()
```

**触发条件**: Redis 连接已断开或出现网络问题

**可能的影响**:
- 关闭时的异常可能导致应用无法正常关闭
- 资源未完全释放

**修复建议**:
```python
async def close(self):
    """关闭连接"""
    if self._redis:
        try:
            await self._redis.close()
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")
        finally:
            self._redis = None
```

**优先级**: 中

---

### 问题 2.3: 文件句柄可能在异常时未关闭

**文件**: `webui/app.py:600-604`

**问题描述**:
在 `_load_skills_from_files()` 中，如果 `yaml.safe_load()` 或后续操作抛出异常，文件句柄可能不会关闭。

```python
for file_path in SKILLS_DIR.glob("*.md"):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter = _parse_yaml_frontmatter(content)
        # ... 后续操作可能抛出异常
```

**修复建议**: 已使用 `with` 语句，文件读取部分是安全的。但需要确保后续操作在 try-except 块内。

**优先级**: 低（当前代码已正确处理）

---

### 问题 2.4: Session 文件保存时可能数据丢失

**文件**: `pi_python/agent/session.py:53-72`

**问题描述**:
`Session.save()` 方法在写入文件时，如果中途失败，可能导致部分写入或文件损坏。

```python
def save(self) -> None:
    """保存会话到 JSONL 文件"""
    if not self.path:
        return

    self.path.parent.mkdir(parents=True, exist_ok=True)

    with open(self.path, "w", encoding="utf-8") as f:
        # 写入元数据
        f.write(json.dumps({...}, ensure_ascii=False) + "\n")
        # 写入消息
        for msg in self.messages:
            f.write(json.dumps({...}, ensure_ascii=False) + "\n")
```

**触发条件**:
- 磁盘空间不足
- 写入过程中断（进程被杀死、断电等）

**可能的影响**:
- 会话数据丢失或损坏
- 无法恢复会话

**修复建议**:
```python
def save(self) -> None:
    """保存会话到 JSONL 文件（原子写入）"""
    if not self.path:
        return

    self.path.parent.mkdir(parents=True, exist_ok=True)

    # 先写入临时文件
    temp_path = self.path.with_suffix('.tmp')
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "type": "metadata",
                "data": self.metadata
            }, ensure_ascii=False) + "\n")

            for msg in self.messages:
                f.write(json.dumps({
                    "type": "message",
                    "data": msg.model_dump()
                }, ensure_ascii=False) + "\n")

        # 原子性地重命名
        temp_path.replace(self.path)
    except Exception as e:
        # 清理临时文件
        if temp_path.exists():
            temp_path.unlink()
        raise
```

**优先级**: 高

---

## 3. 并发与锁机制

### 问题 3.1: Agent 状态非原子更新

**文件**: `src/core/models.py:183-187`

**问题描述**:
`Agent.assign_task()` 方法中，多个字段更新不是原子操作。在多线程/协程环境中可能导致不一致状态。

```python
def assign_task(self, task_id: str) -> None:
    """分配任务"""
    self.current_task_id = task_id
    self.state = AgentState.BUSY
    self.updated_at = datetime.now()
```

**触发条件**:
- 多个协程同时操作同一 Agent
- 在状态更新过程中被中断

**可能的影响**:
- Agent 状态不一致（如 state=BUSY 但 current_task_id=None）
- 统计数据不准确

**修复建议**:
对于 Pydantic 模型，建议使用外部锁保护关键操作：
```python
from threading import Lock

class Agent(BaseModel):
    _lock: Lock = PrivateAttr(default_factory=Lock)

    def assign_task(self, task_id: str) -> None:
        with self._lock:
            self.current_task_id = task_id
            self.state = AgentState.BUSY
            self.updated_at = datetime.now()
```

**优先级**: 中

---

### 问题 3.2: 全局状态变量竞态条件

**文件**: `webui/app.py:961-962`

**问题描述**:
`delete_task()` 使用全局变量 `TASKS_DATA`，在多线程环境中可能导致竞态条件。

```python
@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: int):
    """删除任务"""
    global TASKS_DATA
    TASKS_DATA = [t for t in TASKS_DATA if t["id"] != task_id]
```

**触发条件**:
- 多个请求同时删除不同任务
- 一个请求在删除时，另一个请求在读取

**可能的影响**:
- 数据不一致
- 任务丢失或重复

**修复建议**:
使用异步锁保护共享状态：
```python
import asyncio

_tasks_lock = asyncio.Lock()

@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: int):
    """删除任务"""
    global TASKS_DATA
    async with _tasks_lock:
        TASKS_DATA = [t for t in TASKS_DATA if t["id"] != task_id]
    # ...
```

**优先级**: 中

---

### 问题 3.3: 死锁风险 - 安全检查器中同步调用异步代码

**文件**: `src/tools/security.py:710-715`

**问题描述**:
`validate_session_access()` 方法在同步方法中使用 `run_until_complete()` 调用异步代码，这在已有事件循环的环境中会失败或导致死锁。

```python
def validate_session_access(
    self,
    session_id: str,
    agent_id: str,
    session_manager: "SessionManager",
) -> "SessionInfo":
    import asyncio
    session = asyncio.get_event_loop().run_until_complete(
        session_manager.get_session(session_id)
    )
```

**触发条件**: 在异步上下文中调用此同步方法

**可能的影响**:
- RuntimeError: This event loop is already running
- 死锁

**修复建议**:
只保留异步版本 `validate_session_access_async()`，移除同步版本或在同步版本中抛出弃用警告。

**优先级**: 高

---

## 4. 异常传播与恢复

### 问题 4.1: LLM 调用失败后无重试机制

**文件**: `webui/app.py:1810-1888`

**问题描述**:
`_call_llm_with_tools()` 在 LLM 调用失败时直接返回 `None`，没有重试机制。

```python
async def _call_llm_with_tools(...) -> dict | None:
    try:
        # ... 调用 LLM
    except Exception as e:
        logger.error(f"[Agent] LLM 调用异常: {e}")
        return None
```

**触发条件**:
- 网络超时
- API 限流
- 临时服务不可用

**可能的影响**:
- 临时性故障导致任务失败
- 用户体验差

**修复建议**:
```python
import tenacity

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
    retry=tenacity.retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
)
async def _call_llm_with_tools(...) -> dict | None:
    # ...
```

**优先级**: 中

---

### 问题 4.2: 工具执行异常未区分可恢复与不可恢复错误

**文件**: `pi_python/agent/agent.py:346-357`

**问题描述**:
工具执行失败时，所有异常都被同等处理，没有区分临时性错误（可重试）和永久性错误。

```python
except Exception as e:
    # 工具执行失败
    error_result = ToolResultMessage(
        tool_call_id=tool_call.id,
        content=[TextContent(text=f"Error: {str(e)}")]
    )
    self.state.messages.append(error_result)
```

**修复建议**:
定义可重试异常类型：
```python
class RetryableToolError(Exception):
    """可重试的工具错误"""
    pass

# 在执行时：
except RetryableToolError as e:
    # 重试逻辑
    pass
except Exception as e:
    # 永久性错误
    pass
```

**优先级**: 低

---

### 问题 4.3: 数据库初始化失败后的降级模式不完整

**文件**: `webui/app.py:101-109`

**问题描述**:
数据库初始化失败后降级到内存模式，但聊天历史等功能仍然尝试使用数据库。

```python
if DATABASE_ENABLED:
    try:
        from src.db.database import init_database
        await init_database()
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        logger.warning("降级到内存模式")
        DATABASE_ENABLED = False
```

**触发条件**: 数据库连接失败

**可能的影响**:
- 某些功能在降级模式下不可用但没有提示
- 数据丢失风险

**修复建议**:
在降级模式下明确告知用户限制，并禁用依赖数据库的功能。

**优先级**: 中

---

## 5. 数据一致性

### 问题 5.1: 缓存与实际数据不同步

**文件**: `webui/app.py:869-876`

**问题描述**:
`get_agents()` 端点在返回数据前随机修改 Agent 状态，这会影响全局数据状态，且缓存不感知此修改。

```python
@app.get("/api/v1/agents")
async def get_agents():
    """获取 Agent 列表"""
    # 随机更新一些 Agent 状态，模拟实时变化
    for agent in AGENTS_DATA:
        if random.random() < 0.1:
            agent["status"] = "busy" if agent["status"] == "idle" else "idle"
    return AGENTS_DATA
```

**触发条件**: 每次调用获取 Agent 列表

**可能的影响**:
- 状态变化不可预测
- 缓存数据与实际数据不一致
- 影响其他依赖此状态的逻辑

**修复建议**:
模拟状态变化应该基于实际事件或定时器，而不是在读取时随机修改。

**优先级**: 低（这是模拟代码，生产环境应移除）

---

### 问题 5.2: 技能文件与内存数据不同步

**文件**: `webui/app.py:1024-1029`

**问题描述**:
创建技能时，先保存文件再添加到内存列表。如果内存添加失败，文件已存在但内存中没有。

```python
try:
    _save_skill_to_file(new_skill)
    SKILLS_DATA.append(new_skill)
    logger.info(f"create_skill: 技能创建成功")
```

**修复建议**:
先验证再保存，或使用事务模式：
```python
# 方案1: 先验证，后保存
# 验证名称唯一性已在前面完成
SKILLS_DATA.append(new_skill)  # 先添加到内存
try:
    _save_skill_to_file(new_skill)
except Exception as e:
    SKILLS_DATA.pop()  # 回滚内存操作
    raise
```

**优先级**: 中

---

### 问题 5.3: Task 状态转换无验证

**文件**: `src/core/models.py:264-275`

**问题描述**:
任务状态转换没有验证转换合法性。例如，`COMPLETED` 状态的任务可以再次调用 `start()`。

```python
def start(self) -> None:
    """开始任务"""
    self.status = TaskStatus.IN_PROGRESS
    self.started_at = datetime.now()

def complete(self, output_data: dict[str, Any] = None) -> None:
    """完成任务"""
    self.status = TaskStatus.COMPLETED
    self.completed_at = datetime.now()
```

**触发条件**: 在非预期状态下调用状态转换方法

**可能的影响**:
- 任务状态不一致
- 统计数据错误

**修复建议**:
```python
# 定义合法的状态转换
VALID_TRANSITIONS = {
    TaskStatus.PENDING: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
    TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PENDING],
    TaskStatus.FAILED: [TaskStatus.PENDING],  # 允许重试
    TaskStatus.COMPLETED: [],  # 终态
    TaskStatus.CANCELLED: [],  # 终态
}

def start(self) -> None:
    """开始任务"""
    if self.status not in [TaskStatus.PENDING]:
        raise ValueError(f"Cannot start task in {self.status} state")
    self.status = TaskStatus.IN_PROGRESS
    self.started_at = datetime.now()
```

**优先级**: 中

---

## 6. 边界条件

### 问题 6.1: 无限循环防护 - Agent 最大迭代次数

**文件**: `pi_python/agent/agent.py:173-175`

**问题描述**:
Agent 主循环有 `max_iterations = 50` 限制，但没有可配置方式，也没有日志记录达到限制的情况。

```python
async def _run_loop(self) -> None:
    """运行主循环"""
    max_iterations = 50  # 防止无限循环

    for _ in range(max_iterations):
```

**触发条件**:
- LLM 持续返回工具调用
- 任务复杂度高，需要多轮交互

**可能的影响**:
- 任务在未完成时被截断
- 无警告信息

**修复建议**:
```python
async def _run_loop(self) -> None:
    """运行主循环"""
    max_iterations = self.state.max_iterations or 50

    for iteration in range(max_iterations):
        # ...

    if iteration == max_iterations - 1:
        logger.warning(
            "Agent reached max iterations",
            max_iterations=max_iterations,
        )
        await self._emit(AgentEvent(
            type=AgentEventType.ERROR,
            error=f"Reached maximum iterations ({max_iterations})"
        ))
```

**优先级**: 中

---

### 问题 6.2: 工具参数缺失时的默认值处理

**文件**: `webui/app.py:1691-1693`

**问题描述**:
工具参数 JSON 解析失败时，使用空字典作为默认值，可能导致工具执行失败。

```python
try:
    function_args = json.loads(function_args_str)
except json.JSONDecodeError:
    function_args = {}
```

**触发条件**: LLM 返回格式错误的工具参数

**可能的影响**:
- 工具使用错误参数执行
- 难以调试

**修复建议**:
```python
try:
    function_args = json.loads(function_args_str)
except json.JSONDecodeError as e:
    logger.error(
        "Tool arguments JSON parse failed",
        tool=function_name,
        args_str=function_args_str[:100],
        error=str(e),
    )
    # 返回错误给 LLM 让其修正
    tool_result = f"Error: Invalid JSON arguments. Please provide valid JSON."
```

**优先级**: 中

---

### 问题 6.3: 空消息列表处理

**文件**: `pi_python/agent/agent.py:127-129`

**问题描述**:
`_default_convert_to_llm()` 过滤消息时，如果所有消息都被过滤，会返回空列表，后续可能出错。

```python
def _default_convert_to_llm(self, messages: list[Message]) -> list[Message]:
    """默认消息转换"""
    return [m for m in messages if m.role in ("user", "assistant", "tool_result")]
```

**触发条件**: 消息列表只包含 system 或其他角色的消息

**修复建议**:
```python
def _default_convert_to_llm(self, messages: list[Message]) -> list[Message]:
    """默认消息转换"""
    result = [m for m in messages if m.role in ("user", "assistant", "tool_result")]
    if not result:
        logger.warning("No valid messages after conversion")
    return result
```

**优先级**: 低

---

### 问题 6.4: 超大输出截断后的信息丢失

**文件**: `src/tools/builtin/exec.py:673-677`

**问题描述**:
命令输出超过 1MB 时被截断，但没有保留原始长度信息。

```python
if len(stdout_str) > self.MAX_OUTPUT_LENGTH:
    stdout_str = stdout_str[:self.MAX_OUTPUT_LENGTH] + "\n... (truncated)"
```

**修复建议**:
```python
if len(stdout_str) > self.MAX_OUTPUT_LENGTH:
    original_length = len(stdout_str)
    stdout_str = stdout_str[:self.MAX_OUTPUT_LENGTH] + f"\n... (truncated, original: {original_length} bytes)"
```

**优先级**: 低

---

## 7. 安全性

### 问题 7.1: API Key 明文存储在内存中

**文件**: `webui/app.py:1302-1312`

**问题描述**:
API Key 以明文形式存储在内存中的 `SETTINGS_STORE` 字典中。

```python
SETTINGS_STORE: dict = {
    "aiProvider": "bailian",
    "apiKey": "",  # API Key 由前端设置
    # ...
}
```

**触发条件**: 应用运行时

**可能的影响**:
- 内存转储可能泄露 API Key
- 调试日志可能意外记录

**修复建议**:
1. 使用环境变量或加密存储
2. 在日志中屏蔽敏感字段：
```python
SENSITIVE_FIELDS = {"apiKey", "apiKeyEncrypted"}

def safe_settings(settings: dict) -> dict:
    return {
        k: "***" if k in SENSITIVE_FIELDS else v
        for k, v in settings.items()
    }
```

**优先级**: 高

---

### 问题 7.2: CORS 配置过于宽松

**文件**: `webui/app.py:142-148`

**问题描述**:
CORS 配置允许所有来源访问，不适合生产环境。

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应替换为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**触发条件**: 任何跨域请求

**可能的影响**:
- CSRF 攻击风险
- 数据泄露

**修复建议**:
从配置文件或环境变量读取允许的域名：
```python
import os

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # ...
)
```

**优先级**: 高（生产环境）

---

### 问题 7.3: 路径遍历验证 - Skill 文件

**文件**: `webui/app.py:517-535`

**问题描述**:
虽然 `_validate_skill_path()` 验证了路径，但使用 `resolve()` 在符号链接场景下可能有绕过风险。

```python
def _validate_skill_path(file_path: Path) -> bool:
    try:
        resolved_path = file_path.resolve()
        skills_dir_resolved = SKILLS_DIR.resolve()
        return str(resolved_path).startswith(str(skills_dir_resolved))
    except Exception:
        return False
```

**触发条件**:
- 攻击者创建符号链接指向目标文件
- 路径包含特殊字符

**可能的影响**:
- 读取或写入预期目录外的文件

**修复建议**:
1. 禁止符号链接：
```python
def _validate_skill_path(file_path: Path) -> bool:
    try:
        resolved_path = file_path.resolve()
        skills_dir_resolved = SKILLS_DIR.resolve()

        # 检查是否为符号链接
        if file_path.is_symlink():
            return False

        # 使用相对路径比较，避免字符串前缀匹配问题
        try:
            resolved_path.relative_to(skills_dir_resolved)
            return True
        except ValueError:
            return False
    except Exception:
        return False
```

**优先级**: 中

---

### 问题 7.4: 命令注入风险 - Bash 工具

**文件**: `pi_python/agent/tools.py:233-237`

**问题描述**:
`BashTool` 使用 `asyncio.create_subprocess_shell()` 执行命令，shell 解释器会处理特殊字符。

```python
async def execute(...):
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
```

**触发条件**: 命令中包含 shell 元字符或恶意命令

**缓解措施**: `src/tools/security.py` 中有 `validate_command()` 检查危险命令模式

**建议**:
对于不需要 shell 特性的命令，使用 `create_subprocess_exec()`：
```python
# 解析命令为列表
import shlex
args = shlex.split(command)
proc = await asyncio.create_subprocess_exec(
    args[0],
    *args[1:],
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)
```

**优先级**: 高（取决于安全检查的完整性）

---

### 问题 7.5: SSRF 防护的 DNS 重绑定攻击

**文件**: `src/tools/security.py:474-509`

**问题描述**:
URL 验证时进行 DNS 解析，但解析结果在验证后到实际请求之间可能发生变化（DNS 重绑定攻击）。

```python
def _validate_hostname_not_private(self, hostname: str, url: str) -> None:
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        # 检查解析结果是否为私网地址
```

**触发条件**:
- 攻击者控制 DNS 服务器
- DNS TTL 极短

**可能的影响**:
- 访问内网资源
- 绕过 SSRF 防护

**修复建议**:
在实际请求时再次验证，或在请求时锁定解析结果：
```python
# 在 HTTP 请求时使用自定义的 DNS 解析
async def safe_fetch(self, url: str) -> Response:
    parsed = urlparse(url)
    hostname = parsed.hostname

    # 解析并验证
    ips = socket.getaddrinfo(hostname, 443 if parsed.scheme == "https" else 80)
    for family, _, _, _, sockaddr in ips:
        ip = ipaddress.ip_address(sockaddr[0])
        if self._is_private_ip(ip):
            raise SecurityError(f"Private IP blocked: {ip}")

    # 使用验证后的 IP 进行请求
    # ...
```

**优先级**: 中

---

### 问题 7.6: 敏感文件列表不完整

**文件**: `src/tools/security.py:246-263`

**问题描述**:
敏感文件模式列表可能不完整，遗漏了一些常见的敏感文件。

```python
SENSITIVE_PATTERNS = [
    r"\.env$",
    r"\.env\.",
    r"credentials",
    # ... 可能遗漏：
    # - .aws/credentials
    # - .docker/config.json
    # - kubeconfig
    # - .npmrc
    # - .pypirc
]
```

**修复建议**:
补充完整的敏感文件列表：
```python
SENSITIVE_PATTERNS = [
    # 环境变量
    r"\.env$",
    r"\.env\.",
    r"\.envrc$",
    # 密钥和凭证
    r"credentials",
    r"secrets?",
    r"\.pem$",
    r"\.key$",
    r"\.p12$",
    r"\.pfx$",
    r"id_rsa",
    r"id_ed25519",
    r"\.ssh/",
    # 配置文件
    r"\.gitconfig",
    r"\.netrc",
    r"\.pgpass",
    r"\.npmrc",
    r"\.pypirc",
    r"\.docker/config\.json",
    r"kubeconfig",
    r"\.kube/config",
    r"\.aws/credentials",
    # 其他
    r"password",
    r"token",
    r"api_key",
    r"private_key",
    r"\.htpasswd",
]
```

**优先级**: 中

---

## 8. 总结与优先级

### 高优先级问题 (需立即修复)

| # | 问题 | 文件 | 影响 |
|---|------|------|------|
| 2.1 | 进程会话管理器内存泄漏 | src/tools/builtin/exec.py | 内存持续增长，系统资源耗尽 |
| 2.4 | Session 文件保存非原子 | pi_python/agent/session.py | 数据丢失风险 |
| 3.3 | 安全检查器同步调用异步代码 | src/tools/security.py | 死锁或运行时错误 |
| 7.1 | API Key 明文存储 | webui/app.py | 敏感信息泄露 |
| 7.2 | CORS 配置过于宽松 | webui/app.py | CSRF 攻击风险 |
| 7.4 | 命令注入风险 | pi_python/agent/tools.py | 系统被攻击 |

### 中优先级问题 (建议修复)

| # | 问题 | 文件 | 影响 |
|---|------|------|------|
| 1.1 | 事件订阅者错误被忽略 | pi_python/agent/agent.py | 调试困难 |
| 1.3 | Steering Queue 消息丢失 | pi_python/agent/agent.py | 指令丢失 |
| 2.2 | Redis 连接未正确关闭 | webui/app.py | 资源泄漏 |
| 3.1 | Agent 状态非原子更新 | src/core/models.py | 状态不一致 |
| 3.2 | 全局状态变量竞态条件 | webui/app.py | 数据不一致 |
| 4.1 | LLM 调用无重试机制 | webui/app.py | 临时故障导致失败 |
| 5.2 | 技能文件与内存不同步 | webui/app.py | 数据不一致 |
| 5.3 | Task 状态转换无验证 | src/core/models.py | 状态不一致 |
| 6.1 | Agent 最大迭代无警告 | pi_python/agent/agent.py | 任务截断无感知 |
| 7.3 | 路径遍历符号链接风险 | webui/app.py | 访问非预期文件 |
| 7.5 | SSRF DNS 重绑定攻击 | src/tools/security.py | 绕过防护 |
| 7.6 | 敏感文件列表不完整 | src/tools/security.py | 敏感文件泄露 |

### 低优先级问题 (可延后处理)

| # | 问题 | 文件 | 影响 |
|---|------|------|------|
| 1.2 | EventBus 取消订阅竞态 | webui/event_bus.py | 轻微不一致 |
| 4.2 | 工具错误未分类 | pi_python/agent/agent.py | 无法智能重试 |
| 5.1 | Agent 状态随机修改 | webui/app.py | 模拟代码问题 |
| 6.2 | 工具参数 JSON 解析失败 | webui/app.py | 执行失败 |
| 6.3 | 空消息列表处理 | pi_python/agent/agent.py | 边界情况 |
| 6.4 | 超大输出信息丢失 | src/tools/builtin/exec.py | 信息不完整 |

---

## 附录: 修复优先级建议

1. **立即修复 (P0)**:
   - 问题 2.1: 进程会话内存泄漏
   - 问题 3.3: 死锁风险
   - 问题 7.1: API Key 安全
   - 问题 7.2: CORS 安全

2. **短期修复 (P1 - 1周内)**:
   - 问题 2.4: 原子文件写入
   - 问题 7.4: 命令注入加固
   - 问题 4.1: LLM 重试机制
   - 问题 3.2: 并发安全

3. **中期修复 (P2 - 2周内)**:
   - 数据一致性问题
   - 边界条件完善
   - 安全加固

4. **长期优化 (P3)**:
   - 代码质量改进
   - 日志完善
   - 边界情况处理

---

*报告生成时间: 2026-03-15*