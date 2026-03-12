/**
 * 任务状态管理
 * 管理任务相关的状态和操作
 */

// 使用全局Vue对象（从CDN加载）
const { reactive, computed } = Vue;
import { api } from '../utils/api.js';
import { DEFAULT_TASKS, PRIORITIES, TASK_STATUS } from '../utils/constants.js';
import { appStore } from './appStore.js';

// 状态
const state = reactive({
    tasks: [...DEFAULT_TASKS],
    filter: 'all', // all, pending, in_progress, completed
    searchQuery: '',
    sortBy: 'createdAt', // createdAt, priority, status
    sortOrder: 'desc', // asc, desc
    loading: false,
    error: null
});

// 计算属性
const getters = {
    // 过滤后的任务
    filteredTasks: computed(() => {
        let result = [...state.tasks];
        
        // 状态过滤
        if (state.filter !== 'all') {
            result = result.filter(t => t.status === state.filter);
        }
        
        // 搜索过滤
        if (state.searchQuery) {
            const query = state.searchQuery.toLowerCase();
            result = result.filter(t => 
                t.title.toLowerCase().includes(query) ||
                t.description.toLowerCase().includes(query) ||
                t.assignee.toLowerCase().includes(query)
            );
        }
        
        // 排序
        result.sort((a, b) => {
            let comparison = 0;
            
            switch (state.sortBy) {
                case 'priority':
                    const priorityOrder = { critical: 4, high: 3, normal: 2, low: 1 };
                    comparison = priorityOrder[a.priority] - priorityOrder[b.priority];
                    break;
                case 'status':
                    const statusOrder = { in_progress: 3, pending: 2, completed: 1 };
                    comparison = statusOrder[a.status] - statusOrder[b.status];
                    break;
                case 'createdAt':
                default:
                    comparison = new Date(a.createdAt) - new Date(b.createdAt);
            }
            
            return state.sortOrder === 'desc' ? -comparison : comparison;
        });
        
        return result;
    }),
    
    // 任务统计
    stats: computed(() => {
        const total = state.tasks.length;
        const pending = state.tasks.filter(t => t.status === 'pending').length;
        const inProgress = state.tasks.filter(t => t.status === 'in_progress').length;
        const completed = state.tasks.filter(t => t.status === 'completed').length;
        
        return {
            total,
            pending,
            inProgress,
            completed,
            completionRate: total > 0 ? Math.round((completed / total) * 100) : 0
        };
    }),
    
    // 最近任务
    recentTasks: computed(() => {
        return state.tasks
            .slice()
            .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
            .slice(0, 5);
    }),
    
    // 按优先级分组
    tasksByPriority: computed(() => {
        const grouped = {};
        Object.keys(PRIORITIES).forEach(key => {
            grouped[key] = state.tasks.filter(t => t.priority === key);
        });
        return grouped;
    }),
    
    // 按状态分组
    tasksByStatus: computed(() => {
        const grouped = {};
        Object.keys(TASK_STATUS).forEach(key => {
            grouped[key] = state.tasks.filter(t => t.status === key);
        });
        return grouped;
    })
};

// 方法
const actions = {
    // 加载任务
    async loadTasks() {
        state.loading = true;
        state.error = null;
        
        try {
            const data = await api.getTasks();
            if (Array.isArray(data)) {
                state.tasks = data;
            }
        } catch (error) {
            state.error = error.message;
            appStore.showToast('加载任务失败: ' + error.message, 'error');
        } finally {
            state.loading = false;
        }
    },
    
    // 获取单个任务
    getTaskById(id) {
        return state.tasks.find(t => t.id === id);
    },
    
    // 创建任务
    async createTask(taskData) {
        state.loading = true;
        
        try {
            const newTask = {
                id: Date.now(),
                ...taskData,
                status: 'pending',
                createdAt: new Date().toISOString(),
                time: '刚刚'
            };
            
            // 添加优先级和状态标签
            newTask.priorityText = PRIORITIES[newTask.priority]?.label || '中优先级';
            newTask.statusText = TASK_STATUS.pending.label;
            
            const result = await api.createTask(newTask);
            
            if (result.task || result.status === 'success') {
                state.tasks.unshift(result.task || newTask);
                appStore.showToast('任务创建成功', 'success');
                return true;
            }
        } catch (error) {
            appStore.showToast('创建任务失败: ' + error.message, 'error');
        } finally {
            state.loading = false;
        }
        
        return false;
    },
    
    // 更新任务
    async updateTask(id, updates) {
        state.loading = true;
        
        try {
            const result = await api.updateTask(id, updates);
            
            if (result.status === 'success') {
                const index = state.tasks.findIndex(t => t.id === id);
                if (index > -1) {
                    // 更新优先级和状态标签
                    if (updates.priority) {
                        updates.priorityText = PRIORITIES[updates.priority]?.label;
                    }
                    if (updates.status) {
                        updates.statusText = TASK_STATUS[updates.status]?.label;
                    }
                    
                    state.tasks[index] = { ...state.tasks[index], ...updates };
                }
                appStore.showToast('任务更新成功', 'success');
                return true;
            }
        } catch (error) {
            appStore.showToast('更新任务失败: ' + error.message, 'error');
        } finally {
            state.loading = false;
        }
        
        return false;
    },
    
    // 删除任务
    async deleteTask(id) {
        state.loading = true;
        
        try {
            const result = await api.deleteTask(id);
            
            if (result.status === 'success') {
                const index = state.tasks.findIndex(t => t.id === id);
                if (index > -1) {
                    state.tasks.splice(index, 1);
                }
                appStore.showToast('任务已删除', 'success');
                return true;
            }
        } catch (error) {
            appStore.showToast('删除任务失败: ' + error.message, 'error');
        } finally {
            state.loading = false;
        }
        
        return false;
    },
    
    // 设置过滤器
    setFilter(filter) {
        state.filter = filter;
    },
    
    // 设置搜索
    setSearchQuery(query) {
        state.searchQuery = query;
    },
    
    // 设置排序
    setSort(sortBy, sortOrder = 'desc') {
        state.sortBy = sortBy;
        state.sortOrder = sortOrder;
    },
    
    // 批量删除
    async deleteTasks(ids) {
        let success = 0;
        for (const id of ids) {
            if (await this.deleteTask(id)) {
                success++;
            }
        }
        return success;
    },
    
    // 批量更新状态
    async updateTasksStatus(ids, status) {
        let success = 0;
        for (const id of ids) {
            if (await this.updateTask(id, { status })) {
                success++;
            }
        }
        return success;
    }
};

// 导出 store
export const taskStore = {
    state,
    ...getters,
    ...actions
};

export default taskStore;
