# Tools Output Schema 功能说明

## 概述

本文档介绍 Tools 系统的 `output_schema` 功能，用于描述工具成功执行后的返回数据结构。这是工具契约规范的重要组成部分，使工具的使用者能够清楚地了解工具的输出格式。

---

## 1. 核心概念

### 1.1 OutputField

`OutputField` 用于定义输出数据结构中的单个字段：

```python
from src.tools.base import OutputField

field = OutputField(
    name="content",           # 字段名称
    type="string",            # 字段类型
    description="文件内容",   # 字段描述
    required=True,            # 是否必填
)
```

**支持的类型：**
- `string` - 字符串
- `integer` - 整数
- `number` - 浮点数
- `boolean` - 布尔值
- `array` - 数组
- `object` - 对象

### 1.2 OutputSchema

`OutputSchema` 用于定义工具完整的输出数据结构：

```python
from src.tools.base import OutputField, OutputSchema

schema = OutputSchema(
    description="文件读取结果",
    fields=[
        OutputField(name="content", type="string", description="文件内容"),
        OutputField(name="size", type="integer", description="文件大小"),
        OutputField(name="encoding", type="string", description="文件编码", required=False),
    ],
)
```

---

## 2. 为工具定义 Output Schema

### 2.1 基本示例

在工具类中实现 `output_schema` 属性：

```python
from src.tools.base import BaseTool, OutputField, OutputSchema, ToolParameter

class MyTool(BaseTool):
    NAME = "my_tool"
    DESCRIPTION = "My tool description"
    SCHEMA_VERSION = "1.0.0"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="input", type="string", required=True),
        ]

    @property
    def output_schema(self) -> OutputSchema:
        """定义工具的输出模式"""
        return OutputSchema(
            description="Tool execution result",
            fields=[
                OutputField(name="result", type="string", description="处理结果"),
                OutputField(name="count", type="integer", description="处理数量"),
            ],
        )

    async def execute(self, **kwargs) -> ToolResult:
        # 执行逻辑
        return ToolResult.ok(data={"result": "success", "count": 42})
```

### 2.2 嵌套对象示例

对于复杂的输出结构，可以使用 `nested_schemas`：

```python
@property
def output_schema(self) -> OutputSchema:
    return OutputSchema(
        description="Search results",
        fields=[
            OutputField(name="results", type="array", description="结果列表"),
            OutputField(name="total", type="integer", description="总数"),
        ],
        nested_schemas={
            "result_item": OutputSchema(
                description="Single result item",
                fields=[
                    OutputField(name="id", type="string", description="ID"),
                    OutputField(name="title", type="string", description="标题"),
                    OutputField(name="score", type="number", description="分数"),
                ],
            ),
        },
    )
```

---

## 3. 内置工具的 Output Schema

### 3.1 WebFetchTool

```python
OutputSchema(
    description="Web page content extraction result",
    fields=[
        OutputField(name="url", type="string", description="Original request URL"),
        OutputField(name="finalUrl", type="string", description="Final URL after redirects"),
        OutputField(name="title", type="string", description="Page title"),
        OutputField(name="content", type="string", description="Extracted content"),
        OutputField(name="truncated", type="boolean", description="Whether content was truncated"),
        OutputField(name="contentType", type="string", description="Content type"),
        OutputField(name="statusCode", type="integer", description="HTTP status code"),
    ],
)
```

### 3.2 WebSearchTool

```python
OutputSchema(
    description="Web search results",
    fields=[
        OutputField(name="results", type="array", description="List of search results"),
    ],
    nested_schemas={
        "result_item": OutputSchema(...),
        "cache_info": OutputSchema(...),
    },
)
```

### 3.3 ExecTool

```python
OutputSchema(
    description="Command execution result",
    fields=[
        OutputField(name="exitCode", type="integer", description="Command exit code"),
        OutputField(name="stdout", type="string", description="Standard output"),
        OutputField(name="stderr", type="string", description="Standard error"),
        OutputField(name="sessionId", type="string", description="Session ID for background processes"),
    ],
)
```

### 3.4 ProcessTool

```python
OutputSchema(
    description="Process session management result",
    fields=[
        OutputField(name="sessions", type="array", description="List of sessions"),
        OutputField(name="sessionId", type="string", description="Session ID"),
        OutputField(name="status", type="string", description="Session status"),
        OutputField(name="exitCode", type="integer", description="Exit code"),
        OutputField(name="stdout", type="string", description="Standard output"),
        OutputField(name="stderr", type="string", description="Standard error"),
    ],
)
```

### 3.5 Memory Tools

**MemorySearchTool:**
```python
OutputSchema(
    description="Memory search results",
    fields=[
        OutputField(name="memories", type="array", description="List of matching memory entries"),
        OutputField(name="count", type="integer", description="Number of results"),
    ],
)
```

**MemoryGetTool:**
```python
OutputSchema(
    description="Memory entry data",
    fields=[
        OutputField(name="id", type="string", description="Memory ID"),
        OutputField(name="agent_id", type="string", description="Agent ID"),
        OutputField(name="content", type="string", description="Memory content"),
        OutputField(name="namespace", type="string", description="Namespace"),
        OutputField(name="created_at", type="string", description="Creation time"),
    ],
)
```

---

## 4. 使用 Output Schema

### 4.1 获取工具的 Output Schema

```python
from src.tools.builtin import WebFetchTool

tool = WebFetchTool()
schema = tool.output_schema

print(schema.description)
for field in schema.fields:
    print(f"  - {field.name}: {field.type} ({'required' if field.required else 'optional'})")
```

### 4.2 转换为字典

```python
# OutputSchema 转字典
schema_dict = schema.to_dict()
print(schema_dict)
# 输出:
# {
#     "description": "Web page content extraction result",
#     "type": "object",
#     "properties": {
#         "url": {"type": "string", "description": "Original request URL"},
#         ...
#     },
#     "required": ["url", "finalUrl", ...]
# }

# 工具转字典（包含 output_schema）
tool_dict = tool.to_dict()
print(tool_dict["output_schema"])
```

### 4.3 API Schema 中的输出定义

当使用 `ToolPresenter` 生成 API schema 时，输出模式会包含在 `x-output-schema` 字段中：

```python
from src.tools.presenter import present_tools

presentation = present_tools({"web_fetch", "web_search"})

for schema in presentation.api_schemas:
    print(f"Tool: {schema['function']['name']}")
    print(f"  Version: {schema['x-schema-version']}")
    print(f"  Output: {schema['x-output-schema']['description']}")
```

输出示例：

```json
{
    "type": "function",
    "function": {
        "name": "web_fetch",
        "description": "Fetch and extract content from web URLs securely",
        "parameters": {...}
    },
    "x-schema-version": "1.0.0",
    "x-output-schema": {
        "description": "Web page content extraction result",
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Original request URL"},
            "finalUrl": {"type": "string", "description": "Final URL after redirects"},
            ...
        },
        "required": ["url", "finalUrl", "content", "truncated", "contentType", "statusCode"]
    }
}
```

---

## 5. 设计原则

### 5.1 字段命名

- 使用 `camelCase` 命名（与 JSON 惯例一致）
- 名称应清晰表达字段含义
- 避免缩写，除非是广泛认可的（如 `id`, `url`）

### 5.2 字段类型

- 选择最精确的类型
- 对于可能为空的字段，设置 `required=False`
- 数组类型应说明元素类型

### 5.3 描述规范

- 描述应简洁明了
- 说明字段的用途和格式
- 对于枚举值，列出所有可能的值

### 5.4 版本管理

- 当 output schema 发生变更时，更新 `SCHEMA_VERSION`
- 遵循语义化版本规范：
  - **major**: 删除字段或修改必填项（破坏性变更）
  - **minor**: 添加新字段（向后兼容）
  - **patch**: 修改描述或文档（无功能变更）

---

## 6. 向后兼容性

- `output_schema` 是可选属性，默认为 `None`
- 现有工具无需修改即可继续工作
- 新工具建议实现 `output_schema` 以提供更好的文档

---

## 7. 示例：完整的工具定义

```python
from src.tools.base import (
    BaseTool,
    OutputField,
    OutputSchema,
    ToolParameter,
    ToolResult,
)

class FileReadTool(BaseTool):
    """文件读取工具"""
    
    NAME = "file_read"
    DESCRIPTION = "Read file content"
    SCHEMA_VERSION = "1.0.0"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                required=True,
                description="File path to read",
            ),
            ToolParameter(
                name="encoding",
                type="string",
                required=False,
                default="utf-8",
                description="File encoding",
            ),
        ]

    @property
    def output_schema(self) -> OutputSchema:
        return OutputSchema(
            description="File read result",
            fields=[
                OutputField(
                    name="content",
                    type="string",
                    description="File content",
                    required=True,
                ),
                OutputField(
                    name="size",
                    type="integer",
                    description="File size in bytes",
                    required=True,
                ),
                OutputField(
                    name="encoding",
                    type="string",
                    description="Detected or specified encoding",
                    required=True,
                ),
                OutputField(
                    name="lineCount",
                    type="integer",
                    description="Number of lines",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path")
        encoding = kwargs.get("encoding", "utf-8")
        
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            
            return ToolResult.ok(
                data={
                    "content": content,
                    "size": len(content.encode(encoding)),
                    "encoding": encoding,
                    "lineCount": content.count("\n") + 1,
                }
            )
        except Exception as e:
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to read file: {e}",
            )
```

---

## 8. 参考

- `src/tools/base.py` - OutputField, OutputSchema 定义
- `src/tools/presenter.py` - API schema 生成
- `src/tools/builtin/*.py` - 内置工具实现示例
