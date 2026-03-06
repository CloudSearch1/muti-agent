"""
PlannerAgent - 规划师 Agent

职责：任务分解、优先级排序、资源调度
"""

from datetime import datetime
from typing import Any

import structlog

from ..core.models import (
    AgentRole,
    MessageType,
    Task,
    TaskPriority,
)
from .base import BaseAgent
from .llm_helper import get_planner_llm

logger = structlog.get_logger(__name__)


class PlannerAgent(BaseAgent):
    """
    任务规划师

    负责：
    - 接收高层目标，分解为可执行任务
    - 评估任务优先级和依赖关系
    - 分配任务给合适的 Agent
    - 监控整体进度并调整计划
    """

    ROLE = AgentRole.PLANNER

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 规划师特有配置
        self.max_subtasks = kwargs.get("max_subtasks", 20)
        self.planning_model = kwargs.get("planning_model", "gpt-4")

        # LLM 辅助
        self.llm_helper = get_planner_llm()

        self.logger.info("PlannerAgent initialized")

    async def execute(self, task: Task) -> dict[str, Any]:
        """
        执行规划任务

        将复杂目标分解为可执行的子任务
        """
        self.logger.info(
            "Starting planning",
            task_id=task.id,
            task_title=task.title,
        )

        # 获取任务输入
        goal = task.input_data.get("goal", "")
        context = task.input_data.get("context", {})
        constraints = task.input_data.get("constraints", [])

        # 思考分解策略
        thinking_result = await self.think(
            {
                "goal": goal,
                "context": context,
                "constraints": constraints,
            }
        )

        # 生成子任务
        subtasks = thinking_result.get("subtasks", [])

        # 验证子任务数量
        if len(subtasks) > self.max_subtasks:
            self.logger.warning(
                "Generated subtasks exceed limit",
                generated=len(subtasks),
                limit=self.max_subtasks,
            )
            subtasks = subtasks[: self.max_subtasks]

        # 创建任务对象
        created_tasks = []
        for i, subtask in enumerate(subtasks):
            sub_task = Task(
                title=subtask.get("title", f"Subtask {i+1}"),
                description=subtask.get("description", ""),
                priority=subtask.get("priority", TaskPriority.NORMAL),
                input_data=subtask.get("input_data", {}),
                dependencies=subtask.get("dependencies", []),
                tags=["planned", task.id],
                metadata={"parent_task": task.id, "step": i},
            )
            created_tasks.append(sub_task.to_dict())

            # 发送到黑板
            self.post_message(
                subject=f"New task created: {sub_task.title}",
                content=sub_task.to_dict(),
                message_type=MessageType.TASK,
                priority=sub_task.priority.value,
                task_id=sub_task.id,
            )

        # 更新黑板上的任务计划
        self.put_to_blackboard(
            f"plan:{task.id}",
            {
                "goal": goal,
                "subtasks": created_tasks,
                "created_at": datetime.now().isoformat(),
                "model": self.planning_model,
            },
        )

        return {
            "status": "planning_complete",
            "goal": goal,
            "subtasks_created": len(created_tasks),
            "subtasks": created_tasks,
            "planning_model": self.planning_model,
        }

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        思考任务分解策略

        使用 LLM 进行任务分析和分解
        """
        goal = context.get("goal", "")
        constraints = context.get("constraints", [])

        # 尝试使用 LLM 进行规划
        if self.llm_helper.is_available():
            try:
                result = await self._llm_plan(goal, constraints)
                if result:
                    return result
            except Exception as e:
                self.logger.warning("LLM planning failed, using fallback", error=str(e))

        # Fallback: 使用模拟规划
        subtasks = self._simulate_planning(goal, constraints)

        return {
            "subtasks": subtasks,
            "reasoning": "基于目标复杂度和依赖关系进行分解 (fallback)",
        }

    async def _llm_plan(self, goal: str, constraints: list[str]) -> dict[str, Any] | None:
        """使用 LLM 进行任务规划"""
        prompt = f"""你是一个专业的任务规划师。请将以下目标分解为可执行的子任务。

## 目标
{goal}

## 约束条件
{chr(10).join(f"- {c}" for c in constraints) if constraints else "无特殊约束"}

## 要求
1. 每个子任务应该是独立可执行的
2. 明确任务之间的依赖关系（使用数组索引表示依赖，如 [0] 表示依赖第一个任务）
3. 为每个任务分配合理的优先级 (low/normal/high/critical)
4. 指定每个任务需要的 Agent 角色 (analyst/architect/coder/tester/doc_writer)

## 输出格式 (JSON)
{{
    "reasoning": "规划思路说明",
    "subtasks": [
        {{
            "title": "任务标题",
            "description": "任务描述",
            "priority": "normal",
            "assigned_role": "coder",
            "dependencies": [],
            "input_data": {{}}
        }}
    ]
}}"""

        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一个专业的任务规划师。请以 JSON 格式输出任务分解结果。",
        )

        if result and "subtasks" in result:
            return result

        return None

    def _simulate_planning(
        self,
        goal: str,
        constraints: list[str],
    ) -> list[dict[str, Any]]:
        """
        模拟规划结果（LLM 不可用时的备用方案）
        """
        # 简单示例：根据目标关键词生成任务
        subtasks = []

        goal_lower = goal.lower()

        if "api" in goal_lower or "接口" in goal_lower:
            subtasks.extend(
                [
                    {
                        "title": "分析 API 需求",
                        "description": "理解 API 的功能需求和技术要求",
                        "priority": "high",
                        "assigned_role": "analyst",
                        "dependencies": [],
                        "input_data": {"goal": goal},
                    },
                    {
                        "title": "设计 API 架构",
                        "description": "设计 API 的端点、数据模型和认证机制",
                        "priority": "high",
                        "assigned_role": "architect",
                        "dependencies": ["task_0"],
                        "input_data": {"goal": goal},
                    },
                    {
                        "title": "实现 API 代码",
                        "description": "编写 API 的实现代码",
                        "priority": "normal",
                        "assigned_role": "coder",
                        "dependencies": ["task_1"],
                        "input_data": {"goal": goal},
                    },
                    {
                        "title": "编写 API 测试",
                        "description": "创建单元测试和集成测试",
                        "priority": "normal",
                        "assigned_role": "tester",
                        "dependencies": ["task_2"],
                        "input_data": {"goal": goal},
                    },
                    {
                        "title": "编写 API 文档",
                        "description": "生成 API 使用文档",
                        "priority": "low",
                        "assigned_role": "doc_writer",
                        "dependencies": ["task_2"],
                        "input_data": {"goal": goal},
                    },
                ]
            )
        else:
            # 通用任务分解
            subtasks = [
                {
                    "title": "需求分析",
                    "description": f"分析目标：{goal}",
                    "priority": "high",
                    "assigned_role": "analyst",
                    "dependencies": [],
                    "input_data": {"goal": goal},
                },
                {
                    "title": "方案设计",
                    "description": "设计实现方案",
                    "priority": "high",
                    "assigned_role": "architect",
                    "dependencies": ["task_0"],
                    "input_data": {"goal": goal},
                },
                {
                    "title": "编码实现",
                    "description": "实现功能代码",
                    "priority": "normal",
                    "assigned_role": "coder",
                    "dependencies": ["task_1"],
                    "input_data": {"goal": goal},
                },
            ]

        return subtasks

    def prioritize_tasks(
        self,
        tasks: list[Task],
        criteria: str = "urgency",
    ) -> list[Task]:
        """
        对任务进行优先级排序

        Args:
            tasks: 任务列表
            criteria: 排序标准 (urgency/dependency/complexity)

        Returns:
            排序后的任务列表
        """
        if criteria == "urgency":
            priority_order = {
                TaskPriority.CRITICAL: 0,
                TaskPriority.HIGH: 1,
                TaskPriority.NORMAL: 2,
                TaskPriority.LOW: 3,
            }
            return sorted(
                tasks,
                key=lambda t: (
                    priority_order.get(t.priority, 2),
                    t.created_at,
                ),
            )
        elif criteria == "dependency":
            # 拓扑排序：先执行没有依赖的任务
            return self._topological_sort(tasks)
        else:
            return tasks

    def _topological_sort(self, tasks: list[Task]) -> list[Task]:
        """
        实现完整的拓扑排序（Kahn 算法）
        
        用于处理任务依赖关系，确保先执行没有依赖的任务。
        
        Args:
            tasks: 任务列表，每个任务可能有 dependencies 属性
        
        Returns:
            排序后的任务列表
        """
        if not tasks:
            return []

        # 构建邻接表和入度表
        # 假设任务有 dependencies 属性（依赖的任务 ID 列表）
        task_map = {task.id: task for task in tasks}
        in_degree = {task.id: 0 for task in tasks}
        graph = {task.id: [] for task in tasks}

        # 构建图
        for task in tasks:
            dependencies = getattr(task, 'dependencies', [])
            if not dependencies:
                dependencies = []

            for dep_id in dependencies:
                if dep_id in task_map:
                    graph[dep_id].append(task.id)
                    in_degree[task.id] += 1

        # Kahn 算法
        # 1. 找到所有入度为 0 的节点（没有依赖的任务）
        queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # 2. 取出一个入度为 0 的节点
            current_id = queue.pop(0)
            result.append(task_map[current_id])

            # 3. 减少相邻节点的入度
            for neighbor_id in graph[current_id]:
                in_degree[neighbor_id] -= 1
                # 4. 如果入度变为 0，加入队列
                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)

        # 检查是否有环（如果结果数量少于任务数量，说明有循环依赖）
        if len(result) < len(tasks):
            self.logger.warning(
                "Circular dependency detected in tasks",
                total_tasks=len(tasks),
                sorted_tasks=len(result),
            )
            # 返回已排序的部分，剩余任务按原始顺序
            remaining = [t for t in tasks if t not in result]
            result.extend(remaining)

        self.logger.info(
            "Topological sort complete",
            total_tasks=len(tasks),
            sorted_tasks=len(result),
        )

        return result
