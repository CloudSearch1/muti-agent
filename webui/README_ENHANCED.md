# IntelliTeam Web UI (增强版)

增强版 Web UI，提供完整的实时监控和管理功能。

## 🎨 新功能

### 1. 仪表盘
- 📊 实时系统统计（任务数、Agent、完成率）
- 📈 任务趋势图表（近 7 天）
- 🥧 Agent 任务分布图
- ⚡ Agent 实时状态监控

### 2. 任务管理
- 🔍 搜索 + 状态筛选
- ➕ 创建任务（完整表单）
- 👁️ 查看任务详情（含日志）
- ✏️ 编辑任务
- 🗑️ 删除任务
- 📊 进度跟踪

### 3. Agent 管理
- 🤖 6 个 Agent 实时状态
- 💪 负载监控（当前/最大）
- 📈 性能对比图表
- 📊 详细统计数据

### 4. 工作流可视化
- 🔄 动态流程图
- 🎨 步骤状态（已完成/进行中/待开始）
- 📊 进度条连接
- 📜 执行历史
- 🎚️ 3 种流程模板

### 5. 实时日志
- 📝 终端风格日志
- 🎨 级别颜色区分
- 🔍 级别筛选
- ⬇️ 自动滚动
- 📊 统计卡片

### 6. 全局功能
- 🔄 自动刷新（5 秒）
- 📱 响应式设计
- 🎨 现代化 UI

---

## 🚀 快速启动

### 方法 1: 直接运行（推荐）

```bash
cd /home/x24/.openclaw/workspace/muti-agent

# 启动增强版 Web UI 服务
python webui/server_enhanced.py
```

访问：
- 🌐 **Web UI**: http://localhost:3000
- 📚 **API 文档**: http://localhost:3000/docs
- 💚 **健康检查**: http://localhost:3000/api/v1/health

### 方法 2: 使用 CLI

```bash
python cli.py webui-enhanced
```

### 方法 3: 后台运行

```bash
nohup python webui/server_enhanced.py > webui.log 2>&1 &
```

---

## 📡 API 端点

### 系统 API
- `GET /api/v1/health` - 健康检查
- `GET /api/v1/stats` - 系统统计

### 任务 API
- `GET /api/v1/tasks` - 任务列表
- `GET /api/v1/tasks/{id}` - 任务详情
- `POST /api/v1/tasks` - 创建任务
- `PUT /api/v1/tasks/{id}` - 更新任务
- `DELETE /api/v1/tasks/{id}` - 删除任务
- `GET /api/v1/tasks/recent` - 最近任务

### Agent API
- `GET /api/v1/agents` - Agent 列表
- `GET /api/v1/agents/{name}` - Agent 详情
- `GET /api/v1/agents/{name}/stats` - Agent 统计

### 日志 API
- `GET /api/v1/logs` - 日志列表
- `POST /api/v1/logs` - 创建日志
- `GET /api/v1/logs/stats` - 日志统计
- `DELETE /api/v1/logs` - 清空日志

### 工作流 API
- `GET /api/v1/workflows` - 工作流列表
- `GET /api/v1/workflows/{id}` - 工作流详情
- `GET /api/v1/workflows/history` - 执行历史

---

## 🔧 配置

### 端口配置

编辑 `server_enhanced.py`:

```python
uvicorn.run(app, host="0.0.0.0", port=3000)
```

修改 `port` 参数即可。

### CORS 配置

默认允许所有来源访问，生产环境建议限制：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📊 数据说明

当前使用**内存数据库**（重启后数据清空），包含：

- **4 个预置任务**
- **6 个 Agent**
- **8 条示例日志**
- **3 个工作流模板**

### 对接真实后端

修改 `server_enhanced.py` 中的数据获取函数，替换为真实 API 调用：

```python
@app.get("/api/v1/tasks")
async def get_tasks():
    # 替换为真实数据库查询
    tasks = await database.query("SELECT * FROM tasks")
    return tasks
```

---

## 🎨 界面预览

### 仪表盘
- 4 个统计卡片
- 2 个图表（任务趋势 + Agent 分布）
- Agent 实时状态网格
- 最近任务列表

### 任务管理
- 搜索框 + 筛选器
- 任务卡片列表
- 创建任务弹窗
- 任务详情弹窗

### Agent 管理
- Agent 卡片网格（6 个）
- 负载进度条
- 性能对比柱状图

### 工作流
- 可视化流程图
- 步骤状态指示
- 执行历史列表

### 日志
- 深色终端风格
- 级别筛选
- 统计卡片

---

## 🔗 文件结构

```
webui/
├── index.html              # 经典版 UI
├── index_enhanced.html     # 增强版 UI（新）
├── server_enhanced.py      # 增强版 API 服务（新）
├── server.py               # 经典版服务
├── app.py                  # FastAPI 应用
├── app_complete.py         # 完整版应用
├── app_optimized.py        # 优化版应用
└── app_realtime.py         # 实时版应用
```

---

## 🧪 测试

### 测试 API

```bash
# 健康检查
curl http://localhost:3000/api/v1/health

# 获取统计
curl http://localhost:3000/api/v1/stats

# 获取任务列表
curl http://localhost:3000/api/v1/tasks

# 创建任务
curl -X POST http://localhost:3000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"测试任务","description":"测试描述","priority":"high"}'
```

### 测试 UI

浏览器访问：http://localhost:3000

---

## 📝 更新日志

### v1.0 (2026-03-05)
- ✅ 完整 API 对接
- ✅ 实时数据刷新
- ✅ 任务 CRUD 操作
- ✅ Agent 状态监控
- ✅ 工作流可视化
- ✅ 实时日志查看器
- ✅ 响应式设计

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

*Made with ❤️ by IntelliTeam*
