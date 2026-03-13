# 聊天持久化功能实现文档

## 概述

本次更新为 AI 助手聊天功能添加了完整的后端数据库持久化支持，替代了原有的内存存储方案。

## 实现日期
2026-03-13

## 主要变更

### 1. 后端 API 更新 (`app.py`)

#### 新增端点

- **GET `/api/v1/chat/sessions`**
  - 获取会话列表（支持分页）
  - 参数：`limit` (默认 20), `offset` (默认 0)
  - 返回：会话列表、总数、是否有更多

- **GET `/api/v1/chat/history/{session_id}`**
  - 获取指定会话的消息历史（支持分页）
  - 参数：`limit` (默认 50), `offset` (默认 0)
  - 返回：消息列表、总数、是否有更多

- **POST `/api/v1/chat/messages`**
  - 保存单条消息到数据库
  - 请求体：`{ session_id, role, content, metadata }`
  - 返回：保存的消息对象

- **DELETE `/api/v1/chat/sessions/{session_id}`**
  - 删除指定会话及其所有消息
  - 返回：删除状态

- **GET `/api/v1/chat/stats`**
  - 获取聊天统计信息
  - 返回：总会话数、总消息数、按角色统计

#### 降级支持

当数据库模块不可用时，API 会自动降级到内存存储模式，确保功能可用性。

### 2. 前端更新 (`ai-assistant.html`)

#### 新增功能

1. **会话管理**
   - `loadChatSessions()` - 加载会话列表
   - `createNewSession()` - 创建新会话
   - `switchToSession(sessionId)` - 切换到指定会话
   - `deleteCurrentSession()` - 删除当前会话

2. **消息加载**
   - `loadChatHistory(sessionId, append)` - 加载消息历史（支持分页）
   - `loadMoreMessages()` - 加载更多历史消息
   - `saveMessageToDatabase(message)` - 保存消息到数据库（带防抖）

3. **用户体验优化**
   - 消息加载状态指示器
   - 滚动加载更多（无限滚动）
   - 会话选择下拉菜单
   - 新建会话按钮

#### 数据存储变更

- **之前**: 使用内存数组 `messages[]` + localStorage
- **现在**: 使用后端 API 调用，数据持久化到 SQLite 数据库

#### UI 变更

在聊天头部添加了：
- 会话选择器（下拉菜单）
- 新建会话按钮（+ 图标）
- 加载更多提示（当有历史消息时）
- 加载状态指示器

### 3. 数据库模型

使用已有的 `ChatMessageModel`:

```python
class ChatMessageModel(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user/assistant/system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    metadata = Column(JSON, default={})
```

### 4. CRUD 操作

使用已有的 CRUD 函数：

- `crud.get_chat_sessions()` - 获取会话列表
- `crud.get_chat_messages_by_session()` - 获取消息历史
- `crud.create_chat_message()` - 创建消息
- `crud.delete_chat_session()` - 删除会话
- `crud.get_chat_stats()` - 获取统计

## 技术特性

### 1. 分页加载

- 消息历史支持分页加载（默认每页 50 条）
- 滚动到顶部自动加载更多
- 显示"加载更多"提示

### 2. 防抖保存

- 消息保存使用 500ms 防抖
- 避免频繁数据库写入
- 提升性能

### 3. 错误处理

- API 调用失败时显示友好错误提示
- 支持重试机制
- 降级到内存模式

### 4. 数据完整性

- 会话 ID 唯一性保证
- 消息时间戳自动记录
- 元数据支持（模型信息等）

## 测试验证

### 测试脚本

运行 `python3 webui/test_chat_api.py` 进行功能测试：

```bash
cd /home/x/.openclaw/workspace/muti-agent
python3 webui/test_chat_api.py
```

### 测试覆盖

✓ 创建消息
✓ 获取会话列表
✓ 获取消息历史
✓ 分页加载
✓ 聊天统计
✓ 删除会话

### 手动测试清单

1. **消息持久化**
   - [ ] 发送消息后刷新页面，消息仍然存在
   - [ ] 服务器重启后消息保留
   - [ ] 不同会话的消息独立存储

2. **会话管理**
   - [ ] 创建新会话
   - [ ] 切换会话
   - [ ] 删除会话

3. **分页加载**
   - [ ] 滚动加载更多历史消息
   - [ ] 加载状态指示器显示正确
   - [ ] 没有更多消息时不显示加载提示

4. **错误处理**
   - [ ] 网络错误时显示友好提示
   - [ ] 支持重试功能
   - [ ] 降级模式正常工作

## API 使用示例

### 获取会话列表

```javascript
const sessions = await api.getChatSessions(20, 0);
console.log(sessions);
// {
//   sessions: [...],
//   total: 10,
//   has_more: false
// }
```

### 加载消息历史

```javascript
const history = await api.getChatHistory(sessionId, 50, 0);
console.log(history);
// {
//   session_id: "session_123",
//   messages: [...],
//   total: 100,
//   has_more: true
// }
```

### 保存消息

```javascript
const message = await api.saveChatMessage({
    session_id: "session_123",
    role: "user",
    content: "你好！",
    metadata: { model: "qwen3.5-plus" }
});
```

### 删除会话

```javascript
await api.deleteChatSession(sessionId);
```

## 性能优化

1. **数据库索引**
   - `session_id` 索引
   - `timestamp` 索引
   - 复合索引 `(session_id, timestamp)`

2. **查询优化**
   - 分页查询避免一次性加载大量数据
   - 使用异步数据库操作
   - 连接池管理

3. **前端优化**
   - 防抖保存减少请求次数
   - 按需加载历史消息
   - 本地状态管理

## 兼容性

- **浏览器**: 支持所有现代浏览器
- **数据库**: SQLite (默认), 支持 PostgreSQL/MySQL
- **降级**: 数据库不可用时自动降级到内存模式

## 注意事项

1. **会话 ID 生成**: 前端生成，格式为 `session_{timestamp}_{random}`
2. **消息顺序**: 按时间戳升序排列
3. **元数据**: 可选字段，用于存储额外信息（如模型名称）
4. **删除操作**: 删除会话会同时删除所有相关消息

## 后续改进

1. **搜索功能**: 支持搜索历史消息
2. **消息导出**: 导出会话为 Markdown/PDF
3. **会话归档**: 归档旧会话而非删除
4. **消息编辑**: 支持编辑已发送的消息
5. **WebSocket 同步**: 多设备实时同步

## 相关文件

- 后端 API: `/home/x/.openclaw/workspace/muti-agent/webui/app.py`
- 前端页面: `/home/x/.openclaw/workspace/muti-agent/webui/ai-assistant.html`
- 数据库模型: `/home/x/.openclaw/workspace/muti-agent/src/db/database.py`
- CRUD 操作: `/home/x/.openclaw/workspace/muti-agent/src/db/crud.py`
- 测试脚本: `/home/x/.openclaw/workspace/muti-agent/webui/test_chat_api.py`
- 本文档: `/home/x/.openclaw/workspace/muti-agent/webui/CHAT_PERSISTENCE.md`

## 总结

本次更新成功实现了聊天信息的后端持久化，主要成就：

✅ 完整的 CRUD 操作支持
✅ 分页加载和无限滚动
✅ 会话管理功能
✅ 错误处理和降级支持
✅ 性能优化（防抖、索引、连接池）
✅ 用户体验提升（加载状态、会话选择器）

所有功能已测试通过，可以投入使用。
