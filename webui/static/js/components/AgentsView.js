/**
 * Agent 管理视图组件
 */

import { Badge } from './common/Badge.js';
import { AGENT_STATUS } from '../utils/constants.js';
import { formatNumber } from '../utils/format.js';

export const AgentsView = {
    name: 'AgentsView',
    
    components: {
        Badge
    },
    
    props: {
        agents: {
            type: Array,
            default: () => []
        }
    },
    
    emits: ['view-detail'],
    
    template: `
        <div class="space-y-6">
            <!-- 页面标题 -->
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-white">Agent 团队</h1>
                    <p class="text-gh-text mt-1">共 {{ agents.length }} 个智能体 · {{ activeCount }} 个工作中</p>
                </div>
            </div>
            
            <!-- Agent 卡片网格 -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                <div v-for="agent in agents" :key="agent.name"
                     @click="$emit('view-detail', agent)"
                     class="gh-card card-hover cursor-pointer group">
                    <!-- 头部 -->
                    <div class="flex items-start justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-gh-elevated to-gh-border flex items-center justify-center border border-gh-border group-hover:border-gh-blue/50 transition">
                                <i :class="[agent.icon, 'text-xl text-white']"></i>
                            </div>
                            <div>
                                <h3 class="font-semibold text-white">{{ agent.name }}</h3>
                                <p class="text-sm text-gh-text">{{ agent.role }}</p>
                            </div>
                        </div>
                        <div :class="['flex items-center gap-1.5 text-xs px-2 py-1 rounded-full', agentStatus(agent.status).bgColor]">
                            <i :class="[agentStatus(agent.status).icon, 'text-[8px]', agentStatus(agent.status).color]"></i>
                            <span :class="agentStatus(agent.status).color">{{ agentStatus(agent.status).label }}</span>
                        </div>
                    </div>
                    
                    <!-- 描述 -->
                    <p class="text-sm text-gh-text mb-4 line-clamp-2">{{ agent.description }}</p>
                    
                    <!-- 统计 -->
                    <div class="grid grid-cols-3 gap-2 py-3 border-t border-gh-border">
                        <div class="text-center">
                            <p class="text-lg font-bold text-white">{{ formatNumber(agent.tasksCompleted) }}</p>
                            <p class="text-xs text-gh-text">完成任务</p>
                        </div>
                        <div class="text-center border-x border-gh-border">
                            <p class="text-lg font-bold text-white">{{ agent.avgTime }}s</p>
                            <p class="text-xs text-gh-text">平均耗时</p>
                        </div>
                        <div class="text-center">
                            <p class="text-lg font-bold text-gh-green">{{ agent.successRate }}%</p>
                            <p class="text-xs text-gh-text">成功率</p>
                        </div>
                    </div>
                    
                    <!-- 进度条 -->
                    <div class="mt-4">
                        <div class="flex items-center justify-between text-xs mb-1">
                            <span class="text-gh-text">负载</span>
                            <span class="text-white">{{ agentLoad(agent) }}%</span>
                        </div>
                        <div class="h-1.5 bg-gh-border rounded-full overflow-hidden">
                            <div :class="['h-full rounded-full transition-all', agentLoadColor(agent)]"
                                 :style="{ width: agentLoad(agent) + '%' }"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 团队统计 -->
            <div class="gh-card">
                <div class="gh-card-header">
                    <h2 class="text-lg font-semibold text-white">团队统计</h2>
                </div>
                <div class="gh-card-body">
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-6">
                        <div class="text-center">
                            <p class="text-3xl font-bold text-white">{{ agents.length }}</p>
                            <p class="text-sm text-gh-text mt-1">总Agent数</p>
                        </div>
                        <div class="text-center">
                            <p class="text-3xl font-bold text-gh-green">{{ activeCount }}</p>
                            <p class="text-sm text-gh-text mt-1">工作中</p>
                        </div>
                        <div class="text-center">
                            <p class="text-3xl font-bold text-white">{{ totalTasks }}</p>
                            <p class="text-sm text-gh-text mt-1">总完成任务</p>
                        </div>
                        <div class="text-center">
                            <p class="text-3xl font-bold text-gh-blue">{{ avgSuccessRate }}%</p>
                            <p class="text-sm text-gh-text mt-1">平均成功率</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    computed: {
        activeCount() {
            return this.agents.filter(a => a.status === 'busy').length;
        },
        
        totalTasks() {
            return this.agents.reduce((sum, a) => sum + (a.tasksCompleted || 0), 0);
        },
        
        avgSuccessRate() {
            if (this.agents.length === 0) return 0;
            const avg = this.agents.reduce((sum, a) => sum + (a.successRate || 0), 0) / this.agents.length;
            return Math.round(avg);
        }
    },
    
    methods: {
        formatNumber,
        
        agentStatus(status) {
            return AGENT_STATUS[status] || AGENT_STATUS.offline;
        },
        
        agentLoad(agent) {
            // 模拟负载计算
            return agent.status === 'busy' ? Math.floor(Math.random() * 30) + 60 : Math.floor(Math.random() * 20);
        },
        
        agentLoadColor(agent) {
            const load = this.agentLoad(agent);
            if (load > 80) return 'bg-gh-red';
            if (load > 50) return 'bg-gh-yellow';
            return 'bg-gh-green';
        }
    }
};

export default AgentsView;
