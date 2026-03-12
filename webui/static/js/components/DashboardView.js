/**
 * 仪表盘视图组件
 */

import { Badge } from './common/Badge.js';
import { formatNumber, formatRelativeTime } from '../utils/format.js';
import { TASK_STATUS, AGENT_STATUS } from '../utils/constants.js';

export const DashboardView = {
    name: 'DashboardView',
    
    components: {
        Badge
    },
    
    props: {
        stats: {
            type: Object,
            default: () => ({ totalTasks: 0, activeAgents: 0, completionRate: 0 })
        },
        agents: {
            type: Array,
            default: () => []
        },
        tasks: {
            type: Array,
            default: () => []
        }
    },
    
    emits: ['view-task', 'view-agent'],
    
    template: `
        <div class="space-y-6">
            <!-- 页面标题 -->
            <div class="flex items-center justify-between">
                <h1 class="text-2xl font-bold text-white">仪表盘</h1>
                <span class="text-sm text-gh-text">{{ currentTime }}</span>
            </div>
            
            <!-- 统计卡片 -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="gh-card card-hover p-5">
                    <div class="flex items-start justify-between">
                        <div>
                            <p class="text-sm text-gh-text font-medium">总任务数</p>
                            <p class="text-3xl font-bold text-white mt-1">{{ formatNumber(stats.totalTasks) }}</p>
                            <p class="text-xs text-gh-green mt-2 flex items-center">
                                <i class="fas fa-arrow-up mr-1"></i>+12% 本周
                            </p>
                        </div>
                        <div class="w-12 h-12 bg-gh-elevated rounded-xl flex items-center justify-center border border-gh-border">
                            <i class="fas fa-tasks text-gh-text text-lg"></i>
                        </div>
                    </div>
                </div>
                
                <div class="gh-card card-hover p-5">
                    <div class="flex items-start justify-between">
                        <div>
                            <p class="text-sm text-gh-text font-medium">活跃 Agent</p>
                            <p class="text-3xl font-bold text-white mt-1">{{ stats.activeAgents }}</p>
                            <p class="text-xs text-gh-green mt-2 flex items-center">
                                <i class="fas fa-check-circle mr-1"></i>全部在线
                            </p>
                        </div>
                        <div class="w-12 h-12 bg-gh-elevated rounded-xl flex items-center justify-center border border-gh-border">
                            <i class="fas fa-robot text-gh-text text-lg"></i>
                        </div>
                    </div>
                </div>
                
                <div class="gh-card card-hover p-5">
                    <div class="flex items-start justify-between">
                        <div>
                            <p class="text-sm text-gh-text font-medium">完成率</p>
                            <p class="text-3xl font-bold text-white mt-1">{{ stats.completionRate }}%</p>
                            <p class="text-xs text-gh-text mt-2">本月平均</p>
                        </div>
                        <div class="w-12 h-12 bg-gh-elevated rounded-xl flex items-center justify-center border border-gh-border">
                            <i class="fas fa-chart-pie text-gh-text text-lg"></i>
                        </div>
                    </div>
                </div>
                
                <div class="gh-card card-hover p-5">
                    <div class="flex items-start justify-between">
                        <div>
                            <p class="text-sm text-gh-text font-medium">系统状态</p>
                            <p class="text-3xl font-bold text-gh-green mt-1">正常</p>
                            <p class="text-xs text-gh-text mt-2">运行中</p>
                        </div>
                        <div class="w-12 h-12 bg-gh-green/10 rounded-xl flex items-center justify-center border border-gh-green/20">
                            <i class="fas fa-check-circle text-gh-green text-lg"></i>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 主内容区 -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- 最近任务 -->
                <div class="lg:col-span-2 gh-card">
                    <div class="gh-card-header flex items-center justify-between">
                        <h2 class="text-lg font-semibold text-white flex items-center">
                            <i class="fas fa-clock-rotate-left mr-2 text-gh-text"></i>最近任务
                        </h2>
                        <button @click="$emit('view-task', null)" class="text-sm text-gh-blue hover:underline">
                            查看全部
                        </button>
                    </div>
                    <div class="divide-y divide-gh-border">
                        <div v-for="task in tasks" :key="task.id"
                             @click="$emit('view-task', task)"
                             class="p-4 hover:bg-gh-elevated/30 transition cursor-pointer flex items-center justify-between">
                            <div class="flex items-center gap-4">
                                <div :class="['w-2 h-2 rounded-full', statusColor(task.status)]"></div>
                                <div>
                                    <p class="text-white font-medium">{{ task.title }}</p>
                                    <p class="text-sm text-gh-text">{{ task.agent }} · {{ formatRelativeTime(task.createdAt) }}</p>
                                </div>
                            </div>
                            <Badge :type="priorityType(task.priority)" :text="task.priorityText" size="sm" />
                        </div>
                    </div>
                </div>
                
                <!-- Agent 状态 -->
                <div class="gh-card">
                    <div class="gh-card-header">
                        <h2 class="text-lg font-semibold text-white flex items-center">
                            <i class="fas fa-users mr-2 text-gh-text"></i>Agent 状态
                        </h2>
                    </div>
                    <div class="divide-y divide-gh-border">
                        <div v-for="agent in activeAgents" :key="agent.name"
                             @click="$emit('view-agent', agent)"
                             class="p-4 hover:bg-gh-elevated/30 transition cursor-pointer">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 bg-gh-elevated rounded-lg flex items-center justify-center border border-gh-border">
                                    <i :class="[agent.icon, 'text-gh-text']"></i>
                                </div>
                                <div class="flex-1">
                                    <p class="text-white font-medium">{{ agent.name }}</p>
                                    <p class="text-sm text-gh-text">{{ agent.role }}</p>
                                </div>
                                <div :class="['flex items-center gap-1.5 text-xs', agentStatus(agent.status).color]">
                                    <i :class="[agentStatus(agent.status).icon, 'text-[10px]']"></i>
                                    {{ agentStatus(agent.status).label }}
                                </div>
                            </div>
                            <div class="mt-3 flex items-center gap-4 text-xs text-gh-text">
                                <span><i class="fas fa-check mr-1"></i>{{ agent.tasksCompleted }} 任务</span>
                                <span><i class="fas fa-percentage mr-1"></i>{{ agent.successRate }}% 成功率</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 快速操作 -->
            <div class="gh-card">
                <div class="gh-card-header">
                    <h2 class="text-lg font-semibold text-white">快速操作</h2>
                </div>
                <div class="gh-card-body">
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        <button @click="$emit('view-task', null)" class="flex flex-col items-center gap-3 p-4 rounded-xl border border-gh-border hover:border-gh-blue hover:bg-gh-blue/5 transition group">
                            <div class="w-12 h-12 rounded-xl bg-gh-elevated flex items-center justify-center group-hover:bg-gh-blue/10 transition">
                                <i class="fas fa-plus text-gh-text group-hover:text-gh-blue"></i>
                            </div>
                            <span class="text-sm text-gh-text group-hover:text-white">新建任务</span>
                        </button>
                        
                        <button class="flex flex-col items-center gap-3 p-4 rounded-xl border border-gh-border hover:border-gh-green hover:bg-gh-green/5 transition group">
                            <div class="w-12 h-12 rounded-xl bg-gh-elevated flex items-center justify-center group-hover:bg-gh-green/10 transition">
                                <i class="fas fa-play text-gh-text group-hover:text-gh-green"></i>
                            </div>
                            <span class="text-sm text-gh-text group-hover:text-white">启动工作流</span>
                        </button>
                        
                        <button class="flex flex-col items-center gap-3 p-4 rounded-xl border border-gh-border hover:border-gh-purple hover:bg-gh-purple/5 transition group">
                            <div class="w-12 h-12 rounded-xl bg-gh-elevated flex items-center justify-center group-hover:bg-gh-purple/10 transition">
                                <i class="fas fa-robot text-gh-text group-hover:text-gh-purple"></i>
                            </div>
                            <span class="text-sm text-gh-text group-hover:text-white">AI 助手</span>
                        </button>
                        
                        <button class="flex flex-col items-center gap-3 p-4 rounded-xl border border-gh-border hover:border-gh-yellow hover:bg-gh-yellow/5 transition group">
                            <div class="w-12 h-12 rounded-xl bg-gh-elevated flex items-center justify-center group-hover:bg-gh-yellow/10 transition">
                                <i class="fas fa-cog text-gh-text group-hover:text-gh-yellow"></i>
                            </div>
                            <span class="text-sm text-gh-text group-hover:text-white">系统设置</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    data() {
        return {
            currentTime: ''
        };
    },
    
    computed: {
        activeAgents() {
            return this.agents.slice(0, 5);
        }
    },
    
    mounted() {
        this.updateTime();
        this.timeInterval = setInterval(() => this.updateTime(), 60000);
    },
    
    beforeUnmount() {
        clearInterval(this.timeInterval);
    },
    
    methods: {
        formatNumber,
        formatRelativeTime,
        
        updateTime() {
            this.currentTime = new Date().toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        },
        
        statusColor(status) {
            const colors = {
                pending: 'bg-gh-text',
                in_progress: 'bg-gh-blue',
                completed: 'bg-gh-green'
            };
            return colors[status] || 'bg-gh-text';
        },
        
        priorityType(priority) {
            const types = {
                low: 'neutral',
                normal: 'info',
                high: 'warning',
                critical: 'danger'
            };
            return types[priority] || 'neutral';
        },
        
        agentStatus(status) {
            return AGENT_STATUS[status] || AGENT_STATUS.offline;
        }
    }
};

export default DashboardView;
