/**
 * 全局错误处理工具
 * 提供错误捕获、重试、降级和上报功能
 */

// 错误类型定义
const ErrorTypes = {
  NETWORK: 'NETWORK_ERROR',
  API: 'API_ERROR',
  RESOURCE: 'RESOURCE_ERROR',
  VALIDATION: 'VALIDATION_ERROR',
  UNKNOWN: 'UNKNOWN_ERROR'
};

// 错误重试配置
const RetryConfig = {
  maxRetries: 3,
  initialDelay: 1000,
  maxDelay: 10000,
  backoffMultiplier: 2
};

// 错误日志存储
const errorLog = [];

/**
 * 错误类
 */
class AppError extends Error {
  constructor(type, message, statusCode = null, originalError = null) {
    super(message);
    this.name = 'AppError';
    this.type = type;
    this.statusCode = statusCode;
    this.originalError = originalError;
    this.timestamp = new Date().toISOString();
  }
  
  toJSON() {
    return {
      type: this.type,
      message: this.message,
      statusCode: this.statusCode,
      timestamp: this.timestamp,
      stack: this.stack
    };
  }
}

/**
 * 计算重试延迟（指数退避）
 */
function calculateRetryDelay(attempt) {
  const delay = RetryConfig.initialDelay * Math.pow(RetryConfig.backoffMultiplier, attempt - 1);
  return Math.min(delay, RetryConfig.maxDelay);
}

/**
 * 带重试的异步操作
 */
async function withRetry(operation, options = {}) {
  const {
    maxRetries = RetryConfig.maxRetries,
    shouldRetry = (error) => error.type === ErrorTypes.NETWORK,
    onRetry = (error, attempt) => console.warn(`重试 ${attempt}/${maxRetries}:`, error.message),
    delayCalculator = calculateRetryDelay
  } = options;
  
  let lastError;
  
  for (let attempt = 1; attempt <= maxRetries + 1; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      
      if (attempt <= maxRetries && shouldRetry(error)) {
        const delay = delayCalculator(attempt);
        onRetry(error, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
      } else {
        break;
      }
    }
  }
  
  throw lastError;
}

/**
 * 错误日志记录
 */
function logError(error, context = {}) {
  const logEntry = {
    id: Date.now().toString(36),
    error: error instanceof AppError ? error.toJSON() : {
      name: error.name,
      message: error.message,
      stack: error.stack
    },
    context,
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
    url: window.location.href
  };
  
  errorLog.push(logEntry);
  
  // 保持日志大小合理（最多 100 条）
  if (errorLog.length > 100) {
    errorLog.shift();
  }
  
  // 在开发环境下输出到控制台
  if (process.env.NODE_ENV !== 'production') {
    console.error('[Error Log]', logEntry);
  }
  
  return logEntry.id;
}

/**
 * 获取错误日志
 */
function getErrorLog(filters = {}) {
  let filtered = errorLog;
  
  if (filters.type) {
    filtered = filtered.filter(log => log.error.type === filters.type);
  }
  
  if (filters.startDate) {
    filtered = filtered.filter(log => log.timestamp >= filters.startDate);
  }
  
  if (filters.endDate) {
    filtered = filtered.filter(log => log.timestamp <= filters.endDate);
  }
  
  return filtered;
}

/**
 * 清除错误日志
 */
function clearErrorLog() {
  errorLog.length = 0;
}

/**
 * 导出错误日志为 JSON
 */
function exportErrorLog() {
  const blob = new Blob([JSON.stringify(errorLog, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `error-log-${new Date().toISOString().split('T')[0]}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * 网络错误处理
 */
function handleNetworkError(error) {
  return new AppError(
    ErrorTypes.NETWORK,
    '网络连接失败，请检查网络设置',
    null,
    error
  );
}

/**
 * API 错误处理
 */
function handleApiError(response) {
  const status = response.status;
  
  const errorMessages = {
    400: '请求参数错误',
    401: '未授权，请登录',
    403: '拒绝访问',
    404: '资源不存在',
    500: '服务器内部错误',
    502: '网关错误',
    503: '服务不可用',
    504: '网关超时'
  };
  
  return new AppError(
    ErrorTypes.API,
    errorMessages[status] || `API 错误 (${status})`,
    status,
    response
  );
}

/**
 * 资源加载错误处理
 */
function handleResourceError(resourceName, resourceType) {
  return new AppError(
    ErrorTypes.RESOURCE,
    `资源加载失败：${resourceName} (${resourceType})`,
    null,
    null
  );
}

/**
 * 验证错误处理
 */
function handleValidationError(field, message) {
  return new AppError(
    ErrorTypes.VALIDATION,
    `${field}: ${message}`,
    null,
    null
  );
}

/**
 * 全局错误边界（Vue 3 插件）
 */
function createErrorBoundary(app) {
  // Vue 错误处理
  app.config.errorHandler = (error, instance, info) => {
    const logId = logError(error, {
      component: instance?.$options?.name || 'Unknown',
      vueInfo: info
    });
    
    console.error(`[Vue Error] ${info}:`, error);
    console.error(`[Log ID] ${logId}`);
  };
  
  // 未捕获的 Promise 错误
  window.addEventListener('unhandledrejection', event => {
    const error = event.reason || new Error('Unknown promise rejection');
    const logId = logError(error, {
      type: 'unhandledrejection'
    });
    
    console.error('[Unhandled Rejection]', error);
    console.error(`[Log ID] ${logId}`);
    
    event.preventDefault();
  });
  
  // 全局错误
  window.addEventListener('error', event => {
    const error = event.error || new Error(event.message);
    const logId = logError(error, {
      type: 'global',
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno
    });
    
    console.error('[Global Error]', error);
    console.error(`[Log ID] ${logId}`);
  });
  
  // 资源加载错误
  window.addEventListener('error', event => {
    if (event.target && (event.target.tagName === 'SCRIPT' || event.target.tagName === 'LINK')) {
      const resource = event.target.tagName === 'SCRIPT' ? 'JavaScript' : 'CSS';
      const src = event.target.src || event.target.href;
      const error = handleResourceError(src, resource);
      const logId = logError(error, {
        type: 'resource',
        resourceType: resource,
        src
      });
      
      console.error(`[Resource Error] ${resource}: ${src}`);
      console.error(`[Log ID] ${logId}`);
    }
  }, true);
}

/**
 * 降级策略
 */
const FallbackStrategies = {
  // CDN 降级：主 CDN 失败时切换到备用 CDN
  cdn: function(primary, fallbacks) {
    return new Promise((resolve, reject) => {
      const tryLoad = (index = 0) => {
        if (index >= fallbacks.length) {
          reject(new AppError(ErrorTypes.RESOURCE, '所有 CDN 均不可用'));
          return;
        }
        
        const url = index === 0 ? primary : fallbacks[index - 1];
        console.log(`[CDN Fallback] 尝试加载：${url}`);
        
        // 动态创建 script/link 标签加载
        const isScript = url.endsWith('.js');
        const element = isScript ? document.createElement('script') : document.createElement('link');
        
        if (isScript) {
          element.src = url;
        } else {
          element.rel = 'stylesheet';
          element.href = url;
        }
        
        element.onload = () => {
          console.log(`[CDN Fallback] 加载成功：${url}`);
          resolve();
        };
        
        element.onerror = () => {
          console.warn(`[CDN Fallback] 加载失败：${url}`);
          tryLoad(index + 1);
        };
        
        document.head.appendChild(element);
      };
      
      tryLoad();
    });
  },
  
  // API 降级：API 失败时使用缓存数据
  api: async function(apiCall, cacheKey, defaultData = null) {
    try {
      const data = await apiCall();
      // 成功时更新缓存
      localStorage.setItem(`cache_${cacheKey}`, JSON.stringify({
        data,
        timestamp: Date.now()
      }));
      return data;
    } catch (error) {
      // 失败时使用缓存
      const cached = localStorage.getItem(`cache_${cacheKey}`);
      if (cached) {
        const { data, timestamp } = JSON.parse(cached);
        console.warn(`[API Fallback] 使用缓存数据：${cacheKey}`);
        return data;
      }
      
      // 没有缓存时使用默认值
      console.warn(`[API Fallback] 使用默认数据：${cacheKey}`);
      return defaultData;
    }
  },
  
  // 功能降级：高级功能不可用时使用基础功能
  feature: function(advancedFn, basicFn, featureName) {
    try {
      return advancedFn();
    } catch (error) {
      console.warn(`[Feature Fallback] ${featureName} 降级到基础模式`);
      return basicFn();
    }
  }
};

/**
 * 离线检测
 */
function isOffline() {
  return !navigator.onLine;
}

/**
 * 监听网络状态
 */
function onNetworkStatusChange(callback) {
  window.addEventListener('online', () => callback(true));
  window.addEventListener('offline', () => callback(false));
}

/**
 * 队列离线请求
 */
const offlineQueue = [];

function queueOfflineRequest(request) {
  offlineQueue.push({
    ...request,
    queuedAt: Date.now()
  });
  
  // 保存离线队列到 localStorage
  localStorage.setItem('offlineQueue', JSON.stringify(offlineQueue));
}

/**
 * 处理离线队列
 */
async function processOfflineQueue() {
  if (isOffline()) {
    console.log('[Offline Queue] 网络离线，跳过处理');
    return;
  }
  
  while (offlineQueue.length > 0) {
    const request = offlineQueue[0];
    
    try {
      await request.fn();
      offlineQueue.shift();
      console.log('[Offline Queue] 请求成功，移出队列');
    } catch (error) {
      console.error('[Offline Queue] 请求失败:', error);
      break;
    }
  }
  
  // 更新 localStorage
  localStorage.setItem('offlineQueue', JSON.stringify(offlineQueue));
}

// 导出
window.ErrorHandler = {
  ErrorTypes,
  AppError,
  withRetry,
  logError,
  getErrorLog,
  clearErrorLog,
  exportErrorLog,
  handleNetworkError,
  handleApiError,
  handleValidationError,
  createErrorBoundary,
  FallbackStrategies,
  isOffline,
  onNetworkStatusChange,
  queueOfflineRequest,
  processOfflineQueue
};

console.log('[ErrorHandler] 已加载');
