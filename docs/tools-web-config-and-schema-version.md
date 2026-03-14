# Tools Web 配置和 Schema 版本功能说明

## 概述

本文档说明了对 Tools 系统的两项增强功能：
1. **Web 工具全局配置支持** - 允许通过 `ToolsConfig` 统一配置 Web 相关工具
2. **Schema 版本管理** - 为每个工具添加版本元信息，便于版本追踪和兼容性管理

---

## 1. Web 工具全局配置

### 1.1 WebToolsConfig 模型

新增 `WebToolsConfig` 模型，用于配置 Web 相关工具（`web_fetch`、`web_search`）的行为：

```python
from src.tools.policy import WebToolsConfig

web_config = WebToolsConfig(
    cache_ttl_sec=900,          # 缓存有效期（秒），默认 15 分钟
    max_chars_cap=20000,        # 最大字符数上限
    allow_private_network=False, # 是否允许访问私网地址
    default_timeout_ms=20000,   # 默认请求超时（毫秒）
)
```

### 1.2 在 ToolsConfig 中使用

```python
from src.tools.policy import ToolsConfig, WebToolsConfig

# 创建 Web 配置
web_config = WebToolsConfig(
    cache_ttl_sec=1800,  # 30 分钟
    max_chars_cap=25000,
)

# 创建全局配置
global_config = ToolsConfig(
    profile="coding",
    web=web_config,
)

# 获取 Web 配置（如果未设置则返回默认值）
web = global_config.get_web_config()
```

### 1.3 配置字段说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cache_ttl_sec` | int | 900 | 缓存有效期（秒） |
| `max_chars_cap` | int | 20000 | 最大字符数上限 |
| `allow_private_network` | bool | False | 是否允许访问私网地址 |
| `default_timeout_ms` | int | 20000 | 默认请求超时（毫秒） |

### 1.4 Web 工具使用全局配置

`WebFetchTool` 和 `WebSearchTool` 现在支持通过 `web_config` 参数接收全局配置：

```python
from src.tools.builtin import WebFetchTool, WebSearchTool
from src.tools.policy import WebToolsConfig

web_config = WebToolsConfig(cache_ttl_sec=1800)

# 创建使用全局配置的 WebFetchTool
fetch_tool = WebFetchTool(web_config=web_config)

# 创建使用全局配置的 WebSearchTool
search_tool = WebSearchTool(web_config=web_config)
```

工具初始化时会优先使用传入的参数，否则使用 `web_config` 中的配置，最后使用默认值。

---

## 2. Schema 版本管理

### 2.1 BaseTool 的 SCHEMA_VERSION

`BaseTool` 基类新增 `SCHEMA_VERSION` 类属性，默认值为 `"1.0.0"`：

```python
class BaseTool(ABC):
    NAME: str = None
    DESCRIPTION: str = None
    SCHEMA_VERSION: str = "1.0.0"  # 新增
```

### 2.2 为工具定义 Schema 版本

所有工具类都应该定义自己的 `SCHEMA_VERSION`：

```python
class WebFetchTool(BaseTool):
    NAME = "web_fetch"
    DESCRIPTION = "Fetch and extract content from web URLs securely"
    SCHEMA_VERSION = "1.0.0"  # 定义工具 schema 版本
```

### 2.3 版本规范

遵循语义化版本规范（SemVer）：
- **major**（主版本）: 破坏性变更，可能删除字段或修改必填项
- **minor**（次版本）: 新增功能，仅增加可选字段或新 action
- **patch**（补丁版本）: 修复问题，仅修改文案、默认值或非破坏性约束

### 2.4 获取工具版本

```python
from src.tools.builtin import WebFetchTool

tool = WebFetchTool()
print(tool.SCHEMA_VERSION)  # 输出: 1.0.0

# 通过 to_dict() 获取
tool_dict = tool.to_dict()
print(tool_dict["schema_version"])  # 输出: 1.0.0
```

---

## 3. API Schema 中的版本信息

### 3.1 x-schema-version 元信息

`ToolPresenter` 生成 API schema 时，会在 schema 中包含 `x-schema-version` 元信息：

```python
from src.tools.registry import ToolRegistry
from src.tools.presenter import ToolPresenter
from src.tools.builtin import WebFetchTool

registry = ToolRegistry()
registry.register(WebFetchTool())

presenter = ToolPresenter(registry)
presentation = presenter.present({"web_fetch"})

schema = presentation.api_schemas[0]
print(schema)
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
    "x-schema-version": "1.0.0"
}
```

### 3.2 版本信息用途

- **兼容性检查**: 客户端可以检查工具版本，确保兼容性
- **文档生成**: 自动生成带版本的 API 文档
- **变更追踪**: 追踪工具 schema 的变更历史
- **调试支持**: 在问题排查时快速确定工具版本

---

## 4. 已更新 Schema 版本的工具列表

| 工具名称 | 文件路径 | Schema 版本 |
|----------|----------|-------------|
| `web_fetch` | `src/tools/builtin/web_fetch.py` | 1.0.0 |
| `web_search` | `src/tools/builtin/web_search.py` | 1.0.0 |
| `exec` | `src/tools/builtin/exec.py` | 1.0.0 |
| `process` | `src/tools/builtin/process.py` | 1.0.0 |
| `memory_search` | `src/tools/builtin/memory.py` | 1.0.0 |
| `memory_get` | `src/tools/builtin/memory.py` | 1.0.0 |
| `sessions_list` | `src/tools/builtin/sessions.py` | 1.0.0 |
| `sessions_history` | `src/tools/builtin/sessions.py` | 1.0.0 |
| `sessions_send` | `src/tools/builtin/sessions.py` | 1.0.0 |
| `sessions_spawn` | `src/tools/builtin/sessions.py` | 1.0.0 |
| `session_status` | `src/tools/builtin/sessions.py` | 1.0.0 |
| `agents_list` | `src/tools/builtin/sessions.py` | 1.0.0 |
| `file_tools` | `src/tools/file_tools.py` | 1.0.0 |
| `code_tools` | `src/tools/code_tools.py` | 1.0.0 |
| `git_tools` | `src/tools/git_tools.py` | 1.0.0 |
| `search_tools` | `src/tools/search_tools.py` | 1.0.0 |
| `testing_tools` | `src/tools/test_tools.py` | 1.0.0 |

---

## 5. 使用示例

### 5.1 完整配置示例

```python
from src.tools.policy import ToolsConfig, WebToolsConfig, ProfileType
from src.tools.registry import get_registry

# 创建 Web 配置
web_config = WebToolsConfig(
    cache_ttl_sec=1800,          # 30 分钟缓存
    max_chars_cap=30000,         # 最大 30000 字符
    allow_private_network=False, # 禁止私网访问
    default_timeout_ms=30000,    # 30 秒超时
)

# 创建全局配置
global_config = ToolsConfig(
    profile=ProfileType.CODING,
    allow=["web_fetch", "web_search"],
    deny=["exec"],
    web=web_config,
)

# 获取注册中心并设置策略引擎
registry = get_registry()
registry.set_policy_engine(global_config)

# 注册内置工具（会使用全局 Web 配置）
registry.register_builtin_tools()
```

### 5.2 检查工具版本

```python
from src.tools.registry import get_registry

registry = get_registry()

# 列出所有工具及其版本
for tool_dict in registry.list_tools():
    name = tool_dict["name"]
    version = tool_dict.get("schema_version", "N/A")
    print(f"{name}: {version}")
```

### 5.3 生成带版本的 API Schema

```python
from src.tools.presenter import present_tools

# 生成工具呈现
presentation = present_tools({"web_fetch", "web_search"})

# 打印每个工具的版本
for schema in presentation.api_schemas:
    name = schema["function"]["name"]
    version = schema.get("x-schema-version", "N/A")
    print(f"{name}: schema version {version}")
```

---

## 6. 向后兼容性

- **Web 配置**: 如果不提供 `web_config`，工具会使用默认值，保持向后兼容
- **Schema 版本**: 默认值为 `"1.0.0"`，现有代码无需修改
- **to_dict()**: 新增 `schema_version` 字段，不影响现有代码
- **API Schema**: `x-schema-version` 是扩展字段，不会影响标准 OpenAI function calling 格式

---

## 7. 更新日志

### 2026-03-13

- 新增 `WebToolsConfig` 模型
- 在 `ToolsConfig` 中添加 `web` 字段
- 为所有内置工具添加 `SCHEMA_VERSION`
- 更新 `ToolPresenter` 生成带 `x-schema-version` 的 schema
- 更新 `BaseTool.to_dict()` 包含 `schema_version`

---

## 8. 接口规范符合性

这些更新使 Tools 系统完全符合 `tools-interface-spec.md` 规范：

- ✅ **5.1 ToolsConfig**: 包含 `web` 配置字段
- ✅ **5.1 ToolsConfig**: `web.cacheTtlSec`, `web.maxCharsCap`, `web.allowPrivateNetwork` 配置
- ✅ **12. 兼容性与版本策略**: 每个工具 schema 带 `x-schema-version` 元信息
- ✅ **12. 语义化版本**: 使用 `major.minor.patch` 格式
