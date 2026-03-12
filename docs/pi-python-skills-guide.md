# PI-Python Skills 系统详解

## 概述

PI-Python 的 Skills 系统是一个**基于 Markdown 的技能定义和加载框架**，允许用户通过简单的 Markdown 文件定义可复用的 AI 技能。

## 核心概念

### 什么是 Skill？

Skill（技能）是一组预定义的指令和步骤，用于指导 AI 完成特定任务。与 Tools（工具）不同：

| 对比项 | Skill | Tool |
|--------|-------|------|
| **定义方式** | Markdown 文件 | Python 代码 |
| **执行方式** | 提示词注入 | 函数调用 |
| **灵活性** | 高（自然语言） | 高（代码逻辑） |
| **适用场景** | 复杂任务流程 | 具体功能操作 |
| **示例** | 代码审查流程 | 文件读取/写入 |

### Skill 的组成部分

```python
@dataclass
class Skill:
    name: str              # 技能名称
    description: str       # 技能描述
    triggers: list[str]    # 触发关键词
    steps: list[str]       # 执行步骤
    examples: list[str]    # 使用示例
    path: Path | None      # 文件路径
    raw_content: str       # 原始内容
```

## 代码结构

### 1. Skill Loader (`skills/loader.py`)

负责从 Markdown 文件加载技能：

```python
from pi_python.skills import SkillLoader

# 加载单个技能
skill = SkillLoader.load(Path("skills/code_review/SKILL.md"))

# 发现目录中的所有技能
skill_files = SkillLoader.discover(Path("skills/"))
```

### 2. Skill Registry (`skills/registry.py`)

管理技能的注册和查询：

```python
from pi_python.skills import SkillRegistry

registry = SkillRegistry()

# 注册技能
registry.register(skill)

# 查找匹配的技能
skills = registry.find_matching("帮我审查代码")

# 获取技能
skill = registry.get("Code Review")
```

## 使用方法

### 1. 创建 Skill 文件

创建 `skills/my_skill/SKILL.md`：

```markdown
# 代码审查

## 描述

审查代码变更并提供改进建议。

## 触发

- 代码审查
- review
- 审查代码
- code review

## 步骤

1. 阅读提供的代码变更
2. 分析代码质量和潜在问题
3. 检查是否有安全漏洞
4. 提供改进建议
5. 生成审查报告

## 示例

- 请审查这段代码
- Review PR #123
- 帮我检查这个函数
```

### 2. 加载和使用 Skill

```python
from pi_python.skills import SkillLoader, SkillRegistry
from pi_python.agent import Agent

# 加载技能
skill = SkillLoader.load(Path("skills/code_review/SKILL.md"))

# 注册到 Agent
agent = Agent()
agent.skills.register(skill)

# 使用技能
response = await agent.prompt("请审查这段代码", skills=["Code Review"])
```

### 3. 在 Agent 中自动匹配

```python
from pi_python.agent import Agent

agent = Agent()

# 加载所有技能
for skill_file in SkillLoader.discover(Path("skills/")):
    skill = SkillLoader.load(skill_file)
    agent.skills.register(skill)

# 自动匹配并使用技能
response = await agent.prompt("帮我审查代码")  # 自动匹配 Code Review 技能
```

## 与 OpenClaw Skills 对比

| 特性 | PI-Python Skills | OpenClaw Skills |
|------|------------------|-----------------|
| **格式** | Markdown | Markdown |
| **位置** | `skills/` 目录 | `skills/` 目录 |
| **加载** | 动态加载 | 动态加载 |
| **触发** | 关键词匹配 | 关键词匹配 |
| **注入** | 系统提示词 | 系统提示词 |
| **标准** | Agent Skills | Agent Skills |

## 实际应用示例

### 示例 1: 代码审查技能

```python
from pi_python.skills import create_builtin_skills
from pi_python.agent import Agent

# 使用内置技能
skills = create_builtin_skills()

agent = Agent()
for skill in skills:
    agent.skills.register(skill)

# 触发代码审查
response = await agent.prompt("请审查这段代码：\n\ndef hello():\n    print('Hello')")
```

### 示例 2: 自定义技能

```python
from pi_python.skills import Skill, SkillLoader

# 创建自定义技能
custom_skill = Skill(
    name="API Design",
    description="设计 RESTful API",
    triggers=["API", "接口设计", "REST"],
    steps=[
        "分析需求",
        "设计资源路径",
        "定义请求/响应格式",
        "添加错误处理",
        "生成文档"
    ],
    examples=["帮我设计用户 API", "设计订单接口"]
)

# 保存到文件
skill_content = custom_skill.to_prompt()
Path("skills/api_design/SKILL.md").write_text(skill_content)
```

### 示例 3: 技能组合

```python
# 组合多个技能
skills = [
    SkillLoader.load(Path("skills/code_review/SKILL.md")),
    SkillLoader.load(Path("skills/debug/SKILL.md")),
    SkillLoader.load(Path("skills/docs/SKILL.md")),
]

agent = Agent(skills=skills)

# 根据用户输入自动选择技能
response = await agent.prompt("这段代码有 bug，帮我调试并生成文档")
```

## 高级用法

### 1. 技能优先级

```python
from pi_python.skills import SkillRegistry

registry = SkillRegistry()

# 注册带优先级的技能
registry.register(skill, priority=1)

# 高优先级技能优先匹配
```

### 2. 技能参数化

```markdown
# 代码审查

## 参数

- language: Python
- strict: true

## 步骤

1. 检查 {language} 代码规范
2. {'严格' if strict else '宽松'} 模式审查
```

### 3. 技能链

```python
# 串联多个技能
result1 = await agent.run_skill("Code Review", code)
result2 = await agent.run_skill("Generate Docs", result1)
result3 = await agent.run_skill("Create Tests", result2)
```

## 最佳实践

1. **命名规范**
   - 使用清晰的技能名称
   - 触发词要覆盖常见表达方式

2. **步骤设计**
   - 步骤要具体可执行
   - 避免过于复杂的嵌套

3. **示例丰富**
   - 提供多种表达方式的示例
   - 覆盖不同的使用场景

4. **文件组织**
   ```
   skills/
   ├── code_review/
   │   └── SKILL.md
   ├── debug/
   │   └── SKILL.md
   └── docs/
       └── SKILL.md
   ```

## 总结

PI-Python 的 Skills 系统提供了：

- ✅ **简单定义** - Markdown 格式，易于编写
- ✅ **动态加载** - 运行时加载和更新
- ✅ **自动匹配** - 基于关键词智能匹配
- ✅ **灵活扩展** - 支持自定义和组合

适用于需要**复杂任务流程**和**标准化操作**的场景，与 Tools 系统互补，共同构建强大的 AI Agent 能力。
