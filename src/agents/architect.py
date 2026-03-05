"""
ArchitectAgent - 架构师 Agent

职责：系统设计、技术选型、架构评审
"""

from typing import Any

import structlog

from ..core.models import AgentRole, Task
from .base import BaseAgent
from .llm_helper import get_architect_llm

logger = structlog.get_logger(__name__)


class ArchitectAgent(BaseAgent):
    """
    系统架构师
    
    负责：
    - 系统架构设计
    - 技术栈选型
    - 接口设计
    - 架构评审和优化建议
    """

    ROLE = AgentRole.ARCHITECT

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 架构师特有配置
        self.design_model = kwargs.get("design_model", "gpt-4")
        self.preferred_patterns = kwargs.get("preferred_patterns", [])
        
        # LLM 辅助
        self.llm_helper = get_architect_llm()

        self.logger.info("ArchitectAgent initialized")

    async def execute(self, task: Task) -> dict[str, Any]:
        """
        执行架构设计任务
        """
        self.logger.info(
            "Starting architecture design",
            task_id=task.id,
            task_title=task.title,
        )

        # 获取需求
        requirements = task.input_data.get("requirements", [])
        constraints = task.input_data.get("constraints", {})
        existing_system = task.input_data.get("existing_system", None)

        # 思考架构方案
        design = await self.think({
            "requirements": requirements,
            "constraints": constraints,
            "existing_system": existing_system,
        })

        # 生成架构文档
        architecture_doc = self._generate_architecture_doc(design)

        # 存储到黑板
        self.put_to_blackboard(
            f"architecture:{task.id}",
            architecture_doc,
            description="系统架构设计文档",
        )

        return {
            "status": "design_complete",
            "architecture": architecture_doc,
            "design_decisions": design.get("decisions", []),
        }

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        思考架构设计方案
        """
        requirements = context.get("requirements", [])
        constraints = context.get("constraints", {})

        # 尝试使用 LLM 进行架构设计
        if self.llm_helper.is_available():
            try:
                result = await self._llm_design(requirements, constraints)
                if result:
                    return result
            except Exception as e:
                self.logger.warning("LLM design failed, using fallback", error=str(e))

        # Fallback: 使用模拟设计
        return self._simulate_design(requirements, constraints)
    
    async def _llm_design(
        self,
        requirements: list[str],
        constraints: dict[str, Any],
    ) -> dict[str, Any] | None:
        """使用 LLM 进行架构设计"""
        prompt = f"""你是一位资深系统架构师。请根据以下需求设计系统架构。

## 需求
{chr(10).join(f"- {r}" for r in requirements)}

## 约束
{chr(10).join(f"- {k}: {v}" for k, v in constraints.items()) if constraints else "无特殊约束"}

## 输出要求
1. 选择合适的架构风格
2. 设计核心组件及其职责
3. 选择技术栈并说明理由
4. 说明关键设计决策

## 输出格式 (JSON)
{{
    "architecture_style": "monolith|microservices|serverless|...",
    "components": [
        {{
            "name": "组件名称",
            "technology": "技术选型",
            "responsibility": "职责说明"
        }}
    ],
    "decisions": [
        {{
            "decision": "设计决策",
            "rationale": "选择理由",
            "trade_offs": "权衡考虑"
        }}
    ]
}}"""

        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位资深系统架构师。请以 JSON 格式输出架构设计方案。",
        )
        
        if result:
            return result
        
        return None

    def _build_architecture_prompt(
        self,
        requirements: list[str],
        constraints: dict[str, Any],
    ) -> str:
        """构建架构设计提示词"""
        return f"""
你是一位资深系统架构师。请根据以下需求设计系统架构。

## 需求
{chr(10).join(f"- {r}" for r in requirements)}

## 约束
{chr(10).join(f"- {k}: {v}" for k, v in constraints.items()) if constraints else "无特殊约束"}

## 输出要求
1. 系统整体架构图 (文字描述)
2. 核心技术栈选型及理由
3. 关键组件设计
4. 数据流设计
5. 扩展性和可维护性考虑
"""

    def _simulate_design(
        self,
        requirements: list[str],
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """
        模拟架构设计结果 (临时实现)
        
        TODO: 替换为真实 LLM 调用
        """
        return {
            "architecture_style": "microservices",
            "components": [
                {
                    "name": "API Gateway",
                    "technology": "Kong/Nginx",
                    "responsibility": "请求路由、认证、限流",
                },
                {
                    "name": "Business Services",
                    "technology": "FastAPI (Python)",
                    "responsibility": "核心业务逻辑",
                },
                {
                    "name": "Message Queue",
                    "technology": "Redis Streams",
                    "responsibility": "异步通信、任务队列",
                },
                {
                    "name": "Database",
                    "technology": "PostgreSQL + Milvus",
                    "responsibility": "关系数据 + 向量数据",
                },
            ],
            "decisions": [
                {
                    "decision": "采用微服务架构",
                    "rationale": "便于独立部署和扩展",
                    "trade_offs": "增加了运维复杂度",
                },
            ],
        }

    def _generate_architecture_doc(self, design: dict[str, Any]) -> dict[str, Any]:
        """生成架构文档"""
        return {
            "title": "系统架构设计文档",
            "version": "1.0.0",
            "overview": design.get("architecture_style", "未知架构"),
            "components": design.get("components", []),
            "technology_stack": {
                "backend": "Python 3.11+",
                "framework": "FastAPI",
                "database": "PostgreSQL + Milvus",
                "message_queue": "Redis Streams",
            },
            "design_decisions": design.get("decisions", []),
            "diagrams": {
                "component_diagram": "TODO: 生成组件图",
                "sequence_diagram": "TODO: 生成时序图",
            },
        }

    async def review_architecture(
        self,
        architecture: dict[str, Any],
        criteria: list[str] = None,
    ) -> dict[str, Any]:
        """
        评审架构设计
        
        Args:
            architecture: 架构设计文档
            criteria: 评审标准列表
            
        Returns:
            评审结果
        """
        # TODO: 实现架构评审逻辑
        return {
            "status": "approved",
            "suggestions": [],
            "concerns": [],
        }
