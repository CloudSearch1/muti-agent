"""
IntelliTeam Web UI

基于 FastAPI + Vue 3 的 Web 管理界面
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="IntelliTeam Web UI")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
try:
    app.mount("/static", StaticFiles(directory="webui/static"), name="static")
except:
    pass


@app.get("/", response_class=HTMLResponse)
async def root():
    """返回主页面"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IntelliTeam - 智能研发协作平台</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
                        <span class="text-sm opacity-80">智能研发协作平台</span>
                    </div>
                    <div class="flex space-x-4">
                        <button @click="currentTab = 'dashboard'" :class="{'bg-white text-purple-600': currentTab === 'dashboard'}" class="px-4 py-2 rounded-lg hover:bg-white hover:text-purple-600 transition">
                            📊 仪表盘
                        </button>
                        <button @click="currentTab = 'agents'" :class="{'bg-white text-purple-600': currentTab === 'agents'}" class="px-4 py-2 rounded-lg hover:bg-white hover:text-purple-600 transition">
                            🤖 Agent 团队
                        </button>
                        <button @click="currentTab = 'tasks'" :class="{'bg-white text-purple-600': currentTab === 'tasks'}" class="px-4 py-2 rounded-lg hover:bg-white hover:text-purple-600 transition">
                            📋 任务管理
                        </button>
                        <button @click="currentTab = 'workflows'" :class="{'bg-white text-purple-600': currentTab === 'workflows'}" class="px-4 py-2 rounded-lg hover:bg-white hover:text-purple-600 transition">
                            🔄 工作流
                        </button>
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
                            <div>
                                <p class="text-gray-500 text-sm">总任务数</p>
                                <p class="text-3xl font-bold text-gray-800">{{ stats.totalTasks }}</p>
                            </div>
                            <div class="bg-blue-100 p-4 rounded-full">
                                <span class="text-2xl">📋</span>
                            </div>
                        </div>
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
                                <p class="text-gray-500 text-sm">系统状态</p>
                                <p class="text-lg font-bold text-green-600">运行中</p>
                            </div>
                            <div class="bg-green-100 p-4 rounded-full">
                                <span class="text-2xl">✅</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Agent 状态 -->
                <div class="bg-white rounded-xl shadow-md p-6">
                    <h2 class="text-xl font-bold text-gray-800 mb-4">🤖 Agent 状态</h2>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div v-for="agent in agents" :key="agent.name" class="border rounded-lg p-4 hover:shadow-md transition">
                            <div class="flex items-center justify-between mb-2">
                                <h3 class="font-semibold text-gray-800">{{ agent.name }}</h3>
                                <span :class="agent.status === 'idle' ? 'bg-green-100 text-green-600' : 'bg-blue-100 text-blue-600'" class="px-2 py-1 rounded text-xs">
                                    {{ agent.status === 'idle' ? '空闲' : '工作中' }}
                                </span>
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

            <!-- 任务管理 -->
            <div v-if="currentTab === 'tasks'" class="space-y-6">
                <div class="bg-white rounded-xl shadow-md p-6">
                    <div class="flex justify-between items-center mb-6">
                        <h2 class="text-xl font-bold text-gray-800">📋 任务管理</h2>
                        <button class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition">
                            ➕ 创建任务
                        </button>
                    </div>
                    <div class="space-y-4">
                        <div v-for="task in tasks" :key="task.id" class="border rounded-lg p-4 hover:shadow-md transition">
                            <div class="flex items-start justify-between">
                                <div class="flex-1">
                                    <div class="flex items-center space-x-3 mb-2">
                                        <h3 class="font-semibold text-gray-800">{{ task.title }}</h3>
                                        <span :class="priorityClass(task.priority)" class="px-2 py-1 rounded text-xs text-white">
                                            {{ task.priorityText }}
                                        </span>
                                        <span :class="statusClass(task.status)" class="px-2 py-1 rounded text-xs">
                                            {{ task.statusText }}
                                        </span>
                                    </div>
                                    <p class="text-gray-600 text-sm mb-3">{{ task.description }}</p>
                                    <div class="flex items-center space-x-4 text-sm text-gray-500">
                                        <span>👤 {{ task.assignee }}</span>
                                        <span>🤖 {{ task.agent }}</span>
                                        <span>🕐 {{ task.createdAt }}</span>
                                    </div>
                                </div>
                                <div class="flex space-x-2">
                                    <button class="p-2 text-blue-600 hover:bg-blue-50 rounded">✏️</button>
                                    <button class="p-2 text-red-600 hover:bg-red-50 rounded">🗑️</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 工作流 -->
            <div v-if="currentTab === 'workflows'" class="space-y-6">
                <div class="bg-white rounded-xl shadow-md p-6">
                    <h2 class="text-xl font-bold text-gray-800 mb-6">🔄 工作流</h2>
                    <div class="border rounded-lg p-6">
                        <h3 class="font-bold text-gray-800 mb-4">标准研发流程</h3>
                        <div class="flex items-center justify-between">
                            <div class="flex-1 flex items-center">
                                <div class="text-center">
                                    <div class="bg-blue-100 p-3 rounded-full mb-2">
                                        <span class="text-xl">📋</span>
                                    </div>
                                    <p class="text-sm font-medium">需求分析</p>
                                    <p class="text-xs text-gray-500">Planner</p>
                                </div>
                                <div class="flex-1 mx-4">
                                    <span class="text-gray-400">→</span>
                                </div>
                            </div>
                            <div class="flex-1 flex items-center">
                                <div class="text-center">
                                    <div class="bg-purple-100 p-3 rounded-full mb-2">
                                        <span class="text-xl">🏗️</span>
                                    </div>
                                    <p class="text-sm font-medium">架构设计</p>
                                    <p class="text-xs text-gray-500">Architect</p>
                                </div>
                                <div class="flex-1 mx-4">
                                    <span class="text-gray-400">→</span>
                                </div>
                            </div>
                            <div class="flex-1 flex items-center">
                                <div class="text-center">
                                    <div class="bg-green-100 p-3 rounded-full mb-2">
                                        <span class="text-xl">💻</span>
                                    </div>
                                    <p class="text-sm font-medium">代码开发</p>
                                    <p class="text-xs text-gray-500">Coder</p>
                                </div>
                                <div class="flex-1 mx-4">
                                    <span class="text-gray-400">→</span>
                                </div>
                            </div>
                            <div class="flex-1 flex items-center">
                                <div class="text-center">
                                    <div class="bg-yellow-100 p-3 rounded-full mb-2">
                                        <span class="text-xl">🧪</span>
                                    </div>
                                    <p class="text-sm font-medium">测试</p>
                                    <p class="text-xs text-gray-500">Tester</p>
                                </div>
                                <div class="flex-1 mx-4">
                                    <span class="text-gray-400">→</span>
                                </div>
                            </div>
                            <div class="flex-1 flex items-center">
                                <div class="text-center">
                                    <div class="bg-red-100 p-3 rounded-full mb-2">
                                        <span class="text-xl">📄</span>
                                    </div>
                                    <p class="text-sm font-medium">文档</p>
                                    <p class="text-xs text-gray-500">DocWriter</p>
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
                    stats: {
                        totalTasks: 156,
                        activeAgents: 8,
                        completionRate: 93
                    },
                    agents: [
                        {
                            name: 'Planner',
                            role: '任务规划师',
                            icon: '📋',
                            description: '负责任务分解和优先级排序',
                            status: 'idle',
                            tasksCompleted: 45,
                            avgTime: 2.3,
                            successRate: 98
                        },
                        {
                            name: 'Architect',
                            role: '系统架构师',
                            icon: '🏗️',
                            description: '负责系统架构设计和技术选型',
                            status: 'busy',
                            tasksCompleted: 38,
                            avgTime: 5.7,
                            successRate: 96
                        },
                        {
                            name: 'Coder',
                            role: '代码工程师',
                            icon: '💻',
                            description: '负责代码实现和功能开发',
                            status: 'busy',
                            tasksCompleted: 89,
                            avgTime: 8.2,
                            successRate: 94
                        },
                        {
                            name: 'Tester',
                            role: '测试工程师',
                            icon: '🧪',
                            description: '负责测试用例和质量保障',
                            status: 'idle',
                            tasksCompleted: 67,
                            avgTime: 4.5,
                            successRate: 97
                        },
                        {
                            name: 'DocWriter',
                            role: '文档工程师',
                            icon: '📄',
                            description: '负责技术文档编写',
                            status: 'idle',
                            tasksCompleted: 52,
                            avgTime: 3.8,
                            successRate: 99
                        },
                        {
                            name: 'SeniorArchitect',
                            role: '资深架构师',
                            icon: '🎯',
                            description: '负责复杂系统设计和代码审查',
                            status: 'idle',
                            tasksCompleted: 23,
                            avgTime: 12.5,
                            successRate: 98
                        },
                        {
                            name: 'ResearchAgent',
                            role: '研究助手',
                            icon: '🔍',
                            description: '负责文献调研和技术分析',
                            status: 'idle',
                            tasksCompleted: 15,
                            avgTime: 6.8,
                            successRate: 95
                        }
                    ],
                    tasks: [
                        {
                            id: 1,
                            title: '创建用户管理 API',
                            description: '实现用户注册、登录、权限管理等功能',
                            priority: 'high',
                            priorityText: '高优先级',
                            status: 'in_progress',
                            statusText: '进行中',
                            assignee: '张三',
                            agent: 'Coder',
                            createdAt: '2026-03-03 10:30'
                        },
                        {
                            id: 2,
                            title: '数据库设计',
                            description: '设计用户表和权限表结构',
                            priority: 'normal',
                            priorityText: '中优先级',
                            status: 'completed',
                            statusText: '已完成',
                            assignee: '李四',
                            agent: 'Architect',
                            createdAt: '2026-03-03 09:15'
                        },
                        {
                            id: 3,
                            title: '编写测试用例',
                            description: '为 API 接口编写单元测试',
                            priority: 'normal',
                            priorityText: '中优先级',
                            status: 'pending',
                            statusText: '待处理',
                            assignee: '王五',
                            agent: 'Tester',
                            createdAt: '2026-03-03 11:00'
                        }
                    ]
                }
            },
            methods: {
                priorityClass(priority) {
                    const classes = {
                        low: 'bg-gray-500',
                        normal: 'bg-blue-500',
                        high: 'bg-orange-500',
                        critical: 'bg-red-600'
                    }
                    return classes[priority] || 'bg-gray-500'
                },
                statusClass(status) {
                    const classes = {
                        pending: 'bg-yellow-100 text-yellow-700',
                        in_progress: 'bg-blue-100 text-blue-700',
                        completed: 'bg-green-100 text-green-700',
                        failed: 'bg-red-100 text-red-700'
                    }
                    return classes[status] || 'bg-gray-100 text-gray-700'
                }
            }
        }).mount('#app')
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    print("=" * 60)
    print("  IntelliTeam Web UI")
    print("=" * 60)
    print()
    print("访问地址：http://localhost:8080")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8080)
