/**
 * IntelliTeam Web UI - 主应用入口
 * 模块化架构，组件化设计
 */

import { appStore } from './stores/appStore.js';
import { taskStore } from './stores/taskStore.js';
import { agentStore } from './stores/agentStore.js';
import { api } from './utils/api.js';
import { TABS, DEFAULT_AGENTS, DEFAULT_TASKS, DEFAULT_SKILLS, DEFAULT_WORKFLOWS, DEFAULT_SETTINGS } from './utils/constants.js';
import { formatNumber, formatRelativeTime } from './utils/format.js';

// 导入组件
import { DashboardView } from './components/DashboardView.js';
import { TasksView } from './components/TasksView.js';
import { AgentsView } from './components/AgentsView.js';
import { WorkflowsView } from './components/WorkflowsView.js';
import { SkillsView } from './components/SkillsView.js';
import { AIAssistantView } from './components/AIAssistantView.js';

const { createApp } = Vue;

const app = createApp({
    components: {
        DashboardView,
        TasksView,
        AgentsView,
        WorkflowsView,
        SkillsView,
        AIAssistantView
    },
    
    data() {
        return {
            // 从 store 获取状态
            ...appStore.state,
            ...taskStore.state,
            ...agentStore.state,
            
            // 本地状态
            workflows: [...DEFAULT_WORKFLOWS],
            skills: [...DEFAULT_SKILLS],
            settings: { ...DEFAULT_SETTINGS }
        };
    },
    
    computed: {
        // Store 计算属性
        ...taskStore,
        ...agentStore,
        
        // 本地计算属性
        tabs() {
            return TABS;
        },
        
        unreadCount() {
            return this.notifications.filter(n => !n.read).length;
        },
        
        recentTasks() {
            return this.tasks.slice(0, 5);
        },
        
        stats() {
            return {
                totalTasks: this.tasks.length,
                activeAgents: this.agents.filter(a => a.status === 'busy').length,
                completionRate: this.taskStats.completionRate
            };
        }
    },
    
    async mounted() {
        // 初始化主题
        appStore.initTheme();
        
        // 加载数据
        await this.loadData();
        
        // 隐藏加载状态
        setTimeout(() => {
            appStore.setLoading(false);
        }, 500);
        
        // 启动 Agent 状态模拟
        this.simulationInterval = agentStore.startSimulation(8000);
        
        // 键盘快捷键
        document.addEventListener('keydown', this.handleKeydown);
    },
    
    beforeUnmount() {
        clearInterval(this.simulationInterval);
        document.removeEventListener('keydown', this.handleKeydown);
    },
    
    methods: {
        // Store 方法
        ...appStore,
        ...taskStore,
        ...agentStore,
        
        formatNumber,
        formatRelativeTime,
        
        async loadData() {
            try {
                // 并行加载数据
                await Promise.all([
                    taskStore.loadTasks(),
                    agentStore.loadAgents()
                ]);
            } catch (error) {
                console.error('加载数据失败:', error);
                appStore.showToast('加载数据失败，使用默认数据', 'warning');
            }
        },
        
        // 导航
        setTab(tabId) {
            appStore.setTab(tabId);
        },
        
        // 主题
        toggleTheme() {
            appStore.toggleTheme();
        },
        
        // 搜索
        handleSearch() {
            if (this.searchQuery) {
                appStore.showToast(`搜索: ${this.searchQuery}`, 'info');
            }
        },
        
        // 任务操作
        async handleCreateTask(taskData) {
            const success = await taskStore.createTask(taskData);
            if (success) {
                appStore.closeModal('createTask');
            }
        },
        
        async handleUpdateTask(id, updates) {
            const success = await taskStore.updateTask(id, updates);
            if (success) {
                appStore.closeModal('editTask');
            }
        },
        
        async handleDeleteTask(id) {
            await taskStore.deleteTask(id);
        },
        
        viewTaskDetail(task) {
            if (task) {
                appStore.setSelectedTask(task);
                appStore.openModal('taskDetail');
            } else {
                appStore.setTab('tasks');
            }
        },
        
        editTask(task) {
            appStore.setEditingTask(task);
            appStore.openModal('editTask');
        },
        
        // Agent 操作
        viewAgentDetail(agent) {
            appStore.setSelectedAgent(agent);
            appStore.openModal('agentDetail');
        },
        
        // 技能操作
        async handleCreateSkill(skillData) {
            try {
                const result = await api.createSkill(skillData);
                if (result.skill) {
                    this.skills.push(result.skill);
                    appStore.showToast('技能创建成功', 'success');
                    appStore.closeModal('createSkill');
                }
            } catch (error) {
                appStore.showToast('创建技能失败: ' + error.message, 'error');
            }
        },
        
        async handleUpdateSkill(id, updates) {
            try {
                const result = await api.updateSkill(id, updates);
                if (result.status === 'success') {
                    const index = this.skills.findIndex(s => s.id === id);
                    if (index > -1) {
                        this.skills[index] = { ...this.skills[index], ...updates };
                    }
                    appStore.showToast('技能更新成功', 'success');
                    appStore.closeModal('editSkill');
                }
            } catch (error) {
                appStore.showToast('更新技能失败: ' + error.message, 'error');
            }
        },
        
        async handleToggleSkill(skill) {
            try {
                const result = await api.toggleSkill(skill.id);
                if (result.status === 'success') {
                    skill.enabled = !skill.enabled;
                    appStore.showToast(`技能已${skill.enabled ? '启用' : '禁用'}`, 'success');
                }
            } catch (error) {
                appStore.showToast('操作失败: ' + error.message, 'error');
            }
        },
        
        async handleDeleteSkill(id) {
            try {
                const result = await api.deleteSkill(id);
                if (result.status === 'success') {
                    const index = this.skills.findIndex(s => s.id === id);
                    if (index > -1) {
                        this.skills.splice(index, 1);
                    }
                    appStore.showToast('技能已删除', 'success');
                }
            } catch (error) {
                appStore.showToast('删除失败: ' + error.message, 'error');
            }
        },
        
        // 设置
        async saveSettings() {
            try {
                await api.saveSettings(this.settings);
                appStore.showToast('设置已保存', 'success');
                appStore.showSettings = false;
            } catch (error) {
                appStore.showToast('保存失败: ' + error.message, 'error');
            }
        },
        
        // 键盘快捷键
        handleKeydown(e) {
            // Ctrl/Cmd + K - 搜索
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.querySelector('input[type="text"]')?.focus();
            }
            
            // Ctrl/Cmd + N - 新建任务
            if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
                e.preventDefault();
                if (this.currentTab === 'tasks') {
                    appStore.openModal('createTask');
                }
            }
            
            // ESC - 关闭模态框
            if (e.key === 'Escape') {
                appStore.closeAllModals();
            }
        }
    }
});

// 挂载应用
app.mount('#app');

// 全局错误处理
window.addEventListener('error', (e) => {
    console.error('全局错误:', e.error);
});

window.addEventListener('unhandledrejection', (e) => {
    console.error('未处理的Promise拒绝:', e.reason);
});
