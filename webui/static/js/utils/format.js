/**
 * 格式化工具函数
 * 统一处理日期、数字、文本等格式化
 */

/**
 * 格式化日期
 * @param {string|Date} date - 日期
 * @param {string} format - 格式模板
 * @returns {string} 格式化后的日期
 */
export function formatDate(date, format = 'YYYY-MM-DD HH:mm') {
    if (!date) return '--';
    
    const d = new Date(date);
    if (isNaN(d.getTime())) return '--';
    
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');
    
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
}

/**
 * 格式化相对时间
 * @param {string|Date} date - 日期
 * @returns {string} 相对时间描述
 */
export function formatRelativeTime(date) {
    if (!date) return '--';
    
    const d = new Date(date);
    if (isNaN(d.getTime())) return '--';
    
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    
    const minute = 60 * 1000;
    const hour = 60 * minute;
    const day = 24 * hour;
    const week = 7 * day;
    const month = 30 * day;
    
    if (diff < minute) return '刚刚';
    if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`;
    if (diff < day) return `${Math.floor(diff / hour)} 小时前`;
    if (diff < week) return `${Math.floor(diff / day)} 天前`;
    if (diff < month) return `${Math.floor(diff / week)} 周前`;
    
    return formatDate(date, 'YYYY-MM-DD');
}

/**
 * 格式化数字
 * @param {number} num - 数字
 * @param {number} decimals - 小数位数
 * @returns {string} 格式化后的数字
 */
export function formatNumber(num, decimals = 0) {
    if (num === null || num === undefined) return '--';
    
    const n = Number(num);
    if (isNaN(n)) return '--';
    
    // 大数字简化
    if (n >= 1000000) return (n / 1000000).toFixed(decimals) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(decimals) + 'K';
    
    return n.toFixed(decimals);
}

/**
 * 格式化百分比
 * @param {number} value - 数值 (0-100)
 * @param {number} decimals - 小数位数
 * @returns {string} 格式化后的百分比
 */
export function formatPercent(value, decimals = 1) {
    if (value === null || value === undefined) return '--%';
    
    const num = Number(value);
    if (isNaN(num)) return '--%';
    
    return num.toFixed(decimals) + '%';
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string} 格式化后的文件大小
 */
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    if (!bytes) return '--';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 格式化时长
 * @param {number} seconds - 秒数
 * @returns {string} 格式化后的时长
 */
export function formatDuration(seconds) {
    if (!seconds && seconds !== 0) return '--';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    }
    return `${secs}s`;
}

/**
 * 截断文本
 * @param {string} text - 文本
 * @param {number} maxLength - 最大长度
 * @param {string} suffix - 后缀
 * @returns {string} 截断后的文本
 */
export function truncate(text, maxLength = 100, suffix = '...') {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    
    return text.substring(0, maxLength).trim() + suffix;
}

/**
 * 首字母大写
 * @param {string} str - 字符串
 * @returns {string} 首字母大写的字符串
 */
export function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * 驼峰转空格
 * @param {string} str - 驼峰字符串
 * @returns {string} 空格分隔的字符串
 */
export function camelToSpace(str) {
    if (!str) return '';
    return str
        .replace(/([A-Z])/g, ' $1')
        .replace(/^./, str => str.toUpperCase())
        .trim();
}

/**
 * 生成唯一ID
 * @returns {string} 唯一ID
 */
export function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

/**
 * 防抖函数
 * @param {Function} fn - 原函数
 * @param {number} delay - 延迟时间(ms)
 * @returns {Function} 防抖后的函数
 */
export function debounce(fn, delay = 300) {
    let timer = null;
    return function (...args) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
            fn.apply(this, args);
        }, delay);
    };
}

/**
 * 节流函数
 * @param {Function} fn - 原函数
 * @param {number} limit - 限制时间(ms)
 * @returns {Function} 节流后的函数
 */
export function throttle(fn, limit = 300) {
    let inThrottle = false;
    return function (...args) {
        if (!inThrottle) {
            fn.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
