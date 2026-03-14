"""
PI-Python 开发工具演示

演示 CLI、REPL、调试和测试功能的使用
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pi_python import Agent, AgentState, get_model
from pi_python.agent.tools import BashTool, FileTool
from pi_python.devtools import (
    app,  # CLI
    ReplSession,  # REPL
    DebugTracer,  # 调试
    enable_debug_mode,  # 调试模式
    AgentTestFixture,  # 测试
)


def demo_cli():
    """演示 CLI 使用"""
    print("=" * 60)
    print("1. CLI 演示")
    print("=" * 60)
    
    print("\n创建新的技能：")
    print("  命令: pi-dev new-skill CodeReviewer")
    print("  输出: skills/CodeReviewer.skill.md")
    
    print("\n创建新的扩展：")
    print("  命令: pi-dev new-extension MyExtension")
    print("  输出: extensions/MyExtension.py")
    
    print("\n启动交互式助手：")
    print("  命令: pi-dev start --model openai/gpt-4o")
    print("  命令: pi-dev start --model anthropic/claude-sonnet-4 --debug")
    print("  命令: pi-dev start --skills ./skills --extensions ./extensions")


async def demo_repl():
    """演示 REPL 功能"""
    print("\n" + "=" * 60)
    print("2. REPL 演示")
    print("=" * 60)
    
    # 创建 Agent
    agent = Agent(
        initial_state=AgentState(
            system_prompt="你是一个乐于助人的助手。",
            model=get_model("openai", "gpt-4o-mini"),
            tools=[BashTool(), FileTool()],
            messages=[]
        )
    )
    
    # 创建 REPL 会话（模拟）
    print("\nREPL 可用命令：")
    print("  /help     - 显示帮助信息")
    print("  /clear    - 清除会话历史")
    print("  /history  - 显示会话历史")
    print("  /tools    - 显示可用工具")
    print("  /skills   - 显示可用技能")
    print("  /debug    - 显示调试信息")
    print("  exit/q    - 退出 REPL")
    
    print("\nREPL 特性：")
    print("  ✓ 实时流式响应")
    print("  ✓ 语法高亮")
    print("  ✓ 命令历史")
    print("  ✓ 工具执行状态显示")
    print("  ✓ 错误处理")


def demo_debugging():
    """演示调试功能"""
    print("\n" + "=" * 60)
    print("3. 调试功能演示")
    print("=" * 60)
    
    print("\n启用调试模式：")
    print("  tracer = enable_debug_mode(agent)")
    print("  # 或启动 REPL 时使用 --debug 参数")
    
    print("\n调试功能：")
    print("  ✓ 记录所有 Agent 事件")
    print("  ✓ 统计 LLM 调用次数")
    print("  ✓ 统计工具调用次数")
    print("  ✓ 统计 Token 使用量")
    print("  ✓ 生成 Mermaid 执行流程图")
    print("  ✓ 生成详细调试报告")
    
    print("\n调试报告内容：")
    print("  - 执行时间统计")
    print("  - 事件时间线")
    print("  - 执行流程图（Mermaid）")
    print("  - 错误详情（如果有）")
    print("  - Token 使用情况")


async def demo_testing():
    """演示测试功能"""
    print("\n" + "=" * 60)
    print("4. 测试功能演示")
    print("=" * 60)
    
    # 创建测试夹具
    fixture = AgentTestFixture()
    
    print("\n创建测试 Agent：")
    print("  agent = fixture.create_agent()")
    
    print("\n创建带 Mock 工具的 Agent：")
    print("  mock_tool = fixture.create_mock_tool('test_tool', 'test result')")
    print("  agent = fixture.create_agent(tools=[mock_tool])")
    
    print("\n运行测试并断言：")
    print("  output = await fixture.run_prompt(agent, 'test prompt')")
    print("  fixture.assert_output_contains('expected')")
    print("  fixture.assert_no_errors()")
    print("  fixture.assert_tool_called('test_tool')")
    
    print("\n测试夹具功能：")
    print("  ✓ 自动捕获 Agent 事件")
    print("  ✓ 收集输出文本")
    print("  ✓ 断言工具调用")
    print("  ✓ 断言输出内容")
    print("  ✓ 断言无错误")
    print("  ✓ 断言事件触发")
    print("  ✓ Mock 工具支持")
    print("  ✓ 与 pytest 集成")


async def demo_workflow():
    """演示完整工作流"""
    print("\n" + "=" * 60)
    print("5. 完整工作流演示")
    print("=" * 60)
    
    print("""
步骤 1: 创建新技能
  $ pi-dev new-skill CodeReview
  → 生成 skills/CodeReview.skill.md
  → 编辑技能定义

步骤 2: 创建新扩展
  $ pi-dev new-extension GitIntegration
  → 生成 extensions/GitIntegration.py
  → 实现扩展逻辑

步骤 3: 启动调试会话
  $ pi-dev start --debug --skills ./skills
  → 启用调试模式
  → 加载技能
  → 交互式测试

步骤 4: 编写测试
  → 使用 AgentTestFixture
  → 运行测试用例
  → 验证功能

步骤 5: 查看调试报告
  → 检查 debug_logs/trace_*.json
  → 查看执行流程图
  → 优化性能
    """)


def main():
    """主函数"""
    print("=" * 60)
    print("PI-Python 开发工具套件演示")
    print("=" * 60)
    
    # 演示 CLI
    demo_cli()
    
    # 演示 REPL
    asyncio.run(demo_repl())
    
    # 演示调试
    demo_debugging()
    
    # 演示测试
    asyncio.run(demo_testing())
    
    # 演示工作流
    asyncio.run(demo_workflow())
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)
    
    print("""
开始使用：

1. 安装依赖：
   $ pip install -r requirements.txt

2. 运行 CLI：
   $ python -m pi_python.devtools.cli.main --help

3. 创建技能：
   $ python -m pi_python.devtools.cli.main new-skill MySkill

4. 启动交互式助手：
   $ python -m pi_python.devtools.cli.main start --debug

5. 编写测试：
   使用 AgentTestFixture 创建测试用例

6. 集成到 Slack：
   $ python examples/slack_integration_demo.py
    """)


if __name__ == "__main__":
    main()
