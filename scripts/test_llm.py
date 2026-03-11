"""
测试阿里云 CodePlan API 连接

使用方法:
    python scripts/test_llm.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_llm_connection():
    """测试 LLM 连接"""
    print("[TEST] 测试阿里云 CodePlan API 连接...\n")
    
    try:
        from src.llm import get_llm_service
        
        # 获取 LLM 服务
        llm = get_llm_service()
        
        # 检查配置
        if not llm.is_configured():
            print("❌ LLM 未配置！请检查 .env 文件")
            return False
        
        print("[OK] LLM 已配置")
        print(f"   提供商：{llm.provider.NAME if llm.provider else 'unknown'}")
        print(f"   模型：{llm.provider.model if hasattr(llm.provider, 'model') else 'N/A'}")
        print(f"   API Base: {llm.provider.base_url if hasattr(llm.provider, 'base_url') else 'N/A'}")
        print()
        
        # 测试生成
        print("📝 发送测试请求...")
        print("   Prompt: '用一句话介绍你自己'\n")
        
        response = await llm.generate(
            prompt="用一句话介绍你自己",
            system_prompt="你是一个有帮助的 AI 助手。",
            temperature=0.3,
            max_tokens=100,
        )
        
        print("[OK] 响应成功！")
        print(f"   模型：{response.model}")
        print(f"   内容：{response.content}")
        print(f"   Token 使用：{response.usage}")
        print()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 测试失败：{str(e)}")
        print()
        print("可能的问题:")
        print("  1. API Key 无效或已过期")
        print("  2. 网络连接问题")
        print("  3. .env 文件配置错误")
        print()
        print("建议:")
        print("  - 检查 .env 文件中的 OPENAI_API_KEY 是否正确")
        print("  - 检查网络连接")
        print("  - 访问 https://dashscope.aliyuncs.com 验证 API 状态")
        return False


async def test_workflow():
    """测试简单工作流"""
    print("\n[TEST] 测试 LangGraph 工作流...\n")
    
    try:
        from src.graph import create_workflow
        
        workflow = create_workflow()
        
        print("[OK] 工作流创建成功")
        print(f"   工作流 ID: {workflow.workflow_id}")
        print(f"   Agent 数量：5 (Planner, Architect, Coder, Tester, DocWriter)")
        print()
        
        # 编译工作流
        print("⚙️  编译工作流...")
        workflow.compile()
        print("[OK] 工作流编译成功")
        print()
        
        return True
        
    except ImportError as e:
        print(f"⚠️  LangGraph 未安装：{str(e)}")
        print("   运行：pip install langgraph")
        return False
    except Exception as e:
        print(f"[ERROR] 工作流测试失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("=" * 60)
    print("IntelliTeam - API 连接测试")
    print("=" * 60)
    print()
    
    # 测试 LLM 连接
    llm_ok = await test_llm_connection()
    
    # 测试工作流
    workflow_ok = await test_workflow() if llm_ok else False
    
    # 总结
    print()
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"  LLM 连接：{'[PASS]' if llm_ok else '[FAIL]'}")
    print(f"  工作流：  {'[PASS]' if workflow_ok else '[SKIP]'}")
    print()
    
    if llm_ok:
        print("[SUCCESS] 配置成功！可以开始使用 IntelliTeam 了！")
        print()
        print("下一步:")
        print("  1. 运行 API 服务：python -m src.main")
        print("  2. 访问文档：http://localhost:8000/docs")
        print("  3. 创建工作流：使用 /api/v1/tasks 端点")
    else:
        print("⚠️  请先解决配置问题")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())
