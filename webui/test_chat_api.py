#!/usr/bin/env python3
"""
聊天持久化 API 测试脚本

测试聊天会话和消息的 CRUD 操作
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import init_database, get_db_session, get_database_manager
from src.db import crud


async def test_chat_persistence():
    """测试聊天持久化功能"""
    
    print("=" * 60)
    print("聊天持久化 API 测试")
    print("=" * 60)
    
    # 初始化数据库
    print("\n1. 初始化数据库...")
    await init_database()
    print("✓ 数据库初始化完成")
    
    # 获取数据库会话
    print("\n2. 创建测试会话...")
    db_manager = get_database_manager()
    async with db_manager.async_session_maker() as db:
        # 测试 1: 创建消息
        print("\n3. 测试创建消息...")
        session_id = "test_session_001"
        
        message1 = await crud.create_chat_message(
            db,
            session_id=session_id,
            role="user",
            content="你好，这是一个测试消息！"
        )
        print(f"✓ 创建用户消息：ID={message1.id}")
        
        message2 = await crud.create_chat_message(
            db,
            session_id=session_id,
            role="assistant",
            content="收到！这是 AI 的回复消息。"
        )
        print(f"✓ 创建 AI 消息：ID={message2.id}")
        
        message3 = await crud.create_chat_message(
            db,
            session_id=session_id,
            role="user",
            content="能帮我写个 Python 函数吗？"
        )
        print(f"✓ 创建用户消息：ID={message3.id}")
        
        # 测试 2: 获取会话列表
        print("\n4. 测试获取会话列表...")
        sessions = await crud.get_chat_sessions(db, limit=10, offset=0)
        print(f"✓ 会话列表：共 {len(sessions)} 个会话")
        for s in sessions:
            print(f"  - {s['session_id']}: {s['message_count']} 条消息")
        
        # 测试 3: 获取消息历史
        print("\n5. 测试获取消息历史...")
        messages = await crud.get_chat_messages_by_session(
            db,
            session_id=session_id,
            limit=10,
            offset=0
        )
        print(f"✓ 消息历史：共 {len(messages)} 条消息")
        for msg in messages:
            print(f"  [{msg.role}] {msg.content[:50]}...")
        
        # 测试 4: 获取聊天统计
        print("\n6. 测试获取聊天统计...")
        stats = await crud.get_chat_stats(db)
        print(f"✓ 聊天统计:")
        print(f"  - 总会话数：{stats['total_sessions']}")
        print(f"  - 总消息数：{stats['total_messages']}")
        print(f"  - 按角色统计：{stats['messages_by_role']}")
        
        # 测试 5: 分页加载
        print("\n7. 测试分页加载...")
        messages_page1 = await crud.get_chat_messages_by_session(
            db,
            session_id=session_id,
            limit=2,
            offset=0
        )
        messages_page2 = await crud.get_chat_messages_by_session(
            db,
            session_id=session_id,
            limit=2,
            offset=2
        )
        print(f"✓ 第 1 页：{len(messages_page1)} 条消息")
        print(f"✓ 第 2 页：{len(messages_page2)} 条消息")
        
        # 测试 6: 删除会话
        print("\n8. 测试删除会话...")
        deleted = await crud.delete_chat_session(db, session_id)
        print(f"✓ 删除会话：{'成功' if deleted else '失败'}")
        
        # 验证删除
        sessions_after = await crud.get_chat_sessions(db, limit=10, offset=0)
        test_session_exists = any(s['session_id'] == session_id for s in sessions_after)
        print(f"✓ 验证删除：{'会话仍存在' if test_session_exists else '会话已删除'}")
        
    
    print("\n" + "=" * 60)
    print("所有测试完成！✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_chat_persistence())
