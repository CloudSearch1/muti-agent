"""
Tester Agent 测试脚本

测试真实的 LLM 测试生成功能
"""

import asyncio
import logging

from src.agents.tester import TesterAgent
from src.core.models import Task

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_tester_agent():
    """测试 Tester Agent"""
    print("=" * 60)
    print("  Tester Agent 测试")
    print("=" * 60)
    
    # 创建 Tester Agent
    tester = TesterAgent(
        testing_framework="pytest",
        coverage_target=80,
    )
    
    # 检查 LLM 是否可用
    if not tester.llm_helper.is_available():
        print("\n⚠️  LLM 未配置，将使用模拟模式")
        print("提示：设置 OPENAI_API_KEY 以启用真实功能")
    
    # 创建测试任务
    task = Task(
        id="test-001",
        title="为计算器模块编写测试",
        description="为计算器功能编写完整的单元测试",
        input_data={
            "code_files": [
                {
                    "filename": "calculator.py",
                    "content": """
class Calculator:
    def add(self, a, b):
        return a + b
    
    def subtract(self, a, b):
        return a - b
    
    def multiply(self, a, b):
        return a * b
    
    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
""",
                }
            ],
            "requirements": [
                "测试所有四则运算",
                "测试除零异常",
                "测试边界情况",
            ],
        },
    )
    
    print(f"\n📝 任务：{task.title}")
    print(f"📋 描述：{task.description}")
    print("\n开始执行...\n")
    
    # 执行任务
    try:
        result = await tester.execute(task)
        
        print("\n✅ 任务执行完成！")
        print(f"📊 状态：{result['status']}")
        print(f"📁 创建测试数：{result['test_cases_created']}")
        print(f"✅ 通过数：{result['passed']}")
        print(f"❌ 失败数：{result['failed']}")
        print(f"📈 覆盖率：{result['coverage']:.1f}%")
        
        # 显示测试报告
        if result.get('report'):
            report = result['report']
            print("\n" + "=" * 60)
            print("  测试报告")
            print("=" * 60)
            print(f"📊 总计：{report['summary']['total_tests']} 个测试")
            print(f"✅ 通过：{report['summary']['passed']}")
            print(f"❌ 失败：{report['summary']['failed']}")
            print(f"📈 通过率：{report['summary']['pass_rate']}")
            print(f"📊 覆盖率：{report['summary']['code_coverage']}")
            print(f"🏁 状态：{report['status']}")
        
        # 测试回归测试生成
        print("\n" + "=" * 60)
        print("  测试回归测试生成功能")
        print("=" * 60)
        
        bug_report = {
            "title": "除零时未抛出异常",
            "description": "当除数为 0 时，应该抛出 ValueError 但返回了 inf",
            "steps_to_reproduce": [
                "创建 Calculator 实例",
                "调用 divide(10, 0)",
                "观察返回值为 inf 而不是抛出异常",
            ],
            "expected_behavior": "抛出 ValueError 异常",
            "actual_behavior": "返回 inf",
            "severity": "high",
        }
        
        regression_tests = await tester.generate_regression_tests(bug_report)
        print(f"\n📝 生成回归测试数：{len(regression_tests)}")
        
        for i, test in enumerate(regression_tests[:2], 1):
            print(f"\n📄 回归测试 {i}:")
            print(f"  名称：{test['name']}")
            print(f"  描述：{test['description']}")
            print(f"  优先级：{test['priority']}")
            print(f"  代码预览:")
            lines = test['code'].split('\n')
            for j, line in enumerate(lines[:10]):
                print(f"    {line}")
            if len(lines) > 10:
                print(f"    ... 还有 {len(lines) - 10} 行")
        
        print("\n" + "=" * 60)
        print("  测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_tester_agent())
