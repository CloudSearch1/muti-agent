"""
IntelliTeam Web UI - 实时更新版本

基于 FastAPI + Vue 3 + WebSocket 的实时 Web 管理界面
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import json
from datetime import datetime
from typing import Dict, List

app = FastAPI(title="IntelliTeam Web UI Realtime")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass
    
    async def send_personal(self, websocket: WebSocket, message: dict):
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except:
            pass

manager = ConnectionManager()

# 模拟实时数据
async def generate_realtime_data():
    """生成实时数据"""
    while True:
        await asyncio.sleep(5)  # 每 5 秒更新一次
        
        data = {
            "type": "stats_update",
            "data": {
                "totalTasks": 156 + len(manager.active_connections),
                "activeAgents": 8,
                "completionRate": 93,
                "timestamp": datetime.now().isoformat(),
                "connections": len(manager.active_connections)
            }
        }
        
        await manager.broadcast(data)

@app.get("/")
async def root():
    """返回主页面"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IntelliTeam - 实时智能研发协作平台</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.js"></script>
    <style>
        .pulse { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: .5; }
        }
        .connection-status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
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
                        <span class="text-sm opacity-80">实时智能研发协作平台</span>
                        <span :class="websocketConnected ? 'connected' : 'disconnected'" class="connection-status pulse"></span>
                        <span class="text-xs">{{ websocketConnected ? '实时连接中' : '未连接' }}</span>
                    </div>
                    <div class="flex space-x-4">
                        <button @click="currentTab = 'dashboard'" :class="{'bg-white text-purple-600': currentTab === 'dashboard'}" class="px-4 py-2 rounded-lg hover:bg-white hover:text-purple-600 transition">
                            📊 实时仪表盘
                        </button>
                        <button @click="currentTab = 'agents'" :class="{'bg-white text-purple-600': currentTab === 'agents'}" class="px-4 py-2 rounded-lg hover:bg-white hover:text-purple-600 transition">
                            🤖 Agent 团队
                        </button>
                    </div>
                </div>
            </div>
        </nav>

        <!-- 主内容区 -->
        <div class="container mx-auto px-4 py-8">
            <!-- 实时仪表盘 -->
            <div v-if="currentTab === 'dashboard'" class="space-y-6">
                <!-- 实时统计卡片 -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div class="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-500 text-sm">总任务数</p>
                                <p class="text-3xl font-bold text-gray-800">{{ stats.totalTasks }}</p>
                            </div>
                            <div class="bg-blue-100 p-4 rounded-full">
                                <span class="text-2xl">📋</span>
                            </div>
                        </div>
                        <div class="mt-4 text-xs text-gray-500">更新于：{{ stats.timestamp }}</div>
                    </div>

                    <div class="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-500 text-sm">活跃 Agent</p>
                                <p class="text-3xl font-bold text-gray-800">{{ stats.activeAgents }}</p>
                            </div>
                            <div class="bg-green-100 p-4 rounded-full">
                                <span class="text-2xl">🤖</span>
                            </div>
                        </div>
                    </div>

                    <div class="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-500 text-sm">完成率</p>
                                <p class="text-3xl font-bold text-gray-800">{{ stats.completionRate }}%</p>
                            </div>
                            <div class="bg-purple-100 p-4 rounded-full">
                                <span class="text-2xl">📈</span>
                            </div>
                        </div>
                    </div>

                    <div class="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-gray-500 text-sm">实时连接</p>
                                <p class="text-3xl font-bold text-gray-800">{{ stats.connections || 0 }}</p>
                            </div>
                            <div class="bg-green-100 p-4 rounded-full">
                                <span class="text-2xl">🔌</span>
                            </div>
                        </div>
                        <div class="mt-4 text-xs text-gray-500">WebSocket 连接数</div>
                    </div>
                </div>

                <!-- 实时日志 -->
                <div class="bg-white rounded-xl shadow-md p-6">
                    <h2 class="text-xl font-bold text-gray-800 mb-4">📡 实时日志</h2>
                    <div class="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm h-64 overflow-y-auto">
                        <div v-for="(log, index) in logs" :key="index" class="mb-1">
                            <span class="text-gray-500">[{{ log.time }}]</span>
                            <span :class="log.type === 'error' ? 'text-red-400' : 'text-green-400'">{{ log.message }}</span>
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
                                <div class="bg-purple-100 p-3 rounded-full">
                                    <span class="text-2xl">{{ agent.icon }}</span>
                                </div>
                                <div>
                                    <h3 class="font-bold text-gray-800">{{ agent.name }}</h3>
                                    <p class="text-sm text-gray-600">{{ agent.role }}</p>
                                </div>
                            </div>
                            <p class="text-sm text-gray-600 mb-4">{{ agent.description }}</p>
                            <div class="space-y-2">
                                <div class="flex justify-between text-sm">
                                    <span class="text-gray-500">任务完成</span>
                                    <span class="font-medium">{{ agent.tasksCompleted }}</span>
                                </div>
                                <div class="flex justify-between text-sm">
                                    <span class="text-gray-500">平均耗时</span>
                                    <span class="font-medium">{{ agent.avgTime }}s</span>
                                </div>
                                <div class="flex justify-between text-sm">
                                    <span class="text-gray-500">成功率</span>
                                    <span class="font-medium text-green-600">{{ agent.successRate }}%</span>
                                </div>
                            </div>
                        </div>
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
                    stats: {
                        totalTasks: 0,
                        activeAgents: 0,
                        completionRate: 0,
                        timestamp: '',
                        connections: 0
                    },
                    agents: [],
                    logs: []
                }
            },
            mounted() {
                this.connectWebSocket()
                this.fetchData()
            },
            methods: {
                connectWebSocket() {
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
                    this.websocket = new WebSocket(`${protocol}//${window.location.host}/ws`)
                    
                    this.websocket.onopen = () => {
                        this.websocketConnected = true
                        this.addLog('WebSocket 连接成功', 'success')
                    }
                    
                    this.websocket.onmessage = (event) => {
                        const data = JSON.parse(event.data)
                        if (data.type === 'stats_update') {
                            this.stats = data.data
                            this.addLog(`数据更新：${data.data.totalTasks} 个任务`, 'success')
                        }
                    }
                    
                    this.websocket.onclose = () => {
                        this.websocketConnected = false
                        this.addLog('WebSocket 连接断开，5 秒后重连...', 'error')
                        setTimeout(() => this.connectWebSocket(), 5000)
                    }
                    
                    this.websocket.onerror = () => {
                        this.addLog('WebSocket 错误', 'error')
                    }
                },
                
                async fetchData() {
                    try {
                        // 获取 Agent 数据
                        const agentsRes = await fetch('/api/v1/agents')
                        this.agents = await agentsRes.json()
                        this.addLog(`加载 ${this.agents.length} 个 Agent`, 'success')
                        
                        // 获取统计数据
                        const statsRes = await fetch('/api/v1/stats')
                        this.stats = await statsRes.json()
                        this.addLog('统计数据已加载', 'success')
                    } catch (error) {
                        this.addLog(`数据加载失败：${error.message}`, 'error')
                    }
                },
                
                addLog(message, type = 'info') {
                    const time = new Date().toLocaleTimeString()
                    this.logs.unshift({ time, message, type })
                    if (this.logs.length > 50) {
                        this.logs.pop()
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
    
    # 发送欢迎消息
    await manager.send_personal(websocket, {
        "type": "welcome",
        "message": "欢迎连接到 IntelliTeam 实时系统",
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        while True:
            # 接收客户端消息（心跳等）
            data = await websocket.receive_text()
            print(f"收到客户端消息：{data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({
            "type": "system",
            "message": "有用户断开连接",
            "connections": len(manager.active_connections)
        })

if __name__ == "__main__":
    print("=" * 60)
    print("  IntelliTeam Web UI - Realtime Version")
    print("=" * 60)
    print()
    print("访问地址：http://localhost:8080")
    print("WebSocket: ws://localhost:8080/ws")
    print()
    print("功能特性:")
    print("  ✅ 实时数据更新（每 5 秒）")
    print("  ✅ WebSocket 连接状态显示")
    print("  ✅ 实时日志查看")
    print("  ✅ 连接数统计")
    print()
    
    # 启动实时数据生成
    asyncio.create_task(generate_realtime_data())
    
    uvicorn.run(app, host="0.0.0.0", port=8080)
