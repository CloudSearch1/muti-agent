/**
 * 技能管理视图组件
 */

import { Badge } from './common/Badge.js';
import { DataTable } from './common/DataTable.js';
import { ConfirmDialog } from './common/ConfirmDialog.js';
import { SKILL_CATEGORIES } from '../utils/constants.js';

export const SkillsView = {
    name: 'SkillsView',
    
    components: {
        Badge,
        DataTable,
        ConfirmDialog
    },
    
    props: {
        skills: {
            type: Array,
            default: () => []
        }
    },
    
    emits: ['create', 'edit', 'toggle', 'delete'],
    
    template: `
        <div class="space-y-6">
            <!-- 页面标题 -->
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-white">技能管理</h1>
                    <p class="text-gh-text mt-1">共 {{ skills.length }} 个技能 · {{ enabledCount }} 个已启用</p>
                </div>
                <button @click="$emit('create')" class="btn-primary flex items-center justify-center gap-2">
                    <i class="fas fa-plus"></i>新建技能
                </button>
            </div>
            
            <!-- 过滤 -->
            <div class="flex flex-col sm:flex-row gap-4">
                <div class="flex-1 relative">
                    <input v-model="searchQuery" 
                           type="text" 
                           placeholder="搜索技能..."
                           class="gh-input pl-10">
                    <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gh-text"></i>
                </div>
                <select v-model="filterCategory" class="gh-input w-full sm:w-40">
                    <option value="">所有分类</option>
                    <option v-for="cat in SKILL_CATEGORIES" :key="cat.value" :value="cat.value">{{ cat.label }}</option>
                </select>
                <select v-model="filterStatus" class="gh-input w-full sm:w-40">
                    <option value="">所有状态</option>
                    <option value="enabled">已启用</option>
                    <option value="disabled">已禁用</option>
                </select>
            </div>
            
            <!-- 技能卡片网格 -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div v-for="skill in filteredSkills" :key="skill.id"
                     class="gh-card card-hover group">
                    <div class="flex items-start justify-between mb-3">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-lg bg-gh-elevated flex items-center justify-center border border-gh-border">
                                <i class="fas fa-cube text-gh-text"></i>
                            </div>
                            <div>
                                <h3 class="font-semibold text-white">{{ skill.name }}</h3>
                                <p class="text-xs text-gh-text">v{{ skill.version }}</p>
                            </div>
                        </div>
                        <Badge :type="skill.enabled ? 'success' : 'neutral'" 
                               :text="skill.enabled ? '启用' : '禁用'" 
                               size="sm" />
                    </div>
                    
                    <p class="text-sm text-gh-text mb-3 line-clamp-2">{{ skill.description }}</p>
                    
                    <div class="flex items-center gap-2 mb-4">
                        <span class="text-xs px-2 py-1 rounded bg-gh-elevated text-gh-text border border-gh-border">
                            {{ categoryLabel(skill.category) }}
                        </span>
                    </div>
                    
                    <div class="flex items-center gap-2 pt-3 border-t border-gh-border">
                        <button @click="$emit('edit', skill)" 
                                class="flex-1 btn-secondary text-sm py-1.5">
                            <i class="fas fa-edit mr-1"></i>编辑
                        </button>
                        <button @click="toggleSkill(skill)" 
                                :class="['flex-1 text-sm py-1.5 rounded transition', skill.enabled ? 'btn-secondary' : 'btn-primary']">
                            <i :class="[skill.enabled ? 'fas fa-pause' : 'fas fa-play', 'mr-1']"></i>
                            {{ skill.enabled ? '禁用' : '启用' }}
                        </button>
                        <button @click="confirmDelete(skill)" 
                                class="w-8 h-8 rounded-lg flex items-center justify-center text-gh-text hover:text-gh-red hover:bg-gh-red/10 transition">
                            <i class="fas fa-trash text-sm"></i>
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- 空状态 -->
            <div v-if="filteredSkills.length === 0" class="text-center py-16">
                <div class="w-16 h-16 mx-auto bg-gh-elevated rounded-full flex items-center justify-center mb-4">
                    <i class="fas fa-puzzle-piece text-2xl text-gh-text"></i>
                </div>
                <p class="text-gh-text mb-4">暂无技能</p>
                <button @click="$emit('create')" class="btn-primary">
                    <i class="fas fa-plus mr-2"></i>创建第一个技能
                </button>
            </div>
            
            <!-- 删除确认 -->
            <ConfirmDialog v-model:visible="showDeleteConfirm"
                          type="danger"
                          title="删除技能"
                          :message="deleteMessage"
                          confirmText="删除"
                          @confirm="handleDelete" />
        </div>
    `,
    
    data() {
        return {
            searchQuery: '',
            filterCategory: '',
            filterStatus: '',
            showDeleteConfirm: false,
            skillToDelete: null,
            SKILL_CATEGORIES
        };
    },
    
    computed: {
        enabledCount() {
            return this.skills.filter(s => s.enabled).length;
        },
        
        filteredSkills() {
            let result = [...this.skills];
            
            // 分类过滤
            if (this.filterCategory) {
                result = result.filter(s => s.category === this.filterCategory);
            }
            
            // 状态过滤
            if (this.filterStatus) {
                result = result.filter(s => 
                    this.filterStatus === 'enabled' ? s.enabled : !s.enabled
                );
            }
            
            // 搜索
            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                result = result.filter(s => 
                    s.name.toLowerCase().includes(query) ||
                    s.description.toLowerCase().includes(query)
                );
            }
            
            return result;
        },
        
        deleteMessage() {
            return this.skillToDelete 
                ? `确定要删除技能 "${this.skillToDelete.name}" 吗？此操作不可恢复。`
                : '';
        }
    },
    
    methods: {
        categoryLabel(value) {
            const cat = SKILL_CATEGORIES.find(c => c.value === value);
            return cat ? cat.label : value;
        },
        
        toggleSkill(skill) {
            this.$emit('toggle', skill);
        },
        
        confirmDelete(skill) {
            this.skillToDelete = skill;
            this.showDeleteConfirm = true;
        },
        
        handleDelete() {
            if (this.skillToDelete) {
                this.$emit('delete', this.skillToDelete.id);
                this.showDeleteConfirm = false;
                this.skillToDelete = null;
            }
        }
    }
};

export default SkillsView;
