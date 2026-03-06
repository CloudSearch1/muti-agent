"""
Coder Agent 测试脚本

测试真实的 LLM 代码生成功能
"""

import asyncio
import logging

from src.agents.coder import CoderAgent
from src.core.models import Task

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_coder_agent():
    """测试 Coder Agent"""
    print("=" * 60)
    print("  Coder Agent 测试")
    print("=" * 60)
    
    # 创建 Coder Agent
    coder = CoderAgent(
        preferred_language="python",
        code_style="pep8",
    )
    
    # 检查 LLM 是否可用
    if not coder.llm_helper.is_available():
        print("\n⚠️  LLM 未配置，将使用模拟模式")
        print("提示：设置 OPENAI_API_KEY 或其他 LLM API Key 以启用真实功能")
    
    # 创建测试任务
    task = Task(
        id="test-001",
        title="创建用户管理模块",
        description="实现用户注册、登录、权限管理功能",
        input_data={
            "requirements": """
创建一个用户管理模块，需要包含以下功能：
1. 用户注册（用户名、邮箱、密码）
2. 用户登录（验证用户名和密码）
3. 密码加密（使用 bcrypt）
4. 权限管理（管理员、普通用户）
5. 数据验证（邮箱格式、密码强度）
""",
            "architecture": {
                "pattern": "MVC",
                "database": "SQLite",
            },
        },
    )
    
    print(f"\n📝 任务：{task.title}")
    print(f"📋 描述：{task.description}")
    print("\n开始执行...\n")
    
    # 执行任务
    try:
        result = await coder.execute(task)
        
        print("\n✅ 任务执行完成！")
        print(f"📊 状态：{result['status']}")
        print(f"📁 生成文件数：{result['files_created']}")
        print(f"📝 实现说明：{result['implementation_notes'][:200]}...")
        
        # 显示生成的代码
        if result.get('code_files'):
            print("\n" + "=" * 60)
            print("  生成的代码文件")
            print("=" * 60)
            
            for file_info in result['code_files']:
                print(f"\n📄 文件：{file_info['filename']}")
                print("-" * 60)
                # 显示前 20 行
                lines = file_info['content'].split('\n')
                for i, line in enumerate(lines[:20]):
                    print(f"{i+1:3d} | {line}")
                if len(lines) > 20:
                    print(f"... 还有 {len(lines) - 20} 行")
        
        # 测试代码审查
        print("\n" + "=" * 60)
        print("  测试代码审查功能")
        print("=" * 60)
        
        sample_code = """
def calculate_sum(numbers):
    total = 0
    for n in numbers:
        total += n
    return total
"""
        review_result = await coder.review_code(sample_code)
        print(f"\n📊 审查状态：{review_result['status']}")
        print(f"⭐ 质量评分：{review_result['quality_score']}/100")
        print(f"❗ 发现问题：{len(review_result.get('issues', []))}")
        print(f"💡 建议数量：{len(review_result.get('suggestions', []))}")
        
        if review_result.get('issues'):
            print("\n问题列表:")
            for issue in review_result['issues'][:3]:
                print(f"  - [{issue.get('severity', 'unknown')}] {issue.get('message', '')}")
        
        # 测试代码重构
        print("\n" + "=" * 60)
        print("  测试代码重构功能")
        print("=" * 60)
        
        refactor_result = await coder.refactor_code(sample_code)
        print(f"\n📊 重构状态：{refactor_result['status']}")
        print(f"📝 修改数量：{len(refactor_result.get('changes', []))}")
        print(f"📋 重构总结：{refactor_result.get('summary', '')[:100]}")
        
        if refactor_result.get('refactored_code'):
            print("\n重构后的代码:")
            print("-" * 60)
            lines = refactor_result['refactored_code'].split('\n')
            for i, line in enumerate(lines[:15]):
                print(f"{i+1:3d} | {line}")
        
        print("\n" + "=" * 60)
        print("  测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_coder_agent())
