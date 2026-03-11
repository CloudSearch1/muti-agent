# AI 聊天机器人技术文档

## 目录

1. [系统架构概览](#1-系统架构概览)
2. [前端技术栈和实现细节](#2-前端技术栈和实现细节)
3. [后端 API 设计](#3-后端-api-设计)
4. [前后端交互流程](#4-前后端交互流程)
5. [数据流图](#5-数据流图)
6. [关键代码说明](#6-关键代码说明)
7. [配置说明](#7-配置说明)
8. [错误处理机制](#8-错误处理机制)
9. [部署和运行说明](#9-部署和运行说明)

---

## 1. 系统架构概览

### 1.1 整体架构

AI 聊天机器人采用 **前后端分离** 的架构设计，基于现代 Web 技术栈构建：

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户界面 (Browser)                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Vue 3 + Tailwind CSS                    │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │    │
│  │  │  AI 助手页面  │  │  设置面板    │  │  文件浏览器  │     │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ HTTP/SSE/WebSocket
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      后端服务 (FastAPI)                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                      API 路由层                           │    │
│  │  /api/v1/chat  │  /api/v1/settings  │  /api/v1/models   │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   AI 提供商适配层                          │    │
│  │  Anthropic │ OpenAI │ DeepSeek │ 阿里云百炼 (Qwen)        │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    中间件层                               │    │
│  │  CORS │ GZip │ 缓存 │ WebSocket 管理器                    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ HTTP API
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     外部 AI 服务                                  │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │ Anthropic │  │  OpenAI   │  │ DeepSeek  │  │ 阿里云百炼  │    │
│  │  Claude   │  │   GPT     │  │           │  │   Qwen    │    │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 技术选型

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 前端框架 | Vue 3 | 3.4.21 | 响应式 UI 框架 |
| CSS 框架 | Tailwind CSS | Latest | 原子化 CSS |
| Markdown | Marked.js | Latest | Markdown 渲染 |
| 代码高亮 | Highlight.js | 11.9.0 | 语法高亮 |
| 后端框架 | FastAPI | Latest | 高性能异步框架 |
| HTTP 客户端 | httpx | Latest | 异步 HTTP 客户端 |
| 数据验证 | Pydantic | Latest | 数据模型验证 |

### 1.3 支持的 AI 提供商

系统支持以下 AI 服务提供商：

| 提供商 | 模型示例 | API 格式 | 特点 |
|--------|----------|----------|------|
| **阿里云百炼** | Qwen3.5 Plus, Qwen3 Max, Qwen3 Coder | OpenAI 兼容 | 国产首选，性价比高 |
| **Anthropic** | Claude Opus 4.6, Claude Sonnet 4.6 | Claude API | 最强推理能力 |
| **OpenAI** | GPT-4 Turbo, GPT-3.5 Turbo | OpenAI API | 生态完善 |
| **DeepSeek** | DeepSeek Chat, DeepSeek Coder | OpenAI 兼容 | 代码能力强 |

---

## 2. 前端技术栈和实现细节

### 2.1 文件结构

```
webui/
├── index_v5.html          # 主页面（包含 Vue 应用）
├── static/
│   ├── js/
│   │   ├── error-handler.js    # 错误处理工具
│   │   └── storage-service.js  # 本地存储服务
│   └── images/
└── manifest.json          # PWA 配置
```

### 2.2 Vue 3 应用结构

前端采用 Vue 3 的 **Options API** 风格，核心数据结构如下：

```javascript
// 文件: webui/index_v5.html

const app = Vue.createApp({
    data() {
        return {
            // AI 助手相关状态
            aiMessages: [],           // 消息列表
            aiInputMessage: '',       // 输入框内容
            aiLoading: false,         // 加载状态
            aiSessionId: 'session-' + Date.now(),  // 会话 ID

            // 系统设置
            settings: {
                aiProvider: 'bailian',     // AI 提供商
                model: 'qwen3.5-plus',     // 模型选择
                apiKey: '',                // API Key
                apiEndpoint: '',           // API 端点
                temperature: 0.7,          // 温度参数
                maxTokens: 4096,           // 最大 Token
                showApiKey: false,         // 是否显示 API Key
            },

            // 可用模型列表
            availableModels: {
                anthropic: ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5'],
                openai: ['gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
                deepseek: ['deepseek-chat', 'deepseek-coder'],
                bailian: ['qwen3.5-plus', 'qwen3-max-2026-01-23', 'qwen3-coder-next'],
            },

            // UI 状态
            currentTab: 'dashboard',
            showSettings: false,
            wsConnected: false,
        }
    },

    methods: {
        // 发送 AI 消息
        async sendAiMessage() { ... },

        // 快捷消息发送
        sendQuickAiMessage(message) { ... },

        // 渲染 Markdown
        renderAiMarkdown(content) { ... },

        // 清空聊天
        clearAiChat() { ... },
    },

    mounted() {
        // 初始化：加载设置、连接 WebSocket
        this.loadSettings();
        this.initWebSocket();
    }
});
```

### 2.3 AI 助手界面组件

AI 助手页面包含以下核心组件：

```html
<!-- 文件: webui/index_v5.html -->

<!-- AI 助手 Tab 页面 -->
<div v-if="currentTab === 'ai-assistant'" class="space-y-6">
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6 h-[calc(100vh-220px)]">

        <!-- 左侧：文件浏览器 -->
        <div class="lg:col-span-1 gh-card hidden lg:block overflow-hidden">
            <!-- 文件树组件 -->
        </div>

        <!-- 右侧：聊天区域 -->
        <div class="lg:col-span-3 gh-card flex flex-col overflow-hidden">

            <!-- 聊天头部 -->
            <div class="gh-card-header flex items-center gap-4">
                <div class="w-10 h-10 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg">
                    <i class="fas fa-robot text-white"></i>
                </div>
                <h3 class="font-semibold text-white">AI 助手</h3>
            </div>

            <!-- 消息区域 -->
            <div class="flex-1 overflow-y-auto p-4 space-y-4" ref="aiMessagesContainer">
                <!-- 消息列表 -->
                <div v-for="(msg, index) in aiMessages" :key="index">
                    <!-- 消息内容 -->
                </div>

                <!-- 加载指示器 -->
                <div v-if="aiLoading" class="flex gap-3">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>正在思考...</span>
                </div>
            </div>

            <!-- 输入区域 -->
            <div class="p-4 border-t border-gh-border bg-gh-canvas">
                <!-- 模型选择器 -->
                <div class="flex items-center gap-3 mb-3">
                    <select v-model="settings.aiProvider">...</select>
                    <select v-model="settings.model">...</select>
                </div>

                <!-- 输入框 -->
                <div class="flex gap-3">
                    <textarea v-model="aiInputMessage"
                              @keydown.enter.prevent="sendAiMessage"
                              placeholder="输入消息，按 Enter 发送...">
                    </textarea>
                    <button @click="sendAiMessage" :disabled="aiLoading">
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
```

### 2.4 设置面板

设置面板允许用户配置 AI 提供商和模型参数：

```html
<!-- 设置模态框 -->
<div v-if="showSettings" class="fixed inset-0 ...">
    <div class="bg-gh-canvas rounded-xl shadow-2xl w-full max-w-2xl">
        <!-- AI 提供商配置 -->
        <div class="space-y-4">
            <h4>AI 提供商配置</h4>

            <!-- 提供商选择 -->
            <select v-model="settings.aiProvider" @change="onProviderChange">
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="openai">OpenAI (GPT)</option>
                <option value="deepseek">DeepSeek</option>
                <option value="bailian">阿里云百炼 (Qwen)</option>
            </select>

            <!-- 模型选择 -->
            <select v-model="settings.model">
                <!-- 根据 provider 动态显示模型列表 -->
            </select>

            <!-- API Key 输入 -->
            <input v-model="settings.apiKey"
                   :type="settings.showApiKey ? 'text' : 'password'"
                   placeholder="输入 API Key">

            <!-- API Endpoint (可选) -->
            <input v-model="settings.apiEndpoint"
                   placeholder="自定义 API Endpoint">

            <!-- 模型参数 -->
            <input v-model.number="settings.temperature" type="range" min="0" max="1">
            <select v-model.number="settings.maxTokens">
                <option :value="1024">1024</option>
                <option :value="2048">2048</option>
                <option :value="4096">4096</option>
                <option :value="8192">8192</option>
            </select>
        </div>
    </div>
</div>
```

---

## 3. 后端 API 设计

### 3.1 API 端点列表

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/chat` | POST | AI 聊天接口（支持流式响应） |
| `/api/v1/settings` | GET/POST | 获取/保存系统设置 |
| `/api/v1/settings/models` | GET | 获取可用模型列表 |
| `/api/v1/settings/test` | POST | 测试 API 连接 |
| `/api/v1/chat/history/{session_id}` | GET | 获取聊天历史 |
| `/api/v1/chat/history/{session_id}` | DELETE | 清除聊天历史 |

### 3.2 聊天 API 详细设计

#### 请求模型

```python
# 文件: webui/app.py

from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: str      # user, assistant, system
    content: str   # 消息内容

class ChatRequest(BaseModel):
    """聊天请求模型"""
    messages: List[ChatMessage]   # 消息历史
    stream: bool = True           # 是否流式响应
    temperature: float = 0.7      # 温度参数
    max_tokens: int = 2048        # 最大 Token 数
    provider: Optional[str] = None    # AI 提供商
    model: Optional[str] = None       # 模型名称
    apiKey: Optional[str] = None      # API Key
    endpoint: Optional[str] = None    # API 端点
```

#### 响应格式

**流式响应 (SSE - Server-Sent Events)**:

```
data: {"content": "你好"}
data: {"content": "，"}
data: {"content": "我是"}
data: {"content": "AI"}
data: {"content": "助手"}
data: [DONE]
```

**非流式响应 (JSON)**:

```json
{
    "response": "你好，我是 AI 助手",
    "model": "qwen3.5-plus",
    "timestamp": "2026-03-11T10:30:00"
}
```

### 3.3 核心聊天处理函数

```python
# 文件: webui/app.py

async def generate_chat_response(
    messages: List[ChatMessage],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    provider: str = None,
    api_key: str = None,
    model: str = None,
    endpoint: str = None
) -> AsyncGenerator[str, None]:
    """
    生成聊天响应（流式）

    支持 Anthropic、OpenAI、DeepSeek 和阿里云百炼 API
    """

    # 从全局配置读取默认值
    if not provider:
        provider = SETTINGS_STORE.get("aiProvider", "bailian")
    if not api_key:
        api_key = SETTINGS_STORE.get("apiKey", "")
    if not model:
        model = SETTINGS_STORE.get("model", "qwen3.5-plus")

    # 根据提供商构建 API 请求
    if provider == "bailian":
        # 阿里云百炼 - 使用 OpenAI 兼容格式
        base_url = endpoint or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        api_url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

    elif provider == "anthropic":
        # Anthropic Claude API
        api_url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or "claude-sonnet-4-6",
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "stream": True
        }

    # 发送流式请求
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", api_url, headers=headers, json=payload) as response:
            async for chunk in response.aiter_lines():
                if chunk.startswith("data: "):
                    data = chunk[6:]
                    if data == "[DONE]":
                        yield "data: [DONE]\n\n"
                        return
                    # 解析并转发内容
                    parsed = json.loads(data)
                    content = extract_content(parsed, provider)
                    if content:
                        yield f"data: {json.dumps({'content': content})}\n\n"
```

### 3.4 设置 API

```python
# 文件: webui/app.py

# 设置存储（内存中）
SETTINGS_STORE: dict = {
    "aiProvider": "bailian",
    "apiKey": "",
    "model": "qwen3.5-plus",
    "temperature": 0.7,
    "maxTokens": 4096,
    "autoSave": True,
    "theme": "dark",
    "language": "zh-CN"
}

@app.get("/api/v1/settings")
async def get_settings():
    """获取系统设置"""
    return JSONResponse({
        "success": True,
        "settings": SETTINGS_STORE
    })

@app.post("/api/v1/settings")
async def save_settings(request: dict):
    """保存系统设置"""
    global SETTINGS_STORE
    new_settings = request["settings"]

    # 处理加密的 API Key
    if "apiKeyEncrypted" in new_settings:
        decrypted = decrypt_api_key(new_settings["apiKeyEncrypted"])
        if decrypted:
            new_settings["apiKey"] = decrypted

    SETTINGS_STORE.update(new_settings)
    return JSONResponse({
        "success": True,
        "message": "设置保存成功",
        "settings": SETTINGS_STORE
    })

@app.get("/api/v1/settings/models")
async def get_available_models():
    """获取可用的 AI 模型列表"""
    models = {
        "anthropic": [
            {"id": "claude-opus-4-6", "name": "Claude Opus 4.6"},
            {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"},
        ],
        "openai": [
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
        ],
        "bailian": [
            {"id": "qwen3.5-plus", "name": "Qwen3.5 Plus", "reasoning": True},
            {"id": "qwen3-max-2026-01-23", "name": "Qwen3 Max"},
        ]
    }
    return JSONResponse({"success": True, "models": models})
```

---

## 4. 前后端交互流程

### 4.1 发送消息流程

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  用户   │     │  前端   │     │  后端   │     │ AI API  │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │
     │ 输入消息      │               │               │
     │──────────────>│               │               │
     │               │               │               │
     │               │ POST /api/v1/chat             │
     │               │ (messages, stream=true)       │
     │               │──────────────>│               │
     │               │               │               │
     │               │               │ POST /chat/completions
     │               │               │ stream=true   │
     │               │               │──────────────>│
     │               │               │               │
     │               │               │ SSE chunks    │
     │               │               │<──────────────│
     │               │               │               │
     │               │ SSE chunks    │               │
     │               │<──────────────│               │
     │               │               │               │
     │ 显示响应      │               │               │
     │<──────────────│               │               │
     │               │               │               │
```

### 4.2 前端发送消息代码

```javascript
// 文件: webui/index_v5.html

async sendAiMessage() {
    const message = this.aiInputMessage.trim();
    if (!message || this.aiLoading) return;

    // 添加用户消息到列表
    this.aiMessages.push({
        role: 'user',
        content: message,
        time: new Date().toISOString()
    });
    this.aiInputMessage = '';
    this.aiLoading = true;

    try {
        // 发送 POST 请求
        const response = await fetch('/api/v1/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages: this.aiMessages,
                stream: true,
                // 使用设置中的 API 配置
                provider: this.settings.aiProvider,
                model: this.settings.model,
                apiKey: this.settings.apiKey,
                endpoint: this.settings.apiEndpoint,
                temperature: this.settings.temperature,
                max_tokens: this.settings.maxTokens
            })
        });

        // 添加 AI 回复占位
        this.aiMessages.push({ role: 'assistant', content: '', time: '' });
        const aiIndex = this.aiMessages.length - 1;

        // 读取流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6).trim();
                    if (data === '[DONE]') continue;

                    try {
                        const json = JSON.parse(data);
                        if (json.content) {
                            // 追加内容到 AI 消息
                            this.aiMessages[aiIndex].content += json.content;
                            this.$nextTick(() => this.scrollToBottom());
                        }
                        if (json.error) {
                            this.aiMessages[aiIndex].content += `\n⚠️ 错误: ${json.error}`;
                        }
                    } catch (e) {
                        // 非JSON数据，忽略
                    }
                }
            }
        }
    } catch (error) {
        console.error('聊天请求失败:', error);
        this.aiMessages.push({
            role: 'assistant',
            content: '抱歉，发生了错误。请检查网络连接或稍后重试。'
        });
    } finally {
        this.aiLoading = false;
    }
}
```

### 4.3 WebSocket 实时通信

系统使用 WebSocket 进行实时状态推送：

```python
# 文件: webui/app.py

class WebSocketManager:
    """WebSocket 连接管理器"""
    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}
        self.heartbeat_interval = 30  # 心跳间隔（秒）

    async def connect(self, websocket: WebSocket, client_id: int):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: int):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

websocket_manager = WebSocketManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时数据推送端点"""
    client_id = id(websocket)
    await websocket_manager.connect(websocket, client_id)

    try:
        while True:
            # 推送系统状态
            await websocket.send_json({
                "type": "system_status",
                "data": {
                    "activeAgents": len([a for a in AGENTS_DATA if a["status"] == "busy"]),
                    "totalTasks": len(TASKS_DATA),
                    "timestamp": datetime.now().isoformat()
                }
            })
            await asyncio.sleep(5)  # 5秒推送一次
    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
```

---

## 5. 数据流图

### 5.1 聊天数据流（文字描述）

```
用户输入消息
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 前端 Vue 应用                                                 │
│                                                              │
│  1. 将消息添加到 aiMessages 数组                              │
│  2. 构建 ChatRequest 对象                                     │
│     - messages: 聊天历史                                      │
│     - provider: AI 提供商 (bailian/anthropic/openai)         │
│     - model: 模型名称                                         │
│     - apiKey: API Key                                         │
│     - stream: true (启用流式响应)                             │
│  3. 发送 POST /api/v1/chat 请求                               │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI 后端                                                  │
│                                                              │
│  1. 验证请求参数                                              │
│  2. 从 SETTINGS_STORE 获取默认配置                            │
│  3. 调用 generate_chat_response() 生成器                     │
│  4. 构建 AI API 请求                                          │
│     - 根据 provider 选择 API 格式                             │
│     - 转换消息格式                                            │
│  5. 发送 HTTP 请求到 AI 服务                                  │
│  6. 以 SSE 格式流式返回响应                                   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ AI 服务提供商 (如阿里云百炼)                                   │
│                                                              │
│  1. 接收请求                                                  │
│  2. 处理消息，生成回复                                        │
│  3. 以 SSE 格式流式返回内容块                                 │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 响应返回流程                                                  │
│                                                              │
│  AI 服务 ──SSE chunks──> 后端 ──SSE chunks──> 前端           │
│                                                              │
│  前端处理:                                                    │
│  1. 使用 ReadableStream 读取响应                              │
│  2. 解析每行 "data: {...}" 格式                               │
│  3. 提取 content 字段                                         │
│  4. 追加到 aiMessages 数组中对应的 AI 消息                    │
│  5. 触发 Vue 响应式更新，渲染到界面                           │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 设置保存流程（文字描述）

```
用户修改设置
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 前端处理                                                      │
│                                                              │
│  1. 收集表单数据                                              │
│  2. API Key 加密 (Base64 + 反转)                              │
│     - 目的：防止明文传输                                       │
│  3. 发送 POST /api/v1/settings                                │
│     {                                                        │
│       settings: {                                            │
│         aiProvider: "bailian",                               │
│         model: "qwen3.5-plus",                               │
│         apiKeyEncrypted: "enc:...",                          │
│         temperature: 0.7                                     │
│       }                                                      │
│     }                                                        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 后端处理                                                      │
│                                                              │
│  1. 接收请求                                                  │
│  2. 解密 apiKeyEncrypted                                      │
│     - 去掉 "enc:" 前缀                                        │
│     - Base64 解码                                             │
│     - 反转字符串                                              │
│  3. 更新 SETTINGS_STORE                                       │
│  4. 返回成功响应                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. 关键代码说明

### 6.1 API Key 加密/解密

```python
# 文件: webui/app.py

import base64

def decrypt_api_key(encrypted: str) -> str:
    """
    解密前端加密的 API Key

    前端加密方式：反转 + Base64
    格式：enc:base64(反转的key)
    """
    if not encrypted:
        return ""
    try:
        # 去掉前缀
        if encrypted.startswith("enc:"):
            encrypted = encrypted[4:]

        # Base64 解码
        decoded = base64.b64decode(encrypted).decode('utf-8')

        # 反转回来
        return decoded[::-1]
    except Exception:
        return encrypted  # 解密失败返回原值
```

### 6.2 流式响应处理

```python
# 文件: webui/app.py

async def generate_chat_response(...) -> AsyncGenerator[str, None]:
    """生成流式聊天响应"""

    # 配置超时
    timeout_config = httpx.Timeout(
        connect=10.0,      # 连接超时 10 秒
        read=60.0,         # 读取超时 60 秒
        write=30.0,        # 写入超时 30 秒
        pool=10.0          # 连接池超时 10 秒
    )

    # 支持系统代理
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    async with httpx.AsyncClient(timeout=timeout_config, proxy=proxy) as client:
        async with client.stream("POST", api_url, headers=headers, json=payload) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                yield f"data: {json.dumps({'error': f'API错误: {error_text.decode()}'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            buffer = ""  # 处理不完整的行
            async for chunk_bytes in response.aiter_bytes():
                chunk_text = chunk_bytes.decode('utf-8')
                buffer += chunk_text

                # 按行分割处理
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()

                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            yield "data: [DONE]\n\n"
                            return
                        try:
                            chunk = json.loads(data)
                            # OpenAI 兼容格式
                            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield f"data: {json.dumps({'content': content})}\n\n"
                        except json.JSONDecodeError:
                            continue
```

### 6.3 Markdown 渲染

```javascript
// 文件: webui/index_v5.html

renderAiMarkdown(content) {
    if (!content) return '';

    // 配置 marked.js
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            highlight: function(code, lang) {
                if (typeof hljs !== 'undefined' && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {}
                }
                return code;
            },
            breaks: true,   // 支持 GFM 换行
            gfm: true       // GitHub Flavored Markdown
        });
        return marked.parse(content);
    }

    // 降级处理
    return content.replace(/\n/g, '<br>');
}
```

### 6.4 缓存实现

```python
# 文件: webui/app.py

class ResponseCache:
    """
    内存缓存实现（生产环境建议升级为 Redis）
    """
    def __init__(self, ttl_seconds: int = 60):
        self._cache: dict[str, dict] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> dict | None:
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() < entry['expires']:
                self._hits += 1
                return entry['data']
            # 过期数据清理
            del self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, data: dict):
        self._cache[key] = {
            'data': data,
            'expires': datetime.now() + self._ttl
        }

    def invalidate(self, key: str):
        if key in self._cache:
            del self._cache[key]

    def get_stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%"
        }

response_cache = ResponseCache(ttl_seconds=30)
```

---

## 7. 配置说明

### 7.1 后端配置

系统配置存储在 `src/config/settings.py` 中，使用 Pydantic Settings 管理：

```python
# 文件: src/config/settings.py

class LLMSettings(BaseSettings):
    """LLM 配置"""
    provider: str = "openai"
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 60

    # API Keys (通过环境变量设置)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    dashscope_api_key: str | None = None  # 阿里云百炼

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        extra="ignore"
    )
```

### 7.2 环境变量配置

创建 `.env` 文件：

```bash
# 应用配置
APP_ENV=development
APP_DEBUG=true

# LLM 配置
LLM_PROVIDER=bailian
LLM_MODEL=qwen3.5-plus
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

# API Keys
LLM_OPENAI_API_KEY=sk-...
LLM_ANTHROPIC_API_KEY=sk-ant-...
LLM_DASHSCOPE_API_KEY=sk-...

# 数据库配置
DB_URL=sqlite+aiosqlite:///./intelliteam.db

# Redis 配置
REDIS_ENABLED=false
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 7.3 API Endpoint 配置

各提供商的默认 API 端点：

| 提供商 | 默认 Endpoint | 说明 |
|--------|--------------|------|
| 阿里云百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 中国站 |
| 阿里云百炼 | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | 国际站 |
| Anthropic | `https://api.anthropic.com` | Claude API |
| OpenAI | `https://api.openai.com/v1` | GPT API |
| DeepSeek | `https://api.deepseek.com/v1` | DeepSeek API |

---

## 8. 错误处理机制

### 8.1 后端错误处理

```python
# 文件: webui/app.py

async def generate_chat_response(...) -> AsyncGenerator[str, None]:
    try:
        # ... 生成响应 ...

    except httpx.ConnectError as e:
        logger.error(f"网络连接失败: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': '网络连接失败，请检查网络或代理设置'})}\n\n"
        yield "data: [DONE]\n\n"

    except httpx.TimeoutException as e:
        logger.error(f"请求超时: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"AI 聊天错误: {e}", exc_info=True)
        error_msg = str(e)
        if "未配置" in error_msg:
            msg = '⚠️ LLM 服务未配置。请在设置中配置 API Key。'
        else:
            msg = f'❌ AI 聊天错误: {error_msg}'
        yield f"data: {json.dumps({'content': msg})}\n\n"
        yield "data: [DONE]\n\n"
```

### 8.2 前端错误处理

```javascript
// 文件: webui/index_v5.html

async sendAiMessage() {
    try {
        const response = await fetch('/api/v1/chat', { ... });

        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status}`);
        }

        // 处理流式响应...

    } catch (error) {
        console.error('聊天请求失败:', error);

        // 显示友好的错误消息
        this.aiMessages.push({
            role: 'assistant',
            content: '抱歉，发生了错误。请检查网络连接或稍后重试。',
            time: new Date().toISOString()
        });
    } finally {
        this.aiLoading = false;
    }
}
```

### 8.3 API 连接测试

```python
# 文件: webui/app.py

@app.post("/api/v1/settings/test")
async def test_ai_connection(request: dict):
    """测试 AI API 连接"""
    provider = request.get("provider", "anthropic")
    api_key = request.get("apiKey", "")
    endpoint = request.get("endpoint", "")

    if not api_key:
        return JSONResponse({
            "success": False,
            "error": "API Key 不能为空"
        })

    # 简单验证 API Key 格式
    valid_prefixes = {
        "anthropic": ["sk-ant-"],
        "openai": ["sk-"],
        "deepseek": ["sk-"],
        "bailian": ["sk-"]
    }

    prefixes = valid_prefixes.get(provider, ["sk-"])
    is_valid = any(api_key.startswith(p) for p in prefixes)

    if is_valid:
        return JSONResponse({
            "success": True,
            "message": f"{provider} API 连接成功"
        })
    else:
        return JSONResponse({
            "success": False,
            "error": f"无效的 {provider} API Key 格式"
        })
```

---

## 9. 部署和运行说明

### 9.1 开发环境启动

```bash
# 1. 克隆项目
git clone <repository_url>
cd muti-agent

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置 API Key

# 5. 启动 Web 服务
python -m uvicorn webui.app:app --reload --host 0.0.0.0 --port 8080

# 6. 访问界面
# 浏览器打开 http://localhost:8080
```

### 9.2 生产环境部署

```bash
# 使用 Gunicorn + Uvicorn
pip install gunicorn uvicorn[standard]

# 启动服务（4 个 worker）
gunicorn webui.app:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8080 \
    --timeout 120 \
    --keep-alive 5

# 或使用 uvicorn
uvicorn webui.app:app \
    --host 0.0.0.0 \
    --port 8080 \
    --workers 4 \
    --proxy-headers
```

### 9.3 Docker 部署

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "webui.app:app", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
# 构建镜像
docker build -t intelliteam-webui .

# 运行容器
docker run -d \
    --name intelliteam \
    -p 8080:8080 \
    -e LLM_DASHSCOPE_API_KEY=sk-xxx \
    intelliteam-webui
```

### 9.4 Nginx 反向代理配置

```nginx
# /etc/nginx/sites-available/intelliteam
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;
    }

    # WebSocket 支持
    location /ws {
        proxy_pass http://127.0.0.1:8080/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 9.5 健康检查

```bash
# 检查服务状态
curl http://localhost:8080/api/v1/health

# 响应示例
{
    "status": "ok",
    "timestamp": "2026-03-11T10:30:00",
    "version": "5.2.0",
    "features": {
        "logging": "unified",
        "api_docs": "enabled",
        "cache_stats": "enabled",
        "websocket_heartbeat": "enabled"
    }
}
```

---

## 附录

### A. API 文档访问

启动服务后，可通过以下地址访问 API 文档：

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
- **OpenAPI JSON**: http://localhost:8080/openapi.json

### B. 常见问题排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| API 401 错误 | API Key 无效 | 检查 API Key 是否正确，是否过期 |
| 连接超时 | 网络问题 | 检查网络连接，配置代理 |
| 流式响应中断 | Nginx 缓冲 | 禁用 proxy_buffering |
| WebSocket 断开 | 超时配置 | 增加 proxy_read_timeout |

### C. 性能优化建议

1. **启用 Redis 缓存**：替换内存缓存，支持分布式部署
2. **CDN 加速**：静态资源使用 CDN
3. **启用 Gzip**：FastAPI 已内置，确保开启
4. **连接池配置**：优化 httpx 连接池参数

---

*文档版本: 1.0*
*最后更新: 2026-03-11*
*作者: IntelliTeam 开发团队*