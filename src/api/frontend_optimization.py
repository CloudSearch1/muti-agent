"""
前端性能优化模块

优化 Web UI 加载速度和用户体验
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.gzip import GZipMiddleware
import os


def setup_frontend_optimization(app: FastAPI):
    """
    设置前端性能优化
    
    Args:
        app: FastAPI 应用实例
    """
    
    # 1. 静态资源缓存
    @app.get("/static/{path:path}")
    async def get_static(path: str):
        """提供静态资源，带长期缓存"""
        file_path = f"webui/static/{path}"
        
        if not os.path.exists(file_path):
            return {"error": "File not found"}
        
        response = FileResponse(file_path)
        
        # 设置长期缓存（1 年）
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        
        # 根据文件类型设置 Content-Type
        if path.endswith(".js"):
            response.headers["Content-Type"] = "application/javascript; charset=utf-8"
        elif path.endswith(".css"):
            response.headers["Content-Type"] = "text/css; charset=utf-8"
        elif path.endswith(".svg"):
            response.headers["Content-Type"] = "image/svg+xml"
        elif path.endswith(".png"):
            response.headers["Content-Type"] = "image/png"
        elif path.endswith(".jpg") or path.endswith(".jpeg"):
            response.headers["Content-Type"] = "image/jpeg"
        elif path.endswith(".gif"):
            response.headers["Content-Type"] = "image/gif"
        elif path.endswith(".webp"):
            response.headers["Content-Type"] = "image/webp"
        
        return response
    
    # 2. HTML 资源预加载提示
    @app.get("/", response_class=HTMLResponse)
    async def get_index():
        """提供主页面，带资源预加载"""
        with open("webui/index_v5.html", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 添加资源预加载提示
        preload_hints = """
        <link rel="preload" href="/static/js/app.js" as="script">
        <link rel="preload" href="/static/css/style.css" as="style">
        <link rel="dns-prefetch" href="//localhost:8080">
        <link rel="preconnect" href="//localhost:8080" crossorigin>
        """
        
        # 插入到 head 标签内
        content = content.replace("<head>", f"<head>\n{preload_hints}")
        
        response = HTMLResponse(content=content)
        
        # 设置短期缓存（5 分钟）
        response.headers["Cache-Control"] = "public, max-age=300"
        
        return response
    
    # 3. 添加 GZip 压缩（已在主应用中添加）
    # app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    print("✅ 前端性能优化已配置")
    print("  - 静态资源长期缓存")
    print("  - 资源预加载")
    print("  - DNS 预解析")
    print("  - GZip 压缩")


# ============ 前端性能优化建议 ============

FRONTEND_OPTIMIZATION_TIPS = """
# 前端性能优化清单

## 已实施

1. ✅ 静态资源缓存（1 年）
2. ✅ 资源预加载（preload）
3. ✅ DNS 预解析（dns-prefetch）
4. ✅ GZip 压缩
5. ✅ HTML 短期缓存

## 建议进一步优化

### 1. 代码分割
```javascript
// 使用动态导入实现代码分割
const Dashboard = () => import('./Dashboard.vue');
const Settings = () => import('./Settings.vue');
```

### 2. 懒加载
```javascript
// 图片懒加载
<img loading="lazy" src="image.jpg">

// 路由懒加载
const routes = [
  {
    path: '/dashboard',
    component: () => import('./Dashboard.vue')
  }
];
```

### 3. Tree Shaking
```javascript
// 使用 ES6 模块语法
import { debounce } from 'lodash-es'; // 只导入需要的函数

// 避免
import _ from 'lodash'; // 导入整个库
```

### 4. 资源压缩
```bash
# 安装压缩工具
npm install -D cssnano terser-webpack-plugin

# CSS 压缩
cssnano input.css > output.min.css

# JS 压缩
terser input.js -o output.min.js
```

### 5. 图片优化
```bash
# 使用 WebP 格式
convert image.jpg image.webp

# 压缩图片
imagemin images/* --out-dir=images-optimized
```

### 6. CDN 加速
```html
<!-- 使用 CDN 加载第三方库 -->
<script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/tailwindcss@2/dist/tailwind.min.css">
```

### 7. Service Worker
```javascript
// 注册 Service Worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js')
    .then(reg => console.log('SW registered'))
    .catch(err => console.error('SW error', err));
}
```

### 8. 性能监控
```javascript
// 使用 Performance API
window.addEventListener('load', () => {
  const perfData = performance.getEntriesByType('navigation')[0];
  console.log('Page load time:', perfData.loadEventEnd - perfData.fetchStart);
});
```

## 性能指标目标

- **FCP (First Contentful Paint)**: < 1.5s
- **LCP (Largest Contentful Paint)**: < 2.5s
- **CLS (Cumulative Layout Shift)**: < 0.1
- **FID (First Input Delay)**: < 100ms
- **TTI (Time to Interactive)**: < 3.5s
"""


# ============ 性能监控脚本 ============

PERFORMANCE_MONITOR_SCRIPT = """
# 前端性能监控脚本

## 使用 Lighthouse

```bash
# 安装 Lighthouse CLI
npm install -g lighthouse

# 运行性能测试
lighthouse http://localhost:8080 --output=html --output-path=report.html

# 仅测试性能
lighthouse http://localhost:8080 --only-categories=performance --output=json
```

## 使用 Web Vitals

```javascript
// 安装 web-vitals
npm install web-vitals

// 监控核心指标
import {onCLS, onFID, onFCP, onLCP, onTTFB} from 'web-vitals';

onCLS(console.log);
onFID(console.log);
onFCP(console.log);
onLCP(console.log);
onTTFB(console.log);
```

## 使用 Performance API

```javascript
// 监控页面加载性能
window.addEventListener('load', () => {
  const perfData = performance.getEntriesByType('navigation')[0];
  
  console.log('DNS 查询时间:', perfData.domainLookupEnd - perfData.domainLookupStart);
  console.log('TCP 连接时间:', perfData.connectEnd - perfData.connectStart);
  console.log('首字节时间:', perfData.responseStart);
  console.log('页面加载时间:', perfData.loadEventEnd - perfData.fetchStart);
});

// 监控资源加载
performance.getEntriesByType('resource').forEach(resource => {
  console.log(`${resource.name}: ${resource.duration}ms`);
});
```
"""
