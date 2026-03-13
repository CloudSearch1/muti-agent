/**
 * 工具系统视图组件
 */

import { Badge } from './common/Badge.js';
import { DataTable } from './common/DataTable.js';
import { ConfirmDialog } from './common/ConfirmDialog.js';

export const ToolsView = {
    name: 'ToolsView',
    
    components: {
        Badge,
        DataTable,
        ConfirmDialog
    },
    
    props: {
        tools: {
            type: Array,
            default: () => []
        }
    },
    
    emits: ['execute', 'detail', 'refresh'],
    
    template: `
        <div class="space-y-6">
            <!-- 页面标题 -->
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-white flex items-center gap-3">
                        <i class="fas fa-toolbox text-gh-blue"></i>
                        工具系统
                    </h1>
                    <p class="text-gh-text mt-1">共 {{ tools.length }} 个工具 · {{ enabledCount }} 个已启用</p>
                </div>
                <div class="flex gap-2">
                    <button @click="$emit('refresh')" class="btn-secondary flex items-center gap-2">
                        <i class="fas fa-sync-alt"></i>
                        <span class="hidden sm:inline">刷新</span>
                    </button>
                    <button @click="$emit('execute')" class="btn-primary flex items-center gap-2">
                        <i class="fas fa-play"></i>
                        <span class="hidden sm:inline">执行工具</span>
                    </button>
                </div>
            </div>
            
            <!-- 搜索和过滤 -->
            <div class="gh-card p-4">
                <div class="flex flex-col sm:flex-row gap-4">
                    <div class="flex-1 relative">
                        <input v-model="searchQuery" 
                               type="text" 
                               placeholder="搜索工具..."
                               class="gh-input pl-10">
                        <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gh-text"></i>
                    </div>
                    <select v-model="filterCategory" class="gh-input w-full sm:w-48">
                        <option value="">所有分类</option>
                        <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
                    </select>
                    <select v-model="filterStatus" class="gh-input w-full sm:w-40">
                        <option value="">所有状态</option>
                        <option value="enabled">已启用</option>
                        <option value="disabled">已禁用</option>
                    </select>
                </div>
            </div>
            
            <!-- 工具卡片网格 -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div v-for="tool in filteredTools" :key="tool.name"
                     class="gh-card card-hover group">
                    <div class="flex items-start justify-between mb-3">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-lg bg-gh-elevated flex items-center justify-center border border-gh-border">
                                <i :class="getToolIcon(tool.category)" class="text-lg" :style="{color: getCategoryColor(tool.category)}"></i>
                            </div>
                            <div>
                                <h3 class="font-semibold text-white">{{ tool.name }}</h3>
                                <p class="text-xs text-gh-text">{{ tool.category }}</p>
                            </div>
                        </div>
                        <Badge :type="tool.enabled ? 'success' : 'neutral'" 
                               :text="tool.enabled ? '启用' : '禁用'" 
                               size="sm" />
                    </div>
                    
                    <p class="text-sm text-gh-text mb-4 line-clamp-2">{{ tool.description }}</p>
                    
                    <div class="flex items-center gap-2 pt-3 border-t border-gh-border">
                        <button @click="$emit('detail', tool)" 
                                class="flex-1 btn-secondary text-sm py-1.5">
                            <i class="fas fa-info-circle mr-1"></i>详情
                        </button>
                        <button @click="$emit('execute', tool)" 
                                class="flex-1 btn-primary text-sm py-1.5">
                            <i class="fas fa-play mr-1"></i>执行
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- 空状态 -->
            <div v-if="filteredTools.length === 0" class="text-center py-16">
                <div class="w-16 h-16 mx-auto bg-gh-elevated rounded-full flex items-center justify-center mb-4">
                    <i class="fas fa-toolbox text-2xl text-gh-text"></i>
                </div>
                <p class="text-gh-text mb-4">暂无工具</p>
                <button @click="$emit('refresh')" class="btn-primary">
                    <i class="fas fa-sync-alt mr-2"></i>刷新列表
                </button>
            </div>
        </div>
    `,
    
    data() {
        return {
            searchQuery: '',
            filterCategory: '',
            filterStatus: '',
            categories: ['system', 'web', 'file', 'git', 'search', 'memory', 'general']
        };
    },
    
    computed: {
        enabledCount() {
            return this.tools.filter(t => t.enabled).length;
        },
        
        filteredTools() {
            let result = [...this.tools];
            
            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                result = result.filter(t => 
                    t.name.toLowerCase().includes(query) ||
                    t.description.toLowerCase().includes(query)
                );
            }
            
            if (this.filterCategory) {
                result = result.filter(t => t.category === this.filterCategory);
            }
            
            if (this.filterStatus === 'enabled') {
                result = result.filter(t => t.enabled);
            } else if (this.filterStatus === 'disabled') {
                result = result.filter(t => !t.enabled);
            }
            
            return result;
        }
    },
    
    methods: {
        getToolIcon(category) {
            const icons = {
                'system': 'fas fa-terminal',
                'web': 'fas fa-globe',
                'file': 'fas fa-file',
                'git': 'fas fa-code-branch',
                'search': 'fas fa-search',
                'memory': 'fas fa-brain',
                'general': 'fas fa-toolbox'
            };
            return icons[category] || icons.general;
        },
        
        getCategoryColor(category) {
            const colors = {
                'system': '#0366D6',
                'web': '#33BB22',
                'file': '#F0C744',
                'git': '#8957e5',
                'search': '#DA3633',
                'memory': '#0366D6'
            };
            return colors[category] || '#6A737D';
        }
    }
};
