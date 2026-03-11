# IntelliTeam 快速启动指南

> **5 分钟快速上手 IntelliTeam**

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 方式 1: 使用 pip
pip install -r requirements.txt

# 方式 2: 使用 make
make install
```

### 2. 配置环境

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入 API Key
# OPENAI_API_KEY=sk-your-api-key
```

### 3. 启动服务

```bash
# 方式 1: 使用启动脚本
python start.py

# 方式 2: 使用 CLI
python cli.py start

# 方式 3: 使用 make
make start
```

### 4. 访问界面

- **Web UI**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

---

## 📋 基本使用

### 创建任务

```python
from src.graph import create_workflow

# 创建工作流
workflow = create_workflow()

# 执行任务
result = await workflow.run(
    task_id="task-001",
    task_title="创建用户管理 API",
    task_description="实现用户注册、登录、权限管理",
)
```

### 使用 CLI

```bash
# 创建任务
python cli.py create-task -t "新任务" -d "任务描述"

# 查看状态
python cli.py status

# 运行测试
python cli.py test
```

---

## 🛠️ 常用命令

### 开发

```bash
# 运行测试
make test

# 代码格式化
make format

# 代码检查
make lint

# 开发模式
make dev
```

### 部署

```bash
# 构建 Docker
make build

# 启动服务
make start

# 停止服务
make stop

# 查看日志
make logs
```

### 清理

```bash
# 清理缓存
make clean
```

---

## 📊 项目结构

```
intelliteam/
├── src/              # 源代码
├── webui/            # Web 界面
├── tests/            # 测试
├── examples/         # 示例
├── docs/             # 文档
├── cli.py            # CLI 工具
├── start.py          # 启动器
├── deploy.py         # 部署脚本
└── Makefile          # 构建配置
```

---

## 🤖 Agent 团队

| Agent | 职责 |
|-------|------|
| Planner | 任务规划 |
| Architect | 架构设计 |
| SeniorArchitect | 资深架构师 |
| Coder | 代码开发 |
| Tester | 测试 |
| DocWriter | 文档 |
| ResearchAgent | 研究分析 |

---

## 🔧 配置说明

### 环境变量

编辑 `.env` 文件：

```bash
# LLM 配置
OPENAI_API_KEY=sk-your-key
# 百炼 API 推荐使用 OpenAI 兼容模式
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen3.5-plus

# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/intelliteam
REDIS_URL=redis://localhost:6379/0

# API 配置
API_PORT=8000
```

---

## 📚 更多资源

- [完整文档](docs/)
- [示例代码](examples/)
- [API 参考](http://localhost:8000/docs)
- [GitHub](https://github.com/CloudSearch1/muti-agent)

---

## ❓ 常见问题

### Q: 如何重置环境？

```bash
make clean
make install
```

### Q: 如何查看日志？

```bash
# Docker 日志
make logs

# 文件日志
tail -f logs/intelliteam.log
```

### Q: 如何更新代码？

```bash
git pull
make clean
make install
make test
```

---

*开始使用 IntelliTeam 吧！* 🚀
