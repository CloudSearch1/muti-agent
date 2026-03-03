"""
简单测试 LLM 连接 (无 emoji 版本)
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    print("=" * 60)
    print("IntelliTeam - LLM Connection Test")
    print("=" * 60)
    print()
    
    try:
        from src.llm import get_llm_service
        
        llm = get_llm_service()
        
        if not llm.is_configured():
            print("[FAIL] LLM not configured")
            return
        
        print("[OK] LLM configured")
        print(f"  Provider: {llm.provider.NAME}")
        print(f"  Model: {llm.provider.model}")
        print(f"  API Base: {llm.provider.base_url}")
        print()
        
        # Test generation
        print("Sending test request...")
        response = await llm.generate(
            prompt="Hello, please introduce yourself in one sentence.",
            temperature=0.3,
            max_tokens=100,
        )
        
        print(f"[OK] Response received")
        print(f"  Model: {response.model}")
        print(f"  Content: {response.content[:200]}")
        print()
        
        print("=" * 60)
        print("[SUCCESS] API connection test passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
