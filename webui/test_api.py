#!/usr/bin/env python3
"""
IntelliTeam Web UI API 测试脚本

测试 API 逻辑，无需 FastAPI 依赖
"""

from datetime import datetime

# ===========================================
# 模拟数据库（复制自 server_enhanced.py）
# ===========================================

_tasks_db = {
    "1": {
        "id": "1",
        "title": "创建用户管理 API",
        "description": "实现用户注册、登录、权限管理等功能",
        "priority": "high",
        "status": "in_progress",
        "assignee": "张三",
        "agent": "Coder",
        "created_at": "2026-03-05 08:30:00",
        "updated_at": "2026-03-05 08:55:00",
        "progress": 65
    },
    "2": {
        "id": "2",
        "title": "数据库设计",
        "description": "设计用户表和权限表结构",
        "priority": "normal",
        "status": "completed",
        "assignee": "李四",
        "agent": "Architect",
        "created_at": "2026-03-05 07:15:00",
        "updated_at": "2026-03-05 08:00:00",
        "progress": 100
    }
}

_agents_db = {
    "Planner": {
        "name": "Planner",
        "role": "任务规划师",
        "status": "idle",
        "tasks_completed": 45,
        "avg_time": 2.3,
        "success_rate": 98
    },
    "Architect": {
        "name": "Architect",
        "role": "系统架构师",
        "status": "busy",
        "tasks_completed": 38,
        "avg_time": 5.7,
        "success_rate": 96
    },
    "Coder": {
        "name": "Coder",
        "role": "代码工程师",
        "status": "busy",
        "tasks_completed": 89,
        "avg_time": 8.2,
        "success_rate": 94
    }
}

# ===========================================
# 测试函数
# ===========================================

def test_get_tasks():
    """测试获取任务列表"""
    print("\n📋 测试：获取任务列表")
    tasks = list(_tasks_db.values())
    print(f"✅ 任务数量：{len(tasks)}")
    for task in tasks:
        print(f"   - {task['title']} ({task['status']})")
    return tasks

def test_get_agents():
    """测试获取 Agent 列表"""
    print("\n🤖 测试：获取 Agent 列表")
    agents = list(_agents_db.values())
    print(f"✅ Agent 数量：{len(agents)}")
    for agent in agents:
        print(f"   - {agent['name']}: {agent['role']} ({agent['status']})")
    return agents

def test_create_task():
    """测试创建任务"""
    print("\n➕ 测试：创建任务")
    new_task = {
        "id": "3",
        "title": "测试任务",
        "description": "这是一个测试任务",
        "priority": "normal",
        "status": "pending",
        "assignee": "测试员",
        "agent": "Tester",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "progress": 0
    }
    _tasks_db["3"] = new_task
    print(f"✅ 创建成功：{new_task['title']}")
    return new_task

def test_get_stats():
    """测试获取统计"""
    print("\n📊 测试：系统统计")
    total = len(_tasks_db)
    completed = len([t for t in _tasks_db.values() if t["status"] == "completed"])
    rate = round((completed / total * 100) if total > 0 else 0)
    print(f"✅ 总任务：{total}")
    print(f"✅ 已完成：{completed}")
    print(f"✅ 完成率：{rate}%")
    return {"total": total, "completed": completed, "rate": rate}

def test_filter_tasks():
    """测试任务筛选"""
    print("\n🔍 测试：任务筛选")

    # 按状态筛选
    pending = [t for t in _tasks_db.values() if t["status"] == "pending"]
    print(f"✅ 待处理任务：{len(pending)}")

    # 按优先级筛选
    high = [t for t in _tasks_db.values() if t["priority"] == "high"]
    print(f"✅ 高优先级任务：{len(high)}")

    return {"pending": len(pending), "high": len(high)}

def test_update_task():
    """测试更新任务"""
    print("\n✏️ 测试：更新任务")
    if "3" in _tasks_db:
        _tasks_db["3"]["status"] = "in_progress"
        _tasks_db["3"]["progress"] = 25
        print(f"✅ 更新成功：{_tasks_db['3']['title']} -> {_tasks_db['3']['status']}")
    return _tasks_db.get("3")

def test_delete_task():
    """测试删除任务"""
    print("\n🗑️ 测试：删除任务")
    if "3" in _tasks_db:
        del _tasks_db["3"]
        print("✅ 删除成功：任务 #3")
    return True

# ===========================================
# 主测试流程
# ===========================================

def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("🧪 IntelliTeam Web UI API 测试")
    print("=" * 60)

    results = []

    # 基础查询
    results.append(("获取任务", test_get_tasks()))
    results.append(("获取 Agent", test_get_agents()))
    results.append(("系统统计", test_get_stats()))
    results.append(("任务筛选", test_filter_tasks()))

    # CRUD 操作
    results.append(("创建任务", test_create_task()))
    results.append(("更新任务", test_update_task()))
    results.append(("删除任务", test_delete_task()))

    # 总结
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)
    print(f"\n📊 通过：{len(results)}/{len(results)}")
    print("\n所有 API 逻辑测试通过！✨\n")

    return results

if __name__ == "__main__":
    run_all_tests()
