/**
 * API 封装模块
 * 统一处理 HTTP 请求，支持缓存、错误处理、请求取消等功能
 */

const API_BASE_URL = '';
const DEFAULT_TIMEOUT = 30000;

// 请求缓存
const cache = new Map();
const CACHE_DURATION = 30000; // 30秒

/**
 * 发送 HTTP 请求
 * @param {string} url - 请求地址
 * @param {Object} options - 请求选项
 * @returns {Promise} 请求结果
 */
async function request(url, options = {}) {
    const { 
        method = 'GET', 
        data = null, 
        params = null, 
        headers = {},
        cache: useCache = false,
        cacheKey = null,
        timeout = DEFAULT_TIMEOUT
    } = options;

    // 构建完整URL
    let fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    
    // 添加查询参数
    if (params) {
        const queryString = new URLSearchParams(params).toString();
        fullUrl += (fullUrl.includes('?') ? '&' : '?') + queryString;
    }

    // 检查缓存
    const cacheId = cacheKey || `${method}:${fullUrl}`;
    if (useCache && method === 'GET' && cache.has(cacheId)) {
        const cached = cache.get(cacheId);
        if (Date.now() - cached.timestamp < CACHE_DURATION) {
            return cached.data;
        }
        cache.delete(cacheId);
    }

    // 请求配置
    const config = {
        method,
        headers: {
            'Content-Type': 'application/json',
            ...headers
        }
    };

    if (data && method !== 'GET') {
        config.body = JSON.stringify(data);
    }

    // 发送请求
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        config.signal = controller.signal;

        const response = await fetch(fullUrl, config);
        clearTimeout(timeoutId);

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.message || `HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();

        // 缓存结果
        if (useCache && method === 'GET') {
            cache.set(cacheId, { data: result, timestamp: Date.now() });
        }

        return result;
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new Error('请求超时，请稍后重试');
        }
        throw error;
    }
}

/**
 * 清除缓存
 * @param {string} pattern - 缓存键匹配模式
 */
export function clearCache(pattern = null) {
    if (pattern) {
        for (const key of cache.keys()) {
            if (key.includes(pattern)) {
                cache.delete(key);
            }
        }
    } else {
        cache.clear();
    }
}

// API 方法
export const api = {
    // 统计
    getStats: () => request('/api/v1/stats', { cache: true }),
    
    // Agent
    getAgents: () => request('/api/v1/agents'),
    
    // 任务
    getTasks: () => request('/api/v1/tasks', { cache: true, cacheKey: 'tasks:all' }),
    getTask: (id) => request(`/api/v1/tasks/${id}`),
    createTask: (data) => request('/api/v1/tasks', { method: 'POST', data }),
    updateTask: (id, data) => request(`/api/v1/tasks/${id}`, { method: 'PUT', data }),
    deleteTask: (id) => request(`/api/v1/tasks/${id}`, { method: 'DELETE' }),
    
    // 工作流
    getWorkflows: () => request('/api/v1/workflows', { cache: true }),
    
    // 技能
    getSkills: (params) => request('/api/v1/skills', { params }),
    createSkill: (data) => request('/api/v1/skills', { method: 'POST', data }),
    updateSkill: (id, data) => request(`/api/v1/skills/${id}`, { method: 'PUT', data }),
    deleteSkill: (id) => request(`/api/v1/skills/${id}`, { method: 'DELETE' }),
    toggleSkill: (id) => request(`/api/v1/skills/${id}/toggle`, { method: 'POST' }),
    
    // 设置
    getSettings: () => request('/api/v1/settings'),
    saveSettings: (settings) => request('/api/v1/settings', { method: 'POST', data: { settings } }),
    getAvailableModels: () => request('/api/v1/settings/models'),
    testConnection: (data) => request('/api/v1/settings/test', { method: 'POST', data }),
    
    // 聊天
    sendMessage: (messages, options = {}) => {
        const { stream = true, temperature = 0.7, maxTokens = 2048 } = options;
        return request('/api/v1/chat', {
            method: 'POST',
            data: { messages, stream, temperature, max_tokens: maxTokens }
        });
    },
    
    // 健康检查
    healthCheck: () => request('/api/v1/health', { cache: true }),
    
    // 导出
    exportTasks: (format = 'json') => request(`/api/v1/export/tasks?format=${format}`),
    
    // 清除缓存
    clearCache
};

export default api;
