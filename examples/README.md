# 示例代码 - IntelliTeam 使用示例

本目录包含 IntelliTeam 平台的使用示例。

---

## 📋 示例列表

### 1. 基础示例

#### 1.1 简单任务执行
```python
"""
示例：执行一个简单的编程任务
"""
import asyncio
from src.graph import create_workflow

async def main():
    # 创建工作流
    workflow = create_workflow()
    
    # 执行任务
    result = await workflow.run(
        task_id="example-001",
        task_title="创建 Hello World 函数",
        task_description="创建一个 Python 函数，输出 Hello World",
    )
    
    # 查看结果
    print(f"任务完成：{result.current_step}")
    print(f"Agent 结果：{result.agent_results}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### 1.2 多任务并行
```python
"""
示例：并行执行多个任务
"""
import asyncio
from src.graph import create_workflow

async def run_task(workflow, task_id, title, description):
    """运行单个任务"""
    return await workflow.run(
        task_id=task_id,
        task_title=title,
        task_description=description,
    )

async def main():
    # 创建多个工作流实例
    workflows = [create_workflow() for _ in range(3)]
    
    # 并行执行任务
    tasks = [
        run_task(workflows[0], "task-1", "任务 1", "描述 1"),
        run_task(workflows[1], "task-2", "任务 2", "描述 2"),
        run_task(workflows[2], "task-3", "任务 3", "描述 3"),
    ]
    
    # 等待所有任务完成
    results = await asyncio.gather(*tasks)
    
    # 查看结果
    for i, result in enumerate(results):
        print(f"任务{i+1}完成：{result.current_step}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 2. Agent 示例

#### 2.1 使用 Planner Agent
```python
"""
示例：使用 Planner Agent 分解任务
"""
import asyncio
from src.agents.planner import PlannerAgent
from src.core.models import Task

async def main():
    # 创建 Planner Agent
    planner = PlannerAgent()
    
    # 创建任务
    task = Task(
        title="开发用户管理系统",
        description="创建一个完整的用户管理系统，包括注册、登录、权限管理",
        input_data={
            "goal": "开发用户管理系统",
            "context": {},
        },
    )
    
    # 执行任务
    result = await planner.process_task(task)
    
    # 查看分解结果
    print(f"子任务数量：{result.output_data.get('subtasks_created')}")
    for subtask in result.output_data.get('subtasks', []):
        print(f"  - {subtask['title']}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### 2.2 使用 Coder Agent
```python
"""
示例：使用 Coder Agent 生成代码
"""
import asyncio
from src.agents.coder import CoderAgent
from src.core.models import Task

async def main():
    # 创建 Coder Agent
    coder = CoderAgent()
    
    # 创建任务
    task = Task(
        title="实现快速排序算法",
        description="用 Python 实现快速排序算法，包含注释和测试",
        input_data={
            "requirements": "实现快速排序",
            "architecture": {},
        },
    )
    
    # 执行任务
    result = await coder.process_task(task)
    
    # 查看生成的代码
    for file in result.output_data.get('code_files', []):
        print(f"文件：{file['filename']}")
        print(f"代码：\n{file['content']}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 3. 工具示例

#### 3.1 使用文件工具
```python
"""
示例：使用 FileTools 操作文件
"""
import asyncio
from src.tools.file_tools import FileTools

async def main():
    # 创建文件工具
    file_tools = FileTools(root_dir=".")
    
    # 创建文件
    result = await file_tools.execute(
        action="write",
        path="test.txt",
        content="Hello, IntelliTeam!",
    )
    print(f"创建文件：{result.data}")
    
    # 读取文件
    result = await file_tools.execute(
        action="read",
        path="test.txt",
    )
    print(f"文件内容：{result.data['content']}")
    
    # 列出目录
    result = await file_tools.execute(
        action="list",
        path=".",
    )
    print(f"目录内容：{result.data['count']} 个文件")

if __name__ == "__main__":
    asyncio.run(main())
```

#### 3.2 使用搜索工具
```python
"""
示例：使用 SearchTools 搜索代码
"""
import asyncio
from src.tools.search_tools import SearchTools

async def main():
    # 创建搜索工具
    search_tools = SearchTools(root_dir=".")
    
    # 搜索文件内容
    result = await search_tools.execute(
        action="content",
        query="async def",
        pattern="*.py",
    )
    print(f"找到 {result.data['total_files']} 个文件包含 'async def'")
    
    # 搜索文件名
    result = await search_tools.execute(
        action="filename",
        query="agent",
    )
    print(f"找到 {result.data['count']} 个文件包含 'agent'")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 4. API 示例

#### 4.1 调用 REST API
```python
"""
示例：使用 HTTP 调用 IntelliTeam API
"""
import httpx
import asyncio

async def main():
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # 健康检查
        response = await client.get(f"{base_url}/health")
        print(f"服务状态：{response.json()}")
        
        # 创建任务
        response = await client.post(
            f"{base_url}/api/v1/tasks/",
            json={
                "title": "API 测试任务",
                "description": "通过 API 创建的任务",
                "priority": "normal",
            },
        )
        print(f"创建任务：{response.json()}")
        
        # 获取任务列表
        response = await client.get(f"{base_url}/api/v1/tasks/")
        print(f"任务列表：{response.json()}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 5. 高级示例

#### 5.1 自定义工作流
```python
"""
示例：创建自定义工作流
"""
import asyncio
from src.graph.states import AgentState
from langgraph.graph import StateGraph, END

async def custom_node_1(state: dict) -> dict:
    """自定义节点 1"""
    print("执行节点 1")
    state["step1_done"] = True
    return state

async def custom_node_2(state: dict) -> dict:
    """自定义节点 2"""
    print("执行节点 2")
    state["step2_done"] = True
    return state

def should_continue(state: dict) -> str:
    """条件判断"""
    if state.get("step2_done"):
        return "end"
    return "node2"

async def main():
    # 创建工作流图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("node1", custom_node_1)
    workflow.add_node("node2", custom_node_2)
    
    # 添加边
    workflow.add_edge("node1", "node2")
    workflow.add_conditional_edges(
        "node2",
        should_continue,
        {"end": END, "node2": "node2"},
    )
    
    # 设置入口
    workflow.set_entry_point("node1")
    
    # 编译
    app = workflow.compile()
    
    # 运行
    result = await app.ainvoke({
        "task_id": "custom-001",
        "task_title": "自定义工作流",
    })
    
    print(f"工作流完成：{result}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### 5.2 Agent 协作
```python
"""
示例：多个 Agent 协作完成任务
"""
import asyncio
from src.agents.planner import PlannerAgent
from src.agents.architect import ArchitectAgent
from src.agents.coder import CoderAgent
from src.core.models import Task

async def main():
    # 创建 Agent 团队
    planner = PlannerAgent()
    architect = ArchitectAgent()
    coder = CoderAgent()
    
    # 任务 1: 规划
    planning_task = Task(
        title="开发 Web 应用",
        input_data={"goal": "开发 Web 应用"},
    )
    planning_result = await planner.process_task(planning_task)
    print(f"规划完成：{planning_result.output_data.get('subtasks_created')} 个子任务")
    
    # 任务 2: 架构设计
    architecture_task = Task(
        title="架构设计",
        input_data={
            "requirements": "Web 应用需求",
            "plan": planning_result.output_data,
        },
    )
    architecture_result = await architect.process_task(architecture_task)
    print(f"架构设计完成")
    
    # 任务 3: 代码实现
    coding_task = Task(
        title="代码实现",
        input_data={
            "requirements": "Web 应用需求",
            "architecture": architecture_result.output_data,
        },
    )
    coding_result = await coder.process_task(coding_task)
    print(f"代码实现完成：{coding_result.output_data.get('files_created')} 个文件")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🚀 运行示例

```bash
# 运行基础示例
python examples/01_basic_task.py

# 运行 Agent 示例
python examples/02_agent_usage.py

# 运行工具示例
python examples/03_tools_usage.py

# 运行 API 示例
python examples/04_api_usage.py

# 运行高级示例
python examples/05_advanced.py
```

---

## 📝 说明

1. 确保已安装所有依赖：`pip install -r requirements.txt`
2. 确保 API 服务已启动：`python start.py`
3. 根据示例需求配置 `.env` 文件
4. 运行示例前请阅读示例代码注释

---

*更多示例请访问：https://github.com/CloudSearch1/muti-agent/tree/main/examples*
