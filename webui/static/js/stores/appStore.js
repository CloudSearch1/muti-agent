/**
 * 应用状态管理
 * 管理全局应用状态：导航、主题、通知、加载状态等
 */

import { reactive, computed } from 'vue';
import { TABS, DEFAULT_SETTINGS } from '../utils/constants.js';

// 创建响应式状态
const state = reactive({
    // 导航
    currentTab: 'dashboard',
    tabs: TABS,
    
    // 主题
    isDark: true,
    
    // 加载状态
    loading: false,
    loadingMessage: '',
    
    // 搜索
    searchQuery: '',
    
    // 通知
    toasts: [],
    notifications: [],
    
    // 设置
    settings: { ...DEFAULT_SETTINGS },
    showSettings: false,
    
    // 模态框
    modals: {
        createTask: false,
        editTask: false,
        taskDetail: false,
        createSkill: false,
        editSkill: false,
        agentDetail: false
    },
    
    // 编辑中的数据
    editingTask: null,
    editingSkill: null,
    selectedAgent: null,
    selectedTask: null
});

// 计算属性
const getters = {
    // 未读通知数
    unreadCount: computed(() => {
        return state.notifications.filter(n => !n.read).length;
    }),
    
    // 当前标签信息
    currentTabInfo: computed(() => {
        return state.tabs.find(t => t.id === state.currentTab) || state.tabs[0];
    }),
    
    // 是否有打开的模态框
    hasOpenModal: computed(() => {
        return Object.values(state.modals).some(v => v);
    })
};

// 方法
const actions = {
    // 导航
    setTab(tabId) {
        if (state.tabs.find(t => t.id === tabId)) {
            state.currentTab = tabId;
        }
    },
    
    // 主题
    toggleTheme() {
        state.isDark = !state.isDark;
        document.documentElement.classList.toggle('dark', state.isDark);
        localStorage.setItem('theme', state.isDark ? 'dark' : 'light');
    },
    
    initTheme() {
        const saved = localStorage.getItem('theme');
        if (saved) {
            state.isDark = saved === 'dark';
        } else {
            state.isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        }
        document.documentElement.classList.toggle('dark', state.isDark);
    },
    
    // 加载状态
    setLoading(loading, message = '') {
        state.loading = loading;
        state.loadingMessage = message;
    },
    
    // 搜索
    setSearchQuery(query) {
        state.searchQuery = query;
    },
    
    // Toast 通知
    showToast(message, type = 'info', duration = 3000) {
        const id = Date.now();
        const toast = { id, message, type };
        state.toasts.push(toast);
        
        setTimeout(() => {
            this.removeToast(id);
        }, duration);
        
        return id;
    },
    
    removeToast(id) {
        const index = state.toasts.findIndex(t => t.id === id);
        if (index > -1) {
            state.toasts.splice(index, 1);
        }
    },
    
    // 通知
    addNotification(notification) {
        const id = Date.now();
        state.notifications.unshift({
            id,
            read: false,
            time: new Date().toISOString(),
            ...notification
        });
        
        // 限制通知数量
        if (state.notifications.length > 50) {
            state.notifications.pop();
        }
    },
    
    markNotificationRead(id) {
        const notification = state.notifications.find(n => n.id === id);
        if (notification) {
            notification.read = true;
        }
    },
    
    markAllNotificationsRead() {
        state.notifications.forEach(n => n.read = true);
    },
    
    clearNotifications() {
        state.notifications = [];
    },
    
    // 模态框
    openModal(name) {
        if (state.modals.hasOwnProperty(name)) {
            state.modals[name] = true;
        }
    },
    
    closeModal(name) {
        if (state.modals.hasOwnProperty(name)) {
            state.modals[name] = false;
        }
    },
    
    closeAllModals() {
        Object.keys(state.modals).forEach(key => {
            state.modals[key] = false;
        });
    },
    
    // 设置
    setSettings(settings) {
        state.settings = { ...state.settings, ...settings };
    },
    
    updateSetting(key, value) {
        state.settings[key] = value;
    },
    
    // 编辑数据
    setEditingTask(task) {
        state.editingTask = task ? { ...task } : null;
    },
    
    setEditingSkill(skill) {
        state.editingSkill = skill ? { ...skill } : null;
    },
    
    setSelectedAgent(agent) {
        state.selectedAgent = agent ? { ...agent } : null;
    },
    
    setSelectedTask(task) {
        state.selectedTask = task ? { ...task } : null;
    }
};

// 导出 store
export const appStore = {
    state,
    ...getters,
    ...actions
};

export default appStore;
