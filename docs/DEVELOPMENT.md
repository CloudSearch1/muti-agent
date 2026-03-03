# IntelliTeam 开发文档

> **开发者指南和最佳实践**

---

## 📋 目录

1. [项目结构](#项目结构)
2. [开发环境](#开发环境)
3. [代码规范](#代码规范)
4. [测试指南](#测试指南)
5. [部署流程](#部署流程)

---

## 项目结构

```
intelliteam/
├── src/                      # 源代码
│   ├── agents/               # Agent 实现
│   ├── api/                  # REST API
│   ├── config/               # 配置管理
│   ├── core/                 # 核心模块
│   ├── db/                   # 数据库模型
│   ├── graph/                # LangGraph 工作流
│   ├── llm/                  # LLM 服务
│   ├── memory/               # 记忆系统
│   ├── tools/                # 工具系统
│   └── utils/                # 工具函数
├── tests/                    # 测试用例
├── webui/                    # Web 界面
├── docs/                     # 文档
└── scripts/                  # 工具脚本
```

---

## 开发环境

### 1. 安装依赖

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 开发依赖
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env 文件，填入配置
```

### 3. 启动开发服务器

```bash
# Web UI
python webui/app_complete.py

# API 服务
python src/main.py

# 测试
pytest tests/ -v
```

---

## 代码规范

### 1. 命名规范

```python
# 类名：大驼峰
class MyAgent(BaseAgent):
    pass

# 函数和变量：小写 + 下划线
def my_function():
    my_variable = "value"

# 常量：全大写
MAX_ITERATIONS = 10
```

### 2. 类型注解

```python
from typing import Optional, List, Dict

def process_task(
    task_id: str,
    priority: str = "normal",
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    pass
```

### 3. 文档字符串

```python
def my_function(param1: str, param2: int) -> bool:
    """
    函数说明
    
    Args:
        param1: 参数 1 说明
        param2: 参数 2 说明
        
    Returns:
        返回值说明
    """
    pass
```

---

## 测试指南

### 1. 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_utils.py -v

# 生成覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

### 2. 编写测试

```python
import pytest
from src.utils import my_function

def test_my_function():
    """测试函数"""
    result = my_function("input")
    assert result == "expected"
```

### 3. 测试规范

- 测试文件名：`test_*.py`
- 测试类名：`Test*`
- 测试函数名：`test_*`
- 每个测试独立运行
- 使用断言验证结果

---

## 部署流程

### 1. Docker 部署

```bash
# 构建镜像
docker build -t intelliteam .

# 运行容器
docker run -d -p 8080:8080 intelliteam
```

### 2. Docker Compose

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 3. 生产环境

```bash
# 使用生产配置
export APP_ENV=production
python src/main_prod.py
```

---

## Git 工作流

### 1. 分支管理

```bash
# 主分支
main

# 开发分支
develop

# 功能分支
feature/my-feature

# 修复分支
fix/my-bugfix
```

### 2. 提交规范

```bash
# 功能
feat: Add new feature

# 修复
fix: Fix bug

# 文档
docs: Update README

# 重构
refactor: Refactor code

# 测试
test: Add tests
```

### 3. 推送流程

```bash
# 提交更改
git add .
git commit -m "feat: Add feature"

# 推送到远程
git push origin feature/my-feature

# 创建 Pull Request
# 在 GitHub 上创建 PR 并合并
```

---

## 最佳实践

### 1. 错误处理

```python
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"操作失败：{e}")
    return default_value
```

### 2. 日志记录

```python
from src.utils import get_logger

logger = get_logger(__name__)

logger.info("信息日志")
logger.warning("警告日志")
logger.error("错误日志")
```

### 3. 配置管理

```python
from src.config import get_settings

settings = get_settings()
api_key = settings.openai_api_key
```

---

## 性能优化

### 1. 异步编程

```python
import asyncio

async def my_async_function():
    await asyncio.sleep(1)
    return "result"
```

### 2. 缓存

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def expensive_operation(data):
    return process(data)
```

### 3. 数据库优化

```python
# 使用连接池
# 添加索引
# 批量操作
```

---

## 安全建议

### 1. 密码安全

```python
from src.utils import hash_password

hashed = hash_password(password)
```

### 2. 输入验证

```python
from src.utils import is_valid_email, is_valid_url

if is_valid_email(user_input):
    process_email(user_input)
```

### 3. 环境变量

```bash
# 不要硬编码敏感信息
# 使用 .env 文件
# 添加到 .gitignore
```

---

*持续更新中...* 🚀
