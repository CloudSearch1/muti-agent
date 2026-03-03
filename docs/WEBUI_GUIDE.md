# IntelliTeam Web UI 使用指南

> **基于 FastAPI + Vue 3 的现代化 Web 管理界面**

---

## 🚀 快速启动

### 方式 1: 使用启动脚本

```bash
# Windows
cd F:\ai_agent\webui
start.bat
```

### 方式 2: 命令行启动

```bash
cd F:\ai_agent
python webui\app.py
```

### 方式 3: 使用 CLI

```bash
cd F:\ai_agent
python cli.py webui
```

---

## 🌐 访问地址

启动后访问：
```
http://localhost:8080
```

---

## 📊 功能模块

### 1. 仪表盘 (Dashboard)
- 📊 系统统计卡片（任务数、活跃 Agent、完成率）
- 🤖 Agent 实时状态监控
- 📈 系统运行状态

### 2. Agent 团队
- 👥 查看所有 Agent 信息
- 📊 Agent 绩效统计
- 🎯 Agent 角色和职责

### 3. 任务管理
- 📋 任务列表展示
- ➕ 创建新任务
- ✏️ 编辑任务
- 🗑️ 删除任务
- 🏷️ 优先级和状态标签

### 4. 工作流
- 🔄 标准研发流程可视化
- 📊 工作流状态监控
- 🔗 流程节点展示

---

## 🎨 界面特性

### 现代化设计
- 🎨 Tailwind CSS 样式
- 📱 响应式布局
- 🌙 渐变配色方案
- ✨ 平滑过渡动画

### 交互式体验
- 🖱️ 悬停效果
- 🔄 标签切换
- 📊 实时数据展示
- 🎯 直观的状态指示

---

## 🔧 技术栈

### 后端
- **FastAPI** - 高性能 Web 框架
- **Uvicorn** - ASGI 服务器

### 前端
- **Vue 3** - 渐进式 JavaScript 框架
- **Tailwind CSS** - 原子化 CSS 框架
- **Chart.js** - 数据可视化库

---

## 📋 示例数据

Web UI 当前使用示例数据，后续将连接到真实 API：

### Agent 数据
```python
{
    "name": "Coder",
    "role": "代码工程师",
    "status": "busy",
    "tasksCompleted": 89,
    "avgTime": 8.2,
    "successRate": 94
}
```

### 任务数据
```python
{
    "id": 1,
    "title": "创建用户管理 API",
    "status": "in_progress",
    "priority": "high",
    "assignee": "张三",
    "agent": "Coder"
}
```

---

## 🔌 API 集成（待实现）

后续将集成真实 API：

### 获取 Agent 列表
```javascript
GET /api/v1/agents/
```

### 获取任务列表
```javascript
GET /api/v1/tasks/
```

### 创建任务
```javascript
POST /api/v1/tasks/
```

### 获取系统统计
```javascript
GET /api/v1/stats/
```

---

## 🎯 下一步开发

### Phase 5.2: Web UI 功能完善
- [ ] 连接真实 API
- [ ] 实时数据更新（WebSocket）
- [ ] 任务创建表单
- [ ] Agent 详情页面
- [ ] 工作流编辑器
- [ ] 日志查看器
- [ ] 系统设置页面

### Phase 5.3: 高级功能
- [ ] 图表可视化
- [ ] 数据导出
- [ ] 用户认证
- [ ] 权限管理
- [ ] 通知系统

---

## 📸 界面预览

### 仪表盘
- 4 个统计卡片
- Agent 状态网格
- 系统运行状态

### Agent 团队
- Agent 卡片展示
- 详细统计信息
- 角色和职责说明

### 任务管理
- 任务列表
- 优先级标签
- 状态标签
- 操作按钮

### 工作流
- 流程图可视化
- 节点状态
- 流程说明

---

## 🐛 故障排查

### Q: 无法访问 http://localhost:8080？
**A**: 检查：
1. Web UI 是否启动
2. 端口 8080 是否被占用
3. 防火墙设置

### Q: 页面显示空白？
**A**: 检查：
1. 浏览器控制台是否有错误
2. CDN 资源是否可访问
3. 尝试刷新页面（Ctrl+F5）

### Q: 样式不正常？
**A**: 确保：
1. Tailwind CSS CDN 可访问
2. 浏览器支持现代 CSS
3. 清除浏览器缓存

---

*IntelliTeam Web UI - 让管理更简单* 🚀
