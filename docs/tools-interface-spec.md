# Python Tools 接口规范附录（字段级）

**版本**: v1.0  
**状态**: Draft  
**基线文档**: 《Python Tools 设计文档（严格对齐 OpenClaw Tools）》

---

## 1. 文档说明

本附录给出字段级接口规范，目标是为 Python Runtime 提供可实现、可测试、可审计的统一契约。

本附录仅定义接口与约束，不包含可运行代码。

---

## 2. 统一约定

### 2.1 类型约定

| 类型 | 说明 |
|------|------|
| `string` | UTF-8 文本 |
| `integer` | 32/64 位整数 |
| `number` | 浮点数 |
| `boolean` | 布尔 |
| `object` | JSON 对象 |
| `array<T>` | 元素类型为 T 的数组 |
| `enum` | 枚举字符串 |
| `nullable<T>` | 可空类型，等价 T \| null |

### 2.2 字段规则

- 除非明确声明 **required**，字段均为可选。
- 所有时间字段使用 ISO-8601（UTC），示例: `2026-03-12T03:45:10Z`。
- 所有 ID 字段推荐使用 ULID/UUID，运行时保证唯一性。
- 所有工具入参必须通过 schema 校验后才允许执行。

### 2.3 状态语义

| 状态 | 说明 |
|------|------|
| `ok` | 本次调用已完成并返回最终结果 |
| `accepted` | 请求被接受，异步流程已排队 |
| `running` | 任务正在执行，需后续轮询 |
| `error` | 调用失败，返回标准错误对象 |

---

## 3. 统一 Envelope

### 3.1 ToolCallRequest

```json
{
  "tool": "string",
  "action": "string",
  "params": {},
  "meta": {
    "traceId": "string",
    "idempotencyKey": "string",
    "timeoutMs": 30000
  }
}
```

**字段说明**:

- `tool` **required**: 工具名，如 `web_fetch`。
- `action` **required**: 动作名。单动作工具固定为 `run`。
- `params` **required**: 工具动作参数对象。
- `meta.traceId`: 链路追踪 ID。
- `meta.idempotencyKey`: 幂等键，建议用于外部副作用动作。
- `meta.timeoutMs`: 调用超时，默认由工具自身配置决定。

### 3.2 ToolCallResponse

```json
{
  "status": "ok",
  "data": {},
  "error": null,
  "runtime": {
    "tool": "string",
    "action": "string",
    "durationMs": 120,
    "sessionId": "string",
    "warnings": ["string"]
  }
}
```

**字段说明**:

- `status` **required**: `ok` \| `accepted` \| `running` \| `error`。
- `data`: 成功或进行中时的结果载荷。
- `error`: 失败时返回标准错误对象。
- `runtime.sessionId`: 长任务会话 ID（如 exec/process）。
- `runtime.warnings`: 非致命告警列表。

### 3.3 StandardError

```json
{
  "code": "VALIDATION_ERROR",
  "message": "human readable",
  "retryable": false,
  "details": {},
  "hint": "string"
}
```

**标准错误码**:

| 错误码 | 说明 |
|--------|------|
| `VALIDATION_ERROR` | 参数不合法 |
| `UNAUTHORIZED` | 未授权 |
| `FORBIDDEN` | 权限不足 |
| `NOT_FOUND` | 目标不存在 |
| `CONFLICT` | 状态冲突 |
| `TIMEOUT` | 超时 |
| `RATE_LIMITED` | 限流 |
| `DEPENDENCY_ERROR` | 下游依赖失败 |
| `SECURITY_BLOCKED` | 命中安全策略 |
| `INTERNAL_ERROR` | 内部错误 |

---

## 4. 运行时上下文对象

### 4.1 ToolContext（内部注入）

```json
{
  "agentId": "string",
  "sessionId": "string",
  "provider": "string",
  "model": "string",
  "userId": "string",
  "workspaceId": "string",
  "policySnapshotId": "string"
}
```

**约束**:

- 该对象不可由模型直接填写，必须由运行时注入。
- 所有会话可见性、工具裁剪都以 `policySnapshotId` 对应快照为准。

---

## 5. 策略配置接口

### 5.1 ToolsConfig

```json
{
  "profile": "coding",
  "allow": ["group:fs", "web_search"],
  "deny": ["group:runtime"],
  "byProvider": {
    "openai/gpt-5.2": {
      "allow": ["group:fs", "sessions_list"],
      "deny": ["write"]
    }
  },
  "loopDetection": {
    "enabled": true,
    "warningThreshold": 10,
    "criticalThreshold": 20,
    "globalCircuitBreakerThreshold": 50,
    "historySize": 30
  },
  "web": {
    "cacheTtlSec": 900,
    "maxCharsCap": 20000,
    "allowPrivateNetwork": false
  }
}
```

**约束**:

- `deny` 优先于 `allow`。
- `allow`/`deny` 支持工具名、`group:*`、通配符 `*`。
- `byProvider` 只允许缩小工具集。
- `profile` 可选值: `minimal` \| `coding` \| `messaging` \| `full`。

### 5.2 AgentToolsConfig

```json
{
  "profile": "messaging",
  "allow": ["message", "sessions_list"],
  "deny": ["gateway"],
  "byProvider": {
    "anthropic": {
      "allow": ["message"]
    }
  }
}
```

**约束**:

- Agent 级配置覆盖全局同名字段。
- 覆盖后仍受系统强制安全策略限制。

---

## 6. 工具分组映射

### 6.1 规范组

| 组名 | 包含工具 |
|------|----------|
| `group:runtime` | `exec`,`bash`,`process` |
| `group:fs` | `read`,`write`,`edit`,`apply_patch` |
| `group:sessions` | `sessions_list`,`sessions_history`,`sessions_send`,`sessions_spawn`,`session_status` |
| `group:memory` | `memory_search`,`memory_get` |
| `group:web` | `web_search`,`web_fetch` |
| `group:ui` | `browser`,`canvas` |
| `group:automation` | `cron`,`gateway` |
| `group:messaging` | `message` |
| `group:nodes` | `nodes` |
| `group:openclaw` | 全部内置工具 |

---

## 7. 通用分页与排序

### 7.1 PageRequest

```json
{
  "cursor": "string",
  "limit": 20,
  "sortBy": "createdAt",
  "sortOrder": "desc"
}
```

**约束**:

- `limit` 默认 20，最大 100。
- `sortOrder` 枚举: `asc` \| `desc`。

### 7.2 PageResponse

```json
{
  "items": [],
  "nextCursor": "string",
  "hasMore": true
}
```

---

## 8. 工具接口规范

### 8.1 exec

**动作**: `run`

#### 8.1.1 请求

```json
{
  "cmd": "string",
  "cwd": "string",
  "env": {"KEY":"VALUE"},
  "yieldMs": 1000,
  "timeoutMs": 120000,
  "background": false,
  "pty": false,
  "elevated": false,
  "host": "local",
  "security": { "ask": false },
  "node": { "id": "string" }
}
```

**必填**: `cmd`

**约束**:

- `background=true` 时成功返回 `running` 且必须包含 `sessionId`。
- 若 `process` 被禁用，`background` 必须被忽略并强制同步。

#### 8.1.2 响应 data

```json
{
  "exitCode": 0,
  "stdout": "string",
  "stderr": "string",
  "sessionId": "string"
}
```

### 8.2 process

**动作**: `list` \| `poll` \| `log` \| `write` \| `kill` \| `clear` \| `remove`

#### 8.2.1 list 请求

```json
{ "cursor": "string", "limit": 20 }
```

#### 8.2.2 poll 请求

```json
{ "sessionId": "string", "waitMs": 1000 }
```

#### 8.2.3 log 请求

```json
{ "sessionId": "string", "stream": "stdout", "offset": 0, "maxBytes": 65536 }
```

#### 8.2.4 write 请求

```json
{ "sessionId": "string", "input": "string" }
```

#### 8.2.5 kill\|clear\|remove 请求

```json
{ "sessionId": "string" }
```

**约束**:

- 所有动作都必须做 agent 作用域隔离。
- 不存在或越权会话返回 `NOT_FOUND` 或 `FORBIDDEN`。

### 8.3 web_search

**动作**: `run`

#### 8.3.1 请求

```json
{
  "query": "string",
  "count": 5,
  "locale": "zh-CN",
  "safeSearch": "moderate",
  "freshnessDays": 7
}
```

**约束**:

- `query` 必填。
- `count` 默认 5，范围 1-10。

#### 8.3.2 响应 data

```json
{
  "results": [
    {
      "title": "string",
      "url": "https://...",
      "snippet": "string",
      "source": "string",
      "publishedAt": "2026-03-10T08:00:00Z"
    }
  ],
  "cache": {
    "hit": false,
    "ttlSec": 900
  }
}
```

### 8.4 web_fetch

**动作**: `run`

#### 8.4.1 请求

```json
{
  "url": "https://...",
  "extractMode": "readable",
  "maxChars": 12000,
  "timeoutMs": 20000,
  "headers": { "User-Agent": "string" }
}
```

**约束**:

- 仅允许 http/https。
- 禁止私网地址与本地回环地址。
- 必须对重定向目标重复执行安全校验。
- `maxChars` 不得超过系统 `maxCharsCap`。

#### 8.4.2 响应 data

```json
{
  "url": "https://...",
  "finalUrl": "https://...",
  "title": "string",
  "content": "string",
  "truncated": true,
  "contentType": "text/html",
  "statusCode": 200
}
```

### 8.5 browser

**动作**: `status` \| `start` \| `stop` \| `snapshot` \| `click` \| `type` \| `select` \| `hover` \| `press` \| `scroll` \| `navigate` \| `back` \| `forward` \| `tabs` \| `screenshot` \| `upload` \| `dialog` \| `profile`

#### 8.5.1 通用请求头字段

```json
{ "target": "default", "profile": "default", "node": { "id": "string" } }
```

#### 8.5.2 snapshot 请求

```json
{ "action": "snapshot", "target": "default" }
```

**响应 data**:

```json
{
  "url": "https://...",
  "title": "string",
  "refs": [
    { "ref": "r_001", "role": "button", "name": "Submit", "text": "Submit" }
  ]
}
```

#### 8.5.3 act 类动作请求（以 click 为例）

```json
{ "action": "click", "ref": "r_001", "target": "default" }
```

**约束**:

- click/type/select/hover/press 必须优先使用最新 snapshot 的 ref。
- 非 ref 定位属于降级能力，应记录 warning。

### 8.6 canvas

**动作**: `present` \| `hide` \| `navigate` \| `eval` \| `snapshot` \| `a2ui_push` \| `a2ui_reset`

#### 8.6.1 present 请求

```json
{ "title": "string", "html": "string", "state": {} }
```

#### 8.6.2 eval 请求

```json
{ "script": "string", "args": {} }
```

#### 8.6.3 snapshot 响应 data

```json
{ "dom": "string", "state": {}, "events": [] }
```

### 8.7 nodes

**动作**: `status` \| `list` \| `describe` \| `pair` \| `approve` \| `notify` \| `run` \| `camera` \| `screen` \| `location`

#### 8.7.1 status 请求

```json
{ "nodeId": "string" }
```

#### 8.7.2 run 请求

```json
{ "nodeId": "string", "cmd": "string", "timeoutMs": 120000, "ask": true }
```

#### 8.7.3 camera/screen 请求

```json
{ "nodeId": "string", "mode": "photo", "durationSec": 5, "ask": true }
```

**约束**:

- camera/screen 必须显式同意 `ask=true` 且权限通过。
- 节点不可达返回 `DEPENDENCY_ERROR`。

### 8.8 message

**动作**: `send` \| `list_channels` \| `list_members` \| `create_thread` \| `reply` \| `react` \| `poll_create` \| `poll_vote` \| `moderate`

#### 8.8.1 send 请求

```json
{
  "provider": "slack",
  "channelId": "string",
  "text": "string",
  "threadId": "string",
  "mentions": ["user:123"]
}
```

#### 8.8.2 send 响应 data

```json
{ "messageId": "string", "timestamp": "2026-03-12T03:45:10Z" }
```

**约束**:

- 活动会话绑定时，`channelId` 必须在允许范围内。

### 8.9 cron

**动作**: `status` \| `list` \| `add` \| `update` \| `remove` \| `run` \| `runs` \| `wake`

#### 8.9.1 add 请求

```json
{
  "name": "daily-report",
  "schedule": "0 9 * * *",
  "timezone": "Asia/Shanghai",
  "payload": { "agentId": "string", "prompt": "string" },
  "enabled": true
}
```

#### 8.9.2 runs 请求

```json
{ "jobId": "string", "cursor": "string", "limit": 20 }
```

### 8.10 gateway

**动作**: `restart` \| `config.schema.lookup` \| `config.get` \| `config.apply` \| `config.patch` \| `update.run`

#### 8.10.1 config.get 请求

```json
{ "path": "tools.web" }
```

#### 8.10.2 config.patch 请求

```json
{ "path": "tools.web.maxCharsCap", "value": 30000, "dryRun": false }
```

**约束**:

- 变更配置动作必须记录审计日志（操作者、前后值、时间、traceId）。

### 8.11 sessions_list

**动作**: `run`

**请求**:

```json
{ "cursor": "string", "limit": 20, "agentId": "string" }
```

**响应 data**:

```json
{
  "items": [
    { "sessionId": "string", "agentId": "string", "title": "string", "updatedAt": "2026-03-12T03:45:10Z" }
  ],
  "nextCursor": "string",
  "hasMore": true
}
```

### 8.12 sessions_history

**动作**: `run`

**请求**:

```json
{ "sessionId": "string", "cursor": "string", "limit": 50 }
```

**响应 data**:

```json
{
  "items": [
    { "messageId": "string", "role": "user", "content": "string", "createdAt": "2026-03-12T03:45:10Z" }
  ],
  "nextCursor": "string"
}
```

### 8.13 sessions_send

**动作**: `run`

**请求**:

```json
{ "sessionId": "string", "content": "string", "metadata": {} }
```

**响应 data**:

```json
{ "accepted": true, "messageId": "string" }
```

### 8.14 sessions_spawn

**动作**: `run`

**请求**:

```json
{ "agentId": "string", "title": "string", "initialPrompt": "string", "inheritPolicyFromSessionId": "string" }
```

**响应 data**:

```json
{ "sessionId": "string", "agentId": "string" }
```

### 8.15 session_status

**动作**: `run`

**请求**:

```json
{ "sessionId": "string" }
```

**响应 data**:

```json
{ "sessionId": "string", "state": "idle", "runningTools": [], "updatedAt": "2026-03-12T03:45:10Z" }
```

### 8.16 agents_list

**动作**: `run`

**请求**:

```json
{ "cursor": "string", "limit": 20 }
```

**响应 data**:

```json
{
  "items": [
    { "agentId": "string", "name": "string", "description": "string", "visible": true }
  ],
  "nextCursor": "string"
}
```

**约束**:

- 返回结果必须受 `allowAgents` 和会话可见性策略约束。

---

## 9. 循环检测接口

### 9.1 LoopDetectionConfig

```json
{
  "enabled": true,
  "warningThreshold": 10,
  "criticalThreshold": 20,
  "globalCircuitBreakerThreshold": 50,
  "historySize": 30,
  "detectors": {
    "genericRepeat": true,
    "knownPollNoProgress": true,
    "pingPong": true
  }
}
```

### 9.2 LoopSignal（内部事件）

```json
{
  "level": "warning",
  "detector": "genericRepeat",
  "score": 12,
  "reason": "same tool/action repeated without progress",
  "snapshotId": "string"
}
```

---

## 10. 安全与审计接口

### 10.1 SecurityDecision（内部）

```json
{
  "allowed": false,
  "reasonCode": "SECURITY_BLOCKED",
  "reason": "private network target denied",
  "policyRuleId": "string"
}
```

### 10.2 AuditLogEntry（内部）

```json
{
  "id": "string",
  "timestamp": "2026-03-12T03:45:10Z",
  "actor": { "userId": "string", "agentId": "string" },
  "tool": "gateway",
  "action": "config.patch",
  "paramsRedacted": {},
  "result": "ok",
  "traceId": "string"
}
```

---

## 11. 可观测性指标（建议）

- `tool_calls_total{tool,action,status}`
- `tool_call_latency_ms{tool,action,p50,p95,p99}`
- `tool_validation_fail_total{tool,action}`
- `tool_security_block_total{tool,reasonCode}`
- `tool_loop_warning_total{detector}`
- `tool_process_running_sessions{agentId}`

---

## 12. 兼容性与版本策略

- Schema 采用语义化版本: `major.minor.patch`。
- `major` 变更允许删除字段或改必填。
- `minor` 仅增加可选字段或新 action。
- `patch` 仅修正文案、默认值与非破坏性约束。
- 每个工具 schema 必须带 `x-schema-version` 元信息。

---

## 13. 最小验收矩阵

- [ ] 参数校验: 每个工具 action 至少 3 个无效样例。
- [ ] 权限校验: deny 覆盖 allow、byProvider 收敛正确。
- [ ] 长任务: exec(background=true) + process.poll/log/kill 全链路。
- [ ] Web 安全: 私网 URL、重定向至私网、超长内容截断。
- [ ] 会话隔离: 不同 agent 不能访问对方 process/session。
- [ ] 循环检测: 三类 detector 均可触发并产生告警事件。

---

## 14. 附录 A: Tool Name 保留字

- `exec`
- `bash`
- `process`
- `read`
- `write`
- `edit`
- `apply_patch`
- `memory_search`
- `memory_get`
- `web_search`
- `web_fetch`
- `browser`
- `canvas`
- `nodes`
- `message`
- `cron`
- `gateway`
- `sessions_list`
- `sessions_history`
- `sessions_send`
- `sessions_spawn`
- `session_status`
- `agents_list`

---

## 15. 附录 B: 建议目录结构（仅文档约定）

```
docs/
  python-tools-design.md
  python-tools-interface-spec.md
schemas/
  tools/
    common/
    runtime/
    web/
    ui/
    messaging/
    automation/
    sessions/
```

---

文档版本: 1.0
创建日期: 2026-03-12
对齐版本: OpenClaw 文档 (2026-03-12)
