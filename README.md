# IntelliTeam - 智能研发协作平台

<div align="center">

![IntelliTeam Logo](https://img.shields.io/badge/IntelliTeam-v1.0.0-purple)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Build](https://img.shields.io/badge/Build-Passing-brightgreen)

**多智能体协同平台 - 自动化软件研发全流程**

[文档](docs/) • [示例](examples/) • [API 文档](http://localhost:8000/docs)

</div>

---

## 🎯 项目简介

IntelliTeam 是一个创新的多智能体协同平台，通过 6 个专业 AI Agent 协同工作，自动化处理软件研发全流程：

```
需求澄清 → 任务拆解 → 架构设计 → 代码开发 → 测试 → 文档
```

### 核心特性

- 🤖 **6 个专业 Agent** - 规划师、架构师、程序员、测试员、文档员
- 🔄 **LangGraph 工作流** - 可视化流程编排
- 🧠 **知识增强** - RAG + 黑板系统
- 🔧 **MCP 工具集** - 10+ 实用工具
- 📊 **实时监控** - Prometheus 指标
- 🌐 **Web UI** - 现代化管理界面

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入 API Key
```

### 3. 启动服务

```bash
# 启动 API 服务
python start.py

# 或启动 Web UI
python cli.py webui
```

### 4. 访问界面

- **Web UI**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

---

## 🤖 Agent 团队

| Agent | 职责 | 状态 |
|-------|------|------|
| **Planner** | 任务规划与调度 | ✅ 就绪 |
| **Architect** | 系统架构设计 | ✅ 就绪 |
| **Coder** | 代码开发实现 | ✅ 就绪 |
| **Tester** | 测试用例生成 | ✅ 就绪 |
| **DocWriter** | 技术文档编写 | ✅ 就绪 |

---

## 📋 核心功能

### 任务管理

```python
from src.graph import create_workflow

# 创建工作流
workflow = create_workflow()

# 运行任务
result = await workflow.run(
    task_id="api-001",
    task_title="创建用户管理 API",
    task_description="实现用户注册、登录、权限管理",
)
```

### CLI 工具

```bash
# 启动服务
python cli.py start

# 创建任务
python cli.py create-task -t "新任务" -d "任务描述"

# 查看状态
python cli.py status

# 运行测试
python cli.py test --coverage
```

---

## 🏗️ 项目结构

```
intelliteam/
├── src/                      # 源代码
│   ├── api/                  # REST API
│   ├── agents/               # Agent 实现
│   ├── core/models/          # 数据模型
│   ├── tools/                # 工具系统
│   ├── memory/               # 记忆系统
│   ├── config/               # 配置
│   ├── llm/                  # LLM 服务
│   ├── graph/                # LangGraph 工作流
│   └── db/                   # 数据库
├── webui/                    # Web 界面
├── tests/                    # 测试套件
├── scripts/                  # 工具脚本
├── docs/                     # 文档
├── cli.py                    # CLI 工具
├── start.py                  # 启动器
└── requirements.txt          # 依赖
```

---

## 🧪 测试

```bash
# 运行所有测试
python cli.py test

# 生成覆盖率报告
python cli.py test --coverage

# 运行特定测试
pytest tests/test_agents.py -v
```

---

## 📊 测试报告

| 测试项 | 总数 | 通过 | 失败 | 通过率 |
|--------|------|------|------|--------|
| 核心功能 | 14 | 13 | 1 | 93% |
| Agent 系统 | 5 | 5 | 0 | 100% |
| 工具系统 | 7 | 7 | 0 | 100% |
| API 服务 | 2 | 2 | 0 | 100% |

---

## 🔧 配置说明

### 环境变量

```bash
# LLM 配置
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://coding.dashscope.aliyuncs.com/v1
OPENAI_MODEL=qwen3.5-plus

# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/intelliteam
REDIS_URL=redis://localhost:6379/0

# API 配置
API_HOST=0.0.0.0
API_PORT=8000
```

---

## 📚 文档

- [快速开始](QUICKSTART.md)
- [设计文档](docs/DESIGN.md)
- [部署指南](docs/DEPLOYMENT.md)
- [开发指南](docs/DEVELOPMENT.md)
- [路线图](ROADMAP.md)

---

## 🗺️ 路线图

### Phase 1-4 ✅ 已完成
- 核心框架
- 功能完善
- 生产就绪
- 全面测试

### Phase 5 🔄 进行中
- Web UI 界面
- CLI 工具
- 文档完善

### Phase 6-8 📋 计划中
- 功能增强
- 性能优化
- 企业级特性

详见 [ROADMAP.md](ROADMAP.md)

---

## 🤝 贡献

欢迎贡献代码！请查看 [贡献指南](CONTRIBUTING.md)。

### 开发环境设置

```bash
# Fork 项目
git clone https://github.com/your-username/intelliteam.git

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装开发依赖
pip install -r requirements.txt

# 运行测试
python cli.py test
```

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [FastAPI](https://github.com/tiangolo/fastapi)
- [Vue.js](https://github.com/vuejs/core)
- [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss)

---

<div align="center">

**IntelliTeam - 让研发更智能**

Made with ❤️ by IntelliTeam

</div>
