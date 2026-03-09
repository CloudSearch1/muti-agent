# Phase 1 详细开发计划

> 项目: IntelliTeam
> 阶段: Phase 1 - 核心功能完善
> 预估时间: 14 小时
> 负责人: Claude Code
> 状态: 待执行

---

## 任务概览

| 编号 | 任务 | 优先级 | 预估时间 | 状态 |
|-----|------|-------|---------|------|
| 1.1 | 附件下载功能修复 | P0 | 2h | ✅ 已完成 |
| 1.2 | 数据持久化系统搭建 | P0 | 8h | ✅ 已完成 |
| 1.3 | 状态变更确认机制 | P0 | 2h | ✅ 已完成 |
| 1.4 | 通知系统优化 | P1 | 2h | ✅ 已完成 |

---

## 任务 1.1: 附件下载功能修复

### 1.1.1 需求描述

**问题描述**:
- 用户在任务详情页面上传附件后，无法下载
- 点击下载按钮无响应或报错

**影响范围**:
- `webui/task-detail.html`
- `src/api/main.py` (如果有附件 API)

### 1.1.2 问题分析

**可能原因**:
1. 前端下载逻辑未实现
2. 附件存储在内存中，刷新后丢失
3. 缺少后端文件服务 API
4. CORS 或 Content-Type 问题

### 1.1.3 技术方案

**方案选择**: 
由于当前是纯前端演示，采用 **Base64 + Blob** 方案实现下载

**实现步骤**:

```
┌──────────────────────────────────────────────────────┐
│                    前端下载流程                       │
├──────────────────────────────────────────────────────┤
│                                                      │
│  1. 用户点击下载按钮                                  │
│       ↓                                              │
│  2. 获取附件数据 (Base64 或 File 对象)               │
│       ↓                                              │
│  3. 创建 Blob 对象                                   │
│       ↓                                              │
│  4. 创建临时下载链接                                 │
│       ↓                                              │
│  5. 触发浏览器下载                                   │
│       ↓                                              │
│  6. 清理临时链接                                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 1.1.4 代码修改位置

**文件**: `webui/task-detail.html`

**修改内容**:

```javascript
// 1. 找到 downloadAttachment 方法
// 位置: methods 部分

downloadAttachment(file) {
    // 当前代码可能有 bug，需要修复
    
    // 方案 A: 如果附件是 File 对象
    if (file.raw) {
        const url = URL.createObjectURL(file.raw);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        return;
    }
    
    // 方案 B: 如果附件是 Base64
    if (file.content) {
        const byteCharacters = atob(file.content);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: file.type || 'application/octet-stream' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        return;
    }
    
    // 方案 C: 如果是模拟数据，显示提示
    this.showToast('演示模式下，附件为模拟数据', 'info');
}
```

### 1.1.5 文件上传流程优化

**当前问题**: 上传的文件没有正确存储

**解决方案**:

```javascript
// 上传附件时，存储原始文件对象
handleFileUpload(event) {
    const files = event.target.files;
    for (let file of files) {
        const reader = new FileReader();
        reader.onload = (e) => {
            this.attachments.push({
                id: Date.now(),
                name: file.name,
                size: file.size,
                type: file.type,
                content: e.target.result.split(',')[1], // Base64
                raw: file, // 保留原始文件对象
                uploadedAt: new Date().toLocaleString()
            });
            // 持久化到 localStorage
            this.saveTaskData();
        };
        reader.readAsDataURL(file);
    }
}
```

### 1.1.6 验收标准

| 测试项 | 预期结果 |
|-------|---------|
| 上传 PDF 文件 | 成功添加到附件列表 |
| 上传图片文件 | 成功添加到附件列表 |
| 点击下载按钮 | 浏览器弹出下载对话框 |
| 下载后打开文件 | 文件内容正确，无损坏 |
| 刷新页面后下载 | 附件仍可下载（需持久化配合） |

### 1.1.7 风险点

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| 大文件内存溢出 | 文件超过 50MB 可能卡顿 | 提示用户文件大小限制 |
| localStorage 容量限制 | 约 5MB | 大文件提示并建议后端存储 |
| 文件类型安全 | 恶意文件执行 | 仅下载，不执行 |

---

## 任务 1.2: 数据持久化系统搭建

### 1.2.1 需求描述

**问题描述**:
- 任务状态变更后刷新页面数据丢失
- 任务历史、评论、附件未持久化
- 无法保存用户操作记录

**需求范围**:
- 任务基本信息持久化
- 任务状态持久化
- 任务历史记录持久化
- 评论持久化
- 附件持久化

### 1.2.2 技术选型分析

#### 方案对比

| 方案 | 适用场景 | 容量 | 复杂度 | 协作支持 |
|-----|---------|------|-------|---------|
| LocalStorage | 单机演示 | ~5MB | 低 | ❌ |
| IndexedDB | 大数据量单机 | ~500MB | 中 | ❌ |
| SQLite | 轻量级后端 | 无限制 | 中 | ✅ |
| PostgreSQL | 生产环境 | 无限制 | 高 | ✅ |

#### 推荐方案

**第一阶段（本次实现）**: LocalStorage + IndexedDB
- LocalStorage 存储配置和小数据
- IndexedDB 存储大文件（附件）

**第二阶段（后续扩展）**: 后端 API + 数据库
- FastAPI + SQLite（开发环境）
- FastAPI + PostgreSQL（生产环境）

### 1.2.3 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   Vue 3     │  │   Pinia     │  │   Storage   │          │
│  │   App      │◄─┤   Store    │◄─┤   Service   │          │
│  └─────────────┘  └─────────────┘  └──────┬──────┘          │
└──────────────────────────────────────────┼──────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      ▼
           ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
           │  LocalStorage │      │  IndexedDB   │      │   Backend    │
           │              │      │              │      │   API (未来)  │
           │ - config     │      │ - tasks      │      │              │
           │ - user pref  │      │ - attachments│      │ - PostgreSQL │
           │ - small data │      │ - large files│      │              │
           └──────────────┘      └──────────────┘      └──────────────┘
```

### 1.2.4 数据结构设计

#### 任务数据结构

```typescript
interface Task {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed';
  priority: 'low' | 'normal' | 'high' | 'critical';
  assignee: string;
  agent: string;
  createdAt: string;
  updatedAt: string;
  dueDate?: string;
  tags?: string[];
}

interface TaskHistory {
  id: string;
  taskId: string;
  action: string;
  user: string;
  timestamp: string;
  details?: any;
}

interface Comment {
  id: string;
  taskId: string;
  author: string;
  content: string;
  createdAt: string;
}

interface Attachment {
  id: string;
  taskId: string;
  name: string;
  size: number;
  type: string;
  content?: string; // Base64
  uploadedAt: string;
}
```

#### 存储结构

```javascript
// LocalStorage Keys
const STORAGE_KEYS = {
  TASKS: 'intelliteam_tasks',
  TASK_HISTORY: 'intelliteam_history',
  COMMENTS: 'intelliteam_comments',
  CONFIG: 'intelliteam_config',
  USER_PREF: 'intelliteam_preferences'
};

// IndexedDB Structure
const DB_NAME = 'IntelliTeamDB';
const DB_VERSION = 1;

const DB_STORES = {
  TASKS: 'tasks',
  ATTACHMENTS: 'attachments',
  HISTORY: 'history'
};
```

### 1.2.5 实现步骤

#### Step 1: 创建 Storage Service

**文件**: `webui/js/storage-service.js`

```javascript
/**
 * StorageService - 统一存储服务
 * 提供 LocalStorage 和 IndexedDB 的统一接口
 */
class StorageService {
    constructor() {
        this.dbName = 'IntelliTeamDB';
        this.dbVersion = 1;
        this.db = null;
    }

    // 初始化 IndexedDB
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve(this.db);
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // 创建 tasks 存储
                if (!db.objectStoreNames.contains('tasks')) {
                    const taskStore = db.createObjectStore('tasks', { keyPath: 'id' });
                    taskStore.createIndex('status', 'status', { unique: false });
                    taskStore.createIndex('assignee', 'assignee', { unique: false });
                }
                
                // 创建 attachments 存储
                if (!db.objectStoreNames.contains('attachments')) {
                    const attachStore = db.createObjectStore('attachments', { keyPath: 'id' });
                    attachStore.createIndex('taskId', 'taskId', { unique: false });
                }
                
                // 创建 history 存储
                if (!db.objectStoreNames.contains('history')) {
                    const historyStore = db.createObjectStore('history', { keyPath: 'id' });
                    historyStore.createIndex('taskId', 'taskId', { unique: false });
                }
            };
        });
    }

    // LocalStorage 操作
    get(key) {
        try {
            const data = localStorage.getItem(key);
            return data ? JSON.parse(data) : null;
        } catch (e) {
            console.error('StorageService.get error:', e);
            return null;
        }
    }

    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.error('StorageService.set error:', e);
            return false;
        }
    }

    remove(key) {
        localStorage.removeItem(key);
    }

    // IndexedDB 操作
    async saveTask(task) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readwrite');
            const store = transaction.objectStore('tasks');
            const request = store.put(task);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async getTask(id) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readonly');
            const store = transaction.objectStore('tasks');
            const request = store.get(id);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async getAllTasks() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readonly');
            const store = transaction.objectStore('tasks');
            const request = store.getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async deleteTask(id) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['tasks'], 'readwrite');
            const store = transaction.objectStore('tasks');
            const request = store.delete(id);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    // 附件操作
    async saveAttachment(attachment) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['attachments'], 'readwrite');
            const store = transaction.objectStore('attachments');
            const request = store.put(attachment);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async getAttachmentsByTask(taskId) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['attachments'], 'readonly');
            const store = transaction.objectStore('attachments');
            const index = store.index('taskId');
            const request = index.getAll(taskId);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    // 历史记录操作
    async addHistory(history) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['history'], 'readwrite');
            const store = transaction.objectStore('history');
            const request = store.add(history);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async getHistoryByTask(taskId) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['history'], 'readonly');
            const store = transaction.objectStore('history');
            const index = store.index('taskId');
            const request = index.getAll(taskId);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
}

// 导出单例
const storageService = new StorageService();
```

#### Step 2: 修改 task-detail.html 集成持久化

```javascript
// 在 Vue app 中添加
const app = Vue.createApp({
    data() {
        return {
            // ... 现有数据
            storageReady: false
        };
    },
    
    async mounted() {
        // 初始化存储服务
        await storageService.init();
        this.storageReady = true;
        
        // 加载任务数据
        await this.loadTaskData();
    },
    
    methods: {
        // 加载任务数据
        async loadTaskData() {
            if (!this.storageReady) return;
            
            try {
                // 从 IndexedDB 加载任务
                const tasks = await storageService.getAllTasks();
                if (tasks.length > 0) {
                    // 找到当前任务
                    const task = tasks.find(t => t.id === this.taskId);
                    if (task) {
                        this.task = task;
                    }
                }
                
                // 加载历史记录
                const history = await storageService.getHistoryByTask(this.taskId);
                this.taskHistory = history;
                
                // 加载评论
                const comments = this.loadComments();
                this.comments = comments;
                
                // 加载附件
                const attachments = await storageService.getAttachmentsByTask(this.taskId);
                this.attachments = attachments;
                
            } catch (error) {
                console.error('加载任务数据失败:', error);
            }
        },
        
        // 保存任务数据
        async saveTaskData() {
            if (!this.storageReady) return;
            
            try {
                // 保存到 IndexedDB
                await storageService.saveTask(this.task);
                
                // 同时保存到 LocalStorage 作为备份
                this.saveToLocalStorage();
            } catch (error) {
                console.error('保存任务数据失败:', error);
            }
        },
        
        // 保存到 LocalStorage
        saveToLocalStorage() {
            const key = `task_${this.taskId}`;
            const data = {
                task: this.task,
                history: this.taskHistory,
                comments: this.comments,
                updatedAt: new Date().toISOString()
            };
            storageService.set(key, data);
        },
        
        // 从 LocalStorage 加载
        loadFromLocalStorage() {
            const key = `task_${this.taskId}`;
            return storageService.get(key);
        },
        
        // 更新任务状态（带持久化）
        async updateTaskStatus(newStatus) {
            const oldStatus = this.task.status;
            
            // 添加历史记录
            const historyEntry = {
                id: Date.now().toString(),
                taskId: this.taskId,
                action: `状态从 "${this.getStatusText(oldStatus)}" 变更为 "${this.getStatusText(newStatus)}"`,
                user: '当前用户',
                timestamp: new Date().toLocaleString(),
                oldStatus: oldStatus,
                newStatus: newStatus
            };
            
            await storageService.addHistory(historyEntry);
            this.taskHistory.unshift(historyEntry);
            
            // 更新任务状态
            this.task.status = newStatus;
            this.task.updatedAt = new Date().toISOString();
            
            // 持久化保存
            await this.saveTaskData();
            
            this.showToast(`任务状态已更新为: ${this.getStatusText(newStatus)}`, 'success');
        },
        
        // 添加评论（带持久化）
        async addComment() {
            if (!this.newComment.trim()) return;
            
            const comment = {
                id: Date.now().toString(),
                taskId: this.taskId,
                author: '当前用户',
                content: this.newComment,
                createdAt: new Date().toLocaleString()
            };
            
            this.comments.push(comment);
            this.newComment = '';
            
            // 持久化
            this.saveComments();
            
            // 添加历史记录
            await this.addHistoryEntry('添加了评论');
        },
        
        // 保存评论
        saveComments() {
            const key = `comments_${this.taskId}`;
            storageService.set(key, this.comments);
        },
        
        // 加载评论
        loadComments() {
            const key = `comments_${this.taskId}`;
            return storageService.get(key) || [];
        },
        
        // 添加历史记录
        async addHistoryEntry(action) {
            const entry = {
                id: Date.now().toString(),
                taskId: this.taskId,
                action: action,
                user: '当前用户',
                timestamp: new Date().toLocaleString()
            };
            
            await storageService.addHistory(entry);
            this.taskHistory.unshift(entry);
        }
    }
});
```

### 1.2.6 数据迁移计划

```javascript
// 数据迁移脚本
async function migrateData() {
    // 检查旧版本数据
    const oldTasks = localStorage.getItem('intelliteam_tasks_v1');
    if (oldTasks) {
        const tasks = JSON.parse(oldTasks);
        for (const task of tasks) {
            await storageService.saveTask(task);
        }
        // 迁移完成后删除旧数据
        localStorage.removeItem('intelliteam_tasks_v1');
        console.log('数据迁移完成');
    }
}
```

### 1.2.7 验收标准

| 测试项 | 预期结果 |
|-------|---------|
| 创建新任务 | 数据保存到 IndexedDB |
| 修改任务状态 | 刷新页面后状态保持 |
| 添加评论 | 刷新页面后评论存在 |
| 上传附件 | 刷新页面后附件可下载 |
| 查看历史记录 | 显示完整操作历史 |
| 清除浏览器数据 | 提示用户数据将丢失 |

### 1.2.8 风险点

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| IndexedDB 不支持 | 降级到 LocalStorage | 检测兼容性并提示 |
| 存储空间不足 | 数据丢失 | 定期清理旧数据，提示用户 |
| 数据版本升级 | 数据不兼容 | 实现数据迁移脚本 |

---

## 任务 1.3: 状态变更确认机制

### 1.3.1 需求描述

**问题描述**:
- 点击状态按钮立即变更，无确认步骤
- 容易误操作
- 无法撤销

**需求**:
- 点击状态按钮后弹出确认框
- 显示变更前后的状态
- 支持取消操作

### 1.3.2 交互设计

```
用户点击 "进行中" 按钮
         ↓
┌─────────────────────────────────┐
│                                 │
│   ⚠️ 确认变更任务状态？          │
│                                 │
│   当前状态:  ⚪ 待处理           │
│   变更状态:  🔵 进行中           │
│                                 │
│   此操作将记录到任务历史         │
│                                 │
│   [取消]        [确认变更]       │
│                                 │
└─────────────────────────────────┘
         ↓
用户点击 "确认变更"
         ↓
执行状态变更 + 记录历史
         ↓
显示成功提示
```

### 1.3.3 实现代码

**文件**: `webui/task-detail.html`

```html
<!-- 确认弹窗组件 -->
<div v-if="showStatusConfirm" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center" @click.self="showStatusConfirm = false">
    <div class="bg-white dark:bg-dark-200 rounded-2xl shadow-2xl w-full max-w-md p-6">
        <div class="text-center mb-6">
            <div class="w-16 h-16 mx-auto bg-yellow-100 dark:bg-yellow-900/30 rounded-full flex items-center justify-center mb-4">
                <i class="fas fa-exclamation-triangle text-3xl text-yellow-600"></i>
            </div>
            <h3 class="text-xl font-bold text-gray-800 dark:text-gray-100">确认变更任务状态？</h3>
        </div>
        
        <div class="bg-gray-50 dark:bg-dark-100 rounded-xl p-4 mb-6">
            <div class="flex justify-between items-center mb-3">
                <span class="text-gray-600 dark:text-gray-400">当前状态</span>
                <span class="font-semibold" :class="getStatusClass(task.status)">
                    {{ getStatusText(task.status) }}
                </span>
            </div>
            <div class="flex justify-center my-2">
                <i class="fas fa-arrow-down text-2xl text-gray-400"></i>
            </div>
            <div class="flex justify-between items-center">
                <span class="text-gray-600 dark:text-gray-400">变更状态</span>
                <span class="font-semibold" :class="getStatusClass(pendingStatus)">
                    {{ getStatusText(pendingStatus) }}
                </span>
            </div>
        </div>
        
        <p class="text-sm text-gray-500 dark:text-gray-400 text-center mb-6">
            <i class="fas fa-info-circle mr-1"></i>
            此操作将记录到任务历史，可在历史记录中查看
        </p>
        
        <div class="flex space-x-4">
            <button @click="showStatusConfirm = false" class="flex-1 px-4 py-3 bg-gray-100 dark:bg-dark-100 text-gray-700 dark:text-gray-300 rounded-xl font-medium hover:bg-gray-200 dark:hover:bg-dark-50 transition">
                取消
            </button>
            <button @click="confirmStatusChange" class="flex-1 px-4 py-3 bg-primary-500 text-white rounded-xl font-medium hover:bg-primary-600 transition">
                确认变更
            </button>
        </div>
    </div>
</div>
```

```javascript
// JavaScript 实现
data() {
    return {
        // ... 现有数据
        showStatusConfirm: false,
        pendingStatus: null
    };
},

methods: {
    // 点击状态按钮（显示确认框）
    changeStatus(newStatus) {
        if (newStatus === this.task.status) return;
        
        this.pendingStatus = newStatus;
        this.showStatusConfirm = true;
    },
    
    // 确认状态变更
    async confirmStatusChange() {
        if (!this.pendingStatus) return;
        
        // 执行状态变更
        await this.updateTaskStatus(this.pendingStatus);
        
        // 关闭弹窗
        this.showStatusConfirm = false;
        this.pendingStatus = null;
    },
    
    // 获取状态文本
    getStatusText(status) {
        const statusMap = {
            'pending': '待处理',
            'in_progress': '进行中',
            'completed': '已完成'
        };
        return statusMap[status] || status;
    },
    
    // 获取状态样式类
    getStatusClass(status) {
        const classMap = {
            'pending': 'text-gray-600',
            'in_progress': 'text-blue-600',
            'completed': 'text-green-600'
        };
        return classMap[status] || '';
    }
}
```

### 1.3.4 状态按钮修改

```html
<!-- 状态选择按钮组 -->
<div class="flex space-x-2">
    <button 
        @click="changeStatus('pending')"
        :class="[
            'px-4 py-2 rounded-lg font-medium transition',
            task.status === 'pending' 
                ? 'bg-gray-600 text-white' 
                : 'bg-gray-100 dark:bg-dark-100 text-gray-600 dark:text-gray-400 hover:bg-gray-200'
        ]"
    >
        ⚪ 待处理
    </button>
    
    <button 
        @click="changeStatus('in_progress')"
        :class="[
            'px-4 py-2 rounded-lg font-medium transition',
            task.status === 'in_progress' 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-100 dark:bg-dark-100 text-gray-600 dark:text-gray-400 hover:bg-gray-200'
        ]"
    >
        🔵 进行中
    </button>
    
    <button 
        @click="changeStatus('completed')"
        :class="[
            'px-4 py-2 rounded-lg font-medium transition',
            task.status === 'completed' 
                ? 'bg-green-600 text-white' 
                : 'bg-gray-100 dark:bg-dark-100 text-gray-600 dark:text-gray-400 hover:bg-gray-200'
        ]"
    >
        ✅ 已完成
    </button>
</div>
```

### 1.3.5 验收标准

| 测试项 | 预期结果 |
|-------|---------|
| 点击状态按钮 | 弹出确认框，显示当前和新状态 |
| 点击取消 | 关闭弹窗，状态不变 |
| 点击确认 | 状态变更，添加历史记录 |
| 按 ESC 键 | 关闭弹窗，状态不变 |
| 点击弹窗外部 | 关闭弹窗，状态不变 |

---

## 任务 1.4: 通知系统优化

### 1.4.1 需求描述

**问题描述**:
- 点击"全部已读"后，小红点数字未清除
- 已读通知和未读通知样式相同
- 无法区分哪些通知已读

**需求**:
- 已读通知显示灰色样式
- 未读通知保持高亮
- 小红点数字实时更新为未读数量

### 1.4.2 数据结构

```javascript
// 通知数据结构
interface Notification {
    id: string;
    type: 'info' | 'warning' | 'success' | 'error';
    title: string;
    message: string;
    time: string;
    read: boolean;  // 新增字段
}
```

### 1.4.3 实现代码

**文件**: `webui/index_v5.html`

```javascript
// 数据部分
data() {
    return {
        // ... 现有数据
        notifications: [
            { id: 1, type: 'success', title: '任务完成', message: 'Agent Coder 完成了 API 开发任务', time: '5 分钟前', read: false },
            { id: 2, type: 'info', title: '新任务', message: '您收到了一个新的任务分配', time: '10 分钟前', read: false },
            { id: 3, type: 'warning', title: '截止提醒', message: '任务 "数据库设计" 将在明天到期', time: '1 小时前', read: false }
        ]
    };
},

computed: {
    // 计算未读数量
    unreadCount() {
        return this.notifications.filter(n => !n.read).length;
    }
},

methods: {
    // 全部标记已读
    markAllRead() {
        this.notifications.forEach(n => n.read = true);
        this.showNotifications = false; // 关闭通知面板
        
        // 持久化
        this.saveNotifications();
        
        this.showToast('已将所有通知标记为已读', 'success');
    },
    
    // 保存通知到 LocalStorage
    saveNotifications() {
        localStorage.setItem('intelliteam_notifications', JSON.stringify(this.notifications));
    },
    
    // 加载通知
    loadNotifications() {
        const saved = localStorage.getItem('intelliteam_notifications');
        if (saved) {
            this.notifications = JSON.parse(saved);
        }
    }
}
```

### 1.4.4 HTML 模板修改

```html
<!-- 通知按钮 -->
<button @click="showNotifications = !showNotifications" class="relative p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-100 transition">
    <i class="fas fa-bell text-gray-600 dark:text-gray-400 text-xl"></i>
    <!-- 小红点 - 只显示未读数量 -->
    <span v-if="unreadCount > 0" class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center font-bold">
        {{ unreadCount }}
    </span>
</button>

<!-- 通知面板 -->
<div v-if="showNotifications" class="fixed top-20 right-4 w-80 bg-white dark:bg-dark-200 rounded-xl shadow-2xl z-50 border dark:border-dark-100">
    <div class="p-4 border-b dark:border-dark-100 flex justify-between items-center">
        <h3 class="font-bold text-gray-800 dark:text-gray-100">通知</h3>
        <button @click="markAllRead" class="text-sm text-primary-500 hover:text-primary-600">
            全部已读
        </button>
    </div>
    
    <div class="max-h-96 overflow-y-auto">
        <div v-for="notif in notifications" :key="notif.id" 
             class="p-4 border-b dark:border-dark-100 hover:bg-gray-50 dark:hover:bg-dark-100 transition cursor-pointer"
             :class="{ 'bg-gray-50 dark:bg-dark-100 opacity-60': notif.read }">
            <div class="flex items-start space-x-3">
                <div class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                     :class="{
                         'bg-green-100 dark:bg-green-900/30': notif.type === 'success',
                         'bg-blue-100 dark:bg-blue-900/30': notif.type === 'info',
                         'bg-yellow-100 dark:bg-yellow-900/30': notif.type === 'warning',
                         'bg-red-100 dark:bg-red-900/30': notif.type === 'error'
                     }">
                    <i :class="{
                        'fas fa-check text-green-600': notif.type === 'success',
                        'fas fa-info text-blue-600': notif.type === 'info',
                        'fas fa-exclamation text-yellow-600': notif.type === 'warning',
                        'fas fa-times text-red-600': notif.type === 'error'
                    }"></i>
                </div>
                <div class="flex-1">
                    <p class="font-semibold text-sm" 
                       :class="notif.read ? 'text-gray-500 dark:text-gray-400' : 'text-gray-800 dark:text-gray-100'">
                        {{ notif.title }}
                    </p>
                    <p class="text-sm" 
                       :class="notif.read ? 'text-gray-400 dark:text-gray-500' : 'text-gray-600 dark:text-gray-300'">
                        {{ notif.message }}
                    </p>
                    <p class="text-xs text-gray-400 mt-1">{{ notif.time }}</p>
                </div>
                <!-- 未读指示点 -->
                <span v-if="!notif.read" class="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-2"></span>
            </div>
        </div>
    </div>
</div>
```

### 1.4.5 样式优化

```css
/* 已读通知样式 */
.notification-read {
    opacity: 0.6;
    background-color: rgba(0, 0, 0, 0.02);
}

.dark .notification-read {
    background-color: rgba(255, 255, 255, 0.02);
}

/* 未读通知高亮 */
.notification-unread {
    border-left: 3px solid #3b82f6;
}

/* 通知项 hover 效果 */
.notification-item:hover {
    background-color: rgba(0, 0, 0, 0.05);
}

.dark .notification-item:hover {
    background-color: rgba(255, 255, 255, 0.05);
}
```

### 1.4.6 验收标准

| 测试项 | 预期结果 |
|-------|---------|
| 显示通知列表 | 正确显示所有通知 |
| 未读通知 | 有蓝色圆点标记，文字颜色深 |
| 已读通知 | 无圆点标记，文字颜色浅（灰色） |
| 点击"全部已读" | 所有通知变灰，小红点消失 |
| 小红点数字 | 显示未读数量（非总数） |
| 刷新页面 | 已读状态保持 |

---

## 执行计划

### 时间安排

| 任务 | 开始时间 | 结束时间 | 负责人 |
|-----|---------|---------|-------|
| 1.1 附件下载修复 | Day 1 09:00 | Day 1 11:00 | Claude Code |
| 1.2 持久化系统 | Day 1 13:00 | Day 2 17:00 | Claude Code |
| 1.3 状态确认机制 | Day 3 09:00 | Day 3 11:00 | Claude Code |
| 1.4 通知系统优化 | Day 3 13:00 | Day 3 15:00 | Claude Code |
| 集成测试 | Day 3 15:00 | Day 3 17:00 | Claude Code |

### 依赖关系

```
任务 1.2 (持久化系统)
    ↓
任务 1.1 (附件下载) ← 依赖持久化存储附件
    ↓
任务 1.3 (状态确认) ← 依赖持久化存储历史
    ↓
任务 1.4 (通知系统) ← 可并行
```

### 验收流程

```
开发完成
    ↓
代码审查
    ↓
单元测试
    ↓
集成测试
    ↓
用户验收
    ↓
部署上线
```

---

## 附录

### A. 测试清单

- [ ] 附件上传功能
- [ ] 附件下载功能
- [ ] 任务状态持久化
- [ ] 评论持久化
- [ ] 历史记录持久化
- [ ] 状态变更确认
- [ ] 通知已读/未读
- [ ] 通知持久化
- [ ] 跨浏览器兼容性
- [ ] 移动端响应式

### B. 相关文件

| 文件 | 用途 |
|-----|------|
| `webui/task-detail.html` | 任务详情页面 |
| `webui/index_v5.html` | 主页面 |
| `webui/js/storage-service.js` | 存储服务（新增） |
| `docs/ROADMAP.md` | 产品路线图 |

### C. 参考资料

- [MDN - IndexedDB API](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)
- [MDN - Web Storage API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API)
- [Vue 3 Documentation](https://vuejs.org/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)