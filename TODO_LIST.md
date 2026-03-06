# TODO 清单 - 2026-03-06

_最后更新：2026-03-06 10:35_

---

## 📊 统计概览

| 类别 | TODO 数量 | 优先级 |
|------|-----------|--------|
| **Agent 核心功能** | 27 | 🔴 P1 |
| **LLM 封装层** | 7 | 🔴 P1 |
| **工具模块** | 9 | 🟡 P2 |
| **Web UI** | 2 | 🟢 P3 |
| **总计** | **45** | - |

---

## 🔴 P1 - 高优先级（34 个 TODO）

### 1. Agent 核心功能（27 个 TODO）

#### 1.1 Coder Agent（7 个 TODO）
**文件：** `src/agents/coder.py`

| 行号 | TODO 内容 | 建议实现 |
|------|-----------|----------|
| 181 | 替换为真实 LLM 调用 | 使用 `llm_generate()` |
| 196 | 生成真实代码 | 调用 LLM 生成实际代码 |
| 200 | 生成实际代码 | 实现代码生成逻辑 |
| 205 | 生成工具函数 | 实现工具函数生成 |
| 225 | 实现代码审查逻辑 | 添加代码质量检查 |
| 248 | 实现代码重构逻辑 | 实现重构算法 |
| 252 | 重构后的代码 | 返回实际重构代码 |

**实现示例：**
```python
async def generate_code(self, requirement: str) -> str:
    llm = get_llm()
    prompt = f"根据需求生成 Python 代码：{requirement}"
    return await llm.generate(prompt)
```

---

#### 1.2 Tester Agent（7 个 TODO）
**文件：** `src/agents/tester.py`

| 行号 | TODO 内容 | 建议实现 |
|------|-----------|----------|
| 106 | 调用 LLM API | 使用 `llm_generate()` |
| 145 | 替换为真实 LLM 调用 | 调用 LLM 生成测试 |
| 159 | 生成真实测试用例 | 实现测试生成逻辑 |
| 165 | 生成测试代码 | 生成实际测试代码 |
| 171 | 生成边界测试代码 | 实现边界测试生成 |
| 182 | 实现真实测试执行 | 集成 pytest |
| 239 | 实现回归测试生成 | 生成回归测试套件 |

**实现示例：**
```python
async def generate_tests(self, code: str) -> str:
    llm = get_llm()
    prompt = f"为以下代码生成 pytest 测试用例：\n{code}"
    return await llm.generate(prompt)
```

---

#### 1.3 DocWriter Agent（6 个 TODO）
**文件：** `src/agents/doc_writer.py`

| 行号 | TODO 内容 | 建议实现 |
|------|-----------|----------|
| 99 | 调用 LLM API | 使用 `llm_generate()` |
| 142 | 替换为真实 LLM 调用 | 调用 LLM 生成文档 |
| 183 | 生成真实文档 | 实现文档生成逻辑 |
| 244 | 实现 API 文档自动生成 | 解析代码生成 API 文档 |
| 269 | 实现知识库更新 | 更新文档索引 |
| 291 | 实现文档审查 | 检查文档质量 |

**实现示例：**
```python
async def generate_docs(self, code: str) -> str:
    llm = get_llm()
    prompt = f"为以下代码生成技术文档：\n{code}"
    return await llm.generate(prompt)
```

---

#### 1.4 Architect Agent（4 个 TODO）
**文件：** `src/agents/architect.py`

| 行号 | TODO 内容 | 建议实现 |
|------|-----------|----------|
| 182 | 替换为真实 LLM 调用 | 使用 `llm_generate()` |
| 232 | 生成组件图 | 使用 Mermaid/PlantUML |
| 233 | 生成时序图 | 使用 Mermaid/PlantUML |
| 252 | 实现架构评审逻辑 | 实现评审规则 |

**实现示例：**
```python
async def generate_component_diagram(self, design: dict) -> str:
    # 使用 Mermaid 语法生成组件图
    return f"""graph TD
    A[Client] --> B[API]
    B --> C[Database]
    """
```

---

#### 1.5 SeniorArchitect Agent（2 个 TODO）
**文件：** `src/agents/senior_architect.py`

| 行号 | TODO 内容 | 建议实现 |
|------|-----------|----------|
| 316 | 实现详细架构评审 | 实现评审检查清单 |
| 337 | 实现安全评审 | 实现安全检查规则 |

---

#### 1.6 Planner Agent（1 个 TODO）
**文件：** `src/agents/planner.py`

| 行号 | TODO 内容 | 建议实现 |
|------|-----------|----------|
| 316 | 实现完整的拓扑排序 | 实现任务依赖排序 |

**实现示例：**
```python
from collections import deque

def topological_sort(tasks: list) -> list:
    """拓扑排序实现任务依赖"""
    # Kahn's algorithm
    in_degree = {t.id: 0 for t in tasks}
    for t in tasks:
        for dep in t.dependencies:
            in_degree[dep] += 1
    
    queue = deque([t for t in tasks if in_degree[t.id] == 0])
    result = []
    
    while queue:
        task = queue.popleft()
        result.append(task)
        for dep in task.dependents:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)
    
    return result
```

---

### 2. LLM 封装层（7 个 TODO）

**文件：** `src/llm/llm_provider.py`

| 行号 | TODO 内容 | 优先级 | 建议实现 |
|------|-----------|--------|----------|
| 38 | 实现真实的 OpenAI API 调用 | 🔴 | 集成 openai 库 |
| 43 | 实现真实的 OpenAI JSON 调用 | 🔴 | 使用 function calling |
| 57 | 实现真实的 Claude API 调用 | 🔴 | 集成 anthropic 库 |
| 62 | 实现真实的 Claude JSON 调用 | 🔴 | 使用 tool use |
| 76 | 实现真实的百炼 API 调用 | 🟡 | 集成 dashscope 库 |
| 81 | 实现真实的百炼 JSON 调用 | 🟡 | 使用 function calling |

**实现示例（OpenAI）：**
```python
import openai

class OpenAIProvider(LLMProvider):
    async def generate(self, prompt: str, **kwargs) -> str:
        response = await openai.ChatCompletion.acreate(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response.choices[0].message.content
    
    async def generate_json(self, prompt: str, **kwargs) -> dict:
        import json
        response = await self.generate(
            f"请以 JSON 格式回答：{prompt}",
            **kwargs
        )
        return json.loads(response)
```

---

## 🟡 P2 - 中优先级（9 个 TODO）

### 3. 工具模块（9 个 TODO）

#### 3.1 Test Tools（3 个 TODO）
**文件：** `src/tools/test_tools.py`

| 行号 | TODO 内容 | 建议实现 |
|------|-----------|----------|
| 132 | 计算实际耗时 | 使用 `time.time()` |
| 149 | 集成 coverage.py | 集成 coverage 库 |
| 168 | 生成测试报告 | 生成 HTML/Markdown 报告 |

**实现示例：**
```python
import time
import coverage

async def run_tests(self, test_code: str) -> TestResult:
    start_time = time.time()
    
    # 运行测试
    result = pytest.main(["-v", test_code])
    
    duration_ms = (time.time() - start_time) * 1000
    
    # 生成覆盖率报告
    cov = coverage.Coverage()
    cov.start()
    # ... 运行代码 ...
    cov.stop()
    cov.html_report()
    
    return TestResult(duration_ms=duration_ms, ...)
```

---

#### 3.2 Code Tools（6 个 TODO）
**文件：** `src/tools/code_tools.py`

| 行号 | TODO 内容 | 建议实现 |
|------|-----------|----------|
| 94 | 集成真实格式化器 | 集成 black/ruff |
| 117 | 集成代码分析工具 | 集成 pylint/flake8 |
| 138 | 实现代码转换 | 实现代码转换逻辑 |
| 144 | 转换后的代码 | 返回实际转换代码 |
| 156 | 调用 LLM 生成代码 | 使用 `llm_generate()` |
| 160 | 生成的代码 | 返回实际生成代码 |

**实现示例：**
```python
import black

def format_code(code: str) -> str:
    """使用 black 格式化代码"""
    return black.format_str(code, mode=black.FileMode())

def analyze_code(code: str) -> dict:
    """使用 pylint 分析代码"""
    import pylint.lint
    from io import StringIO
    
    output = StringIO()
    pylint.lint.Run([code], reporter=pylint.reporters.text.TextReporter(output), exit=False)
    return {"issues": output.getvalue()}
```

---

## 🟢 P3 - 低优先级（2 个 TODO）

### 4. Web UI（2 个 TODO）

**文件：** `webui/app.py`

| 行号 | TODO 内容 | 建议实现 |
|------|-----------|----------|
| 63 | 集成 Redis 作为缓存后端 | 可选优化 |
| 480 | 替换为真实的 Agent 状态事件总线 | 需 P1 完成 |

**说明：**
- TODO 63: 当前内存缓存已够用，Redis 是生产环境优化选项
- TODO 480: 需要 Agent 核心功能完成后才能实现真实状态同步

---

### 5. LLM Service（1 个 TODO）

**文件：** `src/llm/service.py`

| 行号 | TODO 内容 | 建议实现 |
|------|-----------|----------|
| 265 | 实现流式调用 | 使用 SSE/WebSocket |

**实现示例：**
```python
async def generate_stream(self, prompt: str):
    """流式生成"""
    async for chunk in self.llm.generate_stream(prompt):
        yield chunk
```

---

## 📋 实施建议

### 第一阶段：核心功能（1-2 周）

**优先级：🔴 P1**

1. **实现真实 LLM API 调用**（7 个 TODO）
   - 集成 OpenAI API
   - 集成 Claude API
   - 集成阿里云百炼（可选）
   - 预计：2-3 天

2. **实现 Agent 核心功能**（27 个 TODO）
   - Coder: 代码生成（2 天）
   - Tester: 测试生成（2 天）
   - DocWriter: 文档生成（1 天）
   - Architect: 图表生成（2 天）
   - Planner: 拓扑排序（1 天）
   - 预计：8-10 天

**小计：34 个 TODO，预计 10-13 天**

---

### 第二阶段：工具完善（3-5 天）

**优先级：🟡 P2**

1. **Test Tools**（3 个 TODO）
   - 集成 coverage.py
   - 生成测试报告
   - 预计：1-2 天

2. **Code Tools**（6 个 TODO）
   - 集成 black/ruff
   - 集成代码分析工具
   - 预计：2-3 天

**小计：9 个 TODO，预计 3-5 天**

---

### 第三阶段：优化增强（可选）

**优先级：🟢 P3**

1. **Web UI 优化**（2 个 TODO）
   - Redis 缓存（可选）
   - Agent 状态事件总线
   - 预计：2-3 天

2. **流式调用**（1 个 TODO）
   - SSE/WebSocket 支持
   - 预计：1 天

**小计：3 个 TODO，预计 3-4 天（可选）**

---

## 📊 完成度评估

| 模块 | 总 TODO | 已完成 | 待完成 | 完成率 |
|------|---------|--------|--------|--------|
| Agent 核心 | 27 | 0 | 27 | 0% |
| LLM 封装 | 7 | 0 | 7 | 0% |
| 工具模块 | 9 | 0 | 9 | 0% |
| Web UI | 2 | 0 | 2 | 0% |
| **总计** | **45** | **0** | **45** | **0%** |

**注：** 框架已完成，待填充具体实现

---

## 🎯 关键路径

```
LLM API 集成 (7 TODO)
    ↓
Agent 核心功能 (27 TODO)
    ↓
工具完善 (9 TODO)
    ↓
Web UI 优化 (2 TODO)
```

**关键路径：** LLM API 集成 → Agent 核心功能

**最短完成时间：** 10-13 天（仅 P1）

---

## ✅ 验收标准

### P1 完成标准
- [ ] 所有 Agent 可调用真实 LLM API
- [ ] Coder 可生成可运行代码
- [ ] Tester 可生成并执行测试
- [ ] DocWriter 可生成文档
- [ ] Architect 可生成图表
- [ ] Planner 可正确排序任务

### P2 完成标准
- [ ] 测试覆盖率和报告
- [ ] 代码格式化和分析
- [ ] 代码转换功能

### P3 完成标准
- [ ] Redis 缓存（可选）
- [ ] 真实 Agent 状态同步
- [ ] 流式调用支持

---

## 📝 更新日志

- 2026-03-06 10:35 - 初始创建，统计 45 个 TODO
  - P1: 34 个（Agent 27 + LLM 7）
  - P2: 9 个（工具模块）
  - P3: 2 个（Web UI）

---

_文档创建时间：2026-03-06 10:35_
