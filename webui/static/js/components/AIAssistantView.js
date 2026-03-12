/**
 * AI 助手视图组件
 */

import { formatDate } from '../utils/format.js';

export const AIAssistantView = {
    name: 'AIAssistantView',
    
    props: {
        settings: {
            type: Object,
            default: () => ({})
        }
    },
    
    template: `
        <div class="h-[calc(100vh-180px)] flex gap-6">
            <!-- 文件浏览器侧边栏 -->
            <div class="w-64 gh-card hidden lg:flex flex-col">
                <div class="gh-card-header flex items-center justify-between">
                    <span class="flex items-center gap-2 text-sm">
                        <i class="fas fa-folder-open text-gh-text"></i>
                        项目文件
                    </span>
                    <button @click="refreshFiles" class="text-gh-text hover:text-white transition">
                        <i class="fas fa-sync-alt" :class="{ 'fa-spin': fileLoading }"></i>
                    </button>
                </div>
                <div class="flex-1 overflow-y-auto p-2">
                    <div v-for="item in fileTree" :key="item.path"
                         @click="selectFile(item)"
                         :class="['flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer text-sm transition',
                                  selectedFile?.path === item.path ? 'bg-gh-blue/20 text-gh-blue' : 'text-gh-text hover:bg-gh-elevated']">
                        <i :class="[item.type === 'folder' ? 'fas fa-folder text-gh-blue' : 'fas fa-file text-gh-text']"></i>
                        <span class="truncate">{{ item.name }}</span>
                    </div>
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
                                <span class="w-2 h-2 rounded-full bg-gh-green animate-pulse"></span>
                                在线
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <button @click="clearChat" class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-white hover:bg-gh-elevated transition" title="清空对话">
                            <i class="fas fa-trash-alt text-sm"></i>
                        </button>
                        <button class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-white hover:bg-gh-elevated transition" title="设置">
                            <i class="fas fa-cog text-sm"></i>
                        </button>
                    </div>
                </div>
                
                <!-- 消息列表 -->
                <div ref="messageContainer" class="flex-1 overflow-y-auto p-4 space-y-4">
                    <div v-if="messages.length === 0" class="h-full flex flex-col items-center justify-center text-gh-text">
                        <div class="w-20 h-20 rounded-full bg-gh-elevated flex items-center justify-center mb-4">
                            <i class="fas fa-robot text-3xl"></i>
                        </div>
                        <p class="text-lg font-medium text-white mb-2">有什么可以帮您的？</p>
                        <p class="text-sm">我可以帮您编写代码、解答问题、分析项目等</p>
                    </div>
                    
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
                            <p class="text-xs mt-1 opacity-60">{{ formatDate(msg.time, 'HH:mm') }}</p>
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
                </div>
                
                <!-- 输入区域 -->
                <div class="p-4 border-t border-gh-border">
                    <div class="flex gap-3">
                        <button class="w-10 h-10 rounded-xl bg-gh-elevated flex items-center justify-center text-gh-text hover:text-white transition">
                            <i class="fas fa-paperclip"></i>
                        </button>
                        <div class="flex-1 relative">
                            <textarea v-model="inputMessage"
                                      @keydown.enter.prevent="sendMessage"
                                      placeholder="输入消息..."
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
        </div>
    `,
    
    data() {
        return {
            messages: [],
            inputMessage: '',
            loading: false,
            fileLoading: false,
            selectedFile: null,
            fileTree: [
                { name: 'src', type: 'folder', path: 'src' },
                { name: 'agents', type: 'folder', path: 'src/agents' },
                { name: 'core', type: 'folder', path: 'src/core' },
                { name: 'webui', type: 'folder', path: 'webui' },
                { name: 'tests', type: 'folder', path: 'tests' },
                { name: 'README.md', type: 'file', path: 'README.md' },
                { name: 'requirements.txt', type: 'file', path: 'requirements.txt' },
                { name: 'pyproject.toml', type: 'file', path: 'pyproject.toml' }
            ]
        };
    },
    
    methods: {
        formatDate,
        
        renderMarkdown(content) {
            if (typeof marked !== 'undefined') {
                return marked.parse(content);
            }
            return content;
        },
        
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
            this.loading = true;
            this.scrollToBottom();
            
            // 模拟AI回复
            setTimeout(() => {
                this.messages.push({
                    role: 'assistant',
                    content: '我理解您的需求。作为AI助手，我可以帮助您：\n\n1. **代码审查** - 分析代码质量和潜在问题\n2. **功能开发** - 根据需求生成代码\n3. **问题解答** - 回答技术问题\n4. **文档生成** - 自动生成技术文档\n\n请问您具体需要什么帮助？',
                    time: new Date()
                });
                this.loading = false;
                this.scrollToBottom();
            }, 1500);
        },
        
        scrollToBottom() {
            this.$nextTick(() => {
                const container = this.$refs.messageContainer;
                if (container) {
                    container.scrollTop = container.scrollHeight;
                }
            });
        },
        
        clearChat() {
            this.messages = [];
        },
        
        selectFile(file) {
            this.selectedFile = file;
        },
        
        refreshFiles() {
            this.fileLoading = true;
            setTimeout(() => {
                this.fileLoading = false;
            }, 500);
        }
    },
    
    mounted() {
        // 欢迎消息
        setTimeout(() => {
            if (this.messages.length === 0) {
                this.messages.push({
                    role: 'assistant',
                    content: '您好！我是 IntelliTeam AI 助手。我可以帮助您编写代码、解答问题、分析项目等。请问有什么可以帮您的？',
                    time: new Date()
                });
            }
        }, 500);
    }
};

export default AIAssistantView;
