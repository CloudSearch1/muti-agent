"""
DocWriter Agent 测试脚本

测试真实的 LLM 文档生成功能
"""

import asyncio
import logging

from src.agents.doc_writer import DocWriterAgent
from src.core.models import Task

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_doc_writer_agent():
    """测试 DocWriter Agent"""
    print("=" * 60)
    print("  DocWriter Agent 测试")
    print("=" * 60)
    
    # 创建 DocWriter Agent
    doc_writer = DocWriterAgent(
        doc_format="markdown",
    )
    
    # 检查 LLM 是否可用
    if not doc_writer.llm_helper.is_available():
        print("\n⚠️  LLM 未配置，将使用模拟模式")
        print("提示：设置 OPENAI_API_KEY 以启用真实功能")
    
    # 创建测试任务 1：生成 README
    task1 = Task(
        id="doc-001",
        title="生成项目 README",
        description="为 Python 项目生成 README 文档",
        input_data={
            "content_type": "readme",
            "source_material": {
                "project_name": "IntelliTeam",
                "description": "智能研发协作平台",
                "features": [
                    "多 Agent 协作",
                    "任务管理",
                    "代码生成",
                    "测试自动化",
                ],
                "installation": "pip install intelliteam",
                "usage": "from intelliteam import Agent",
            },
            "target_audience": "developers",
        },
    )
    
    print(f"\n📝 任务 1: {task1.title}")
    print("开始生成 README...\n")
    
    try:
        result1 = await doc_writer.execute(task1)
        
        print("\n✅ README 生成完成！")
        print(f"📊 状态：{result1['status']}")
        print(f"📄 字数：{result1['word_count']}")
        
        # 显示文档预览
        if result1.get('document'):
            doc = result1['document']
            print("\n" + "=" * 60)
            print("  README 预览（前 500 字）")
            print("=" * 60)
            content = doc.get('content', '')
            print(content[:500])
            if len(content) > 500:
                print(f"\n... 还有 {len(content) - 500} 字")
        
        # 测试任务 2：生成 API 文档
        print("\n" + "=" * 60)
        print("  测试 API 文档生成功能")
        print("=" * 60)
        
        code_files = [
            {
                "filename": "calculator.py",
                "content": """
class Calculator:
    \"\"\"简单的计算器类\"\"\"
    
    def add(self, a: float, b: float) -> float:
        \"\"\"加法运算\"\"\"
        return a + b
    
    def subtract(self, a: float, b: float) -> float:
        \"\"\"减法运算\"\"\"
        return a - b
    
    def divide(self, a: float, b: float) -> float:
        \"\"\"除法运算\"\"\"
        if b == 0:
            raise ValueError("除数不能为零")
        return a / b
""",
            }
        ]
        
        api_doc = await doc_writer.generate_api_doc(code_files)
        
        print(f"\n✅ API 文档生成完成！")
        print(f"📊 接口数：{len(api_doc.get('endpoints', []))}")
        print(f"📊 模型数：{len(api_doc.get('models', []))}")
        
        # 显示 API 文档预览
        content = api_doc.get('content', '')
        print("\nAPI 文档预览:")
        print("-" * 60)
        lines = content.split('\n')
        for i, line in enumerate(lines[:20]):
            print(line)
        if len(lines) > 20:
            print(f"... 还有 {len(lines) - 20} 行")
        
        # 测试任务 3：知识库更新
        print("\n" + "=" * 60)
        print("  测试知识库更新功能")
        print("=" * 60)
        
        kb_result = await doc_writer.update_knowledge_base(
            topic="Python 异步编程",
            content="""
Python 异步编程使用 async/await 语法。
async def 定义协程函数。
await 用于等待异步操作完成。
asyncio 是 Python 的异步编程库。
事件循环是异步编程的核心。
            """,
            tags=["python", "async", "programming"],
        )
        
        print(f"\n✅ 知识库更新完成！")
        print(f"📝 主题：{kb_result['topic']}")
        print(f"📝 摘要：{kb_result.get('summary', '')[:100]}...")
        print(f"🏷️  关键词：{kb_result.get('keywords', [])}")
        print(f"🏷️  标签：{kb_result.get('tags', [])}")
        
        # 测试任务 4：文档审查
        print("\n" + "=" * 60)
        print("  测试文档审查功能")
        print("=" * 60)
        
        sample_doc = {
            "title": "快速开始指南",
            "content": """
# 快速开始

## 安装
pip install package

## 使用
import package
package.run()

## 说明
这个包很简单。
            """,
        }
        
        review = await doc_writer.review_document(sample_doc)
        
        print(f"\n✅ 文档审查完成！")
        print(f"📊 状态：{review['status']}")
        print(f"⭐ 质量评分：{review['quality_score']}/100")
        print(f"💪 优点：{len(review.get('strengths', []))} 个")
        print(f"📝 建议：{len(review.get('suggestions', []))} 个")
        
        if review.get('suggestions'):
            print("\n改进建议:")
            for i, sug in enumerate(review['suggestions'][:3], 1):
                print(f"  {i}. [{sug.get('severity', 'info')}] {sug.get('description', '')}")
        
        print("\n" + "=" * 60)
        print("  测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_doc_writer_agent())
