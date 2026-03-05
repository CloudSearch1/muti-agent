/**
 * IntelliTeam Service Worker
 * 提供离线缓存、后台同步、推送通知等 PWA 功能
 */

const CACHE_NAME = 'intelliteam-v1';
const STATIC_CACHE = 'static-v1';
const DYNAMIC_CACHE = 'dynamic-v1';

// 静态资源缓存（立即缓存）
const STATIC_ASSETS = [
  '/',
  '/index_v5.html',
  '/manifest.json',
  '/static/js/error-handler.js',
  'https://cdn.tailwindcss.com',
  'https://cdn.staticfile.org/vue/3.4.21/vue.global.prod.js',
  'https://cdn.staticfile.org/font-awesome/6.5.1/css/all.min.css'
];

// 动态缓存配置
const DYNAMIC_ROUTES = [
  '/api/v1/stats',
  '/api/v1/agents',
  '/api/v1/tasks',
  '/api/v1/workflows'
];

// 缓存策略配置
const CACHE_STRATEGIES = {
  // 静态资源：Cache First
  static: ['GET'],
  // API 请求：Network First，失败时使用缓存
  api: ['GET'],
  // 图片：Cache First
  images: ['GET']
};

// 安装事件 - 预缓存静态资源
self.addEventListener('install', event => {
  console.log('[SW] Install', CACHE_NAME);
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('[SW] 预缓存静态资源');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log('[SW] 预缓存完成');
        return self.skipWaiting(); // 激活新的 SW
      })
      .catch(err => {
        console.error('[SW] 预缓存失败:', err);
      })
  );
});

// 激活事件 - 清理旧缓存
self.addEventListener('activate', event => {
  console.log('[SW] Activate');
  
  event.waitUntil(
    caches.keys()
      .then(keys => {
        return Promise.all(
          keys
            .filter(key => key !== STATIC_CACHE && key !== DYNAMIC_CACHE)
            .map(key => {
              console.log('[SW] 删除旧缓存:', key);
              return caches.delete(key);
            })
        );
      })
      .then(() => {
        console.log('[SW] 激活完成');
        return self.clients.claim(); // 接管所有客户端
      })
  );
});

// 获取事件 - 根据策略处理请求
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  
  // 只处理同源请求
  if (url.origin !== location.origin) {
    return;
  }
  
  // 根据请求类型选择策略
  if (isStaticAsset(request)) {
    // 静态资源：Cache First
    event.respondWith(cacheFirst(request));
  } else if (isApiRequest(request)) {
    // API 请求：Network First
    event.respondWith(networkFirst(request));
  } else if (isImageRequest(request)) {
    // 图片：Cache First
    event.respondWith(cacheFirst(request));
  } else {
    // 默认：Network First
    event.respondWith(networkFirst(request));
  }
});

/**
 * 判断是否为静态资源
 */
function isStaticAsset(request) {
  const url = request.url;
  return STATIC_ASSETS.some(asset => url.includes(asset));
}

/**
 * 判断是否为 API 请求
 */
function isApiRequest(request) {
  return request.url.includes('/api/');
}

/**
 * 判断是否为图片请求
 */
function isImageRequest(request) {
  return request.destination === 'image' || 
         /\.(png|jpg|jpeg|gif|svg|webp|ico)$/i.test(request.url);
}

/**
 * Cache First 策略
 * 优先从缓存读取，缓存没有再从网络获取
 */
async function cacheFirst(request) {
  const cached = await caches.match(request);
  
  if (cached) {
    console.log('[SW] Cache Hit:', request.url);
    
    // 同时从网络更新缓存（不等待）
    fetch(request).then(response => {
      if (response && response.status === 200) {
        caches.open(STATIC_CACHE).then(cache => {
          cache.put(request, response);
        });
      }
    }).catch(() => {
      // 网络失败，忽略
    });
    
    return cached;
  }
  
  // 缓存没有，从网络获取
  try {
    const response = await fetch(request);
    
    if (response && response.status === 200) {
      const clone = response.clone();
      caches.open(STATIC_CACHE).then(cache => {
        cache.put(request, clone);
      });
    }
    
    return response;
  } catch (error) {
    console.error('[SW] Cache First 失败:', request.url, error);
    
    // 如果是导航请求，返回离线页面
    if (request.mode === 'navigate') {
      return caches.match('/offline.html');
    }
    
    throw error;
  }
}

/**
 * Network First 策略
 * 优先从网络获取，网络失败时使用缓存
 */
async function networkFirst(request) {
  try {
    // 尝试从网络获取
    const response = await fetch(request);
    
    if (response && response.status === 200) {
      // 成功，更新缓存
      const clone = response.clone();
      caches.open(DYNAMIC_CACHE).then(cache => {
        cache.put(request, clone);
      });
    }
    
    return response;
  } catch (error) {
    console.log('[SW] Network 失败，使用缓存:', request.url);
    
    // 网络失败，使用缓存
    const cached = await caches.match(request);
    
    if (cached) {
      console.log('[SW] Cache Hit:', request.url);
      return cached;
    }
    
    // 缓存也没有
    if (request.mode === 'navigate') {
      return caches.match('/offline.html');
    }
    
    // API 请求返回错误响应
    if (isApiRequest(request)) {
      return new Response(
        JSON.stringify({
          error: 'Offline',
          message: '网络不可用，请检查网络连接',
          cached: false
        }),
        {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }
    
    throw error;
  }
}

/**
 * 后台同步
 */
self.addEventListener('sync', event => {
  console.log('[SW] Sync:', event.tag);
  
  if (event.tag === 'sync-offline-queue') {
    event.waitUntil(syncOfflineQueue());
  }
});

/**
 * 同步离线队列
 */
async function syncOfflineQueue() {
  // 从 IndexedDB 或 localStorage 获取离线队列
  // 这里简化处理，实际应该使用 IndexedDB
  console.log('[SW] 同步离线队列');
  
  // 通知客户端同步完成
  const clients = await self.clients.matchAll();
  clients.forEach(client => {
    client.postMessage({
      type: 'SYNC_COMPLETE',
      tag: 'sync-offline-queue'
    });
  });
}

/**
 * 推送通知
 */
self.addEventListener('push', event => {
  console.log('[SW] Push received');
  
  const data = event.data ? event.data.json() : {};
  
  const options = {
    body: data.body || '新消息',
    icon: 'static/images/icon-96x96.png',
    badge: 'static/images/icon-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: data.id || 1
    },
    actions: [
      {
        action: 'view',
        title: '查看',
        icon: 'static/images/icon-72x72.png'
      },
      {
        action: 'dismiss',
        title: '关闭'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title || 'IntelliTeam', options)
  );
});

/**
 * 通知点击处理
 */
self.addEventListener('notificationclick', event => {
  console.log('[SW] Notification click:', event.action);
  
  event.notification.close();
  
  if (event.action === 'view') {
    event.waitUntil(
      clients.openWindow('/')
    );
  } else if (event.action === 'dismiss') {
    // 关闭通知，不做其他操作
  } else {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

/**
 * 消息处理
 */
self.addEventListener('message', event => {
  console.log('[SW] Message:', event.data);
  
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      caches.keys().then(keys => {
        return Promise.all(keys.map(key => caches.delete(key)));
      })
    );
  }
  
  if (event.data && event.data.type === 'GET_CACHE_STATUS') {
    event.waitUntil(
      caches.keys().then(keys => {
        return Promise.all(
          keys.map(key => {
            return caches.open(key).then(cache => {
              return cache.keys().then(requests => {
                return {
                  cacheName: key,
                  requestCount: requests.length
                };
              });
            });
          })
        );
      }).then(cacheStatus => {
        event.ports[0].postMessage({
          type: 'CACHE_STATUS',
          data: cacheStatus
        });
      })
    );
  }
});

console.log('[SW] Service Worker loaded');
