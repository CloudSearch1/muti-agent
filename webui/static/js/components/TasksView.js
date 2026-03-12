/**
 * 任务管理视图组件
 */

import { Badge } from './common/Badge.js';
import { DataTable } from './common/DataTable.js';
import { Modal } from './common/Modal.js';
import { ConfirmDialog } from './common/ConfirmDialog.js';
import { PRIORITIES, TASK_STATUS, DEFAULT_AGENTS } from '../utils/constants.js';
import { formatRelativeTime } from '../utils/format.js';

export const TasksView = {
    name: 'TasksView',
    
    components: {
        Badge,
        DataTable,
        Modal,
        ConfirmDialog
    },
    
    props: {
        tasks: {
            type: Array,
            default: () => []
        }
    },
    
    emits: ['create-task', 'edit-task', 'delete-task', 'view-detail'],
    
    template: `
        <div class="space-y-6">
            <!-- 页面标题 -->
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-white">任务管理</h1>
                    <p class="text-gh-text mt-1">共 {{ tasks.length }} 个任务</p>
                </div>
                <button @click="$emit('create-task')" class="btn-primary flex items-center justify-center gap-2">
                    <i class="fas fa-plus"></i>新建任务
                </button>
            </div>
            
            <!-- 统计卡片 -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div v-for="stat in taskStats" :key="stat.key"
                     @click="filterStatus = stat.key"
                     :class="['gh-card p-4 cursor-pointer transition', filterStatus === stat.key ? 'border-gh-blue bg-gh-blue/5' : 'card-hover']">
                    <p class="text-sm text-gh-text">{{ stat.label }}</p>
                    <p class="text-2xl font-bold text-white mt-1">{{ stat.count }}</p>
                </div>
            </div>
            
            <!-- 过滤和搜索 -->
            <div class="flex flex-col sm:flex-row gap-4">
                <div class="flex-1 relative">
                    <input v-model="searchQuery" 
                           type="text" 
                           placeholder="搜索任务..."
                           class="gh-input pl-10">
                    <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gh-text"></i>
                </div>
                <select v-model="filterPriority" class="gh-input w-full sm:w-40">
                    <option value="">所有优先级</option>
                    <option v-for="(item, key) in PRIORITIES" :key="key" :value="key">{{ item.label }}</option>
                </select>
                <select v-model="sortBy" class="gh-input w-full sm:w-40">
                    <option value="createdAt">最新创建</option>
                    <option value="priority">优先级</option>
                    <option value="status">状态</option>
                </select>
            </div>
            
            <!-- 任务列表 -->
            <div class="gh-card overflow-hidden">
                <DataTable :columns="columns" 
                          :data="filteredTasks"
                          :loading="loading"
                          :selectable="true"
                          v-model:selectedKeys="selectedTasks"
                          @row-click="handleRowClick">
                    <!-- 标题列 -->
                    <template #title="{ row }">
                        <div>
                            <p class="text-white font-medium">{{ row.title }}</p>
                            <p class="text-xs text-gh-text truncate max-w-xs">{{ row.description }}</p>
                        </div>
                    </template>
                    
                    <!-- 优先级列 -->
                    <template #priority="{ value }">
                        <Badge :type="priorityType(value)" :text="PRIORITIES[value]?.label || value" size="sm" />
                    </template>
                    
                    <!-- 状态列 -->
                    <template #status="{ value }">
                        <div class="flex items-center gap-2">
                            <i :class="[TASK_STATUS[value]?.icon, TASK_STATUS[value]?.color]"></i>
                            <span :class="TASK_STATUS[value]?.color">{{ TASK_STATUS[value]?.label }}</span>
                        </div>
                    </template>
                    
                    <!-- 负责人列 -->
                    <template #assignee="{ row }">
                        <div class="flex items-center gap-2">
                            <div class="w-6 h-6 rounded-full bg-gh-elevated flex items-center justify-center text-xs">
                                {{ row.assignee.charAt(0) }}
                            </div>
                            <span>{{ row.assignee }}</span>
                        </div>
                    </template>
                    
                    <!-- Agent列 -->
                    <template #agent="{ value }">
                        <span class="text-gh-blue">{{ value }}</span>
                    </template>
                    
                    <!-- 时间列 -->
                    <template #createdAt="{ value }">
                        <span class="text-gh-text text-xs">{{ formatRelativeTime(value) }}</span>
                    </template>
                    
                    <!-- 操作列 -->
                    <template #actions="{ row }">
                        <div class="flex items-center gap-2">
                            <button @click.stop="$emit('edit-task', row)" 
                                    class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-white hover:bg-gh-elevated transition"
                                    title="编辑">
                                <i class="fas fa-edit text-sm"></i>
                            </button>
                            <button @click.stop="confirmDelete(row)" 
                                    class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-gh-red hover:bg-gh-red/10 transition"
                                    title="删除">
                                <i class="fas fa-trash text-sm"></i>
                            </button>
                        </div>
                    </template>
                </DataTable>
            </div>
            
            <!-- 删除确认 -->
            <ConfirmDialog v-model:visible="showDeleteConfirm"
                          type="danger"
                          title="删除任务"
                          :message="deleteMessage"
                          confirmText="删除"
                          :confirmLoading="deleting"
                          @confirm="handleDelete" />
        </div>
    `,
    
    data() {
        return {
            loading: false,
            searchQuery: '',
            filterStatus: 'all',
            filterPriority: '',
            sortBy: 'createdAt',
            selectedTasks: [],
            showDeleteConfirm: false,
            deleting: false,
            taskToDelete: null,
            PRIORITIES,
            TASK_STATUS,
            columns: [
                { key: 'title', title: '任务', width: '300px' },
                { key: 'priority', title: '优先级', width: '100px', align: 'center' },
                { key: 'status', title: '状态', width: '120px', align: 'center' },
                { key: 'assignee', title: '负责人', width: '120px' },
                { key: 'agent', title: 'Agent', width: '120px' },
                { key: 'createdAt', title: '创建时间', width: '120px', align: 'center' },
                { key: 'actions', title: '操作', width: '100px', align: 'center' }
            ]
        };
    },
    
    computed: {
        taskStats() {
            const all = this.tasks.length;
            const pending = this.tasks.filter(t => t.status === 'pending').length;
            const inProgress = this.tasks.filter(t => t.status === 'in_progress').length;
            const completed = this.tasks.filter(t => t.status === 'completed').length;
            
            return [
                { key: 'all', label: '全部', count: all },
                { key: 'pending', label: '待处理', count: pending },
                { key: 'in_progress', label: '进行中', count: inProgress },
                { key: 'completed', label: '已完成', count: completed }
            ];
        },
        
        filteredTasks() {
            let result = [...this.tasks];
            
            // 状态过滤
            if (this.filterStatus !== 'all') {
                result = result.filter(t => t.status === this.filterStatus);
            }
            
            // 优先级过滤
            if (this.filterPriority) {
                result = result.filter(t => t.priority === this.filterPriority);
            }
            
            // 搜索
            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                result = result.filter(t => 
                    t.title.toLowerCase().includes(query) ||
                    t.description.toLowerCase().includes(query)
                );
            }
            
            // 排序
            result.sort((a, b) => {
                if (this.sortBy === 'createdAt') {
                    return new Date(b.createdAt) - new Date(a.createdAt);
                }
                if (this.sortBy === 'priority') {
                    const order = { critical: 4, high: 3, normal: 2, low: 1 };
                    return order[b.priority] - order[a.priority];
                }
                return 0;
            });
            
            return result;
        },
        
        deleteMessage() {
            return this.taskToDelete 
                ? `确定要删除任务 "${this.taskToDelete.title}" 吗？此操作不可恢复。`
                : '';
        }
    },
    
    methods: {
        formatRelativeTime,
        
        priorityType(priority) {
            const types = {
                low: 'neutral',
                normal: 'info',
                high: 'warning',
                critical: 'danger'
            };
            return types[priority] || 'neutral';
        },
        
        handleRowClick(row) {
            this.$emit('view-detail', row);
        },
        
        confirmDelete(task) {
            this.taskToDelete = task;
            this.showDeleteConfirm = true;
        },
        
        async handleDelete() {
            if (!this.taskToDelete) return;
            
            this.deleting = true;
            this.$emit('delete-task', this.taskToDelete.id);
            this.deleting = false;
            this.showDeleteConfirm = false;
            this.taskToDelete = null;
        }
    }
};

export default TasksView;
