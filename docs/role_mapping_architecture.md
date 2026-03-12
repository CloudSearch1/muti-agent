# Agent 角色映射架构图

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户代码层                                 │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  container.create_agent_by_role(AgentRole.PLANNER)       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        容器层 (Container)                        │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  AgentContainer                                         │    │
│  │  ├─ create_agent_by_role()     创建 Agent              │    │
│  │  ├─ create_all_agents()        批量创建                │    │
│  │  ├─ get_agent_by_role()        获取 Agent (智能缓存)   │    │
│  │  └─ _agents: dict             Agent 实例缓存           │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    枚举层 (AgentRole Enum)                       │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  AgentRole (StrEnum)                                    │    │
│  │  ├─ PLANNER = "planner"                                 │    │
│  │  ├─ ARCHITECT = "architect"                             │    │
│  │  ├─ CODER = "coder"                                     │    │
│  │  ├─ TESTER = "tester"                                   │    │
│  │  ├─ DOC_WRITER = "doc_writer"                           │    │
│  │  ├─ RESEARCHER = "researcher"                           │    │
│  │  └─ SENIOR_ARCHITECT = "senior_architect"              │    │
│  │                                                          │    │
│  │  类方法:                                                 │    │
│  │  ├─ get_agent_class(role) → Agent 类                    │    │
│  │  ├─ get_all_roles() → 角色列表                          │    │
│  │  └─ from_string(str) → AgentRole                        │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 延迟导入
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Agent 类层 (Classes)                         │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  BaseAgent (抽象基类)                                   │    │
│  │  └─ 所有 Agent 的通用接口和基础功能                     │    │
│  └────────────────────────────────────────────────────────┘    │
│                              ▲                                   │
│                              │ 继承                              │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  具体 Agent 类:                                          │  │
│  │  ├─ PlannerAgent        ROLE = AgentRole.PLANNER        │  │
│  │  ├─ ArchitectAgent      ROLE = AgentRole.ARCHITECT      │  │
│  │  ├─ CoderAgent          ROLE = AgentRole.CODER          │  │
│  │  ├─ TesterAgent         ROLE = AgentRole.TESTER         │  │
│  │  ├─ DocWriterAgent      ROLE = AgentRole.DOC_WRITER     │  │
│  │  ├─ ResearchAgent       ROLE = AgentRole.RESEARCHER     │  │
│  │  └─ SeniorArchitectAgent ROLE = AgentRole.SENIOR_ARCHITECT │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 数据流图

### 创建 Agent 的流程

```
用户代码
   │
   ├─ container.create_agent_by_role(AgentRole.PLANNER)
   │
   ▼
AgentContainer
   │
   ├─ 调用 AgentRole.get_agent_class(AgentRole.PLANNER)
   │
   ▼
AgentRole.get_agent_class()
   │
   ├─ 延迟导入: from ..agents import PlannerAgent
   │
   ├─ 查找映射表: {AgentRole.PLANNER: PlannerAgent}
   │
   ▼
返回 PlannerAgent 类
   │
   ▼
AgentContainer
   │
   ├─ 调用 PlannerAgent(name="planner", **kwargs)
   │
   ├─ 注册到 _agents 字典
   │
   ▼
返回 PlannerAgent 实例
   │
   ▼
用户代码使用 Agent
```

### 获取 Agent 的流程（智能缓存）

```
用户代码
   │
   ├─ container.get_agent_by_role(AgentRole.PLANNER)
   │
   ▼
AgentContainer
   │
   ├─ 检查 _agents 字典
   │  │
   │  ├─ 已存在? ──Yes──> 返回缓存的实例
   │  │
   │  No
   │  │
   │  ▼
   │  检查 _agent_factories 字典
   │  │
   │  ├─ 已存在? ──Yes──> 调用工厂函数创建实例
   │  │                   │
   │  │                   └──> 缓存并返回
   │  │
   │  No
   │  │
   │  ▼
   │  调用 create_agent_by_role()
   │  │
   │  └──> 自动创建并缓存
   │
   ▼
返回 Agent 实例
```

## 角色映射关系表

```
┌─────────────────┬──────────────────────┬───────────────────────┐
│  AgentRole 枚举  │      Agent 类         │      角色描述         │
├─────────────────┼──────────────────────┼───────────────────────┤
│ PLANNER         │ PlannerAgent         │ 任务规划师            │
│ ARCHITECT       │ ArchitectAgent       │ 系统架构师            │
│ CODER           │ CoderAgent           │ 代码工程师            │
│ TESTER          │ TesterAgent          │ 测试工程师            │
│ DOC_WRITER      │ DocWriterAgent       │ 技术文档工程师        │
│ RESEARCHER      │ ResearchAgent        │ 研究助手              │
│ SENIOR_ARCHITECT│ SeniorArchitectAgent │ 资深架构师            │
└─────────────────┴──────────────────────┴───────────────────────┘
```

## 使用场景对比

### 传统方式（不推荐）

```
┌────────────────────────────────────────────────────────┐
│  用户代码需要手动判断和创建                            │
│                                                         │
│  if role == "planner":                                 │
│      agent = PlannerAgent()                            │
│  elif role == "coder":                                 │
│      agent = CoderAgent()                              │
│  elif role == "tester":                                │
│      agent = TesterAgent()                             │
│  # ... 需要在多处维护这个映射                          │
└────────────────────────────────────────────────────────┘
```

### 新方式（推荐）

```
┌────────────────────────────────────────────────────────┐
│  用户代码统一使用接口                                  │
│                                                         │
│  container = get_agent_container()                     │
│  agent = container.create_agent_by_role(role)          │
│                                                         │
│  # 或获取所有 Agent                                    │
│  agents = container.create_all_agents()                │
└────────────────────────────────────────────────────────┘
```

## 性能特性

### 延迟导入机制

```
启动时:
  └─ 不导入 Agent 类，快速启动

首次调用 get_agent_class():
  └─ 导入所需的 Agent 类

后续调用:
  └─ 使用缓存的映射关系，无需重复导入
```

### 智能缓存机制

```
┌────────────────────────────────────────────────────────┐
│  AgentContainer._agents 字典                          │
│                                                         │
│  {                                                     │
│    "planner": <PlannerAgent 实例>,                     │
│    "coder": <CoderAgent 实例>,                         │
│    "tester": <TesterAgent 实例>,                       │
│    ...                                                 │
│  }                                                     │
│                                                         │
│  特点:                                                 │
│  - 首次创建后缓存                                      │
│  - 后续访问直接返回                                    │
│  - 避免重复实例化                                      │
└────────────────────────────────────────────────────────┘
```

## 扩展流程

### 添加新角色的步骤

```
步骤 1: 在 AgentRole 中添加枚举值
  │
  ├─ class AgentRole(StrEnum):
  │      DATA_SCIENTIST = "data_scientist"
  │
  ▼
步骤 2: 创建新的 Agent 类
  │
  ├─ class DataScientistAgent(BaseAgent):
  │      ROLE = AgentRole.DATA_SCIENTIST
  │      # 实现抽象方法
  │
  ▼
步骤 3: 在 __init__.py 中导出
  │
  ├─ from .data_scientist import DataScientistAgent
  │  __all__.append("DataScientistAgent")
  │
  ▼
步骤 4: 更新映射表
  │
  ├─ def get_agent_class(cls, role):
  │      mapping = {
  │          ...,
  │          cls.DATA_SCIENTIST: DataScientistAgent,
  │      }
  │
  ▼
完成! 新角色可用
```

## 关键设计决策

### 1. 为什么使用延迟导入？

```
问题: 循环依赖
  └─ AgentRole 在 core.models
  └─ Agent 类在 agents 包
  └─ Agent 类需要引用 AgentRole
  └─ AgentRole 需要引用 Agent 类

解决: 延迟导入
  └─ get_agent_class() 方法内部导入
  └─ 只在需要时才导入
  └─ 打破循环依赖
```

### 2. 为什么映射表是硬编码的？

```
优点:
  ├─ 编译时检查
  ├─ 性能优异 (O(1) 查找)
  ├─ 代码清晰
  └─ 易于维护

缺点:
  └─ 需要手动更新

权衡:
  └─ Agent 类不会频繁变化
  └─ 硬编码带来的好处远大于灵活性
  └─ 如需动态注册，可使用容器的方法
```

### 3. 为什么使用枚举而非字符串？

```
枚举的优势:
  ├─ 类型安全 (编译时检查)
  ├─ 自动补全 (IDE 支持)
  ├─ 重构友好 (重命名安全)
  └─ 文档清晰 (值有明确的含义)

字符串的问题:
  ├─ 容易拼写错误
  ├─ 无编译时检查
  └─ 重构困难
```

## 总结

该架构设计提供了：

1. **清晰的分层** - 用户代码、容器层、枚举层、Agent 类层职责分明
2. **统一的接口** - 所有角色映射通过 `AgentRole` 枚举管理
3. **智能的缓存** - 容器自动管理 Agent 实例的生命周期
4. **灵活的扩展** - 添加新角色只需 4 个步骤
5. **优异的性能** - 延迟导入 + 智能缓存 + O(1) 查找

这是一个经过深思熟虑的设计，平衡了简洁性、可维护性、性能和扩展性。
