/**
 * Agent 状态管理
 * 管理 Agent 相关的状态和操作
 */

import { reactive, computed } from 'vue';
import { api } from '../utils/api.js';
import { DEFAULT_AGENTS, AGENT_STATUS } from '../utils/constants.js';
import { appStore } from './appStore.js';

// 状态
const state = reactive({
    agents: [...DEFAULT_AGENTS],
    loading: false,
    error: null,
    selectedAgent: null
});

// 计算属性
const getters = {
    // 活跃 Agent 数
    activeCount: computed(() => {
        return state.agents.filter(a => a.status === 'busy').length;
    }),
    
    // 在线 Agent 数
    onlineCount: computed(() => {
        return state.agents.filter(a => a.status !== 'offline').length;
    }),
    
    // 按状态分组
    agentsByStatus: computed(() => {
        const grouped = { idle: [], busy: [], offline: [] };
        state.agents.forEach(agent => {
            if (grouped[agent.status]) {
                grouped[agent.status].push(agent);
            }
        });
        return grouped;
    }),
    
    // 统计信息
    stats: computed(() => {
        const totalTasks = state.agents.reduce((sum, a) => sum + (a.tasksCompleted || 0), 0);
        const avgSuccessRate = state.agents.length > 0 
            ? state.agents.reduce((sum, a) => sum + (a.successRate || 0), 0) / state.agents.length 
            : 0;
        const avgTime = state.agents.length > 0
            ? state.agents.reduce((sum, a) => sum + (a.avgTime || 0), 0) / state.agents.length
            : 0;
        
        return {
            totalTasks,
            avgSuccessRate: Math.round(avgSuccessRate),
            avgTime: avgTime.toFixed(1)
        };
    }),
    
    // 获取 Agent 状态信息
    getAgentStatus: computed(() => (status) => {
        return AGENT_STATUS[status] || AGENT_STATUS.offline;
    })
};

// 方法
const actions = {
    // 加载 Agents
    async loadAgents() {
        state.loading = true;
        state.error = null;
        
        try {
            const data = await api.getAgents();
            if (Array.isArray(data)) {
                state.agents = data;
            }
        } catch (error) {
            state.error = error.message;
            appStore.showToast('加载 Agent 失败: ' + error.message, 'error');
        } finally {
            state.loading = false;
        }
    },
    
    // 获取单个 Agent
    getAgentByName(name) {
        return state.agents.find(a => a.name === name);
    },
    
    // 更新 Agent 状态
    updateAgentStatus(name, newStatus, metadata = {}) {
        const agent = state.agents.find(a => a.name === name);
        if (agent) {
            agent.status = newStatus;
            if (metadata.tasksCompleted !== undefined) {
                agent.tasksCompleted = metadata.tasksCompleted;
            }
            if (metadata.avgTime !== undefined) {
                agent.avgTime = metadata.avgTime;
            }
            if (metadata.successRate !== undefined) {
                agent.successRate = metadata.successRate;
            }
        }
    },
    
    // 批量更新状态
    updateAgentsStatus(updates) {
        updates.forEach(({ name, status, metadata }) => {
            this.updateAgentStatus(name, status, metadata);
        });
    },
    
    // 选择 Agent
    selectAgent(agent) {
        state.selectedAgent = agent ? { ...agent } : null;
    },
    
    // 模拟状态变化（用于演示）
    simulateStatusChange() {
        const idleAgents = state.agents.filter(a => a.status === 'idle');
        const busyAgents = state.agents.filter(a => a.status === 'busy');
        
        // 随机让一个空闲 Agent 变为忙碌
        if (idleAgents.length > 0 && Math.random() > 0.7) {
            const agent = idleAgents[Math.floor(Math.random() * idleAgents.length)];
            this.updateAgentStatus(agent.name, 'busy', {
                tasksCompleted: agent.tasksCompleted + 1
            });
        }
        
        // 随机让一个忙碌 Agent 变为空闲
        if (busyAgents.length > 0 && Math.random() > 0.6) {
            const agent = busyAgents[Math.floor(Math.random() * busyAgents.length)];
            this.updateAgentStatus(agent.name, 'idle');
        }
    },
    
    // 开始状态模拟
    startSimulation(interval = 5000) {
        return setInterval(() => {
            this.simulateStatusChange();
        }, interval);
    }
};

// 导出 store
export const agentStore = {
    state,
    ...getters,
    ...actions
};

export default agentStore;
