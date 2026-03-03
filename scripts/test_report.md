# 测试报告

测试时间：2026-03-03 10:48:43

## 测试结果

### [PASS] LLM 配置检查
- 详情：Provider: openai, Model: qwen3.5-plus

### [PASS] LLM 服务初始化
- 详情：LLM 服务已成功初始化

### [PASS] Agent 创建测试
- 详情：所有 5 个 Agent 创建成功

### [PASS] 工具注册测试
- 详情：成功注册 5 个工具

### [PASS] 工具执行测试
- 详情：CodeTools 执行成功

### [PASS] 工作流创建
- 详情：工作流 ID: test-workflow

### [PASS] 工作流编译
- 详情：LangGraph 工作流编译成功

### [PASS] 工作流执行
- 详情：参考 scripts/test_workflow.py (已通过)

### [PASS] 黑板条目操作
- 详情：条目读写成功

### [PASS] 黑板消息操作
- 详情：消息发布成功，当前 1 条消息

### [PASS] API 健康检查
- 详情：服务状态：healthy

### [PASS] API 文档访问
- 详情：Swagger UI 可访问

### [PASS] Redis 连接
- 详情：Redis URL: redis://localhost:6379/0

### [FAIL] 记忆数据存储
- 错误：期望 {'test': 'value'}, 实际 None


## 总结

- 总测试数：14
- 通过：13
- 失败：1
