# 示例：基础任务执行
"""
展示如何使用 IntelliTeam 执行一个简单的编程任务
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph import create_workflow


async def main():
    """主函数"""
    print("=" * 60)
    print("IntelliTeam 示例 - 基础任务执行")
    print("=" * 60)
    print()
    
    # 创建工作流
    print("[1/3] 创建工作流...")
    workflow = create_workflow()
    print(f"  工作流 ID: {workflow.workflow_id}")
    print()
    
    # 执行任务
    print("[2/3] 执行任务...")
    print("  任务：创建一个 Python 计算器模块")
    print()
    
    result = await workflow.run(
        task_id="example-calculator",
        task_title="创建计算器模块",
        task_description="创建一个 Python 计算器模块，支持加减乘除四则运算，包含单元测试",
    )
    
    # 查看结果
    print("[3/3] 任务完成！")
    print()
    print("=" * 60)
    print("执行结果")
    print("=" * 60)
    print()
    print(f"最终状态：{result.current_step}")
    print(f"错误：{result.error or '无'}")
    print()
    
    # 显示各 Agent 的执行结果
    print("Agent 执行结果:")
    for agent_name, agent_result in result.agent_results.items():
        print(f"\n  {agent_name}:")
        if isinstance(agent_result, dict):
            for key, value in agent_result.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"    {key}: {value[:100]}...")
                else:
                    print(f"    {key}: {value}")
        else:
            print(f"    {agent_result}")
    
    print()
    print("=" * 60)
    print("示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
