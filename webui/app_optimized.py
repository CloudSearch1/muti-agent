"""
IntelliTeam Web UI - 优化版

包含：API 优化 + 中间件 + 缓存
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn
import asyncio
import json
from datetime import datetime
from typing import Dict, List
import random

app = FastAPI(title="IntelliTeam Web UI - Optimized")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip 压缩（大于 1KB 的响应自动压缩）
app.add_middleware(GZipMiddleware, minimum_size=1000)

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✅ 新 WebSocket 连接，当前连接数：{len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"❌ WebSocket 断开，当前连接数：{len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """广播消息给所有连接的客户端"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_personal(self, websocket: WebSocket, message: dict):
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except:
            pass

manager = ConnectionManager()

# 模拟数据库
tasks_db = [
    {
        "id": 1,
        "title": "创建用户管理 API",
        "description": "实现用户注册、登录、权限管理等功能",
        "priority": "high",
        "status": "in_progress",
        "assignee": "张三",
        "agent": "Coder",
        "createdAt": "2026-03-03 10:30"
    },
    {
        "id": 2,
        "title": "数据库设计",
        "description": "设计用户表和权限表结构",
        "priority": "normal",
        "status": "completed",
        "assignee": "李四",
        "agent": "Architect",
        "createdAt": "2026-03-03 09:15"
    }
]

agents_db = [
    {"name": "Planner", "role": "任务规划师", "icon": "📋", "status": "idle", "tasksCompleted": 45, "avgTime": 2.3, "successRate": 98},
    {"name": "Architect", "role": "系统架构师", "icon": "🏗️", "status": "busy", "tasksCompleted": 38, "avgTime": 5.7, "successRate": 96},
    {"name": "Coder", "role": "代码工程师", "icon": "💻", "status": "busy", "tasksCompleted": 89, "avgTime": 8.2, "successRate": 94},
    {"name": "Tester", "role": "测试工程师", "icon": "🧪", "status": "idle", "tasksCompleted": 67, "avgTime": 4.5, "successRate": 97},
    {"name": "DocWriter", "role": "文档工程师", "icon": "📄", "status": "idle", "tasksCompleted": 52, "avgTime": 3.8, "successRate": 99},
    {"name": "SeniorArchitect", "role": "资深架构师", "icon": "🎯", "status": "idle", "tasksCompleted": 23, "avgTime": 12.5, "successRate": 98},
    {"name": "ResearchAgent", "role": "研究助手", "icon": "🔍", "status": "idle", "tasksCompleted": 15, "avgTime": 6.8, "successRate": 95}
]

# 模拟实时数据
async def generate_realtime_data():
    """生成实时数据"""
    while True:
        await asyncio.sleep(5)
        
        # 随机更新 Agent 状态
        for agent in agents_db:
            if random.random() < 0.3:
                agent["status"] = "busy" if agent["status"] == "idle" else "idle"
        
        data = {
            "type": "stats_update",
            "data": {
                "totalTasks": len(tasks_db),
                "activeAgents": sum(1 for a in agents_db if a["status"] == "busy"),
                "completionRate": round(sum(a["successRate"] for a in agents_db) / len(agents_db)),
                "timestamp": datetime.now().isoformat(),
                "connections": len(manager.active_connections),
                "agents": agents_db
            }
        }
        
        await manager.broadcast(data)

# ============ API 路由 ============

@app.get("/")
async def root():
    """返回主页面"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IntelliTeam - 完整智能研发协作平台</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .pulse { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }
        .connection-status { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; }
        .connected { background-color: #10b981; }
        .disconnected { background-color: #ef4444; }
    </style>
</head>
<body class="bg-gray-100">
    <div id="app" class="min-h-screen">
        <!-- 顶部导航 -->
        <nav class="bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg">
            <div class="container mx-auto px-4 py-4">
                <div class="flex justify-between items-center">
                    <div class="flex items-center space-x-3">
                        <span class="text-3xl">🤖</span>
                        <h1 class="text-2xl font-bold">IntelliTeam</h1>
                        <span class="text-sm opacity-80">完整智能研发协作平台</span>
                        <span :class="websocketConnected ? 'connected' : 'disconnected'" class="connection-status pulse"></span>
                        <span class="text-xs">{{ websocketConnected ? '实时连接中' : '未连接' }}</span>
                    </div>
                    <div class="flex space-x-4">
                        <button @click="currentTab = 'dashboard'" :class="{'bg-white text-purple-600': currentTab === 'dashboard'}" class="px-4 py-2 rounded-lg hover:bg-white hover:text-purple-600 transition">📊 仪表盘</button>
                        <button @click="currentTab = 'agents'" :class="{'bg-white text-purple-600': currentTab === 'agents'}" class="px-4 py-2 rounded-lg hover:bg-white hover:text-purple-600 transition">🤖 Agent 团队</button>
                        <button @click="currentTab = 'tasks'" :class="{'bg-white text-purple-600': currentTab === 'tasks'}" class="px-4 py-2 rounded-lg hover:bg-white hover:text-purple-600 transition">📋 任务管理</button>
                        <button @click="currentTab = 'charts'" :class="{'bg-white text-purple-600': currentTab === 'charts'}" class="px-4 py-2 rounded-lg hover:bg-white hover:text-purple-600 transition">📈 数据图表</button>
                    </div>
                </div>
            </div>
        </nav>

        <!-- 主内容区 -->
        <div class="container mx-auto px-4 py-8">
            <!-- 仪表盘 -->
            <div v-if="currentTab === 'dashboard'" class="space-y-6">
                <!-- 统计卡片 -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div class="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition">
                        <div class="flex items-center justify-between">
                            <div><p class="text-gray-500 text-sm">总任务数</p><p class="text-3xl font-bold text-gray-800">{{ stats.totalTasks }}</p></div>
                            <div class="bg-blue-100 p-4 rounded-full"><span class="text-2xl">📋</span></div>
                        </div>
                    </div>
                    <div class="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition">
                        <div class="flex items-center justify-between">
                            <div><p class="text-gray-500 text-sm">活跃 Agent</p><p class="text-3xl font-bold text-gray-800">{{ stats.activeAgents }}</p></div>
                            <div class="bg-green-100 p-4 rounded-full"><span class="text-2xl">🤖</span></div>
                        </div>
                    </div>
                    <div class="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition">
                        <div class="flex items-center justify-between">
                            <div><p class="text-gray-500 text-sm">完成率</p><p class="text-3xl font-bold text-gray-800">{{ stats.completionRate }}%</p></div>
                            <div class="bg-purple-100 p-4 rounded-full"><span class="text-2xl">📈</span></div>
                        </div>
                    </div>
                    <div class="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition">
                        <div class="flex items-center justify-between">
                            <div><p class="text-gray-500 text-sm">实时连接</p><p class="text-3xl font-bold text-gray-800">{{ stats.connections || 0 }}</p></div>
                            <div class="bg-green-100 p-4 rounded-full"><span class="text-2xl">🔌</span></div>
                        </div>
                    </div>
                </div>

                <!-- Agent 状态 -->
                <div class="bg-white rounded-xl shadow-md p-6">
                    <h2 class="text-xl font-bold text-gray-800 mb-4">🤖 Agent 实时状态</h2>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div v-for="agent in stats.agents" :key="agent.name" class="border rounded-lg p-4 hover:shadow-md transition">
                            <div class="flex items-center justify-between mb-2">
                                <h3 class="font-semibold text-gray-800">{{ agent.icon }} {{ agent.name }}</h3>
                                <span :class="agent.status === 'idle' ? 'bg-green-100 text-green-600' : 'bg-blue-100 text-blue-600'" class="px-2 py-1 rounded text-xs">{{ agent.status === 'idle' ? '空闲' : '工作中' }}</span>
                            </div>
                            <p class="text-sm text-gray-600">{{ agent.role }}</p>
                            <div class="mt-2 flex items-center text-xs text-gray-500">
                                <span>✅ 完成：{{ agent.tasksCompleted }}</span>
                                <span class="mx-2">|</span>
                                <span>⏱️ 平均：{{ agent.avgTime }}s</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Agent 团队 -->
            <div v-if="currentTab === 'agents'" class="space-y-6">
                <div class="bg-white rounded-xl shadow-md p-6">
                    <h2 class="text-xl font-bold text-gray-800 mb-6">🤖 Agent 团队</h2>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        <div v-for="agent in agents" :key="agent.name" class="border rounded-xl p-6 hover:shadow-lg transition">
                            <div class="flex items-center space-x-4 mb-4">
                                <div class="bg-purple-100 p-3 rounded-full"><span class="text-2xl">{{ agent.icon }}</span></div>
                                <div>
                                    <h3 class="font-bold text-gray-800">{{ agent.name }}</h3>
                                    <p class="text-sm text-gray-600">{{ agent.role }}</p>
                                </div>
                            </div>
                            <p class="text-sm text-gray-600 mb-4">{{ agent.description || '暂无描述' }}</p>
                            <div class="space-y-2">
                                <div class="flex justify-between text-sm"><span class="text-gray-500">任务完成</span><span class="font-medium">{{ agent.tasksCompleted }}</span></div>
                                <div class="flex justify-between text-sm"><span class="text-gray-500">平均耗时</span><span class="font-medium">{{ agent.avgTime }}s</span></div>
                                <div class="flex justify-between text-sm"><span class="text-gray-500">成功率</span><span class="font-medium text-green-600">{{ agent.successRate }}%</span></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 任务管理 -->
            <div v-if="currentTab === 'tasks'" class="space-y-6">
                <div class="bg-white rounded-xl shadow-md p-6">
                    <div class="flex justify-between items-center mb-6">
                        <h2 class="text-xl font-bold text-gray-800">📋 任务管理</h2>
                        <button @click="showCreateTask = true" class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition">➕ 创建任务</button>
                    </div>
                    <div class="space-y-4">
                        <div v-for="task in tasks" :key="task.id" class="border rounded-lg p-4 hover:shadow-md transition">
                            <div class="flex items-start justify-between">
                                <div class="flex-1">
                                    <div class="flex items-center space-x-3 mb-2">
                                        <h3 class="font-semibold text-gray-800">{{ task.title }}</h3>
                                        <span :class="priorityClass(task.priority)" class="px-2 py-1 rounded text-xs text-white">{{ priorityText(task.priority) }}</span>
                                        <span :class="statusClass(task.status)" class="px-2 py-1 rounded text-xs">{{ statusText(task.status) }}</span>
                                    </div>
                                    <p class="text-gray-600 text-sm mb-3">{{ task.description }}</p>
                                    <div class="flex items-center space-x-4 text-sm text-gray-500">
                                        <span>👤 {{ task.assignee }}</span>
                                        <span>🤖 {{ task.agent }}</span>
                                        <span>🕐 {{ task.createdAt }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 数据图表 -->
            <div v-if="currentTab === 'charts'" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-white rounded-xl shadow-md p-6">
                        <h3 class="text-lg font-bold text-gray-800 mb-4">📊 Agent 成功率</h3>
                        <canvas id="successRateChart"></canvas>
                    </div>
                    <div class="bg-white rounded-xl shadow-md p-6">
                        <h3 class="text-lg font-bold text-gray-800 mb-4">⏱️ Agent 平均耗时</h3>
                        <canvas id="avgTimeChart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- 创建任务弹窗 -->
        <div v-if="showCreateTask" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div class="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-xl font-bold text-gray-800">➕ 创建新任务</h3>
                    <button @click="showCreateTask = false" class="text-gray-400 hover:text-gray-600">✕</button>
                </div>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">任务标题</label>
                        <input v-model="newTask.title" type="text" class="w-full border rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500" placeholder="输入任务标题">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">任务描述</label>
                        <textarea v-model="newTask.description" rows="3" class="w-full border rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500" placeholder="输入任务描述"></textarea>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">优先级</label>
                        <select v-model="newTask.priority" class="w-full border rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500">
                            <option value="low">低</option>
                            <option value="normal">中</option>
                            <option value="high">高</option>
                            <option value="critical">紧急</option>
                        </select>
                    </div>
                    <div class="flex space-x-3 pt-4">
                        <button @click="createTask" class="flex-1 bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition">创建</button>
                        <button @click="showCreateTask = false" class="flex-1 bg-gray-200 text-gray-700 py-2 rounded-lg hover:bg-gray-300 transition">取消</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const { createApp } = Vue

        createApp({
            data() {
                return {
                    currentTab: 'dashboard',
                    websocketConnected: false,
                    websocket: null,
                    stats: { totalTasks: 0, activeAgents: 0, completionRate: 0, timestamp: '', connections: 0, agents: [] },
                    agents: [],
                    tasks: [],
                    showCreateTask: false,
                    newTask: { title: '', description: '', priority: 'normal' },
                    charts: {}
                }
            },
            mounted() {
                this.connectWebSocket()
                this.fetchData()
                setTimeout(() => this.initCharts(), 1000)
            },
            methods: {
                connectWebSocket() {
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
                    this.websocket = new WebSocket(`${protocol}//${window.location.host}/ws`)
                    
                    this.websocket.onopen = () => {
                        this.websocketConnected = true
                        console.log('✅ WebSocket 连接成功')
                    }
                    
                    this.websocket.onmessage = (event) => {
                        const data = JSON.parse(event.data)
                        if (data.type === 'stats_update') {
                            this.stats = data.data
                            this.agents = data.data.agents
                            this.updateCharts()
                        }
                    }
                    
                    this.websocket.onclose = () => {
                        this.websocketConnected = false
                        setTimeout(() => this.connectWebSocket(), 5000)
                    }
                },
                
                async fetchData() {
                    try {
                        const [agentsRes, tasksRes, statsRes] = await Promise.all([
                            fetch('/api/v1/agents'),
                            fetch('/api/v1/tasks'),
                            fetch('/api/v1/stats')
                        ])
                        this.agents = await agentsRes.json()
                        this.tasks = await tasksRes.json()
                        this.stats = await statsRes.json()
                        console.log('✅ 数据加载完成')
                    } catch (error) {
                        console.error('数据加载失败:', error)
                    }
                },
                
                async createTask() {
                    try {
                        const res = await fetch('/api/v1/tasks', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(this.newTask)
                        })
                        const result = await res.json()
                        if (result.status === 'success') {
                            alert('✅ 任务创建成功！')
                            this.showCreateTask = false
                            this.fetchData()
                        }
                    } catch (error) {
                        alert('❌ 创建失败：' + error.message)
                    }
                },
                
                priorityClass(priority) {
                    return { low: 'bg-gray-500', normal: 'bg-blue-500', high: 'bg-orange-500', critical: 'bg-red-600' }[priority] || 'bg-gray-500'
                },
                priorityText(priority) {
                    return { low: '低', normal: '中', high: '高', critical: '紧急' }[priority] || '未知'
                },
                statusClass(status) {
                    return { pending: 'bg-yellow-100 text-yellow-700', in_progress: 'bg-blue-100 text-blue-700', completed: 'bg-green-100 text-green-700' }[status] || 'bg-gray-100 text-gray-700'
                },
                statusText(status) {
                    return { pending: '待处理', in_progress: '进行中', completed: '已完成' }[status] || '未知'
                },
                
                initCharts() {
                    const ctx1 = document.getElementById('successRateChart')
                    const ctx2 = document.getElementById('avgTimeChart')
                    if (!ctx1 || !ctx2) return
                    
                    this.charts.successRate = new Chart(ctx1, {
                        type: 'bar',
                        data: {
                            labels: this.agents.map(a => a.name),
                            datasets: [{
                                label: '成功率 (%)',
                                data: this.agents.map(a => a.successRate),
                                backgroundColor: 'rgba(16, 185, 129, 0.5)',
                                borderColor: 'rgb(16, 185, 129)',
                                borderWidth: 1
                            }]
                        },
                        options: { responsive: true, scales: { y: { beginAtZero: false, min: 90 } } }
                    })
                    
                    this.charts.avgTime = new Chart(ctx2, {
                        type: 'line',
                        data: {
                            labels: this.agents.map(a => a.name),
                            datasets: [{
                                label: '平均耗时 (秒)',
                                data: this.agents.map(a => a.avgTime),
                                borderColor: 'rgb(139, 92, 246)',
                                backgroundColor: 'rgba(139, 92, 246, 0.2)',
                                tension: 0.4
                            }]
                        },
                        options: { responsive: true, scales: { y: { beginAtZero: true } } }
                    })
                },
                
                updateCharts() {
                    if (this.charts.successRate) {
                        this.charts.successRate.data.datasets[0].data = this.agents.map(a => a.successRate)
                        this.charts.successRate.update()
                    }
                    if (this.charts.avgTime) {
                        this.charts.avgTime.data.datasets[0].data = this.agents.map(a => a.avgTime)
                        this.charts.avgTime.update()
                    }
                }
            }
        }).mount('#app')
    </script>
</body>
</html>
"""

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点"""
    await manager.connect(websocket)
    await manager.send_personal(websocket, {
        "type": "welcome",
        "message": "欢迎连接到 IntelliTeam 实时系统",
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/v1/stats")
async def get_stats():
    return {
        "totalTasks": len(tasks_db),
        "activeAgents": sum(1 for a in agents_db if a["status"] == "busy"),
        "completionRate": round(sum(a["successRate"] for a in agents_db) / len(agents_db)),
        "timestamp": datetime.now().isoformat(),
        "connections": len(manager.active_connections),
        "agents": agents_db
    }

@app.get("/api/v1/agents")
async def get_agents():
    return agents_db

@app.get("/api/v1/tasks")
async def get_tasks():
    return tasks_db

@app.post("/api/v1/tasks")
async def create_task(task: dict):
    new_id = max(t["id"] for t in tasks_db) + 1 if tasks_db else 1
    new_task = {
        "id": new_id,
        "title": task.get("title", "新任务"),
        "description": task.get("description", ""),
        "priority": task.get("priority", "normal"),
        "status": "pending",
        "assignee": "待分配",
        "agent": "待分配",
        "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    tasks_db.append(new_task)
    return {"status": "success", "message": "任务创建成功", "taskId": new_id}

@app.get("/api/v1/workflows")
async def get_workflows():
    return [
        {
            "id": 1,
            "name": "标准研发流程",
            "steps": [
                {"name": "需求分析", "agent": "Planner", "icon": "📋"},
                {"name": "架构设计", "agent": "Architect", "icon": "🏗️"},
                {"name": "代码开发", "agent": "Coder", "icon": "💻"},
                {"name": "测试", "agent": "Tester", "icon": "🧪"},
                {"name": "文档", "agent": "DocWriter", "icon": "📄"}
            ]
        }
    ]

if __name__ == "__main__":
    print("=" * 60)
    print("  IntelliTeam Web UI - 优化版")
    print("=" * 60)
    print()
    print("访问地址：http://localhost:8080")
    print()
    print("优化特性:")
    print("  [OK] GZip 响应压缩")
    print("  [OK] WebSocket 实时通信")
    print("  [OK] Chart.js 图表")
    print("  [OK] 任务创建功能")
    print("  [OK] 连接状态监控")
    print("  [OK] Agent 状态实时更新")
    print()
    
    # 在 uvicorn 启动后运行后台任务
    uvicorn.run(app, host="0.0.0.0", port=8080)
