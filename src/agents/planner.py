"""
PlannerAgent - 规划师 Agent

职责：任务分解、优先级排序、资源调度
"""

from typing import Any, Optional
from datetime import datetime
import structlog

from ..core.models import (
    AgentRole,
    Task,
    TaskStatus,
    TaskPriority,
    Message,
    MessageType,
)
from .base import BaseAgent


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
        thinking_result = await self.think({
            "goal": goal,
            "context": context,
            "constraints": constraints,
        })
        
        # 生成子任务
        subtasks = thinking_result.get("subtasks", [])
        
        # 验证子任务数量
        if len(subtasks) > self.max_subtasks:
            self.logger.warning(
                "Generated subtasks exceed limit",
                generated=len(subtasks),
                limit=self.max_subtasks,
            )
            subtasks = subtasks[:self.max_subtasks]
        
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
        
        # 构建提示词
        prompt = f"""
你是一个专业的任务规划师。请将以下目标分解为可执行的子任务。

## 目标
{goal}

## 约束条件
{chr(10).join(f"- {c}" for c in constraints) if constraints else "无特殊约束"}

## 要求
1. 每个子任务应该是独立可执行的
2. 明确任务之间的依赖关系
3. 为每个任务分配合理的优先级 (low/normal/high/critical)
4. 指定每个任务需要的 Agent 角色 (analyst/architect/coder/tester/doc_writer)

## 输出格式 (JSON)
{{
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
}}
"""
        
        self.logger.debug("Planning prompt prepared", prompt_length=len(prompt))
        
        # TODO: 调用 LLM API
        # 这里使用模拟返回
        subtasks = self._simulate_planning(goal, constraints)
        
        return {
            "subtasks": subtasks,
            "reasoning": "基于目标复杂度和依赖关系进行分解",
        }
    
    def _simulate_planning(
        self,
        goal: str,
        constraints: list[str],
    ) -> list[dict[str, Any]]:
        """
        模拟规划结果 (临时实现)
        
        TODO: 替换为真实 LLM 调用
        """
        # 简单示例：根据目标关键词生成任务
        subtasks = []
        
        goal_lower = goal.lower()
        
        if "api" in goal_lower or "接口" in goal_lower:
            subtasks.extend([
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
            ])
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
            # TODO: 实现完整的拓扑排序
            return tasks
        else:
            return tasks
