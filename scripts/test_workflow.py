"""
测试 LangGraph 工作流
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_workflow():
    """测试完整工作流"""
    print("=" * 60)
    print("IntelliTeam - LangGraph 工作流测试")
    print("=" * 60)
    print()
    
    try:
        from src.graph import create_workflow
        
        # 创建工作流
        print("[1/3] 创建工作流...")
        workflow = create_workflow("test-workflow-001")
        print(f"  工作流 ID: {workflow.workflow_id}")
        print(f"  Agent: Planner, Architect, Coder, Tester, DocWriter")
        print()
        
        # 编译工作流
        print("[2/3] 编译工作流...")
        workflow.compile()
        print("  编译成功！")
        print()
        
        # 运行工作流
        print("[3/3] 运行工作流...")
        print("  任务：创建一个简单的计算器 API")
        print()
        
        result = await workflow.run(
            task_id="calc-api-001",
            task_title="创建计算器 API",
            task_description="创建一个 REST API，支持加减乘除四则运算",
            input_data={
                "language": "python",
                "framework": "fastapi",
            },
        )
        
        print()
        print("=" * 60)
        print("工作流执行完成！")
        print("=" * 60)
        print()
        print(f"最终状态：{result.current_step}")
        print(f"错误：{result.error or '无'}")
        print()
        
        # 显示各 Agent 结果
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
        print("[SUCCESS] 工作流测试完成！")
        print("=" * 60)
        
    except ImportError as e:
        print(f"[ERROR] 导入失败：{str(e)}")
        print("  请确保已安装 langgraph: pip install langgraph")
    except Exception as e:
        print(f"[ERROR] 测试失败：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_workflow())
