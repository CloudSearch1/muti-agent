"""
Slack 集成示例

演示如何使用 PI-Python 的 Slack 集成功能
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

# 导入 PI-Python 模块
from pi_python.integrations import (
    SlackIntegration,
    MessageRouter,
    Route,
    get_integration_registry,
)
from pi_python.integrations.router import create_router
from pi_python import Agent, AgentState, get_model


def create_coding_agent() -> Agent:
    """创建编程助手 Agent"""
    return Agent(
        initial_state=AgentState(
            system_prompt="""你是一个专业的编程助手。

你可以帮助用户：
1. 编写和调试代码
2. 解释技术概念
3. 审查代码质量
4. 提供技术建议

请用中文回复，保持专业和友好。""",
            model=get_model("openai", "gpt-4o"),
            tools=[],
            messages=[]
        )
    )


def create_docs_agent() -> Agent:
    """创建文档助手 Agent"""
    return Agent(
        initial_state=AgentState(
            system_prompt="""你是一个专业的技术文档助手。

你可以帮助用户：
1. 生成代码文档
2. 编写 API 文档
3. 创建使用指南
4. 优化文档结构

请用中文回复，保持清晰和专业。""",
            model=get_model("openai", "gpt-4o-mini"),
            tools=[],
            messages=[]
        )
    )


async def main():
    """主函数"""
    
    # 检查环境变量
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_SIGNING_SECRET"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print("错误：缺少以下环境变量:")
        for var in missing:
            print(f"  - {var}")
        print("\n请设置环境变量后再运行此示例")
        return
    
    print("=" * 60)
    print("PI-Python Slack 集成示例")
    print("=" * 60)
    
    # 1. 创建 Agent
    print("\n[1/4] 创建 Agent...")
    coding_agent = create_coding_agent()
    docs_agent = create_docs_agent()
    print("✓ Agent 创建完成")
    
    # 2. 创建消息路由器
    print("\n[2/4] 配置消息路由...")
    router = create_router()
    
    # 添加 Agent 到路由
    router.add_agent("coding", coding_agent)
    router.add_agent("docs", docs_agent)
    router.add_agent("default", coding_agent)  # 默认 Agent
    
    # 配置路由规则
    # 代码相关问题路由到 coding Agent
    router.add_route(Route(
        pattern=r"(代码|code|编程|program|bug|错误|debug|调试)",
        agent_id="coding",
        priority=10
    ))
    
    # 文档相关问题路由到 docs Agent
    router.add_route(Route(
        pattern=r"(文档|doc|文档化|documentation|readme)",
        agent_id="docs",
        priority=10
    ))
    
    print("✓ 路由配置完成")
    print(f"  - 路由规则数: {len(router.routes)}")
    print(f"  - Agent 数量: {len(router.agent_pool)}")
    
    # 3. 创建 Slack 集成
    print("\n[3/4] 创建 Slack 集成...")
    
    slack_config = {
        "bot_token": os.getenv("SLACK_BOT_TOKEN"),
        "app_token": os.getenv("SLACK_APP_TOKEN"),
        "signing_secret": os.getenv("SLACK_SIGNING_SECRET")
    }
    
    slack = SlackIntegration(slack_config)
    
    # 将 Slack 消息路由到 Agent
    async def route_to_agent(message):
        return await router.handle_message(message)
    
    slack.on_message(route_to_agent)
    print("✓ Slack 集成创建完成")
    
    # 4. 注册到全局注册表并启动
    print("\n[4/4] 启动集成...")
    registry = get_integration_registry()
    registry.register("slack", slack)
    
    await slack.start()
    print("✓ Slack 集成已启动")
    
    print("\n" + "=" * 60)
    print("集成已启动！现在你可以在 Slack 中:")
    print("1. 直接给 Bot 发消息")
    print("2. 在频道中 @Bot 提及")
    print("3. 系统会根据你的问题自动路由到合适的 Agent")
    print("\n按 Ctrl+C 停止")
    print("=" * 60)
    
    # 保持运行
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止...")
        await slack.stop()
        print("已停止")


if __name__ == "__main__":
    asyncio.run(main())
