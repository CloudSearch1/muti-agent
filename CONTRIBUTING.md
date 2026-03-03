# 贡献指南

感谢你对 IntelliTeam 项目的关注！欢迎贡献代码！🎉

---

## 📋 目录

- [开发环境设置](#开发环境设置)
- [代码规范](#代码规范)
- [提交规范](#提交规范)
- [Pull Request 流程](#pull-request-流程)
- [测试要求](#测试要求)

---

## 开发环境设置

### 1. Fork 项目

```bash
# 在 GitHub 上 Fork 项目
# 然后克隆到本地
git clone https://github.com/your-username/intelliteam.git
cd intelliteam
```

### 2. 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. 安装开发依赖

```bash
# 安装依赖
pip install -r requirements.txt

# 安装开发工具
pip install black ruff mypy pre-commit
```

### 4. 配置 Git

```bash
# 添加上游仓库
git remote add upstream https://github.com/original-owner/intelliteam.git

# 安装 pre-commit 钩子
pre-commit install
```

---

## 代码规范

### Python 代码规范

遵循 [PEP 8](https://pep8.org/) 规范：

```python
# ✅ 好的代码
def calculate_total(items: list[float]) -> float:
    """计算总金额"""
    return sum(items)

# ❌ 不好的代码
def calc(l):
    return sum(l)
```

### 类型注解

所有函数必须添加类型注解：

```python
from typing import Optional

def get_user(user_id: str) -> Optional[dict]:
    """获取用户信息"""
    pass
```

### 文档字符串

所有公开函数和类必须添加文档字符串：

```python
class Agent:
    """Agent 基类"""
    
    async def execute(self, task: Task) -> dict:
        """
        执行任务
        
        Args:
            task: 要执行的任务
            
        Returns:
            执行结果
        """
        pass
```

### 代码格式化

使用 Black 格式化代码：

```bash
# 格式化所有 Python 文件
black src/ tests/

# 检查格式
black --check src/ tests/
```

使用 Ruff 检查代码：

```bash
# 检查代码
ruff check src/ tests/

# 自动修复
ruff check --fix src/ tests/
```

---

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

### 提交类型

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响代码运行）
- `refactor`: 重构（既不是新功能也不是修复）
- `test`: 测试相关
- `chore`: 构建过程或辅助工具变动

### 提交格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 示例

```bash
# 新功能
git commit -m "feat(agent): 添加新的 CoderAgent"

# Bug 修复
git commit -m "fix(api): 修复任务创建接口的参数验证"

# 文档更新
git commit -m "docs(readme): 更新快速开始指南"

# 重构
git commit -m "refactor(core): 优化 Agent 执行逻辑"
```

---

## Pull Request 流程

### 1. 创建分支

```bash
# 从 main 分支创建新分支
git checkout -b feature/your-feature-name

# 或修复分支
git checkout -b fix/issue-123
```

### 2. 开发并提交

```bash
# 开发完成后提交
git add .
git commit -m "feat: 实现新功能"
```

### 3. 同步上游代码

```bash
# 获取上游最新代码
git fetch upstream

# 变基到最新 main 分支
git rebase upstream/main
```

### 4. 推送分支

```bash
# 推送到远程
git push origin feature/your-feature-name
```

### 5. 创建 Pull Request

1. 在 GitHub 上访问你的 Fork
2. 点击 "Compare & pull request"
3. 填写 PR 描述
4. 等待代码审查

---

## 测试要求

### 1. 单元测试

所有新功能必须添加单元测试：

```python
# tests/test_new_feature.py
def test_new_feature():
    """测试新功能"""
    result = new_feature()
    assert result == expected
```

### 2. 运行测试

```bash
# 运行所有测试
python cli.py test

# 运行特定测试
pytest tests/test_new_feature.py -v

# 生成覆盖率报告
pytest --cov=src --cov-report=html
```

### 3. 测试覆盖率

- 新功能覆盖率必须 > 80%
- 核心模块覆盖率必须 > 90%

---

## 代码审查清单

提交 PR 前请确认：

- [ ] 代码已格式化（Black）
- [ ] 代码检查通过（Ruff）
- [ ] 类型注解完整（MyPy）
- [ ] 单元测试通过
- [ ] 测试覆盖率达标
- [ ] 文档已更新
- [ ] 提交信息规范

---

## 常见问题

### Q: 如何贡献文档？

直接修改 `docs/` 目录下的 Markdown 文件，无需复杂流程。

### Q: 如何报告 Bug？

在 GitHub Issues 中创建 Issue，使用 Bug Report 模板。

### Q: 如何提议新功能？

在 GitHub Issues 中创建 Issue，使用 Feature Request 模板。

---

## 联系方式

- GitHub Issues: [提交问题](https://github.com/intelliteam/intelliteam/issues)
- 邮箱：team@intelliteam.ai

---

感谢你的贡献！🎉
