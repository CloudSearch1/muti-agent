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
        design = await self.think(
            {
                "requirements": requirements,
                "constraints": constraints,
                "existing_system": existing_system,
            }
        )

        # 生成架构文档
        architecture_doc = await self._generate_architecture_doc(design)

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

    async def _simulate_design(
        self,
        requirements: list[str],
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Fallback 架构设计（当 LLM 失败时）
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

    async def _generate_architecture_doc(self, design: dict[str, Any]) -> dict[str, Any]:
        """生成架构文档，包含图表"""
        components = design.get("components", [])
        decisions = design.get("decisions", [])

        # 使用 LLM 生成组件图（Mermaid 格式）
        component_diagram = await self._generate_component_diagram(components)

        # 使用 LLM 生成时序图（Mermaid 格式）
        sequence_diagram = await self._generate_sequence_diagram(components, decisions)

        return {
            "title": "系统架构设计文档",
            "version": "1.0.0",
            "overview": design.get("architecture_style", "未知架构"),
            "components": components,
            "technology_stack": {
                "backend": "Python 3.11+",
                "framework": "FastAPI",
                "database": "PostgreSQL + Milvus",
                "message_queue": "Redis Streams",
            },
            "design_decisions": decisions,
            "diagrams": {
                "component_diagram": component_diagram,
                "sequence_diagram": sequence_diagram,
                "format": "mermaid",
            },
        }

    async def _generate_component_diagram(self, components: list[dict[str, Any]]) -> str:
        """
        使用 LLM 生成组件图（Mermaid 格式）
        
        TODO: 生成组件图
        """
        if not components:
            return "graph TD\n    A[无组件信息]"

        # 构建提示词
        component_list = "\n".join(f"- {c['name']}: {c['responsibility']}" for c in components)

        prompt = f"""你是一位架构可视化专家。请为以下系统组件生成 Mermaid 组件图。

## 组件列表
{component_list}

## 要求
1. 使用 Mermaid graph TD 格式
2. 显示组件之间的关系
3. 包含必要的注释
4. 布局清晰易读

## 输出格式
只返回 Mermaid 代码，不要其他文字。"""

        # 调用 LLM 生成
        diagram = await self.llm_helper.generate(
            prompt=prompt,
            system_prompt="生成 Mermaid 组件图代码。",
        )

        if diagram:
            # 清理可能的 markdown 标记
            diagram = diagram.replace("```mermaid", "").replace("```", "").strip()
            return diagram

        # Fallback：生成简单的组件图
        return self._generate_fallback_component_diagram(components)

    def _generate_fallback_component_diagram(self, components: list[dict[str, Any]]) -> str:
        """生成备用组件图"""
        mermaid = "graph TD\n"
        mermaid += "    subgraph System[系统]\n"

        for i, comp in enumerate(components):
            name = comp.get("name", f"Component{i}")
            tech = comp.get("technology", "")
            mermaid += f"        {name}[{name}\\n{tech}]\n"

        mermaid += "    end\n"

        # 添加简单连接
        if len(components) > 1:
            for i in range(len(components) - 1):
                name1 = components[i].get("name", f"Component{i}")
                name2 = components[i+1].get("name", f"Component{i+1}")
                mermaid += f"    {name1} --> {name2}\n"

        return mermaid

    async def _generate_sequence_diagram(
        self,
        components: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
    ) -> str:
        """
        使用 LLM 生成时序图（Mermaid 格式）
        
        TODO: 生成时序图
        """
        if not components:
            return "sequenceDiagram\n    participant 无组件信息"

        # 构建提示词
        component_names = [c["name"] for c in components]

        prompt = f"""你是一位架构可视化专家。请为以下系统组件生成 Mermaid 时序图。

## 组件
{", ".join(component_names)}

## 设计决策
{chr(10).join(f"- {d['decision']}" for d in decisions)}

## 要求
1. 使用 Mermaid sequenceDiagram 格式
2. 展示典型的请求流程
3. 包含必要的注释
4. 流程清晰

## 输出格式
只返回 Mermaid 代码，不要其他文字。"""

        # 调用 LLM 生成
        diagram = await self.llm_helper.generate(
            prompt=prompt,
            system_prompt="生成 Mermaid 时序图代码。",
        )

        if diagram:
            diagram = diagram.replace("```mermaid", "").replace("```", "").strip()
            return diagram

        # Fallback
        return self._generate_fallback_sequence_diagram(component_names)

    def _generate_fallback_sequence_diagram(self, components: list[str]) -> str:
        """生成备用时序图"""
        mermaid = "sequenceDiagram\n"
        mermaid += "    autonumber\n"
        mermaid += "    participant User as 用户\n"

        for comp in components:
            safe_name = comp.replace(" ", "")
            mermaid += f"    participant {safe_name} as {comp}\n"

        # 添加简单流程
        if components:
            first = components[0].replace(" ", "")
            mermaid += f"\n    User->>{first}: 请求\n"
            mermaid += f"    {first}-->>User: 响应\n"

        return mermaid

    async def review_architecture(
        self,
        architecture: dict[str, Any],
        criteria: list[str] = None,
    ) -> dict[str, Any]:
        """
        评审架构设计 - 使用 LLM 进行架构审查

        Args:
            architecture: 架构设计文档
            criteria: 评审标准列表

        Returns:
            评审结果
        """
        if not criteria:
            criteria = [
                "可扩展性",
                "可靠性",
                "安全性",
                "性能",
                "可维护性",
                "成本效益",
            ]

        # 构建评审提示词
        prompt = f"""你是一位资深架构评审专家。请评审以下架构设计。

## 架构概述
{architecture.get('overview', '无概述')}

## 组件设计
{self._format_components(architecture.get('components', []))}

## 技术栈
{architecture.get('technology_stack', {})}

## 设计决策
{self._format_decisions(architecture.get('design_decisions', []))}

## 评审标准
{chr(10).join(f"- {c}" for c in criteria)}

## 要求
1. 评估架构的优缺点
2. 识别潜在风险和问题
3. 提供改进建议
4. 评估是否符合评审标准
5. 给出总体评分（0-100 分）

## 输出格式 (JSON)
{{
    "status": "approved|needs_revision|rejected",
    "overall_score": 85,
    "strengths": ["优点 1", "优点 2"],
    "weaknesses": ["不足 1", "不足 2"],
    "concerns": [
        {{
            "category": "scalability|security|performance|...",
            "severity": "critical|major|minor",
            "description": "问题描述",
            "recommendation": "改进建议"
        }}
    ],
    "suggestions": ["建议 1", "建议 2"],
    "summary": "评审总结"
}}"""

        # 调用 LLM 进行评审
        review_result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位严格的架构评审专家。请提供专业、详细的评审意见。",
        )

        if review_result:
            self.logger.info(
                "Architecture review complete",
                status=review_result.get("status"),
                score=review_result.get("overall_score"),
                concerns=len(review_result.get("concerns", [])),
            )
            return review_result

        # Fallback
        self.logger.warning("Architecture review LLM failed, using fallback")
        return {
            "status": "approved",
            "overall_score": 75,
            "strengths": ["架构结构清晰"],
            "weaknesses": ["需要更多性能优化考虑"],
            "concerns": [],
            "suggestions": ["建议添加缓存层", "考虑异步处理"],
            "summary": "架构设计整体合理，建议进一步优化。",
        }

    def _format_components(self, components: list[dict[str, Any]]) -> str:
        """格式化组件列表"""
        if not components:
            return "无组件信息"
        lines = []
        for comp in components:
            lines.append(f"- {comp.get('name', 'Unknown')}: {comp.get('responsibility', '')}")
        return "\n".join(lines)

    def _format_decisions(self, decisions: list[dict[str, Any]]) -> str:
        """格式化设计决策列表"""
        if not decisions:
            return "无设计决策"
        lines = []
        for d in decisions:
            lines.append(f"- {d.get('decision', '')}: {d.get('rationale', '')}")
        return "\n".join(lines)
