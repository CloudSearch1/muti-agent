"""
Architect Agent 测试脚本

测试真实的 LLM 架构设计和图表生成功能
"""

import asyncio
import logging

from src.agents.architect import ArchitectAgent
from src.core.models import Task

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_architect_agent():
    """测试 Architect Agent"""
    print("=" * 60)
    print("  Architect Agent 测试")
    print("=" * 60)
    
    # 创建 Architect Agent
    architect = ArchitectAgent(
        preferred_patterns=["MVC", "微服务"],
    )
    
    # 检查 LLM 是否可用
    if not architect.llm_helper.is_available():
        print("\n⚠️  LLM 未配置，将使用模拟模式")
        print("提示：设置 OPENAI_API_KEY 以启用真实功能")
    
    # 创建测试任务
    task = Task(
        id="arch-001",
        title="设计电商平台架构",
        description="为一个中型电商平台设计系统架构",
        input_data={
            "requirements": [
                "支持 10 万日活用户",
                "高并发订单处理",
                "实时库存管理",
                "多渠道销售（Web、App、小程序）",
                "数据分析和报表",
            ],
            "constraints": {
                "budget": "中等",
                "timeline": "3 个月",
                "team_size": "10 人",
                "tech_preference": "Python + React",
            },
        },
    )
    
    print(f"\n📝 任务：{task.title}")
    print("开始设计系统架构...\n")
    
    try:
        result = await architect.execute(task)
        
        print("\n✅ 架构设计完成！")
        print(f"📊 状态：{result['status']}")
        print(f"📋 设计决策数：{len(result['design_decisions'])}")
        
        # 显示架构文档
        if result.get('architecture'):
            arch = result['architecture']
            print("\n" + "=" * 60)
            print("  架构设计文档")
            print("=" * 60)
            print(f"🏗️  架构风格：{arch.get('overview', '未知')}")
            print(f"📦 组件数：{len(arch.get('components', []))}")
            
            print("\n组件列表:")
            for comp in arch.get('components', [])[:5]:
                print(f"  - {comp.get('name', 'Unknown')}: {comp.get('technology', '')}")
            
            # 显示图表
            diagrams = arch.get('diagrams', {})
            if diagrams.get('component_diagram'):
                print("\n" + "-" * 60)
                print("  组件图（Mermaid 格式）")
                print("-" * 60)
                comp_diagram = diagrams['component_diagram']
                lines = comp_diagram.split('\n')
                for i, line in enumerate(lines[:15]):
                    print(line)
                if len(lines) > 15:
                    print(f"... 还有 {len(lines) - 15} 行")
            
            if diagrams.get('sequence_diagram'):
                print("\n" + "-" * 60)
                print("  时序图（Mermaid 格式预览）")
                print("-" * 60)
                seq_diagram = diagrams['sequence_diagram']
                lines = seq_diagram.split('\n')
                for i, line in enumerate(lines[:10]):
                    print(line)
        
        # 测试架构评审
        print("\n" + "=" * 60)
        print("  测试架构评审功能")
        print("=" * 60)
        
        if result.get('architecture'):
            review = await architect.review_architecture(result['architecture'])
            
            print(f"\n✅ 架构评审完成！")
            print(f"📊 状态：{review['status']}")
            print(f"⭐ 总体评分：{review.get('overall_score', 0)}/100")
            print(f"💪 优点：{len(review.get('strengths', []))} 个")
            print(f"⚠️  关注点：{len(review.get('concerns', []))} 个")
            print(f"💡 建议：{len(review.get('suggestions', []))} 个")
            
            if review.get('concerns'):
                print("\n主要关注点:")
                for i, concern in enumerate(review['concerns'][:3], 1):
                    print(f"  {i}. [{concern.get('severity', 'info')}] {concern.get('description', '')}")
                    if concern.get('recommendation'):
                        print(f"     建议：{concern['recommendation']}")
            
            if review.get('summary'):
                print(f"\n📝 评审总结：{review['summary']}")
        
        print("\n" + "=" * 60)
        print("  测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_architect_agent())
