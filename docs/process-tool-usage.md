# Process 工具使用文档

## 概述

Process 工具用于管理由 Exec 工具创建的后台进程会话。它提供了完整的会话生命周期管理功能。

## 工具名称

`process`

## 支持的动作

### 1. list - 列出后台会话

列出当前 agent 创建的所有后台会话。

**参数**:
- `action`: "list" (必需)
- `cursor`: 分页游标 (可选)
- `limit`: 返回数量限制，默认 20，最大 100 (可选)

**示例**:
```python
result = await tool.execute(
    action="list",
    limit=10
)

# 返回格式
{
    "items": [
        {
            "session_id": "sess-123",
            "agent_id": "agent-001",
            "status": "running",
            "command": "python script.py",
            "cwd": "/home/user",
            "created_at": "2026-03-12T10:00:00Z",
            "exit_code": null,
            "pid": 12345,
            "stdout_bytes": 1024,
            "stderr_bytes": 0
        }
    ],
    "next_cursor": null,
    "has_more": false
}
```

### 2. poll - 轮询会话状态

检查会话的当前状态，可选择等待一段时间。

**参数**:
- `action`: "poll" (必需)
- `session_id`: 会话 ID (必需)
- `wait_ms`: 等待时间（毫秒），默认 1000 (可选)

**示例**:
```python
result = await tool.execute(
    action="poll",
    session_id="sess-123",
    wait_ms=2000
)

# 返回格式
{
    "session_id": "sess-123",
    "status": "running",  # running | completed | killed | error
    "exit_code": null,
    "stdout_bytes": 2048,
    "stderr_bytes": 0
}
```

### 3. log - 获取会话日志

获取会话的标准输出或错误输出。

**参数**:
- `action`: "log" (必需)
- `session_id`: 会话 ID (必需)
- `stream`: 日志流类型，可选 "stdout"、"stderr" 或 "both"，默认 "stdout" (可选)
- `offset`: 字节偏移量，默认 0 (可选)
- `max_bytes`: 最大读取字节数，默认 65536，最大 1048576 (可选)

**示例**:
```python
# 获取标准输出
result = await tool.execute(
    action="log",
    session_id="sess-123",
    stream="stdout"
)

# 获取错误输出
result = await tool.execute(
    action="log",
    session_id="sess-123",
    stream="stderr"
)

# 获取所有输出
result = await tool.execute(
    action="log",
    session_id="sess-123",
    stream="both",
    max_bytes=100000
)

# 返回格式
{
    "session_id": "sess-123",
    "stream": "stdout",
    "data": "base64_encoded_content",
    "offset": 0,
    "bytes_read": 1024,
    "eof": false
}
```

### 4. write - 向会话写入输入

向正在运行的进程的标准输入写入数据。

**参数**:
- `action`: "write" (必需)
- `session_id`: 会话 ID (必需)
- `input`: 输入内容 (必需)

**示例**:
```python
result = await tool.execute(
    action="write",
    session_id="sess-123",
    input="hello world\n"
)

# 返回格式
{
    "session_id": "sess-123",
    "written": true
}
```

**注意**: 只有状态为 "running" 的会话才能接受输入。

### 5. kill - 终止会话

终止正在运行的会话。

**参数**:
- `action`: "kill" (必需)
- `session_id`: 会话 ID (必需)

**示例**:
```python
result = await tool.execute(
    action="kill",
    session_id="sess-123"
)

# 返回格式
{
    "session_id": "sess-123",
    "killed": true
}
```

**行为**:
- 首先尝试发送 SIGTERM (terminate)
- 如果 5 秒内进程未退出，发送 SIGKILL (kill)
- 更新会话状态为 "killed"

### 6. clear - 清理会话资源

清空会话的输出缓冲区（stdout/stderr）。

**参数**:
- `action`: "clear" (必需)
- `session_id`: 会话 ID (必需)

**示例**:
```python
result = await tool.execute(
    action="clear",
    session_id="sess-123"
)

# 返回格式
{
    "session_id": "sess-123",
    "cleared": true
}
```

### 7. remove - 删除会话记录

完全删除会话记录。如果会话仍在运行，会先终止进程。

**参数**:
- `action`: "remove" (必需)
- `session_id`: 会话 ID (必需)

**示例**:
```python
result = await tool.execute(
    action="remove",
    session_id="sess-123"
)

# 返回格式
{
    "session_id": "sess-123",
    "removed": true
}
```

## Agent 作用域隔离

所有操作都会验证 `agent_id`，确保只能访问自己创建的会话：

- 如果会话不存在，返回 NOT_FOUND 错误
- 如果会话属于其他 agent，返回 NOT_FOUND 错误（不暴露其他 agent 的信息）

## 错误处理

工具返回标准化的错误响应：

```python
{
    "success": false,
    "error": "Session not found: sess-123",
    "metadata": {
        "error_code": "NOT_FOUND"
    }
}
```

## 与 Exec 工具的关系

- **Exec 工具**: 负责创建后台进程会话（`background=true`）
- **Process 工具**: 负责管理已创建的会话

两者共享同一个 `ProcessSessionManager` 实例，确保状态一致性。

## 使用流程示例

### 典型的后台任务管理流程

```python
from src.tools import ExecTool, ProcessTool

# 1. 创建后台进程
exec_tool = ExecTool(agent_id="agent-001")
exec_result = await exec_tool.execute(
    cmd="python long_running_script.py",
    background=True
)

session_id = exec_result.data["session_id"]

# 2. 轮询状态
process_tool = ProcessTool(agent_id="agent-001")
while True:
    poll_result = await process_tool.execute(
        action="poll",
        session_id=session_id,
        wait_ms=1000
    )
    
    if poll_result.data["status"] in ["completed", "killed", "error"]:
        break
    
    # 检查输出
    log_result = await process_tool.execute(
        action="log",
        session_id=session_id,
        stream="stdout"
    )
    print(f"Output: {log_result.data['data']}")

# 3. 获取最终输出
final_log = await process_tool.execute(
    action="log",
    session_id=session_id,
    stream="both"
)

# 4. 清理
await process_tool.execute(
    action="remove",
    session_id=session_id
)
```

### 交互式进程管理

```python
# 启动交互式程序
exec_result = await exec_tool.execute(
    cmd="python interactive_app.py",
    background=True
)

session_id = exec_result.data["session_id"]

# 发送输入
await process_tool.execute(
    action="write",
    session_id=session_id,
    input="user_command\n"
)

# 读取响应
log_result = await process_tool.execute(
    action="log",
    session_id=session_id,
    stream="stdout"
)

# 结束会话
await process_tool.execute(
    action="kill",
    session_id=session_id
)
```

## 注意事项

1. **会话生命周期**: 会话会在进程结束后保留，直到显式删除
2. **资源清理**: 建议在会话完成后调用 `remove` 清理资源
3. **输入限制**: 只有状态为 "running" 的会话才能接受输入
4. **日志大小**: 使用 `max_bytes` 限制单次读取的数据量，避免内存问题
5. **Agent 隔离**: 确保使用正确的 agent_id 创建和管理会话

## 最佳实践

1. **定期轮询**: 对于长时间运行的任务，使用合理的 `wait_ms` 避免频繁轮询
2. **增量读取**: 使用 `offset` 参数增量读取日志，而不是每次都从头开始
3. **错误处理**: 始终检查 `success` 字段，处理可能的错误
4. **资源管理**: 使用 try-finally 确保会话被正确清理
5. **超时处理**: 为长时间任务设置合理的超时机制

## 集成示例

### FastAPI 集成

```python
from fastapi import APIRouter, HTTPException
from src.tools import ProcessTool

router = APIRouter()

@router.post("/sessions/{session_id}/kill")
async def kill_session(session_id: str, agent_id: str):
    tool = ProcessTool(agent_id=agent_id)
    result = await tool.execute(action="kill", session_id=session_id)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    
    return result.data
```

### 异步任务管理

```python
import asyncio

async def monitor_session(session_id: str, agent_id: str):
    tool = ProcessTool(agent_id=agent_id)
    
    while True:
        result = await tool.execute(
            action="poll",
            session_id=session_id,
            wait_ms=5000
        )
        
        if result.data["status"] != "running":
            break
        
        # 获取最新输出
        log = await tool.execute(
            action="log",
            session_id=session_id,
            stream="stdout",
            offset=-1000  # 最后 1000 字节
        )
        
        yield log.data
```

## 故障排查

### 问题: 会话不存在

**原因**: session_id 错误或属于其他 agent

**解决**: 检查 session_id 和 agent_id 是否正确

### 问题: 无法写入输入

**原因**: 会话不在 running 状态

**解决**: 先轮询确认会话状态为 running

### 问题: 日志读取失败

**原因**: offset 超出范围或 stream 参数错误

**解决**: 检查 offset 和 stream 参数，使用合理的默认值

### 问题: 进程无法终止

**原因**: 进程可能忽略了 SIGTERM 信号

**解决**: kill 动作会自动使用 SIGKILL 作为后备方案
