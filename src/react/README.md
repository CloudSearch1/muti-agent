# ReAct Agent 系统

基于 LangChain 的 ReAct (Reasoning + Acting) Agent 实现，为 IntelliTeam 平台提供动态推理和工具调用能力。

## 🎯 概述

ReAct Agent 是一种结合**推理**（Reasoning）和**行动**（Acting）的 Agent 范式，通过循环迭代的方式完成任务：

```
Thought → Action → Observation → Thought → ...
```

### 核心特性

- ✅ **动态推理**：LLM 自主决策下一步行动
- ✅ **工具驱动**：自动选择和调用工具
- ✅ **完整记录**：可追溯的推理链
- ✅ **循环检测**：避免陷入无限循环
- ✅ **性能监控**：完整的执行统计和指标
- ✅ **异步支持**：高性能异步执行
- ✅ **灵活配置**：支持自定义 Prompt 和参数

---

## 📦 安装

```bash
# 安装核心依赖
pip install langchain langchain-core langchain-openai

# 可选：其他 LLM 提供商
pip install langchain-anthropic  # Claude
pip install langchain-azure  # Azure OpenAI
```

---

## 🚀 快速开始

### 1. 创建简单的 ReAct Agent

```python
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
from src.react import ReActAgent, ReActConfig
from src.core import Task

# 创建 LLM
llm = ChatOpenAI(model="gpt-4")

# 定义工具
def search_code(query: str) -> str:
    return f"Found code for: {query}"

tools = [
    Tool(name="search_code", func=search_code, description="Search code"),
]

# 创建 Agent
config = ReActConfig(max_iterations=10)
agent = ReActAgent(llm=llm, tools=tools, config=config)

# 执行任务
task = Task(title="Test", description="Search for authentication code")

async with agent.lifecycle():
    result = await agent.process_task(task)
    print(result.output_data["output"])
```

### 2. 使用具体的 ReAct Agent

```python
from langchain_openai import ChatOpenAI
from src.agents.react_coder import create_react_coder_agent
from src.core import Task

# 创建 Agent（自动加载工具）
coder = create_react_coder_agent(llm=ChatOpenAI(model="gpt-4"))

# 执行任务
task = Task(
    title="实现用户认证",
    description="实现基于 JWT 的用户登录功能",
)

async with coder.lifecycle():
    result = await coder.process_task(task)
    
    # 查看结果
    print(result.output_data["output"])
    print(result.output_data.get("code_changes", []))
```

---

## 📚 核心组件

### 1. ReActAgent 基类

所有 ReAct Agent 的基类，封装了完整的推理循环。

```python
from src.react import ReActAgent, ReActConfig

agent = ReActAgent(
    llm=llm,
    tools=tools,
    config=ReActConfig(
        max_iterations=15,
        max_execution_time=300.0,
        enable_loop_detection=True,
    ),
)
```

### 2. 工具适配器

将 IntelliTeam 工具转换为 LangChain 格式。

```python
from src.react import ToolAdapter

# 批量适配
langchain_tools = ToolAdapter.adapt_batch(intelliteam_tools)

# 从函数创建
tool = ToolAdapter.adapt_from_function(
    func=my_function,
    name="my_tool",
    description="Tool description",
)
```

### 3. 回调处理器

监控执行过程、记录推理链、检测循环。

```python
from src.react import ReActCallbackHandler, LoopDetectionCallback

# 推理链记录
callback = ReActCallbackHandler(verbose=True)

# 循环检测
loop_detector = LoopDetectionCallback(max_same_action=3)

# 使用回调
result = await agent.executor.ainvoke(
    {"input": task.description},
    callbacks=[callback, loop_detector],
)
```

### 4. Prompt 模板

支持默认模板和角色特定模板。

```python
from src.react.prompts import (
    get_default_react_prompt,
    get_role_specific_prompt,
    get_custom_react_prompt,
)

# 默认模板
prompt = get_default_react_prompt()

# 角色特定模板
coder_prompt = get_role_specific_prompt("coder")

# 自定义模板
custom_prompt = get_custom_react_prompt(
    role_description="性能优化专家",
    responsibilities=["分析性能瓶颈", "优化代码"],
)
```

---

## 🏗️ 架构

```
┌─────────────────────────────────────────┐
│         ReActAgent (BaseAgent)          │
│  - 推理循环管理                           │
│  - 状态跟踪                               │
│  - 最大迭代控制                           │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│       LangChain AgentExecutor           │
│  - create_react_agent()                 │
│  - AgentExecutor                        │
│  - Prompt Template                      │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│          Tool Adapter Layer             │
│  - IntelliTeam → LangChain 工具转换     │
│  - 权限检查                              │
│  - 结果格式化                            │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│        Tool Registry (Existing)         │
│  - CodeTools, FileTools, GitTools...    │
└─────────────────────────────────────────┘
```

---

## 📂 文件结构

```
src/
  react/
    __init__.py              # 模块入口
    agent.py                 # ReActAgent 基类
    prompts.py               # Prompt 模板
    tool_adapter.py          # 工具适配器
    callbacks.py             # 回调处理器
    exceptions.py            # 自定义异常
    types.py                 # 类型定义
    README.md                # 本文档
  
  agents/
    react_coder.py           # ReAct Coder Agent
    react_tester.py          # ReAct Tester Agent
    react_architect.py       # ReAct Architect Agent

tests/
  test_react_agent.py        # 测试用例
```

---

## 🔧 配置参数

```python
from src.react import ReActConfig

config = ReActConfig(
    # 迭代控制
    max_iterations=15,              # 最大迭代次数
    max_execution_time=300.0,       # 最大执行时间（秒）
    
    # 错误处理
    handle_parsing_errors=True,     # 处理 LLM 输出解析错误
    early_stopping_method="generate",  # 提前停止方法
    
    # 循环检测
    enable_loop_detection=True,     # 启用循环检测
    max_same_action=3,              # 相同动作最大重复次数
    
    # 工具控制
    timeout_per_tool=30.0,          # 单个工具超时
    
    # 日志
    verbose=False,                  # 详细日志
    stream_output=False,            # 流式输出
)
```

---

## 📊 执行结果

```python
result = {
    "output": "最终答案",
    "reasoning_chain": [
        {
            "thought": "思考内容",
            "action": "工具名称",
            "action_input": {"param": "value"},
            "observation": "工具执行结果",
        },
        # ... 更多步骤
    ],
    "iterations": 5,
    "total_execution_time": 12.5,
    "success": True,
    "metadata": {...},
}
```

---

## 🧪 测试

```bash
# 运行所有测试
pytest tests/test_react_agent.py

# 运行特定测试
pytest tests/test_react_agent.py::test_react_agent_initialization

# 运行集成测试（需要真实 LLM）
pytest tests/test_react_agent.py -m integration
```

---

## 📖 最佳实践

### 1. 选择合适的迭代次数

- **简单任务**：5-10 次迭代
- **中等任务**：10-15 次迭代
- **复杂任务**：15-20 次迭代

### 2. 工具设计原则

- ✅ 描述清晰：明确说明工具的功能和输入输出
- ✅ 单一职责：每个工具只做一件事
- ✅ 错误处理：返回错误信息而不是抛出异常

### 3. 任务描述技巧

- ✅ 明确目标：清晰描述期望的结果
- ✅ 提供上下文：包含必要的背景信息
- ✅ 列出要求：明确技术要求和约束条件

---

## 🔍 监控和调试

### LangSmith 追踪

```python
import os

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-api-key"
os.environ["LANGCHAIN_PROJECT"] = "intelliteam-react"
```

访问 [LangSmith](https://smith.langchain.com) 查看详细的追踪信息。

---

## 📝 示例项目

查看 `docs/REACT_USAGE_GUIDE.md` 获取完整的示例代码和高级用法。

---

## 🤝 与现有系统集成

ReAct Agent 完全兼容现有的 IntelliTeam 系统：

- ✅ 共享工具系统（ToolRegistry）
- ✅ 共享 LLM 配置
- ✅ 共享黑板机制（Blackboard）
- ✅ 集成到工作流（LangGraph）

---

## 📚 参考资料

- [ReAct 论文](https://arxiv.org/abs/2210.03629)
- [LangChain ReAct 文档](https://python.langchain.com/docs/modules/agents/agent_types/react)
- [LangSmith 追踪](https://docs.smith.langchain.com/)

---

## 📄 许可证

MIT License

---

*版本: v1.0.0 | 创建时间: 2026-03-14 | 维护者: IntelliTeam*
