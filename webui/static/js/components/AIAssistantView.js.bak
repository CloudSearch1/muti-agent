/**
 * AI 助手视图组件 - 完整版
 * 支持聊天、Agent 选择、任务管理、WebSocket 实时通信
 */

import { formatDate } from '../utils/format.js';
import { api } from '../utils/api.js';

// 简单的 Markdown 渲染
function renderMarkdown(content) {
    if (!content) return '';
    return content
        .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre class="bg-gh-bg p-3 rounded-md my-2 overflow-x-auto"><code>$2</code></pre>')
        .replace(/`([^`]+)`/g, '<code class="bg-gh-bg px-1.5 py-0.5 rounded text-sm">$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}

export default {
    name: 'AIAssistantView',
    
    props: {
        settings: {
            type: Object,
            default: () => ({})
        }
    },
    
    template: `
        <div class="h-[calc(100vh-180px)] flex gap-6">
            <!-- 左侧边栏：Agent 列表 -->
            <div class="w-72 gh-card flex flex-col">
                <div class="gh-card-header flex items-center justify-between">
                    <span class="flex items-center gap-2 text-sm">
                        <i class="fas fa-users text-gh-blue"></i>
                        Agent 团队
                    </span>
                    <span class="text-xs text-gh-text">{{ agents.filter(a => a.status === 'busy').length }} 忙碌</span>
                </div>
                <div class="flex-1 overflow-y-auto p-2 space-y-2">
                    <!-- Agent 选择卡片 -->
                    <div v-for="agent in agents" :key="agent.name"
                         @click="selectAgent(agent)"
                         :class="['p-3 rounded-lg cursor-pointer transition border',
                                  selectedAgent?.name === agent.name 
                                    ? 'bg-gh-blue/20 border-gh-blue text-white' 
                                    : 'bg-gh-canvas border-gh-border hover:border-gh-blue/50']">
                        <div class="flex items-center gap-3">
                            <div :class="['w-10 h-10 rounded-lg flex items-center justify-center',
                                          selectedAgent?.name === agent.name ? 'bg-gh-blue' : 'bg-gh-elevated']">
                                <i :class="[agent.icon, selectedAgent?.name === agent.name ? 'text-white' : 'text-gh-text']"></i>
                            </div>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2">
                                    <span class="font-medium text-sm truncate">{{ agent.name }}</span>
                                    <span :class="['w-2 h-2 rounded-full', agent.status === 'busy' ? 'bg-gh-green animate-pulse' : 'bg-gh-text']"></span>
                                </div>
                                <p class="text-xs text-gh-text truncate">{{ agent.role }}</p>
                            </div>
                        </div>
                        <div class="mt-2 flex items-center gap-4 text-xs text-gh-text">
                            <span><i class="fas fa-check-circle mr-1"></i>{{ agent.tasksCompleted }}</span>
                            <span><i class="fas fa-clock mr-1"></i>{{ agent.avgTime }}min</span>
                            <span><i class="fas fa-percent mr-1"></i>{{ agent.successRate }}%</span>
                        </div>
                    </div>
                </div>
                
                <!-- 新建任务按钮 -->
                <div class="p-3 border-t border-gh-border">
                    <button @click="showNewTaskModal = true" 
                            class="w-full py-2.5 bg-gh-green hover:bg-gh-green/90 text-white rounded-lg font-medium transition flex items-center justify-center gap-2">
                        <i class="fas fa-plus"></i>
                        新建任务
                    </button>
                </div>
            </div>
            
            <!-- 聊天区域 -->
            <div class="flex-1 gh-card flex flex-col">
                <!-- 聊天头部 -->
                <div class="gh-card-header flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-full bg-gradient-to-br from-gh-blue to-gh-purple flex items-center justify-center">
                            <i class="fas fa-robot text-white"></i>
                        </div>
                        <div>
                            <h3 class="font-semibold text-white">AI 助手</h3>
                            <p class="text-xs text-gh-text flex items-center gap-1">
                                <span :class="['w-2 h-2 rounded-full', wsConnected ? 'bg-gh-green' : 'bg-gh-text']"></span>
                                {{ wsConnected ? '实时连接' : '离线' }}
                                <span v-if="selectedAgent" class="ml-2 px-2 py-0.5 bg-gh-blue/20 text-gh-blue rounded-full text-xs">
                                    {{ selectedAgent.name }}
                                </span>
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <button @click="exportChat" class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-white hover:bg-gh-elevated transition" title="导出对话">
                            <i class="fas fa-download text-sm"></i>
                        </button>
                        <button @click="clearChat" class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-white hover:bg-gh-elevated transition" title="清空对话">
                            <i class="fas fa-trash-alt text-sm"></i>
                        </button>
                        <button @click="showSettings = true" class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-white hover:bg-gh-elevated transition" title="设置">
                            <i class="fas fa-cog text-sm"></i>
                        </button>
                    </div>
                </div>
                
                <!-- 消息列表 -->
                <div ref="messageContainer" class="flex-1 overflow-y-auto p-4 space-y-4">
                    <!-- 空状态 -->
                    <div v-if="messages.length === 0" class="h-full flex flex-col items-center justify-center text-gh-text">
                        <div class="w-20 h-20 rounded-full bg-gh-elevated flex items-center justify-center mb-4">
                            <i class="fas fa-robot text-3xl text-gh-blue"></i>
                        </div>
                        <p class="text-lg font-medium text-white mb-2">有什么可以帮您的？</p>
                        <p class="text-sm mb-4">我可以帮您编写代码、解答问题、分析项目等</p>
                        <div class="flex gap-2 flex-wrap justify-center">
                            <button @click="quickAsk('帮我分析这段代码')" class="px-3 py-1.5 bg-gh-elevated hover:bg-gh-blue/20 text-gh-text hover:text-gh-blue rounded-lg text-sm transition">
                                代码分析
                            </button>
                            <button @click="quickAsk('帮我创建一个新功能')" class="px-3 py-1.5 bg-gh-elevated hover:bg-gh-blue/20 text-gh-text hover:text-gh-blue rounded-lg text-sm transition">
                                功能开发
                            </button>
                            <button @click="quickAsk('帮我写测试用例')" class="px-3 py-1.5 bg-gh-elevated hover:bg-gh-blue/20 text-gh-text hover:text-gh-blue rounded-lg text-sm transition">
                                编写测试
                            </button>
                            <button @click="quickAsk('帮我优化性能')" class="px-3 py-1.5 bg-gh-elevated hover:bg-gh-blue/20 text-gh-text hover:text-gh-blue rounded-lg text-sm transition">
                                性能优化
                            </button>
                        </div>
                    </div>
                    
                    <!-- 消息列表 -->
                    <div v-for="(msg, index) in messages" :key="index"
                         :class="['flex gap-3', msg.role === 'user' ? 'flex-row-reverse' : '']">
                        <div :class="['w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                                      msg.role === 'user' ? 'bg-gh-elevated' : 'bg-gradient-to-br from-gh-blue to-gh-purple']">
                            <i :class="[msg.role === 'user' ? 'fas fa-user text-gh-text' : 'fas fa-robot text-white', 'text-sm']"></i>
                        </div>
                        <div :class="['max-w-[80%] rounded-2xl px-4 py-3',
                                      msg.role === 'user' ? 'bg-gh-blue text-white rounded-tr-sm' : 'bg-gh-elevated text-gh-light rounded-tl-sm']">
                            <div v-if="msg.role === 'assistant'" v-html="renderMarkdown(msg.content)" class="prose prose-invert prose-sm max-w-none"></div>
                            <div v-else>{{ msg.content }}</div>
                            <div class="flex items-center gap-2 mt-1 text-xs opacity-60">
                                <span>{{ formatDate(msg.time, 'HH:mm') }}</span>
                                <span v-if="msg.model" class="px-1.5 py-0.5 bg-gh-bg rounded">{{ msg.model }}</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 加载中 -->
                    <div v-if="loading" class="flex gap-3">
                        <div class="w-8 h-8 rounded-full bg-gradient-to-br from-gh-blue to-gh-purple flex items-center justify-center">
                            <i class="fas fa-robot text-white text-sm"></i>
                        </div>
                        <div class="bg-gh-elevated rounded-2xl rounded-tl-sm px-4 py-3">
                            <div class="flex gap-1">
                                <span class="w-2 h-2 rounded-full bg-gh-text animate-bounce" style="animation-delay: 0s"></span>
                                <span class="w-2 h-2 rounded-full bg-gh-text animate-bounce" style="animation-delay: 0.1s"></span>
                                <span class="w-2 h-2 rounded-full bg-gh-text animate-bounce" style="animation-delay: 0.2s"></span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 错误提示 -->
                    <div v-if="error" class="flex gap-3">
                        <div class="w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
                            <i class="fas fa-exclamation-triangle text-red-500 text-sm"></i>
                        </div>
                        <div class="bg-red-500/10 border border-red-500/30 rounded-2xl px-4 py-3 text-red-400 text-sm">
                            {{ error }}
                            <button @click="retryLastMessage" class="ml-2 text-red-400 hover:text-red-300 underline">重试</button>
                        </div>
                    </div>
                </div>
                
                <!-- 输入区域 -->
                <div class="p-4 border-t border-gh-border">
                    <!-- 文件附件预览 -->
                    <div v-if="attachments.length > 0" class="flex gap-2 mb-3 flex-wrap">
                        <div v-for="(file, index) in attachments" :key="index" 
                             class="flex items-center gap-2 px-3 py-1.5 bg-gh-elevated rounded-lg text-sm">
                            <i class="fas fa-file text-gh-blue"></i>
                            <span class="text-gh-text">{{ file.name }}</span>
                            <button @click="removeAttachment(index)" class="text-gh-text hover:text-white">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                    
                    <div class="flex gap-3">
                        <label class="w-10 h-10 rounded-xl bg-gh-elevated flex items-center justify-center text-gh-text hover:text-white cursor-pointer transition">
                            <input type="file" @change="handleFileSelect" class="hidden" multiple>
                            <i class="fas fa-paperclip"></i>
                        </label>
                        <div class="flex-1 relative">
                            <textarea v-model="inputMessage"
                                      @keydown.enter.exact.prevent="sendMessage"
                                      @input="autoResize"
                                      ref="inputRef"
                                      placeholder="输入消息，按 Enter 发送..."
                                      rows="1"
                                      class="w-full bg-gh-elevated border border-gh-border rounded-xl px-4 py-2.5 text-gh-light placeholder-gh-text resize-none focus:outline-none focus:border-gh-blue transition"
                                      style="min-height: 44px; max-height: 120px;"></textarea>
                        </div>
                        <button @click="sendMessage" 
                                :disabled="!inputMessage.trim() || loading"
                                :class="['w-10 h-10 rounded-xl flex items-center justify-center transition',
                                         inputMessage.trim() && !loading ? 'bg-gh-blue text-white hover:bg-gh-blue/80' : 'bg-gh-elevated text-gh-text cursor-not-allowed']">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                    </div>
                    <p class="text-xs text-gh-text mt-2 text-center">AI 生成的内容仅供参考，请核实重要信息</p>
                </div>
            </div>
            
            <!-- 右侧边栏：任务列表 -->
            <div class="w-80 gh-card flex flex-col hidden xl:flex">
                <div class="gh-card-header flex items-center justify-between">
                    <span class="flex items-center gap-2 text-sm">
                        <i class="fas fa-tasks text-gh-green"></i>
                        最近任务
                    </span>
                    <button @click="loadTasks" class="text-gh-text hover:text-white transition">
                        <i class="fas fa-sync-alt" :class="{ 'fa-spin': tasksLoading }"></i>
                    </button>
                </div>
                <div class="flex-1 overflow-y-auto p-2 space-y-2">
                    <div v-for="task in tasks" :key="task.id"
                         class="p-3 bg-gh-canvas border border-gh-border rounded-lg hover:border-gh-blue/50 transition cursor-pointer"
                         @click="viewTaskDetail(task)">
                        <div class="flex items-start justify-between gap-2">
                            <span class="font-medium text-sm text-white truncate flex-1">{{ task.title }}</span>
                            <span :class="['px-2 py-0.5 rounded-full text-xs whitespace-nowrap',
                                          task.priority === 'critical' ? 'bg-red-500/20 text-red-400' :
                                          task.priority === 'high' ? 'bg-orange-500/20 text-orange-400' :
                                          task.priority === 'normal' ? 'bg-blue-500/20 text-blue-400' :
                                          'bg-gh-text/20 text-gh-text']">
                                {{ task.priorityText }}
                            </span>
                        </div>
                        <p class="text-xs text-gh-text mt-1 line-clamp-2">{{ task.description }}</p>
                        <div class="flex items-center justify-between mt-2 text-xs text-gh-text">
                            <span class="flex items-center gap-1">
                                <i :class="['fas', task.agent ? 'fa-robot' : 'fa-user']"></i>
                                {{ task.agent || task.assignee }}
                            </span>
                            <span :class="['px-2 py-0.5 rounded-full',
                                          task.status === 'completed' ? 'bg-gh-green/20 text-gh-green' :
                                          task.status === 'in_progress' ? 'bg-gh-blue/20 text-gh-blue' :
                                          'bg-gh-text/20 text-gh-text']">
                                {{ task.statusText }}
                            </span>
                        </div>
                    </div>
                    <div v-if="tasks.length === 0" class="text-center text-gh-text py-8">
                        <i class="fas fa-inbox text-3xl mb-2"></i>
                        <p class="text-sm">暂无任务</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 新建任务 Modal -->
        <div v-if="showNewTaskModal" class="fixed inset-0 bg-black/70 flex items-center justify-center z-50" @click.self="showNewTaskModal = false">
            <div class="bg-gh-canvas border border-gh-border rounded-xl w-full max-w-md p-6">
                <h3 class="text-lg font-semibold text-white mb-4">新建任务</h3>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm text-gh-text mb-1">任务标题</label>
                        <input v-model="newTask.title" type="text" 
                               class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue"
                               placeholder="输入任务标题">
                    </div>
                    <div>
                        <label class="block text-sm text-gh-text mb-1">任务描述</label>
                        <textarea v-model="newTask.description" rows="3"
                                  class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue resize-none"
                                  placeholder="描述任务内容"></textarea>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm text-gh-text mb-1">优先级</label>
                            <select v-model="newTask.priority" 
                                    class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue">
                                <option value="low">低优先级</option>
                                <option value="normal">中优先级</option>
                                <option value="high">高优先级</option>
                                <option value="critical">紧急</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm text-gh-text mb-1">分配 Agent</label>
                            <select v-model="newTask.agent" 
                                    class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue">
                                <option value="">选择 Agent</option>
                                <option v-for="agent in agents" :key="agent.name" :value="agent.name">{{ agent.name }}</option>
                            </select>
                        </div>
                    </div>
                </div>
                <div class="flex gap-3 mt-6">
                    <button @click="showNewTaskModal = false" 
                            class="flex-1 py-2.5 bg-gh-elevated hover:bg-gh-elevated/80 text-white rounded-lg transition">
                        取消
                    </button>
                    <button @click="createTask" 
                            :disabled="!newTask.title || creatingTask"
                            class="flex-1 py-2.5 bg-gh-green hover:bg-gh-green/90 text-white rounded-lg transition disabled:opacity-50">
                        {{ creatingTask ? '创建中...' : '创建任务' }}
                    </button>
                </div>
            </div>
        </div>
        
        <!-- 设置 Modal -->
        <div v-if="showSettings" class="fixed inset-0 bg-black/70 flex items-center justify-center z-50" @click.self="showSettings = false">
            <div class="bg-gh-canvas border border-gh-border rounded-xl w-full max-w-md p-6">
                <h3 class="text-lg font-semibold text-white mb-4">AI 设置</h3>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm text-gh-text mb-1">AI 提供商</label>
                        <select v-model="localSettings.aiProvider" 
                                class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue">
                            <option value="bailian">阿里云百炼</option>
                            <option value="anthropic">Anthropic</option>
                            <option value="openai">OpenAI</option>
                            <option value="deepseek">DeepSeek</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm text-gh-text mb-1">模型</label>
                        <select v-model="localSettings.model" 
                                class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue">
                            <option v-for="model in availableModels" :key="model.id" :value="model.id">
                                {{ model.name }} - {{ model.description }}
                            </option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm text-gh-text mb-1">API Key</label>
                        <input v-model="localSettings.apiKey" type="password" 
                               class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue"
                               placeholder="sk-...">
                    </div>
                    <div>
                        <label class="block text-sm text-gh-text mb-1">温度 ({{ localSettings.temperature }})</label>
                        <input v-model="localSettings.temperature" type="range" min="0" max="1" step="0.1"
                               class="w-full">
                    </div>
                </div>
                <div class="flex gap-3 mt-6">
                    <button @click="testConnection" 
                            class="flex-1 py-2.5 bg-gh-elevated hover:bg-gh-elevated/80 text-white rounded-lg transition">
                        测试连接
                    </button>
                    <button @click="saveSettings" 
                            class="flex-1 py-2.5 bg-gh-blue hover:bg-gh-blue/90 text-white rounded-lg transition">
                        保存
                    </button>
                </div>
            </div>
        </div>
    `,
    
    data() {
        return {
            messages: [],
            inputMessage: '',
            attachments: [],
            loading: false,
            error: null,
            wsConnected: false,
            ws: null,
            
            // Agent 相关
            agents: [],
            selectedAgent: null,
            
            // 任务相关
            tasks: [],
            tasksLoading: false,
            showNewTaskModal: false,
            creatingTask: false,
            newTask: {
                title: '',
                description: '',
                priority: 'normal',
                agent: ''
            },
            
            // 设置相关
            showSettings: false,
            localSettings: {
                aiProvider: 'bailian',
                apiKey: '',
                model: 'qwen3.5-plus',
                temperature: 0.7
            },
            availableModels: []
        };
    },
    
    methods: {
        renderMarkdown,
        formatDate,
        
        // WebSocket 连接
        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            try {
                this.ws = new WebSocket(wsUrl);
                
                this.ws.onopen = () => {
                    this.wsConnected = true;
                    console.log('WebSocket 已连接');
                };
                
                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                };
                
                this.ws.onclose = () => {
                    this.wsConnected = false;
                    console.log('WebSocket 已断开，尝试重连...');
                    setTimeout(() => this.connectWebSocket(), 5000);
                };
                
                this.ws.onerror = (error) => {
                    console.error('WebSocket 错误:', error);
                };
            } catch (e) {
                console.error('WebSocket 连接失败:', e);
            }
        },
        
        handleWebSocketMessage(data) {
            const { type, data: payload } = data;
            
            if (type === 'agent_update') {
                // 更新 Agent 状态
                const agent = this.agents.find(a => a.name === payload.name);
                if (agent) {
                    agent.status = payload.status;
                }
            } else if (type === 'task_update') {
                // 更新任务列表
                this.loadTasks();
            }
        },
        
        // 加载数据
        async loadAgents() {
            try {
                const data = await api.getAgents();
                this.agents = Array.isArray(data) ? data : [];
                if (this.agents.length > 0 && !this.selectedAgent) {
                    this.selectedAgent = this.agents[0];
                }
            } catch (e) {
                console.error('加载 Agent 失败:', e);
            }
        },
        
        async loadTasks() {
            this.tasksLoading = true;
            try {
                const data = await api.getTasks();
                this.tasks = Array.isArray(data) ? data.slice(0, 10) : [];
            } catch (e) {
                console.error('加载任务失败:', e);
            } finally {
                this.tasksLoading = false;
            }
        },
        
        async loadSettings() {
            try {
                const data = await api.getSettings();
                if (data.settings) {
                    this.localSettings = { ...this.localSettings, ...data.settings };
                }
                
                // 加载可用模型
                const modelsData = await api.getAvailableModels();
                if (modelsData.models) {
                    const providerModels = modelsData.models[this.localSettings.aiProvider] || [];
                    this.availableModels = providerModels;
                }
            } catch (e) {
                console.error('加载设置失败:', e);
            }
        },
        
        // Agent 选择
        selectAgent(agent) {
            this.selectedAgent = agent;
        },
        
        // 发送消息
        async sendMessage() {
            const message = this.inputMessage.trim();
            if (!message || this.loading) return;
            
            // 添加用户消息
            this.messages.push({
                role: 'user',
                content: message,
                time: new Date()
            });
            
            this.inputMessage = '';
            this.error = null;
            this.loading = true;
            this.scrollToBottom();
            
            // 重置 textarea 高度
            if (this.$refs.inputRef) {
                this.$refs.inputRef.style.height = '44px';
            }
            
            try {
                // 构建聊天消息
                const chatMessages = this.messages.slice(-10).map(msg => ({
                    role: msg.role,
                    content: msg.content
                }));
                
                // 添加系统提示
                if (this.selectedAgent) {
                    chatMessages.unshift({
                        role: 'system',
                        content: `你是一个${this.selectedAgent.role}，名叫${this.selectedAgent.name}。${this.selectedAgent.description}。请用专业的方式帮助用户。`
                    });
                }
                
                // 使用流式请求
                await this.sendStreamingChat(chatMessages);
            } catch (e) {
                console.error('发送消息失败:', e);
                this.error = e.message || '发送失败，请重试';
                this.loading = false;
            }
        },
        
        async sendStreamingChat(messages) {
            const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
            const url = `${protocol}//${window.location.host}/api/v1/chat`;
            
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    messages,
                    stream: true,
                    temperature: parseFloat(this.localSettings.temperature),
                    max_tokens: 4096,
                    provider: this.localSettings.aiProvider,
                    model: this.localSettings.model,
                    apiKey: this.localSettings.apiKey
                })
            });
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.message || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            // 创建 AI 消息占位
            const aiMessageIndex = this.messages.length;
            this.messages.push({
                role: 'assistant',
                content: '',
                time: new Date(),
                model: this.localSettings.model
            });
            
            // 读取流式响应
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullContent = '';
            
            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value, { stream: true });
                    const lines = chunk.split('\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = line.slice(6);
                            if (data === '[DONE]') {
                                break;
                            }
                            try {
                                const parsed = JSON.parse(data);
                                if (parsed.content) {
                                    fullContent += parsed.content;
                                    this.messages[aiMessageIndex].content = fullContent;
                                    this.scrollToBottom();
                                }
                                if (parsed.error) {
                                    throw new Error(parsed.error);
                                }
                            } catch (e) {
                                // 忽略解析错误
                            }
                        }
                    }
                }
            } finally {
                reader.releaseLock();
            }
            
            this.loading = false;
            this.scrollToBottom();
        },
        
        // 快速提问
        quickAsk(question) {
            this.inputMessage = question;
            this.sendMessage();
        },
        
        // 重试最后一条消息
        async retryLastMessage() {
            if (this.messages.length < 2) return;
            
            const lastUserMessage = [...this.messages].reverse().find(m => m.role === 'user');
            if (!lastUserMessage) return;
            
            // 删除最后一条 AI 消息和错误
            this.messages = this.messages.filter(m => m !== this.messages[this.messages.length - 1]);
            this.error = null;
            
            this.inputMessage = lastUserMessage.content;
            await this.sendMessage();
        },
        
        // 清空对话
        clearChat() {
            if (confirm('确定要清空对话历史吗？')) {
                this.messages = [];
            }
        },
        
        // 导出对话
        exportChat() {
            if (this.messages.length === 0) {
                alert('暂无对话可导出');
                return;
            }
            
            let content = '# AI 助手对话记录\n\n';
            content += `导出时间：${new Date().toLocaleString('zh-CN')}\n\n`;
            content += '---\n\n';
            
            for (const msg of this.messages) {
                const role = msg.role === 'user' ? '👤 用户' : '🤖 AI';
                const time = new Date(msg.time).toLocaleString('zh-CN');
                content += `### ${role} - ${time}\n\n`;
                content += `${msg.content}\n\n`;
                content += '---\n\n';
            }
            
            const blob = new Blob([content], { type: 'text/markdown' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ai-chat-${Date.now()}.md`;
            a.click();
            URL.revokeObjectURL(url);
        },
        
        // 文件处理
        handleFileSelect(event) {
            const files = Array.from(event.target.files);
            this.attachments.push(...files.map(f => ({
                name: f.name,
                size: f.size,
                file: f
            })));
        },
        
        removeAttachment(index) {
            this.attachments.splice(index, 1);
        },
        
        // 自动调整 textarea 高度
        autoResize(event) {
            const target = event.target;
            target.style.height = 'auto';
            target.style.height = Math.min(target.scrollHeight, 120) + 'px';
        },
        
        // 滚动到底部
        scrollToBottom() {
            this.$nextTick(() => {
                const container = this.$refs.messageContainer;
                if (container) {
                    container.scrollTop = container.scrollHeight;
                }
            });
        },
        
        // 新建任务
        async createTask() {
            if (!this.newTask.title) return;
            
            this.creatingTask = true;
            try {
                await api.createTask({
                    title: this.newTask.title,
                    description: this.newTask.description,
                    priority: this.newTask.priority,
                    agent: this.newTask.agent || this.selectedAgent?.name
                });
                
                this.showNewTaskModal = false;
                this.newTask = { title: '', description: '', priority: 'normal', agent: '' };
                await this.loadTasks();
            } catch (e) {
                alert('创建任务失败：' + e.message);
            } finally {
                this.creatingTask = false;
            }
        },
        
        // 查看任务详情
        viewTaskDetail(task) {
            window.location.href = `/task-detail?id=${task.id}`;
        },
        
        // 设置相关
        async testConnection() {
            try {
                const result = await api.testConnection({
                    provider: this.localSettings.aiProvider,
                    apiKey: this.localSettings.apiKey
                });
                
                if (result.success) {
                    alert('连接测试成功！');
                } else {
                    alert('连接失败：' + (result.error || '未知错误'));
                }
            } catch (e) {
                alert('测试失败：' + e.message);
            }
        },
        
        async saveSettings() {
            try {
                await api.saveSettings(this.localSettings);
                this.showSettings = false;
                alert('设置已保存');
            } catch (e) {
                alert('保存失败：' + e.message);
            }
        }
    },
    
    mounted() {
        this.loadAgents();
        this.loadTasks();
        this.loadSettings();
        this.connectWebSocket();
        
        // 定期刷新 Agent 状态
        setInterval(() => {
            this.loadAgents();
        }, 30000);
        
        // 定期刷新任务列表
        setInterval(() => {
            this.loadTasks();
        }, 60000);
    },
    
    beforeUnmount() {
        if (this.ws) {
            this.ws.close();
        }
    }
};

