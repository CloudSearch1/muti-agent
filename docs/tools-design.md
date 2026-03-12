# Python Tools 设计文档（严格对齐 OpenClaw Tools）

## 1. 文档目标与范围

本文定义一个 Python 版 Tools 子系统，行为与 OpenClaw 文档中的 Tools 机制保持一致：工具是类型化能力，受策略裁剪后暴露给模型，并通过统一调用协议执行。

范围覆盖：策略系统、工具注册与暴露、核心工具契约、长任务模型（exec/process）、循环检测、安全要求、推荐编排流。

## 2. 设计原则（必须遵守）

- **工具必须是"typed + no shelling"的一等能力**，不依赖"提示词里让模型自己拼命令"来替代工具。
- **工具可见性由配置策略决定**，且被禁用工具不能发送到模型 provider。
- **工具调用前必须完成策略裁剪**，且遵守优先级（见第 5 节）。
- **模型端必须同时收到"系统提示中的工具说明"和"结构化 tool schema"**；任一缺失都不可调用。

## 3. 术语

- **Tool**：一个可调用能力，包含名称、参数 schema、执行器、返回 schema。
- **Tool Policy**：profile、allow、deny、byProvider 的组合策略。
- **Tool Group**：`group:*` 语法，对多个工具名进行展开。
- **Session Tool**：`sessions_*` 与 `agents_list`，用于多会话/多 agent 协作。

## 4. 总体架构（Python）

建议分层如下（规范，不是示例代码）：

- **tool_contract**：输入输出 schema、执行状态、错误模型。
- **tool_registry**：注册内置工具与插件工具，支持按名字与组展开。
- **tool_policy**：实现 profile/byProvider/allow/deny 合并裁剪。
- **tool_presenter**：构造系统提示文本 + API schema（双通道输出）。
- **tool_runtime**：实际执行、超时控制、后台任务与进程会话。
- **tool_guardrails**：循环检测、权限校验、同意门禁、SSRF/私网防护。

## 5. 策略系统规范（核心）

### 5.1 全局开关与 allow/deny

- `tools.deny` 优先于 `tools.allow`。
- 匹配大小写不敏感。
- 支持 `*` 通配。
- 若 `tools.allow` 只包含未知或未加载插件工具，系统应记录 warning 并忽略该 allowlist（避免核心工具被误清空）。

### 5.2 Profile（基础白名单）

支持 profile：

- **minimal**：仅 `session_status`。
- **coding**：`group:fs`, `group:runtime`, `group:sessions`, `group:memory`, `image`。
- **messaging**：`group:messaging` + `sessions_list`/`sessions_history`/`sessions_send`/`session_status`。
- **full**：不限制（等同未设置）。

并支持每个 agent 覆盖：`agents.list[].tools.profile`。

### 5.3 Provider 定向策略

- `tools.byProvider` 在 profile 之后、allow/deny 之前应用。
- 只能"缩小工具集"，不能扩大。
- key 支持 provider 或 provider/model。
- 支持 agent 级覆盖：`agents.list[].tools.byProvider`。

### 5.4 Tool Group 展开

必须支持以下组：

- `group:runtime`=`exec`,`bash`,`process`
- `group:fs`=`read`,`write`,`edit`,`apply_patch`
- `group:sessions`=`sessions_list`,`sessions_history`,`sessions_send`,`sessions_spawn`,`session_status`
- `group:memory`=`memory_search`,`memory_get`
- `group:web`=`web_search`,`web_fetch`
- `group:ui`=`browser`,`canvas`
- `group:automation`=`cron`,`gateway`
- `group:messaging`=`message`
- `group:nodes`=`nodes`
- `group:openclaw`=所有内置工具（不含 provider 插件工具）

## 6. 工具暴露协议

运行时对每轮请求执行：

1. 计算当前 agent + provider/model 的有效工具集（策略合并 + group 展开 + 去重）。
2. 生成系统提示中的工具说明（可读）。
3. 生成 API tool schemas（结构化）。
4. 两者取交集，最终暴露给模型。

## 7. Tool 契约规范（Python）

每个工具必须定义：

- name、description。
- action 枚举（若该工具是多动作模型，如 browser, nodes, message, cron, gateway, process）。
- input_schema（Pydantic/JSON Schema）。
- output_schema（含 status、结果载荷、错误）。
- timeouts 与 retry 策略。
- security_precheck（权限、同意、目标合法性、会话隔离）。

建议统一 status 语义：

- **ok**：完成。
- **running**：后台运行中（必须返回可追踪会话标识）。
- **error**：失败（可恢复/不可恢复错误码区分）。

该语义与 exec/process 模式一致。

## 8. 关键工具行为要求

### 8.1 exec + process（长任务）

- exec 支持 `yieldMs`/`background`/`timeout`/`elevated`/`host`/`security`/`ask`/`node`/`pty`。
- 后台时返回 `running` + `sessionId`。
- 后续必须通过 process 的 `list`/`poll`/`log`/`write`/`kill`/`clear`/`remove` 管理。
- 若禁用了 process，exec 必须同步执行并忽略后台参数。
- process 结果需做 agent 作用域隔离（看不到其他 agent 会话）。

### 8.2 web_search / web_fetch

- 两者与浏览器自动化分离；JS-heavy 或登录流程要走 browser。
- **web_search**：query 必填，count 1-10，默认缓存 15 分钟。
- **web_fetch**：仅 http/https，支持 `extractMode`、`maxChars`，maxChars 受 maxCharsCap 限制。
- web_fetch 必须阻止私网/内网目标并重检重定向（SSRF guard）。

### 8.3 browser

- 必须实现 `snapshot` -> `act(ref)` 的引用式交互。act 必须依赖 snapshot 的 ref。
- 支持状态、标签页、导航、截图、上传、对话框与 profile 管理动作。

### 8.4 canvas / nodes

- **canvas**：`present`/`hide`/`navigate`/`eval`/`snapshot`/`a2ui_push`/`a2ui_reset`。
- **nodes**：节点发现、配对审批、通知、远程运行、摄像头/录屏/定位等动作。
- 摄像头/屏幕能力需要前台与权限确认。

### 8.5 message / cron / gateway

- **message**：跨渠道发送、投票、反应、线程、权限与管理类动作。活动会话绑定下必须限制目标，避免跨上下文泄漏。
- **cron**：`status`/`list`/`add`/`update`/`remove`/`run`/`runs`/`wake`。

## 9. 推荐编排流

```
用户请求
  ↓
策略裁剪（profile -> byProvider -> allow/deny）
  ↓
Group 展开 + 去重
  ↓
生成系统提示（可读说明）
  ↓
生成 API Schema（结构化）
  ↓
双通道取交集
  ↓
发送到模型 Provider
  ↓
模型返回 tool_calls
  ↓
权限校验 + 同意门禁
  ↓
执行工具
  ↓
返回结果（ok/running/error）
```

## 10. 实现建议

### 10.1 目录结构

```
pi_python/tools/
├── __init__.py
├── contract.py      # Tool 契约定义
├── registry.py      # 工具注册表
├── policy.py        # 策略系统
├── presenter.py     # 提示词生成
├── runtime.py       # 运行时执行
├── guardrails.py    # 安全防护
├── builtin/         # 内置工具
│   ├── __init__.py
│   ├── exec.py      # Exec Tool
│   ├── web.py       # Web Search/Fetch
│   ├── browser.py   # Browser Tool
│   ├── sessions.py  # Session Tools
│   └── ...
└── plugins/         # 插件目录
```

### 10.2 配置示例

```python
# openclaw.json 等效配置
TOOLS_CONFIG = {
    "tools": {
        "profile": "coding",  # minimal/coding/messaging/full
        "allow": ["custom_tool"],
        "deny": ["dangerous_tool"],
        "byProvider": {
            "openai": {"deny": ["exec"]},
            "anthropic/claude-opus": {"allow": ["group:coding"]}
        }
    },
    "agents": {
        "defaults": {
            "tools": {
                "profile": "coding"
            }
        }
    }
}
```

## 11. 与 OpenClaw 的差异

| 特性 | OpenClaw (TypeScript) | PI-Python |
|------|----------------------|-----------|
| 语言 | TypeScript | Python |
| 执行环境 | Node.js | Python 3.10+ |
| 进程管理 | 内置 process 工具 | subprocess + asyncio |
| 浏览器 | Playwright | Selenium/Playwright |
| 沙箱 | 内置 sandbox | Docker/可选 |

## 12. 补充工具规范

### 12.1 gateway 工具

- **功能**: restart/config.schema.lookup/config.get/config.apply/config.patch/update.run
- **权限**: 高权限操作，需要用户明确同意

### 12.2 sessions_* / agents_list

- **功能**: 会话列举、历史、跨会话发送、spawn、状态查询
- **限制**: agents_list 需受 allowAgents 限制
- **沙箱**: 沙箱场景下需遵守会话可见性钳制逻辑

### 12.3 通用参数约定

- **Gateway 类工具**（canvas/nodes/cron）统一支持：gatewayUrl/gatewayToken/timeoutMs
- **安全要求**: 当设置了 gatewayUrl，必须显式提供 gatewayToken（不继承隐式环境凭据）
- **Browser 统一支持**: profile/target/node

## 13. 循环检测与护栏

### 13.1 配置

- 默认可关闭；开启后使用 warningThreshold/criticalThreshold/globalCircuitBreakerThreshold/historySize
- 检测器必须至少包含：genericRepeat、knownPollNoProgress、pingPong
- 支持 agent 级覆盖

### 13.2 检测策略

| 检测器 | 描述 |
|--------|------|
| genericRepeat | 通用重复检测 |
| knownPollNoProgress | 无进展轮询检测 |
| pingPong | 乒乓消息检测 |

## 14. 安全与合规要求

### 14.1 高风险动作

- **节点运行、摄像头、录屏**必须在明确用户同意后执行
- **媒体类调用**前先做 status/describe 或权限检查

### 14.2 Web 抓取安全

- 必须具备私网拦截
- 重定向重检
- 大小限制与缓存策略

## 15. 推荐编排流（Python 运行时默认 playbook）

### 15.1 Browser 流程

```
status/start -> snapshot -> act -> screenshot
```

### 15.2 Canvas 流程

```
present -> a2ui_push(optional) -> snapshot
```

### 15.3 Nodes 流程

```
status -> describe -> notify/run/camera/screen
```

## 16. 配置映射建议（Python）

将 JSON 配置映射为 Pydantic 模型：

```python
from pydantic import BaseModel
from typing import Optional, List, Dict

class ToolsConfig(BaseModel):
    profile: str = "coding"
    allow: List[str] = []
    deny: List[str] = []
    byProvider: Dict[str, ProviderScopedPolicy] = {}
    loopDetection: Optional[LoopDetectionConfig] = None
    web: Optional[WebConfig] = None
    elevated: Optional[ElevatedConfig] = None

class AgentToolsConfig(BaseModel):
    """Agent 级工具配置（仅覆盖，不反向污染全局）"""
    profile: Optional[str] = None
    allow: Optional[List[str]] = None
    deny: Optional[List[str]] = None
    byProvider: Optional[Dict[str, ProviderScopedPolicy]] = None

class ProviderScopedPolicy(BaseModel):
    """Provider 定向策略（只做收窄）"""
    profile: Optional[str] = None
    allow: Optional[List[str]] = None
    deny: Optional[List[str]] = None
```

该映射是工程实现建议，语义约束来自 OpenClaw 文档。

## 17. 验收清单（Definition of Done）

- [ ] 策略优先级与 group 展开结果可单测验证
- [ ] 同一输入下，系统提示工具列表与 API schema 工具列表一致
- [ ] exec/process 背景任务生命周期可回归测试
- [ ] web_fetch SSRF 与重定向防护可安全测试
- [ ] 循环检测阈值触发与中断策略可观测
- [ ] 会话/agent 可见性边界（sessions_*, agents_list）可验证

## 18. 参考文档

- https://docs.openclaw.ai/tools/exec
- https://docs.openclaw.ai/automation/hooks
- https://docs.openclaw.ai/concepts/tools
- https://docs.openclaw.ai/tools/gateway
- https://docs.openclaw.ai/tools/sessions

---

文档版本: 1.1
创建日期: 2026-03-12
更新日期: 2026-03-12
对齐版本: OpenClaw 文档 (2026-03-12)
