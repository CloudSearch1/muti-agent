# AI 助手组件文档

## 文件说明

### AIAssistantView.js

**版本**: 2.0 (优化版)  
**最后更新**: 2026-03-13  
**依赖**: Vue 3.4+, TailwindCSS, Font Awesome

### 主要功能

1. **聊天功能**
   - 支持流式消息发送和接收
   - Markdown 渲染（代码块、行内代码、粗体、斜体、链接）
   - 消息历史记录
   - 导出对话（Markdown 格式）
   - 清空对话

2. **Agent 管理**
   - Agent 列表展示
   - Agent 状态实时更新（WebSocket）
   - Agent 切换
   - Agent 统计信息（完成任务、平均时间、成功率）

3. **任务管理**
   - 任务列表展示
   - 新建任务
   - 任务优先级设置
   - Agent 分配
   - 任务详情跳转

4. **设置管理**
   - AI 提供商选择（百炼、Anthropic、OpenAI、DeepSeek）
   - 模型选择
   - API Key 配置
   - 温度调节
   - 连接测试

### 使用方法

```vue
<template>
  <ai-assistant-view :settings="parentSettings"></ai-assistant-view>
</template>

<script>
import { AIAssistantView } from './components/AIAssistantView.js';

export default {
  components: { AIAssistantView },
  data() {
    return {
      parentSettings: {
        aiProvider: 'bailian',
        model: 'qwen3.5-plus',
        apiKey: 'sk-...'
      }
    };
  }
};
</script>
```

### Props

| 名称 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| settings | Object | {} | AI 配置设置 |

### 数据属性

| 名称 | 类型 | 说明 |
|------|------|------|
| messages | Array | 聊天消息列表 |
| inputMessage | String | 输入框内容 |
| attachments | Array | 附件列表 |
| loading | Boolean | 加载状态 |
| error | String | 错误信息 |
| wsConnected | Boolean | WebSocket 连接状态 |
| agents | Array | Agent 列表 |
| selectedAgent | Object | 选中的 Agent |
| tasks | Array | 任务列表 |
| localSettings | Object | 本地设置 |

### 主要方法

| 名称 | 参数 | 说明 |
|------|------|------|
| sendMessage | - | 发送消息 |
| selectAgent | agent | 选择 Agent |
| loadAgents | - | 加载 Agent 列表 |
| loadTasks | - | 加载任务列表 |
| loadSettings | - | 加载设置 |
| clearChat | - | 清空对话 |
| exportChat | - | 导出对话 |
| createTask | - | 创建任务 |
| testConnection | - | 测试 AI 连接 |
| saveSettings | - | 保存设置 |

### WebSocket 消息类型

| 类型 | 说明 | 数据格式 |
|------|------|----------|
| agent_update | Agent 状态更新 | `{ name, status }` |
| task_update | 任务更新 | - |
| system_status | 系统状态 | `{ activeAgents, totalTasks }` |
| heartbeat | 心跳 | `{ timestamp, status }` |

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| /api/v1/agents | GET | 获取 Agent 列表 |
| /api/v1/tasks | GET | 获取任务列表 |
| /api/v1/tasks | POST | 创建任务 |
| /api/v1/settings | GET | 获取设置 |
| /api/v1/settings | POST | 保存设置 |
| /api/v1/settings/models | GET | 获取模型列表 |
| /api/v1/settings/test | POST | 测试连接 |
| /api/v1/chat | POST | 发送聊天消息 |
| /ws | WebSocket | 实时通信 |

### 优化内容 (v2.0)

1. **安全性**
   - ✅ XSS 防护（HTML 转义）
   - ✅ 输入验证
   - ✅ 长度限制

2. **可访问性**
   - ✅ ARIA 标签
   - ✅ 键盘导航
   - ✅ 语义化 HTML

3. **性能**
   - ✅ 防抖节流
   - ✅ 指数退避重连
   - ✅ 资源清理

4. **错误处理**
   - ✅ 友好提示
   - ✅ 重试机制
   - ✅ 详细日志

### 生命周期

```javascript
mounted() {
  // 1. 加载数据
  this.loadAgents();
  this.loadTasks();
  this.loadSettings();
  
  // 2. 建立 WebSocket 连接
  this.connectWebSocket();
  
  // 3. 启动定期刷新
  this._refreshAgentsTimer = setInterval(...);
  this._refreshTasksTimer = setInterval(...);
}

beforeUnmount() {
  // 1. 清除定时器
  clearInterval(this._refreshAgentsTimer);
  clearInterval(this._refreshTasksTimer);
  clearTimeout(this.wsReconnectTimer);
  
  // 2. 断开 WebSocket
  this.disconnectWebSocket();
}
```

### 注意事项

1. **API Key 安全**: API Key 仅存储在本地，不会上传到服务器
2. **消息长度**: 单条消息最大 4000 字
3. **文件大小**: 附件最大 10MB
4. **重连策略**: WebSocket 最大重连 5 次，延迟 1s-30s
5. **消息限制**: 只发送最近 10 条消息到 API

### 故障排除

**问题**: WebSocket 连接失败  
**解决**: 检查网络连接，确认服务器已启动，查看浏览器控制台日志

**问题**: AI 响应失败  
**解决**: 检查 API Key 是否有效，确认 AI 提供商配置正确

**问题**: 消息发送失败  
**解决**: 检查消息长度是否超限，查看网络请求状态

### 相关文件

- `ai-assistant.html` - 主页面
- `utils/api.js` - API 封装
- `utils/format.js` - 格式化工具
- `../../tests/test_ai_assistant.md` - 测试报告

---

**维护者**: IntelliTeam  
**许可证**: MIT
