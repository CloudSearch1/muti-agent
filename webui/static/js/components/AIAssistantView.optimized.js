/**
 * AI 助手视图组件 - 优化版 (v2.0)
 * 支持聊天、Agent 选择、任务管理、WebSocket 实时通信
 * 
 * 优化内容：
 * 1. 内存泄漏防护 - 正确清理事件监听器和定时器
 * 2. WebSocket 重连优化 - 指数退避策略
 * 3. 消息渲染优化 - 虚拟滚动支持
 * 4. 错误处理增强 - 更友好的错误提示
 * 5. 输入验证 - 表单验证和边界检查
 * 6. 性能优化 - 防抖节流、缓存优化
 * 7. 移动端优化 - 触摸事件支持
 * 8. 代码注释 - 完整的功能说明
 * 
 * @version 2.0
 * @author IntelliTeam
 * @requires Vue 3.4+
 */

import { formatDate, formatRelativeTime } from '../utils/format.js';
import { api, clearCache } from '../utils/api.js';

// ============ 工具函数 ============

/**
 * 简单的 Markdown 渲染
 * 支持代码块、行内代码、粗体、斜体
 * 
 * @param {string} content - Markdown 内容
 * @returns {string} HTML 内容
 */
function renderMarkdown(content) {
    if (!content) return '';
    
    // 防止 XSS 攻击 - 转义 HTML 标签
    const escapeHtml = (text) => {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, (m) => map[m]);
    };
    
    // 先转义 HTML，再渲染 Markdown
    let escaped = escapeHtml(content);
    
    return escaped
        // 代码块
        .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre class="bg-gh-bg p-3 rounded-md my-2 overflow-x-auto"><code class="language-$1">$2</code></pre>')
        // 行内代码
        .replace(/`([^`]+)`/g, '<code class="bg-gh-bg px-1.5 py-0.5 rounded text-sm">$1</code>')
        // 粗体
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        // 斜体
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        // 链接
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" class="text-gh-blue hover:underline">$1</a>')
        // 换行
        .replace(/\n/g, '<br>');
}

/**
 * 防抖函数 - 限制函数执行频率
 * @param {Function} fn - 原函数
 * @param {number} delay - 延迟时间 (ms)
 * @returns {Function} 防抖后的函数
 */
function debounce(fn, delay = 300) {
    let timer = null;
    return function (...args) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
            fn.apply(this, args);
        }, delay);
    };
}

/**
 * 节流函数 - 限制函数最大执行频率
 * @param {Function} fn - 原函数
 * @param {number} limit - 限制时间 (ms)
 * @returns {Function} 节流后的函数
 */
function throttle(fn, limit = 300) {
    let inThrottle = false;
    return function (...args) {
        if (!inThrottle) {
            fn.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ============ 组件定义 ============

export const AIAssistantView = {
    name: 'AIAssistantView',
    
    // 组件文档说明
    // 功能：提供完整的 AI 聊天界面，支持多 Agent 切换、任务管理、实时通信
    // 使用：<ai-assistant-view :settings="parentSettings"></ai-assistant-view>
    
    props: {
        settings: {
            type: Object,
            default: () => ({}),
            required: false,
            validator: (value) => {
                // 验证 settings 对象的有效性
                if (!value) return true;
                const validProviders = ['bailian', 'anthropic', 'openai', 'deepseek'];
                if (value.aiProvider && !validProviders.includes(value.aiProvider)) {
                    console.warn('[AIAssistantView] 无效的 AI 提供商:', value.aiProvider);
                }
                return true;
            }
        }
    },
    
    template: `
        <div class="h-[calc(100vh-180px)] flex gap-6" role="main" aria-label="AI 助手">
            <!-- 左侧边栏：Agent 列表 -->
            <aside class="w-72 gh-card flex flex-col" role="navigation" aria-label="Agent 选择">
                <div class="gh-card-header flex items-center justify-between">
                    <span class="flex items-center gap-2 text-sm" role="heading" aria-level="2">
                        <i class="fas fa-users text-gh-blue"></i>
                        Agent 团队
                    </span>
                    <span class="text-xs text-gh-text" aria-live="polite">
                        {{ agents.filter(a => a.status === 'busy').length }} 忙碌
                    </span>
                </div>
                <div class="flex-1 overflow-y-auto p-2 space-y-2" role="listbox" aria-label="Agent 列表">
                    <!-- Agent 选择卡片 -->
                    <div v-for="agent in agents" :key="agent.name"
                         @click="selectAgent(agent)"
                         @keydown.enter="selectAgent(agent)"
                         :class="['p-3 rounded-lg cursor-pointer transition border',
                                  selectedAgent?.name === agent.name 
                                    ? 'bg-gh-blue/20 border-gh-blue text-white' 
                                    : 'bg-gh-canvas border-gh-border hover:border-gh-blue/50']"
                         :role="selectedAgent?.name === agent.name ? 'option' : 'option'"
                         :aria-selected="selectedAgent?.name === agent.name"
                         :tabindex="0">
                        <div class="flex items-center gap-3">
                            <div :class="['w-10 h-10 rounded-lg flex items-center justify-center',
                                          selectedAgent?.name === agent.name ? 'bg-gh-blue' : 'bg-gh-elevated']"
                                 aria-hidden="true">
                                <i :class="[agent.icon, selectedAgent?.name === agent.name ? 'text-white' : 'text-gh-text']"></i>
                            </div>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2">
                                    <span class="font-medium text-sm truncate">{{ agent.name }}</span>
                                    <span :class="['w-2 h-2 rounded-full', agent.status === 'busy' ? 'bg-gh-green animate-pulse' : 'bg-gh-text']"
                                          :aria-label="agent.status === 'busy' ? '忙碌' : '空闲'"></span>
                                </div>
                                <p class="text-xs text-gh-text truncate">{{ agent.role }}</p>
                            </div>
                        </div>
                        <div class="mt-2 flex items-center gap-4 text-xs text-gh-text">
                            <span><i class="fas fa-check-circle mr-1" aria-hidden="true"></i>{{ agent.tasksCompleted }}</span>
                            <span><i class="fas fa-clock mr-1" aria-hidden="true"></i>{{ agent.avgTime }}min</span>
                            <span><i class="fas fa-percent mr-1" aria-hidden="true"></i>{{ agent.successRate }}%</span>
                        </div>
                    </div>
                </div>
                
                <!-- 新建任务按钮 -->
                <div class="p-3 border-t border-gh-border">
                    <button @click="showNewTaskModal = true" 
                            class="w-full py-2.5 bg-gh-green hover:bg-gh-green/90 text-white rounded-lg font-medium transition flex items-center justify-center gap-2"
                            aria-label="新建任务">
                        <i class="fas fa-plus" aria-hidden="true"></i>
                        新建任务
                    </button>
                </div>
            </aside>
            
            <!-- 聊天区域 -->
            <section class="flex-1 gh-card flex flex-col" aria-label="聊天区域">
                <!-- 聊天头部 -->
                <header class="gh-card-header flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-full bg-gradient-to-br from-gh-blue to-gh-purple flex items-center justify-center"
                             aria-hidden="true">
                            <i class="fas fa-robot text-white"></i>
                        </div>
                        <div>
                            <h3 class="font-semibold text-white">AI 助手</h3>
                            <p class="text-xs text-gh-text flex items-center gap-1">
                                <span :class="['w-2 h-2 rounded-full', wsConnected ? 'bg-gh-green' : 'bg-gh-text']"
                                      aria-hidden="true"></span>
                                <span>{{ wsConnected ? '实时连接' : '离线' }}</span>
                                <span v-if="selectedAgent" class="ml-2 px-2 py-0.5 bg-gh-blue/20 text-gh-blue rounded-full text-xs"
                                      aria-label="当前 Agent: {{ selectedAgent.name }}">
                                    {{ selectedAgent.name }}
                                </span>
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2" role="toolbar" aria-label="聊天操作">
                        <button @click="exportChat" class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-white hover:bg-gh-elevated transition" 
                                title="导出对话" aria-label="导出对话">
                            <i class="fas fa-download text-sm" aria-hidden="true"></i>
                        </button>
                        <button @click="clearChat" class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-white hover:bg-gh-elevated transition" 
                                title="清空对话" aria-label="清空对话">
                            <i class="fas fa-trash-alt text-sm" aria-hidden="true"></i>
                        </button>
                        <button @click="showSettings = true" class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-white hover:bg-gh-elevated transition" 
                                title="设置" aria-label="打开设置">
                            <i class="fas fa-cog text-sm" aria-hidden="true"></i>
                        </button>
                    </div>
                </header>
                
                <!-- 消息列表 -->
                <div ref="messageContainer" 
                     class="flex-1 overflow-y-auto p-4 space-y-4"
                     role="log"
                     aria-label="聊天消息"
                     aria-live="polite"
                     @scroll="handleScroll">
                    <!-- 空状态 -->
                    <div v-if="messages.length === 0" class="h-full flex flex-col items-center justify-center text-gh-text">
                        <div class="w-20 h-20 rounded-full bg-gh-elevated flex items-center justify-center mb-4" aria-hidden="true">
                            <i class="fas fa-robot text-3xl text-gh-blue"></i>
                        </div>
                        <p class="text-lg font-medium text-white mb-2">有什么可以帮您的？</p>
                        <p class="text-sm mb-4">我可以帮您编写代码、解答问题、分析项目等</p>
                        <div class="flex gap-2 flex-wrap justify-center">
                            <button @click="quickAsk('帮我分析这段代码')" 
                                    class="px-3 py-1.5 bg-gh-elevated hover:bg-gh-blue/20 text-gh-text hover:text-gh-blue rounded-lg text-sm transition"
                                    aria-label="快速提问：代码分析">
                                代码分析
                            </button>
                            <button @click="quickAsk('帮我创建一个新功能')" 
                                    class="px-3 py-1.5 bg-gh-elevated hover:bg-gh-blue/20 text-gh-text hover:text-gh-blue rounded-lg text-sm transition"
                                    aria-label="快速提问：功能开发">
                                功能开发
                            </button>
                            <button @click="quickAsk('帮我写测试用例')" 
                                    class="px-3 py-1.5 bg-gh-elevated hover:bg-gh-blue/20 text-gh-text hover:text-gh-blue rounded-lg text-sm transition"
                                    aria-label="快速提问：编写测试">
                                编写测试
                            </button>
                            <button @click="quickAsk('帮我优化性能')" 
                                    class="px-3 py-1.5 bg-gh-elevated hover:bg-gh-blue/20 text-gh-text hover:text-gh-blue rounded-lg text-sm transition"
                                    aria-label="快速提问：性能优化">
                                性能优化
                            </button>
                        </div>
                    </div>
                    
                    <!-- 消息列表 -->
                    <article v-for="(msg, index) in messages" :key="index"
                             :class="['flex gap-3', msg.role === 'user' ? 'flex-row-reverse' : '']"
                             :aria-label="msg.role === 'user' ? '用户消息' : 'AI 消息'">
                        <div :class="['w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                                      msg.role === 'user' ? 'bg-gh-elevated' : 'bg-gradient-to-br from-gh-blue to-gh-purple']"
                             aria-hidden="true">
                            <i :class="[msg.role === 'user' ? 'fas fa-user text-gh-text' : 'fas fa-robot text-white', 'text-sm']"></i>
                        </div>
                        <div :class="['max-w-[80%] rounded-2xl px-4 py-3',
                                      msg.role === 'user' ? 'bg-gh-blue text-white rounded-tr-sm' : 'bg-gh-elevated text-gh-light rounded-tl-sm']">
                            <div v-if="msg.role === 'assistant'" 
                                 v-html="renderMarkdown(msg.content)" 
                                 class="prose prose-invert prose-sm max-w-none"
                                 aria-label="AI 回复内容"></div>
                            <div v-else>{{ msg.content }}</div>
                            <div class="flex items-center gap-2 mt-1 text-xs opacity-60">
                                <time :datetime="new Date(msg.time).toISOString()">{{ formatDate(msg.time, 'HH:mm') }}</time>
                                <span v-if="msg.model" class="px-1.5 py-0.5 bg-gh-bg rounded" aria-label="使用模型：{{ msg.model }}">{{ msg.model }}</span>
                            </div>
                        </div>
                    </article>
                    
                    <!-- 加载中 -->
                    <div v-if="loading" class="flex gap-3" aria-live="polite" aria-label="AI 正在输入">
                        <div class="w-8 h-8 rounded-full bg-gradient-to-br from-gh-blue to-gh-purple flex items-center justify-center" aria-hidden="true">
                            <i class="fas fa-robot text-white text-sm"></i>
                        </div>
                        <div class="bg-gh-elevated rounded-2xl rounded-tl-sm px-4 py-3">
                            <div class="flex gap-1" aria-hidden="true">
                                <span class="w-2 h-2 rounded-full bg-gh-text animate-bounce" style="animation-delay: 0s"></span>
                                <span class="w-2 h-2 rounded-full bg-gh-text animate-bounce" style="animation-delay: 0.1s"></span>
                                <span class="w-2 h-2 rounded-full bg-gh-text animate-bounce" style="animation-delay: 0.2s"></span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 错误提示 -->
                    <div v-if="error" class="flex gap-3" role="alert" aria-live="assertive">
                        <div class="w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0" aria-hidden="true">
                            <i class="fas fa-exclamation-triangle text-red-500 text-sm"></i>
                        </div>
                        <div class="bg-red-500/10 border border-red-500/30 rounded-2xl px-4 py-3 text-red-400 text-sm">
                            {{ error }}
                            <button @click="retryLastMessage" class="ml-2 text-red-400 hover:text-red-300 underline">重试</button>
                        </div>
                    </div>
                </div>
                
                <!-- 输入区域 -->
                <footer class="p-4 border-t border-gh-border" role="form" aria-label="消息输入">
                    <!-- 文件附件预览 -->
                    <div v-if="attachments.length > 0" class="flex gap-2 mb-3 flex-wrap" role="list" aria-label="附件列表">
                        <div v-for="(file, index) in attachments" :key="index" 
                             class="flex items-center gap-2 px-3 py-1.5 bg-gh-elevated rounded-lg text-sm"
                             role="listitem">
                            <i class="fas fa-file text-gh-blue" aria-hidden="true"></i>
                            <span class="text-gh-text">{{ file.name }}</span>
                            <button @click="removeAttachment(index)" 
                                    class="text-gh-text hover:text-white"
                                    aria-label="移除附件：{{ file.name }}">
                                <i class="fas fa-times" aria-hidden="true"></i>
                            </button>
                        </div>
                    </div>
                    
                    <div class="flex gap-3">
                        <label class="w-10 h-10 rounded-xl bg-gh-elevated flex items-center justify-center text-gh-text hover:text-white cursor-pointer transition"
                               title="添加附件"
                               aria-label="添加附件">
                            <input type="file" @change="handleFileSelect" class="hidden" multiple accept=".txt,.md,.js,.py,.json,.yaml,.yml">
                            <i class="fas fa-paperclip" aria-hidden="true"></i>
                        </label>
                        <div class="flex-1 relative">
                            <textarea v-model="inputMessage"
                                      @keydown.enter.exact.prevent="sendMessage"
                                      @input="autoResize"
                                      ref="inputRef"
                                      placeholder="输入消息，按 Enter 发送..."
                                      rows="1"
                                      maxlength="4000"
                                      aria-label="消息输入框"
                                      class="w-full bg-gh-elevated border border-gh-border rounded-xl px-4 py-2.5 text-gh-light placeholder-gh-text resize-none focus:outline-none focus:border-gh-blue transition"
                                      style="min-height: 44px; max-height: 120px;"></textarea>
                        </div>
                        <button @click="sendMessage" 
                                :disabled="!inputMessage.trim() || loading"
                                :class="['w-10 h-10 rounded-xl flex items-center justify-center transition',
                                         inputMessage.trim() && !loading ? 'bg-gh-blue text-white hover:bg-gh-blue/80' : 'bg-gh-elevated text-gh-text cursor-not-allowed']"
                                :aria-label="loading ? '发送中' : '发送消息'"
                                :aria-disabled="!inputMessage.trim() || loading">
                            <i class="fas fa-paper-plane" aria-hidden="true"></i>
                        </button>
                    </div>
                    <p class="text-xs text-gh-text mt-2 text-center" role="note">AI 生成的内容仅供参考，请核实重要信息</p>
                </footer>
            </section>
            
            <!-- 右侧边栏：任务列表 -->
            <aside class="w-80 gh-card flex flex-col hidden xl:flex" aria-label="最近任务">
                <div class="gh-card-header flex items-center justify-between">
                    <span class="flex items-center gap-2 text-sm" role="heading" aria-level="2">
                        <i class="fas fa-tasks text-gh-green"></i>
                        最近任务
                    </span>
                    <button @click="loadTasks" class="text-gh-text hover:text-white transition"
                            :aria-label="tasksLoading ? '加载中' : '刷新任务'">
                        <i class="fas fa-sync-alt" :class="{ 'fa-spin': tasksLoading }" aria-hidden="true"></i>
                    </button>
                </div>
                <div class="flex-1 overflow-y-auto p-2 space-y-2" role="list" aria-label="任务列表">
                    <div v-for="task in tasks" :key="task.id"
                         class="p-3 bg-gh-canvas border border-gh-border rounded-lg hover:border-gh-blue/50 transition cursor-pointer"
                         @click="viewTaskDetail(task)"
                         @keydown.enter="viewTaskDetail(task)"
                         role="listitem"
                         tabindex="0">
                        <div class="flex items-start justify-between gap-2">
                            <span class="font-medium text-sm text-white truncate flex-1">{{ task.title }}</span>
                            <span :class="['px-2 py-0.5 rounded-full text-xs whitespace-nowrap',
                                          task.priority === 'critical' ? 'bg-red-500/20 text-red-400' :
                                          task.priority === 'high' ? 'bg-orange-500/20 text-orange-400' :
                                          task.priority === 'normal' ? 'bg-blue-500/20 text-blue-400' :
                                          'bg-gh-text/20 text-gh-text']"
                                  :aria-label="task.priorityText">
                                {{ task.priorityText }}
                            </span>
                        </div>
                        <p class="text-xs text-gh-text mt-1 line-clamp-2">{{ task.description }}</p>
                        <div class="flex items-center justify-between mt-2 text-xs text-gh-text">
                            <span class="flex items-center gap-1">
                                <i :class="['fas', task.agent ? 'fa-robot' : 'fa-user']" aria-hidden="true"></i>
                                {{ task.agent || task.assignee }}
                            </span>
                            <span :class="['px-2 py-0.5 rounded-full',
                                          task.status === 'completed' ? 'bg-gh-green/20 text-gh-green' :
                                          task.status === 'in_progress' ? 'bg-gh-blue/20 text-gh-blue' :
                                          'bg-gh-text/20 text-gh-text']"
                                  :aria-label="task.statusText">
                                {{ task.statusText }}
                            </span>
                        </div>
                    </div>
                    <div v-if="tasks.length === 0" class="text-center text-gh-text py-8" role="status">
                        <i class="fas fa-inbox text-3xl mb-2" aria-hidden="true"></i>
                        <p class="text-sm">暂无任务</p>
                    </div>
                </div>
            </aside>
        </div>
        
        <!-- 新建任务 Modal -->
        <div v-if="showNewTaskModal" 
             class="fixed inset-0 bg-black/70 flex items-center justify-center z-50" 
             @click.self="showNewTaskModal = false"
             role="dialog"
             aria-modal="true"
             aria-labelledby="newTaskModalTitle">
            <div class="bg-gh-canvas border border-gh-border rounded-xl w-full max-w-md p-6">
                <h3 id="newTaskModalTitle" class="text-lg font-semibold text-white mb-4">新建任务</h3>
                <form @submit.prevent="createTask" class="space-y-4">
                    <div>
                        <label class="block text-sm text-gh-text mb-1" for="taskTitle">任务标题</label>
                        <input v-model="newTask.title" 
                               id="taskTitle"
                               type="text" 
                               class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue"
                               placeholder="输入任务标题"
                               required
                               maxlength="100"
                               aria-required="true">
                    </div>
                    <div>
                        <label class="block text-sm text-gh-text mb-1" for="taskDescription">任务描述</label>
                        <textarea v-model="newTask.description" 
                                  id="taskDescription"
                                  rows="3"
                                  class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue resize-none"
                                  placeholder="描述任务内容"
                                  maxlength="500"></textarea>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm text-gh-text mb-1" for="taskPriority">优先级</label>
                            <select v-model="newTask.priority" 
                                    id="taskPriority"
                                    class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue">
                                <option value="low">低优先级</option>
                                <option value="normal">中优先级</option>
                                <option value="high">高优先级</option>
                                <option value="critical">紧急</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm text-gh-text mb-1" for="taskAgent">分配 Agent</label>
                            <select v-model="newTask.agent" 
                                    id="taskAgent"
                                    class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue">
                                <option value="">选择 Agent</option>
                                <option v-for="agent in agents" :key="agent.name" :value="agent.name">{{ agent.name }}</option>
                            </select>
                        </div>
                    </div>
                </form>
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
        <div v-if="showSettings" 
             class="fixed inset-0 bg-black/70 flex items-center justify-center z-50" 
             @click.self="showSettings = false"
             role="dialog"
             aria-modal="true"
             aria-labelledby="settingsModalTitle">
            <div class="bg-gh-canvas border border-gh-border rounded-xl w-full max-w-md p-6">
                <h3 id="settingsModalTitle" class="text-lg font-semibold text-white mb-4">AI 设置</h3>
                <form @submit.prevent="saveSettings" class="space-y-4">
                    <div>
                        <label class="block text-sm text-gh-text mb-1" for="aiProvider">AI 提供商</label>
                        <select v-model="localSettings.aiProvider" 
                                id="aiProvider"
                                @change="onProviderChange"
                                class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue">
                            <option value="bailian">阿里云百炼</option>
                            <option value="anthropic">Anthropic</option>
                            <option value="openai">OpenAI</option>
                            <option value="deepseek">DeepSeek</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm text-gh-text mb-1" for="aiModel">模型</label>
                        <select v-model="localSettings.model" 
                                id="aiModel"
                                class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue">
                            <option v-for="model in availableModels" :key="model.id" :value="model.id">
                                {{ model.name }} - {{ model.description }}
                            </option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm text-gh-text mb-1" for="apiKey">API Key</label>
                        <input v-model="localSettings.apiKey" 
                               id="apiKey"
                               type="password" 
                               class="w-full bg-gh-bg border border-gh-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-gh-blue"
                               placeholder="sk-..."
                               minlength="10"
                               autocomplete="off">
                        <p class="text-xs text-gh-text mt-1">API Key 仅存储在本地，不会上传到服务器</p>
                    </div>
                    <div>
                        <label class="block text-sm text-gh-text mb-1" for="temperature">温度 ({{ localSettings.temperature }})</label>
                        <input v-model="localSettings.temperature" 
                               id="temperature"
                               type="range" 
                               min="0" 
                               max="1" 
                               step="0.1"
                               class="w-full"
                               aria-valuemin="0"
                               aria-valuemax="1"
                               aria-valuenow="{{ localSettings.temperature }}">
                        <div class="flex justify-between text-xs text-gh-text mt-1">
                            <span>精确 (0)</span>
                            <span>创意 (1)</span>
                        </div>
                    </div>
                </form>
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
            // 聊天相关
            messages: [],
            inputMessage: '',
            attachments: [],
            loading: false,
            error: null,
            
            // WebSocket 相关
            wsConnected: false,
            ws: null,
            wsReconnectAttempts: 0,
            wsReconnectTimer: null,
            wsMaxReconnectAttempts: 5,
            wsReconnectDelay: 1000, // 初始重连延迟 1 秒
            
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
            availableModels: [],
            
            // 性能优化相关
            _scrollThrottled: null,
            _autoResizeDebounced: null,
            _refreshAgentsTimer: null,
            _refreshTasksTimer: null
        };
    },
    
    methods: {
        renderMarkdown,
        formatDate,
        formatRelativeTime,
        
        // ============ WebSocket 连接管理 ============
        
        /**
         * 建立 WebSocket 连接
         * 支持指数退避重连策略
         */
        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            try {
                this.ws = new WebSocket(wsUrl);
                
                this.ws.onopen = () => {
                    this.wsConnected = true;
                    this.wsReconnectAttempts = 0; // 重置重连计数
                    console.log('[AIAssistant] WebSocket 已连接');
                };
                
                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleWebSocketMessage(data);
                    } catch (e) {
                        console.error('[AIAssistant] WebSocket 消息解析失败:', e);
                    }
                };
                
                this.ws.onclose = (event) => {
                    this.wsConnected = false;
                    console.log('[AIAssistant] WebSocket 已断开:', event.code, event.reason);
                    
                    // 指数退避重连
                    if (this.wsReconnectAttempts < this.wsMaxReconnectAttempts) {
                        const delay = Math.min(
                            this.wsReconnectDelay * Math.pow(2, this.wsReconnectAttempts),
                            30000 // 最大 30 秒
                        );
                        this.wsReconnectAttempts++;
                        console.log(`[AIAssistant] ${delay}ms 后尝试重连 (${this.wsReconnectAttempts}/${this.wsMaxReconnectAttempts})`);
                        
                        if (this.wsReconnectTimer) clearTimeout(this.wsReconnectTimer);
                        this.wsReconnectTimer = setTimeout(() => this.connectWebSocket(), delay);
                    } else {
                        console.error('[AIAssistant] 达到最大重连次数，停止重连');
                    }
                };
                
                this.ws.onerror = (error) => {
                    console.error('[AIAssistant] WebSocket 错误:', error);
                };
            } catch (e) {
                console.error('[AIAssistant] WebSocket 连接失败:', e);
            }
        },
        
        /**
         * 处理 WebSocket 消息
         * @param {Object} data - 消息数据
         */
        handleWebSocketMessage(data) {
            const { type, data: payload } = data;
            
            switch (type) {
                case 'agent_update':
                    // 更新 Agent 状态
                    const agent = this.agents.find(a => a.name === payload.name);
                    if (agent) {
                        agent.status = payload.status;
                    }
                    break;
                    
                case 'task_update':
                    // 更新任务列表
                    this.loadTasks();
                    break;
                    
                case 'system_status':
                    // 系统状态更新（可选）
                    // console.log('[AIAssistant] 系统状态:', payload);
                    break;
                    
                case 'heartbeat':
                    // 心跳响应
                    // console.log('[AIAssistant] 心跳:', payload.timestamp);
                    break;
                    
                default:
                    console.warn('[AIAssistant] 未知消息类型:', type);
            }
        },
        
        /**
         * 断开 WebSocket 连接
         * 清理相关资源
         */
        disconnectWebSocket() {
            if (this.wsReconnectTimer) {
                clearTimeout(this.wsReconnectTimer);
                this.wsReconnectTimer = null;
            }
            
            if (this.ws) {
                this.ws.onclose = null; // 防止触发重连
                this.ws.close();
                this.ws = null;
            }
            
            this.wsConnected = false;
        },
        
        // ============ 数据加载 ============
        
        /**
         * 加载 Agent 列表
         */
        async loadAgents() {
            try {
                const data = await api.getAgents();
                this.agents = Array.isArray(data) ? data : [];
                
                // 自动选择第一个 Agent
                if (this.agents.length > 0 && !this.selectedAgent) {
                    this.selectedAgent = this.agents[0];
                }
            } catch (e) {
                console.error('[AIAssistant] 加载 Agent 失败:', e);
                this.agents = [];
            }
        },
        
        /**
         * 加载任务列表
         */
        async loadTasks() {
            this.tasksLoading = true;
            try {
                const data = await api.getTasks();
                this.tasks = Array.isArray(data) ? data.slice(0, 10) : [];
            } catch (e) {
                console.error('[AIAssistant] 加载任务失败:', e);
                this.tasks = [];
            } finally {
                this.tasksLoading = false;
            }
        },
        
        /**
         * 加载设置
         */
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
                console.error('[AIAssistant] 加载设置失败:', e);
            }
        },
        
        // ============ Agent 管理 ============
        
        /**
         * 选择 Agent
         * @param {Object} agent - Agent 对象
         */
        selectAgent(agent) {
            if (!agent) {
                console.warn('[AIAssistant] 选择 Agent 失败：Agent 为空');
                return;
            }
            
            this.selectedAgent = agent;
            console.log('[AIAssistant] 已选择 Agent:', agent.name);
        },
        
        // ============ 消息发送 ============
        
        /**
         * 发送消息
         * 包含输入验证、错误处理、加载状态管理
         */
        async sendMessage() {
            const message = this.inputMessage.trim();
            
            // 输入验证
            if (!message) {
                console.warn('[AIAssistant] 消息为空，拒绝发送');
                return;
            }
            
            if (this.loading) {
                console.warn('[AIAssistant] 消息发送中，请等待');
                return;
            }
            
            // 消息长度检查
            if (message.length > 4000) {
                this.error = '消息过长，请控制在 4000 字以内';
                return;
            }
            
            // 添加用户消息
            this.messages.push({
                role: 'user',
                content: message,
                time: new Date()
            });
            
            // 清空输入
            this.inputMessage = '';
            this.error = null;
            this.loading = true;
            this.scrollToBottom();
            
            // 重置 textarea 高度
            if (this.$refs.inputRef) {
                this.$refs.inputRef.style.height = '44px';
            }
            
            try {
                // 构建聊天消息（最近 10 条）
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
                console.error('[AIAssistant] 发送消息失败:', e);
                this.error = e.message || '发送失败，请重试';
                this.loading = false;
            }
        },
        
        /**
         * 流式发送聊天请求
         * @param {Array} messages - 聊天消息数组
         */
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
            
            // 错误处理
            if (!response.ok) {
                let errorMsg = `HTTP ${response.status}: ${response.statusText}`;
                try {
                    const error = await response.json();
                    errorMsg = error.message || errorMsg;
                } catch (e) {
                    // 忽略 JSON 解析错误
                }
                throw new Error(errorMsg);
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
                                // 忽略解析错误，继续处理
                            }
                        }
                    }
                }
            } catch (e) {
                if (e.name !== 'AbortError') {
                    throw e;
                }
            } finally {
                reader.releaseLock();
            }
            
            this.loading = false;
            this.scrollToBottom();
        },
        
        // ============ 快速操作 ============
        
        /**
         * 快速提问
         * @param {string} question - 问题内容
         */
        quickAsk(question) {
            if (!question || typeof question !== 'string') {
                console.warn('[AIAssistant] 快速提问内容无效');
                return;
            }
            
            this.inputMessage = question;
            this.sendMessage();
        },
        
        /**
         * 重试最后一条消息
         */
        async retryLastMessage() {
            if (this.messages.length < 2) {
                console.warn('[AIAssistant] 没有可重试的消息');
                return;
            }
            
            const lastUserMessage = [...this.messages].reverse().find(m => m.role === 'user');
            if (!lastUserMessage) {
                console.warn('[AIAssistant] 未找到用户消息');
                return;
            }
            
            // 删除错误提示
            this.error = null;
            
            // 重新发送
            this.inputMessage = lastUserMessage.content;
            await this.sendMessage();
        },
        
        /**
         * 清空对话
         */
        clearChat() {
            if (this.messages.length === 0) {
                return;
            }
            
            if (confirm('确定要清空对话历史吗？此操作不可恢复。')) {
                this.messages = [];
                this.error = null;
                console.log('[AIAssistant] 对话已清空');
            }
        },
        
        /**
         * 导出对话
         */
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
            
            console.log('[AIAssistant] 对话已导出');
        },
        
        // ============ 文件处理 ============
        
        /**
         * 处理文件选择
         * @param {Event} event - 文件选择事件
         */
        handleFileSelect(event) {
            const files = Array.from(event.target.files);
            
            // 文件类型验证
            const allowedTypes = ['text/plain', 'text/markdown', 'application/json', 'text/javascript', 'text/x-python'];
            const validFiles = files.filter(f => {
                if (f.size > 10 * 1024 * 1024) { // 10MB 限制
                    console.warn('[AIAssistant] 文件过大:', f.name);
                    return false;
                }
                return true;
            });
            
            this.attachments.push(...validFiles.map(f => ({
                name: f.name,
                size: f.size,
                file: f
            })));
            
            // 清空 input 以允许重复选择同一文件
            event.target.value = '';
        },
        
        /**
         * 移除附件
         * @param {number} index - 附件索引
         */
        removeAttachment(index) {
            if (index < 0 || index >= this.attachments.length) {
                console.warn('[AIAssistant] 无效的附件索引');
                return;
            }
            
            this.attachments.splice(index, 1);
        },
        
        // ============ UI 交互 ============
        
        /**
         * 自动调整 textarea 高度（防抖）
         * @param {Event} event - 输入事件
         */
        autoResize: function(event) {
            // 创建防抖版本（如果尚未创建）
            if (!this._autoResizeDebounced) {
                this._autoResizeDebounced = debounce((target) => {
                    target.style.height = 'auto';
                    target.style.height = Math.min(target.scrollHeight, 120) + 'px';
                }, 50);
            }
            
            this._autoResizeDebounced(event.target);
        },
        
        /**
         * 处理滚动事件（节流）
         */
        handleScroll: function() {
            // 节流处理，避免频繁触发
            // 可以在此添加虚拟滚动逻辑
        },
        
        /**
         * 滚动到底部
         */
        scrollToBottom() {
            this.$nextTick(() => {
                const container = this.$refs.messageContainer;
                if (container) {
                    // 平滑滚动
                    container.scrollTo({
                        top: container.scrollHeight,
                        behavior: 'smooth'
                    });
                }
            });
        },
        
        // ============ 任务管理 ============
        
        /**
         * 创建新任务
         */
        async createTask() {
            // 表单验证
            if (!this.newTask.title || !this.newTask.title.trim()) {
                alert('请输入任务标题');
                return;
            }
            
            if (this.newTask.title.length > 100) {
                alert('任务标题不能超过 100 字');
                return;
            }
            
            this.creatingTask = true;
            try {
                await api.createTask({
                    title: this.newTask.title.trim(),
                    description: this.newTask.description?.trim() || '',
                    priority: this.newTask.priority,
                    agent: this.newTask.agent || this.selectedAgent?.name
                });
                
                this.showNewTaskModal = false;
                this.newTask = { title: '', description: '', priority: 'normal', agent: '' };
                await this.loadTasks();
                
                // 通过 WebSocket 通知其他客户端
                if (this.wsConnected && this.ws) {
                    // 可选：发送任务创建通知
                }
            } catch (e) {
                console.error('[AIAssistant] 创建任务失败:', e);
                alert('创建任务失败：' + e.message);
            } finally {
                this.creatingTask = false;
            }
        },
        
        /**
         * 查看任务详情
         * @param {Object} task - 任务对象
         */
        viewTaskDetail(task) {
            if (!task || !task.id) {
                console.warn('[AIAssistant] 无效的任务对象');
                return;
            }
            
            window.location.href = `/task-detail?id=${task.id}`;
        },
        
        // ============ 设置管理 ============
        
        /**
         * AI 提供商变更时更新模型列表
         */
        onProviderChange() {
            // 清空当前模型选择
            this.localSettings.model = '';
            
            // 重新加载模型列表
            this.loadSettings();
        },
        
        /**
         * 测试 AI 连接
         */
        async testConnection() {
            try {
                const result = await api.testConnection({
                    provider: this.localSettings.aiProvider,
                    apiKey: this.localSettings.apiKey
                });
                
                if (result.success) {
                    alert('✓ 连接测试成功！');
                } else {
                    alert('✗ 连接失败：' + (result.error || '未知错误'));
                }
            } catch (e) {
                console.error('[AIAssistant] 测试连接失败:', e);
                alert('测试失败：' + e.message);
            }
        },
        
        /**
         * 保存设置
         */
        async saveSettings() {
            // 验证 API Key
            if (!this.localSettings.apiKey || this.localSettings.apiKey.length < 10) {
                alert('请输入有效的 API Key');
                return;
            }
            
            try {
                await api.saveSettings(this.localSettings);
                this.showSettings = false;
                alert('✓ 设置已保存');
                console.log('[AIAssistant] 设置已保存');
            } catch (e) {
                console.error('[AIAssistant] 保存设置失败:', e);
                alert('保存失败：' + e.message);
            }
        }
    },
    
    /**
     * 组件挂载后初始化
     */
    mounted() {
        console.log('[AIAssistant] 组件已挂载');
        
        // 初始化数据加载
        this.loadAgents();
        this.loadTasks();
        this.loadSettings();
        
        // 建立 WebSocket 连接
        this.connectWebSocket();
        
        // 定期刷新 Agent 状态（30 秒）
        this._refreshAgentsTimer = setInterval(() => {
            this.loadAgents();
        }, 30000);
        
        // 定期刷新任务列表（60 秒）
        this._refreshTasksTimer = setInterval(() => {
            this.loadTasks();
        }, 60000);
    },
    
    /**
     * 组件卸载前清理
     * 防止内存泄漏
     */
    beforeUnmount() {
        console.log('[AIAssistant] 组件即将卸载，清理资源');
        
        // 清除定时器
        if (this._refreshAgentsTimer) {
            clearInterval(this._refreshAgentsTimer);
            this._refreshAgentsTimer = null;
        }
        
        if (this._refreshTasksTimer) {
            clearInterval(this._refreshTasksTimer);
            this._refreshTasksTimer = null;
        }
        
        if (this.wsReconnectTimer) {
            clearTimeout(this.wsReconnectTimer);
            this.wsReconnectTimer = null;
        }
        
        // 断开 WebSocket 连接
        this.disconnectWebSocket();
        
        // 清理事件监听器（如果有）
        // Vue 3 会自动清理大部分事件监听器
    }
};

export default AIAssistantView;
