# IntelliTeam 快速开始 (统一版)

**最后更新**: 2026-03-12  
**版本**: v1.0  
**状态**: 统一版本

---

## 🚀 快速开始

### 前置要求

- Python 3.11+
- pip (Python 包管理器)
- Git (可选)

---

### 第 1 步: 安装依赖

```bash
# 克隆项目 (如尚未克隆)
git clone https://github.com/CloudSearch1/muti-agent.git
cd muti-agent

# 安装 Python 依赖
pip install -r requirements.txt
```

**验证安装**:
```bash
python --version  # 应显示 3.11+
pip list | grep fastapi  # 应显示 fastapi
```

---

### 第 2 步: 配置环境

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入必需配置
# 必需配置:
# - OPENAI_API_KEY: 你的 API 密钥
# - SECRET_KEY: 随机字符串 (用于 JWT)
# - DATABASE_URL: 数据库连接地址
# - REDIS_URL: Redis 连接地址
```

**配置文件位置**: `M:\AI Agent\muti-agent\.env`

**配置说明**: [详细配置指南](configuration.md)

---

### 第 3 步: 启动服务

#### 选项 A: 一键启动 (推荐)

```bash
# 启动所有服务 (API + Web UI)
python start.py
```

启动后访问:
- **API 文档**: http://localhost:8000/docs
- **Web UI**: http://localhost:8080
- **健康检查**: http://localhost:8000/health

#### 选项 B: 分别启动

```bash
# 启动 API 服务 (终端 1)
python cli.py start

# 启动 Web UI (终端 2)
python cli.py webui
```

#### 选项 C: 开发模式

```bash
# 启动 API 服务 (带热重载)
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 启动 Web UI (带热重载)
python -m uvicorn webui.app:app --host 0.0.0.0 --port 8080 --reload
```

---

### 第 4 步: 验证安装

#### 验证 API 服务

```bash
curl http://localhost:8000/health
```

**预期响应**:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-12T10:00:00",
  "version": "1.0.0"
}
```

#### 验证 Web UI

在浏览器中打开: http://localhost:8080

**预期结果**: 看到 IntelliTeam 管理界面

---

## 📋 基本使用

### 创建第一个任务

```python
import asyncio
from src.graph import create_workflow

async def main():
    # 创建工作流
    workflow = create_workflow()
    
    # 执行任务
    result = await workflow.run(
        task_id="my-first-task",
        task_title="创建 Hello World 函数",
        task_description="创建一个 Python 函数，输出 'Hello, IntelliTeam!'",
    )
    
    # 查看结果
    print(f"任务状态: {result.status}")
    print(f"完成步骤: {result.current_step}")

if __name__ == "__main__":
    asyncio.run(main())
```

**保存为**: `first_task.py`

**运行**:
```bash
python first_task.py
```

### 使用 CLI 工具

```bash
# 创建任务
python cli.py create-task \
  --title "用户管理系统" \
  --description "实现用户注册、登录、权限管理"

# 查看任务状态
python cli.py status

# 列出所有任务
python cli.py list-tasks

# 运行测试
python cli.py test
```

---

## 🔧 常用命令

### 开发命令

```bash
# 运行测试
python cli.py test

# 运行测试并生成覆盖率报告
python cli.py test --coverage

# 代码格式化
black src/ tests/

# 代码检查
ruff check src/ tests/

# 类型检查
mypy src/
```

### 部署命令

```bash
# 构建 Docker 镜像
docker build -t intelliteam .

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

---

## 🎯 下一步

- 📚 查看 [详细文档](..)
- 🎮 运行 [示例代码](../../examples/)
- 🔧 阅读 [配置指南](configuration.md)
- 🚀 了解 [部署方案](../deployment/)

---

## ❓ 常见问题

### Q: 启动时提示缺少依赖?

**A**: 确保已安装所有依赖:
```bash
pip install -r requirements.txt
```

### Q: 无法访问服务?

**A**: 检查:
1. 服务是否启动成功 (查看日志)
2. 端口是否被占用 ([端口配置](../getting-started/ports-config.md))
3. 防火墙设置

### Q: API 密钥无效?

**A**: 检查 `.env` 文件:
```bash
# 正确的格式
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# 错误的格式 (不要加引号)
OPENAI_API_KEY="sk-xxxxxxxx"  # ❌
```

### Q: 数据库连接失败?

**A**: 检查:
1. 数据库服务是否运行
2. 连接字符串是否正确
3. 用户名密码是否正确

---

## 🔗 相关资源

- [项目主页](../../README.md)
- [配置说明](configuration.md)
- [端口配置](../getting-started/ports-config.md)
- [部署指南](../deployment/)
- [故障排查](../operations/troubleshooting.md)

---

*最后更新: 2026-03-12*  
*文档版本: v1.0*  
*维护者: @IntelliTeam*
