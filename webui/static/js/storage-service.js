/**
 * StorageService - 统一存储服务
 * 提供 LocalStorage 和 IndexedDB 的统一接口
 *
 * 功能:
 * - LocalStorage: 存储配置、用户偏好、小数据
 * - IndexedDB: 存储任务、附件、历史记录等大数据
 */

class StorageService {
    constructor() {
        this.dbName = 'IntelliTeamDB';
        this.dbVersion = 1;
        this.db = null;
        this.isReady = false;

        // 存储键名常量
        this.KEYS = {
            TASKS: 'intelliteam_tasks',
            CONFIG: 'intelliteam_config',
            USER_PREF: 'intelliteam_preferences',
            NOTIFICATIONS: 'intelliteam_notifications',
            THEME: 'intelliteam_theme'
        };
    }

    /**
     * 初始化 IndexedDB
     * @returns {Promise<IDBDatabase>}
     */
    async init() {
        if (this.isReady) return this.db;

        return new Promise((resolve, reject) => {
            // 检查 IndexedDB 支持
            if (!window.indexedDB) {
                console.warn('IndexedDB 不支持，将使用 LocalStorage 作为后备');
                this.isReady = true;
                resolve(null);
                return;
            }

            const request = indexedDB.open(this.dbName, this.dbVersion);

            request.onerror = () => {
                console.error('IndexedDB 打开失败:', request.error);
                this.isReady = true;
                resolve(null);
            };

            request.onsuccess = () => {
                this.db = request.result;
                this.isReady = true;
                console.log('IndexedDB 初始化成功');
                resolve(this.db);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // 创建 tasks 存储
                if (!db.objectStoreNames.contains('tasks')) {
                    const taskStore = db.createObjectStore('tasks', { keyPath: 'id' });
                    taskStore.createIndex('status', 'status', { unique: false });
                    taskStore.createIndex('assignee', 'assignee', { unique: false });
                    taskStore.createIndex('createdAt', 'createdAt', { unique: false });
                }

                // 创建 attachments 存储
                if (!db.objectStoreNames.contains('attachments')) {
                    const attachStore = db.createObjectStore('attachments', { keyPath: 'id' });
                    attachStore.createIndex('taskId', 'taskId', { unique: false });
                    attachStore.createIndex('uploadedAt', 'uploadedAt', { unique: false });
                }

                // 创建 history 存储
                if (!db.objectStoreNames.contains('history')) {
                    const historyStore = db.createObjectStore('history', { keyPath: 'id' });
                    historyStore.createIndex('taskId', 'taskId', { unique: false });
                    historyStore.createIndex('timestamp', 'timestamp', { unique: false });
                }

                // 创建 comments 存储
                if (!db.objectStoreNames.contains('comments')) {
                    const commentStore = db.createObjectStore('comments', { keyPath: 'id' });
                    commentStore.createIndex('taskId', 'taskId', { unique: false });
                    commentStore.createIndex('createdAt', 'createdAt', { unique: false });
                }

                console.log('IndexedDB 数据结构创建完成');
            };
        });
    }

    // ==================== LocalStorage 操作 ====================

    /**
     * 获取 LocalStorage 数据
     * @param {string} key
     * @returns {any}
     */
    get(key) {
        try {
            const data = localStorage.getItem(key);
            return data ? JSON.parse(data) : null;
        } catch (e) {
            console.error('StorageService.get error:', e);
            return null;
        }
    }

    /**
     * 设置 LocalStorage 数据
     * @param {string} key
     * @param {any} value
     * @returns {boolean}
     */
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.error('StorageService.set error:', e);
            // 可能是存储空间不足
            if (e.name === 'QuotaExceededError') {
                console.warn('LocalStorage 空间不足，尝试清理旧数据');
                this.cleanupOldData();
                // 重试一次
                try {
                    localStorage.setItem(key, JSON.stringify(value));
                    return true;
                } catch (e2) {
                    console.error('重试失败:', e2);
                }
            }
            return false;
        }
    }

    /**
     * 删除 LocalStorage 数据
     * @param {string} key
     */
    remove(key) {
        localStorage.removeItem(key);
    }

    /**
     * 清理旧数据
     */
    cleanupOldData() {
        // 清理超过 30 天的任务缓存
        const keys = Object.keys(localStorage);
        keys.forEach(key => {
            if (key.startsWith('task_')) {
                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    if (data.updatedAt) {
                        const age = Date.now() - new Date(data.updatedAt).getTime();
                        if (age > 30 * 24 * 60 * 60 * 1000) {
                            localStorage.removeItem(key);
                        }
                    }
                } catch (e) {
                    // 无效数据，删除
                    localStorage.removeItem(key);
                }
            }
        });
    }

    // ==================== IndexedDB 操作 ====================

    /**
     * 检查 IndexedDB 是否可用
     * @returns {boolean}
     */
    isIndexedDBReady() {
        return this.db !== null;
    }

    /**
     * 通用 IndexedDB 操作
     * @param {string} storeName
     * @param {string} mode - 'readonly' 或 'readwrite'
     * @returns {IDBObjectStore}
     */
    getStore(storeName, mode = 'readonly') {
        if (!this.db) throw new Error('IndexedDB 未初始化');
        const transaction = this.db.transaction([storeName], mode);
        return transaction.objectStore(storeName);
    }

    // ==================== 任务操作 ====================

    /**
     * 保存任务
     * @param {Object} task
     * @returns {Promise<any>}
     */
    async saveTask(task) {
        if (!this.isIndexedDBReady()) {
            // 降级到 LocalStorage
            const tasks = this.get(this.KEYS.TASKS) || {};
            tasks[task.id] = task;
            return this.set(this.KEYS.TASKS, tasks);
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('tasks', 'readwrite');
                const request = store.put({
                    ...task,
                    updatedAt: task.updatedAt || new Date().toISOString()
                });
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * 获取单个任务
     * @param {string} id
     * @returns {Promise<Object|null>}
     */
    async getTask(id) {
        if (!this.isIndexedDBReady()) {
            const tasks = this.get(this.KEYS.TASKS) || {};
            return tasks[id] || null;
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('tasks', 'readonly');
                const request = store.get(id);
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * 获取所有任务
     * @returns {Promise<Array>}
     */
    async getAllTasks() {
        if (!this.isIndexedDBReady()) {
            const tasks = this.get(this.KEYS.TASKS) || {};
            return Object.values(tasks);
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('tasks', 'readonly');
                const request = store.getAll();
                request.onsuccess = () => resolve(request.result || []);
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * 删除任务
     * @param {string} id
     * @returns {Promise<void>}
     */
    async deleteTask(id) {
        if (!this.isIndexedDBReady()) {
            const tasks = this.get(this.KEYS.TASKS) || {};
            delete tasks[id];
            return this.set(this.KEYS.TASKS, tasks);
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('tasks', 'readwrite');
                const request = store.delete(id);
                request.onsuccess = () => resolve();
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * 按状态获取任务
     * @param {string} status
     * @returns {Promise<Array>}
     */
    async getTasksByStatus(status) {
        const allTasks = await this.getAllTasks();
        return allTasks.filter(t => t.status === status);
    }

    // ==================== 附件操作 ====================

    /**
     * 保存附件
     * @param {Object} attachment
     * @returns {Promise<any>}
     */
    async saveAttachment(attachment) {
        if (!this.isIndexedDBReady()) {
            // 附件存储在 LocalStorage 可能会超限，需要压缩或提示
            console.warn('附件存储到 LocalStorage 可能受限');
            return this.set(`attachment_${attachment.id}`, attachment);
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('attachments', 'readwrite');
                const request = store.put({
                    ...attachment,
                    uploadedAt: attachment.uploadedAt || new Date().toISOString()
                });
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * 获取任务的所有附件
     * @param {string} taskId
     * @returns {Promise<Array>}
     */
    async getAttachmentsByTask(taskId) {
        if (!this.isIndexedDBReady()) {
            // 从 LocalStorage 查找
            const attachments = [];
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && key.startsWith('attachment_')) {
                    const attachment = this.get(key);
                    if (attachment && attachment.taskId === taskId) {
                        attachments.push(attachment);
                    }
                }
            }
            return attachments;
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('attachments', 'readonly');
                const index = store.index('taskId');
                const request = index.getAll(taskId);
                request.onsuccess = () => resolve(request.result || []);
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * 删除附件
     * @param {string} id
     * @returns {Promise<void>}
     */
    async deleteAttachment(id) {
        if (!this.isIndexedDBReady()) {
            this.remove(`attachment_${id}`);
            return;
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('attachments', 'readwrite');
                const request = store.delete(id);
                request.onsuccess = () => resolve();
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    // ==================== 历史记录操作 ====================

    /**
     * 添加历史记录
     * @param {Object} history
     * @returns {Promise<any>}
     */
    async addHistory(history) {
        const entry = {
            id: history.id || `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            taskId: history.taskId,
            action: history.action,
            user: history.user || '系统',
            timestamp: history.timestamp || new Date().toISOString(),
            details: history.details || null
        };

        if (!this.isIndexedDBReady()) {
            const key = `history_${entry.taskId}`;
            const histories = this.get(key) || [];
            histories.unshift(entry);
            // 限制历史记录数量
            if (histories.length > 100) {
                histories.length = 100;
            }
            return this.set(key, histories);
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('history', 'readwrite');
                const request = store.add(entry);
                request.onsuccess = () => resolve(entry);
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * 获取任务历史记录
     * @param {string} taskId
     * @returns {Promise<Array>}
     */
    async getHistoryByTask(taskId) {
        if (!this.isIndexedDBReady()) {
            return this.get(`history_${taskId}`) || [];
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('history', 'readonly');
                const index = store.index('taskId');
                const request = index.getAll(taskId);
                request.onsuccess = () => {
                    const result = request.result || [];
                    // 按时间倒序排列
                    result.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                    resolve(result);
                };
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    // ==================== 评论操作 ====================

    /**
     * 添加评论
     * @param {Object} comment
     * @returns {Promise<any>}
     */
    async addComment(comment) {
        const entry = {
            id: comment.id || `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            taskId: comment.taskId,
            author: comment.author || '匿名用户',
            content: comment.content,
            createdAt: comment.createdAt || new Date().toISOString()
        };

        if (!this.isIndexedDBReady()) {
            const key = `comments_${entry.taskId}`;
            const comments = this.get(key) || [];
            comments.push(entry);
            return this.set(key, comments);
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('comments', 'readwrite');
                const request = store.add(entry);
                request.onsuccess = () => resolve(entry);
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * 获取任务评论
     * @param {string} taskId
     * @returns {Promise<Array>}
     */
    async getCommentsByTask(taskId) {
        if (!this.isIndexedDBReady()) {
            return this.get(`comments_${taskId}`) || [];
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('comments', 'readonly');
                const index = store.index('taskId');
                const request = index.getAll(taskId);
                request.onsuccess = () => {
                    const result = request.result || [];
                    // 按时间排序
                    result.sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt));
                    resolve(result);
                };
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    /**
     * 删除评论
     * @param {string} commentId
     * @param {string} taskId
     * @returns {Promise<void>}
     */
    async deleteComment(commentId, taskId) {
        if (!this.isIndexedDBReady()) {
            const key = `comments_${taskId}`;
            const comments = this.get(key) || [];
            const filtered = comments.filter(c => c.id !== commentId);
            return this.set(key, filtered);
        }

        return new Promise((resolve, reject) => {
            try {
                const store = this.getStore('comments', 'readwrite');
                const request = store.delete(commentId);
                request.onsuccess = () => resolve();
                request.onerror = () => reject(request.error);
            } catch (e) {
                reject(e);
            }
        });
    }

    // ==================== 通知操作 ====================

    /**
     * 保存通知
     * @param {Array} notifications
     */
    saveNotifications(notifications) {
        return this.set(this.KEYS.NOTIFICATIONS, notifications);
    }

    /**
     * 获取通知
     * @returns {Array}
     */
    getNotifications() {
        return this.get(this.KEYS.NOTIFICATIONS) || [];
    }

    /**
     * 标记所有通知为已读
     */
    markAllNotificationsRead() {
        const notifications = this.getNotifications();
        notifications.forEach(n => n.read = true);
        return this.saveNotifications(notifications);
    }

    // ==================== 用户偏好 ====================

    /**
     * 保存用户偏好
     * @param {Object} preferences
     */
    savePreferences(preferences) {
        return this.set(this.KEYS.USER_PREF, preferences);
    }

    /**
     * 获取用户偏好
     * @returns {Object}
     */
    getPreferences() {
        return this.get(this.KEYS.USER_PREF) || {
            theme: 'dark',
            language: 'zh-CN',
            notifications: true
        };
    }

    /**
     * 保存主题设置
     * @param {string} theme - 'light' 或 'dark'
     */
    saveTheme(theme) {
        return this.set(this.KEYS.THEME, theme);
    }

    /**
     * 获取主题设置
     * @returns {string}
     */
    getTheme() {
        return this.get(this.KEYS.THEME) || 'dark';
    }

    // ==================== 数据导出/导入 ====================

    /**
     * 导出所有数据
     * @returns {Promise<Object>}
     */
    async exportAllData() {
        const data = {
            tasks: await this.getAllTasks(),
            notifications: this.getNotifications(),
            preferences: this.getPreferences(),
            theme: this.getTheme(),
            exportedAt: new Date().toISOString()
        };

        // 导出历史和评论
        const allHistory = [];
        const allComments = [];

        for (const task of data.tasks) {
            const history = await this.getHistoryByTask(task.id);
            const comments = await this.getCommentsByTask(task.id);
            allHistory.push(...history);
            allComments.push(...comments);
        }

        data.history = allHistory;
        data.comments = allComments;

        return data;
    }

    /**
     * 导入数据
     * @param {Object} data
     */
    async importData(data) {
        // 导入任务
        if (data.tasks) {
            for (const task of data.tasks) {
                await this.saveTask(task);
            }
        }

        // 导入历史
        if (data.history) {
            for (const entry of data.history) {
                await this.addHistory(entry);
            }
        }

        // 导入评论
        if (data.comments) {
            for (const comment of data.comments) {
                await this.addComment(comment);
            }
        }

        // 导入通知
        if (data.notifications) {
            this.saveNotifications(data.notifications);
        }

        // 导入偏好
        if (data.preferences) {
            this.savePreferences(data.preferences);
        }

        // 导入主题
        if (data.theme) {
            this.saveTheme(data.theme);
        }
    }

    /**
     * 清除所有数据
     */
    async clearAll() {
        // 清除 LocalStorage
        localStorage.clear();

        // 清除 IndexedDB
        if (this.isIndexedDBReady()) {
            const storeNames = ['tasks', 'attachments', 'history', 'comments'];
            for (const name of storeNames) {
                await new Promise((resolve, reject) => {
                    try {
                        const store = this.getStore(name, 'readwrite');
                        const request = store.clear();
                        request.onsuccess = () => resolve();
                        request.onerror = () => reject(request.error);
                    } catch (e) {
                        resolve();
                    }
                });
            }
        }
    }

    /**
     * 获取存储使用情况
     * @returns {Object}
     */
    getStorageInfo() {
        let localStorageSize = 0;
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            const value = localStorage.getItem(key);
            localStorageSize += key.length + value.length;
        }

        return {
            localStorage: {
                used: localStorageSize,
                usedMB: (localStorageSize / 1024 / 1024).toFixed(2),
                limit: 5 * 1024 * 1024, // 约 5MB
                limitMB: '5'
            },
            indexedDB: this.isIndexedDBReady() ? 'available' : 'unavailable'
        };
    }
}

// 创建单例
const storageService = new StorageService();

// 自动初始化（在页面加载时）
if (typeof window !== 'undefined') {
    window.storageService = storageService;

    // 在 DOM 加载完成后自动初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            storageService.init().catch(e => console.error('StorageService 初始化失败:', e));
        });
    } else {
        storageService.init().catch(e => console.error('StorageService 初始化失败:', e));
    }
}