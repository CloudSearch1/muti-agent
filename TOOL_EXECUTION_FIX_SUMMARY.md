# 工具执行修复总结

## 问题描述

工具系统成功注册（13个工具），但在实际执行时出现错误：
- `'WriteTool' object has no attribute 'execute_async'`
- `'ExecTool' object has no attribute 'execute_async'`
- 执行 `pwd` 等命令时参数不匹配

## 根本原因

代码中存在多个不一致的接口调用：

1. **工具类实现错误**：`file_ops.py` 中的工具类使用了 `PARAMETERS` 类属性（大写）和 `execute_async` 方法，但 `BaseTool` 抽象类要求实现 `parameters` 属性（小写）和 `execute` 方法

2. **调用代码错误**：`webui/app.py` 和 `src/tools/adapter.py` 调用了 `tool.execute_async()`，但工具类实现的是 `execute()`

3. **内部调用错误**：`file_ops.py` 中的工具类调用了 `self.file_tools.execute_async()`，但 `FileTools` 实现的是 `execute()`

4. **参数名称不匹配**：AI 模型调用 ExecTool 时使用 `command` 参数，但 ExecTool 期望的是 `cmd` 参数

## 修复内容

### 1. 修复工具类定义 (`src/tools/builtin/file_ops.py`)

**修改前：**
```python
class ReadTool(BaseTool):
    NAME = "read"
    DESCRIPTION = "读取文件内容"
    PARAMETERS = [  # ❌ 错误：应该是 parameters 属性
        {"name": "path", "type": "string", "description": "文件路径", "required": True}
    ]
    
    async def execute_async(self, path: str, **kwargs) -> ToolResult:  # ❌ 错误：应该是 execute
        return await self.file_tools.execute_async(action="read", path=path)
```

**修改后：**
```python
class ReadTool(BaseTool):
    NAME = "read"
    DESCRIPTION = "读取文件内容"
    
    @property
    def parameters(self) -> list[ToolParameter]:  # ✅ 正确：parameters 属性
        return [ToolParameter(name="path", type="string", description="文件路径", required=True)]
    
    async def execute(self, path: str, **kwargs) -> ToolResult:  # ✅ 正确：execute 方法
        return await self.file_tools.execute(action="read", path=path)  # ✅ 正确：调用 execute
```

**影响工具：**
- `ReadTool`
- `WriteTool`
- `EditTool`
- `ApplyPatchTool`
- `SessionsListTool`
- `SessionsHistoryTool`

### 2. 修复调用代码 (`webui/app.py`)

**修改前（第 1559 行）：**
```python
result = await tool.execute_async(**function_args)  # ❌ 错误
```

**修改后：**
```python
result = await tool.execute(**function_args)  # ✅ 正确
```

**增强错误日志（第 1572 行）：**
```python
logger.error(f"[Agent] 工具执行错误: {e}", exc_info=True)  # ✅ 添加 exc_info=True
```

### 3. 修复适配器代码 (`src/tools/adapter.py`)

**修改前（第 109 行）：**
```python
result = await self._tool.execute_async(**params)  # ❌ 错误
```

**修改后：**
```python
result = await self._tool.execute(**params)  # ✅ 正确
```

### 4. 修复内部调用 (`src/tools/builtin/file_ops.py`)

将所有 `self.file_tools.execute_async()` 调用改为 `self.file_tools.execute()`

**影响位置：**
- `ReadTool.execute()`: `execute_async(action="read")` → `execute(action="read")`
- `WriteTool.execute()`: `execute_async(action="write")` → `execute(action="write")`
- `EditTool.execute()`: 两次调用 `execute_async` → `execute`
- `ApplyPatchTool.execute()`: `execute_async(action="write")` → `execute(action="write")`

### 5. 修复 ExecTool 参数兼容性 (`src/tools/builtin/exec.py`)

**修改 execute 方法（第 467 行）：**
```python
async def execute(self, **kwargs) -> ToolResult:
    """
    执行命令

    根据 background 参数决定同步或异步执行
    """
    # 兼容 AI 模型可能使用的 'command' 参数
    if 'command' in kwargs and 'cmd' not in kwargs:
        kwargs['cmd'] = kwargs.pop('command')
        self.logger.debug(f"Converted 'command' parameter to 'cmd': {kwargs['cmd']}")

    # 解析请求
    try:
        request = ExecRequest(**kwargs)
    except Exception as e:
        return ToolResult.error(...)
```

## 修复验证

测试脚本验证所有工具类能够：
1. ✅ 正确实例化
2. ✅ 实现 `parameters` 属性
3. ✅ 实现 `execute` 方法
4. ✅ 通过 `__call__` 调用
5. ✅ 正确执行文件读写操作
6. ✅ ExecTool 能正确处理 `command` 参数并转换为 `cmd`

## 技术细节

### BaseTool 抽象接口

```python
class BaseTool(ABC):
    NAME: str = None
    DESCRIPTION: str = None
    
    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """返回参数定义列表"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具逻辑"""
        pass
    
    async def __call__(self, **kwargs) -> ToolResult:
        """调用入口，内部调用 execute"""
        result = await self.execute(**kwargs)
        return result
```

### 调用链

```
webui/app.py
  → tool.execute(**kwargs)  [修复前: execute_async]
    → BaseTool.__call__()
      → tool.execute(**kwargs)
        → 具体工具实现 (ReadTool/WriteTool/ExecTool等)
```

### ExecTool 参数兼容性

```
AI 模型调用: {'command': 'pwd'}
  → ExecTool.execute(command='pwd')
    → 自动转换为: kwargs['cmd'] = kwargs.pop('command')
      → ExecRequest(cmd='pwd')
        → 正常执行命令
```

## 启动日志验证

```
2026-03-14 15:52:45 [info] Tool registered tool_name=read
2026-03-14 15:52:45 - __main__ - INFO - ✓ 注册工具: read
2026-03-14 15:52:45 [info] Tool registered tool_name=write
2026-03-14 15:52:45 - __main__ - INFO - ✓ 注册工具: write
...
2026-03-14 15:52:45 - __main__ - INFO - Agent 框架已加载，共注册 13 个工具
```

测试日志：
```
2026-03-14 16:08:26 [debug] Converted 'command' parameter to 'cmd': pwd tool_name=exec
   执行成功
```

## 后续使用

现在 AI 助手可以正常使用工具功能：
- ✅ 读取文件 (`read`)
- ✅ 写入文件 (`write`)
- ✅ 编辑文件 (`edit`)
- ✅ 执行命令 (`exec`) - 支持 `cmd` 和 `command` 两种参数
- ✅ 其他 9 个工具

当用户请求"创建文件夹"、"读取文件"、"执行 pwd 命令"等操作时，AI 将自动调用相应工具并执行。
