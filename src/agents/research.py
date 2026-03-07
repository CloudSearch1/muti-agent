"""
研究助手 Agent

职责：文献调研、技术分析、趋势研究
"""

from typing import Any

import structlog

from ..core.models import AgentRole, Task
from .base import BaseAgent
from .llm_helper import get_researcher_llm

logger = structlog.get_logger(__name__)


class ResearchAgent(BaseAgent):
    """
    研究助手 Agent

    负责：
    - 技术文献调研
    - 竞品分析
    - 技术趋势研究
    - 最佳实践总结
    - 技术方案对比
    """

    ROLE = AgentRole.RESEARCHER

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 研究助手特有配置
        self.search_enabled = kwargs.get("search_enabled", False)
        self.max_sources = kwargs.get("max_sources", 10)

        # LLM 辅助
        self.llm_helper = get_researcher_llm()

        logger.info("ResearchAgent initialized")

    async def execute(self, task: Task) -> dict[str, Any]:
        """
        执行研究任务
        """
        research_type = task.input_data.get("type", "general")

        if research_type == "literature":
            return await self._literature_review(task)
        elif research_type == "competitive":
            return await self._competitive_analysis(task)
        elif research_type == "trend":
            return await self._trend_analysis(task)
        elif research_type == "comparison":
            return await self._technology_comparison(task)
        else:
            return await self._general_research(task)

    async def _literature_review(self, task: Task) -> dict[str, Any]:
        """文献调研"""
        topic = task.input_data.get("topic", "")
        keywords = task.input_data.get("keywords", [])

        logger.info(
            "Starting literature review",
            topic=topic,
            keywords_count=len(keywords),
        )

        # 思考调研方向
        review_result = await self.think(
            {
                "type": "literature_review",
                "topic": topic,
                "keywords": keywords,
            }
        )

        return {
            "status": "review_complete",
            "topic": topic,
            "sources": review_result.get("sources", []),
            "key_findings": review_result.get("key_findings", []),
            "summary": review_result.get("summary", ""),
            "references": review_result.get("references", []),
        }

    async def _competitive_analysis(self, task: Task) -> dict[str, Any]:
        """竞品分析"""
        product = task.input_data.get("product", "")
        competitors = task.input_data.get("competitors", [])

        logger.info(
            "Starting competitive analysis",
            product=product,
            competitors_count=len(competitors),
        )

        analysis_result = await self.think(
            {
                "type": "competitive_analysis",
                "product": product,
                "competitors": competitors,
            }
        )

        return {
            "status": "analysis_complete",
            "product": product,
            "competitors": analysis_result.get("competitors", []),
            "strengths": analysis_result.get("strengths", []),
            "weaknesses": analysis_result.get("weaknesses", []),
            "opportunities": analysis_result.get("opportunities", []),
            "threats": analysis_result.get("threats", []),
        }

    async def _trend_analysis(self, task: Task) -> dict[str, Any]:
        """趋势分析"""
        technology = task.input_data.get("technology", "")
        time_range = task.input_data.get("time_range", "1 year")

        logger.info(
            "Starting trend analysis",
            technology=technology,
            time_range=time_range,
        )

        trend_result = await self.think(
            {
                "type": "trend_analysis",
                "technology": technology,
                "time_range": time_range,
            }
        )

        return {
            "status": "trend_complete",
            "technology": technology,
            "current_state": trend_result.get("current_state", ""),
            "emerging_trends": trend_result.get("emerging_trends", []),
            "predictions": trend_result.get("predictions", []),
            "recommendations": trend_result.get("recommendations", []),
        }

    async def _technology_comparison(self, task: Task) -> dict[str, Any]:
        """技术方案对比"""
        technologies = task.input_data.get("technologies", [])
        criteria = task.input_data.get("criteria", [])

        logger.info(
            "Starting technology comparison",
            technologies_count=len(technologies),
            criteria_count=len(criteria),
        )

        comparison_result = await self.think(
            {
                "type": "technology_comparison",
                "technologies": technologies,
                "criteria": criteria,
            }
        )

        return {
            "status": "comparison_complete",
            "technologies": comparison_result.get("technologies", []),
            "comparison_matrix": comparison_result.get("matrix", {}),
            "recommendation": comparison_result.get("recommendation", ""),
            "trade_offs": comparison_result.get("trade_offs", []),
        }

    async def _general_research(self, task: Task) -> dict[str, Any]:
        """通用研究"""
        topic = task.input_data.get("topic", "")

        logger.info("Starting general research", topic=topic)

        research_result = await self.think(
            {
                "type": "general_research",
                "topic": topic,
            }
        )

        return {
            "status": "research_complete",
            "topic": topic,
            "findings": research_result.get("findings", []),
            "summary": research_result.get("summary", ""),
        }

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """思考/研究过程 - 使用 LLM 进行研究分析"""
        research_type = context.get("type", "")

        # 尝试使用 LLM 进行研究
        if self.llm_helper.is_available():
            try:
                result = await self._llm_research(research_type, context)
                if result:
                    return result
            except Exception as e:
                logger.warning("LLM research failed, using fallback", error=str(e))

        # Fallback: 使用模拟研究
        if research_type == "literature_review":
            return self._simulate_literature_review(context)
        elif research_type == "competitive_analysis":
            return self._simulate_competitive_analysis(context)
        elif research_type == "trend_analysis":
            return self._simulate_trend_analysis(context)
        elif research_type == "technology_comparison":
            return self._simulate_technology_comparison(context)
        else:
            return self._simulate_general_research(context)

    async def _llm_research(self, research_type: str, context: dict[str, Any]) -> dict[str, Any] | None:
        """使用 LLM 进行研究分析"""
        if research_type == "literature_review":
            return await self._llm_literature_review(context)
        elif research_type == "competitive_analysis":
            return await self._llm_competitive_analysis(context)
        elif research_type == "trend_analysis":
            return await self._llm_trend_analysis(context)
        elif research_type == "technology_comparison":
            return await self._llm_technology_comparison(context)
        else:
            return await self._llm_general_research(context)

    async def _llm_literature_review(self, context: dict[str, Any]) -> dict[str, Any] | None:
        """使用 LLM 进行文献调研"""
        topic = context.get("topic", "")
        keywords = context.get("keywords", [])

        prompt = f"""你是一位资深技术研究员。请针对以下主题进行文献调研分析。

## 研究主题
{topic}

## 关键词
{", ".join(keywords) if keywords else "无特定关键词"}

## 要求
1. 总结该领域的主要研究方向
2. 列出关键发现和重要结论
3. 识别研究空白和未来方向
4. 提供参考来源建议

## 输出格式 (JSON)
{{
    "sources": [
        {{"title": "文献标题", "year": 2024, "citations": 150, "relevance": "high|medium|low"}}
    ],
    "key_findings": ["关键发现 1", "关键发现 2"],
    "research_gaps": ["研究空白 1", "研究空白 2"],
    "summary": "研究总结",
    "references": ["参考来源建议"]
}}"""

        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位资深技术研究员。请以 JSON 格式输出文献调研结果。",
        )

        if result:
            self.logger.info("LLM literature review complete", topic=topic)
            return result

        return None

    async def _llm_competitive_analysis(self, context: dict[str, Any]) -> dict[str, Any] | None:
        """使用 LLM 进行竞品分析"""
        product = context.get("product", "")
        competitors = context.get("competitors", [])

        prompt = f"""你是一位资深产品分析师。请进行竞品分析。

## 产品
{product}

## 竞品列表
{", ".join(competitors) if competitors else "请识别主要竞品"}

## 要求
1. 分析各产品的优劣势
2. 进行 SWOT 分析
3. 识别市场机会
4. 提供差异化建议

## 输出格式 (JSON)
{{
    "competitors": [
        {{"name": "竞品名", "market_share": "市场份额估计", "strengths": ["优势"], "weaknesses": ["劣势"]}}
    ],
    "strengths": ["我们产品的优势"],
    "weaknesses": ["我们产品的劣势"],
    "opportunities": ["市场机会"],
    "threats": ["潜在威胁"],
    "differentiation": ["差异化建议"]
}}"""

        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位资深产品分析师。请以 JSON 格式输出竞品分析结果。",
        )

        if result:
            self.logger.info("LLM competitive analysis complete", product=product)
            return result

        return None

    async def _llm_trend_analysis(self, context: dict[str, Any]) -> dict[str, Any] | None:
        """使用 LLM 进行趋势分析"""
        technology = context.get("technology", "")
        time_range = context.get("time_range", "1 year")

        prompt = f"""你是一位资深技术趋势分析师。请分析以下技术的发展趋势。

## 技术领域
{technology}

## 分析时间范围
{time_range}

## 要求
1. 分析当前技术状态
2. 识别新兴趋势
3. 预测未来发展
4. 提供采用建议

## 输出格式 (JSON)
{{
    "current_state": "当前技术状态描述",
    "emerging_trends": ["趋势 1", "趋势 2"],
    "predictions": ["预测 1", "预测 2"],
    "adoption_stage": "早期采用者|早期大众|晚期大众|落后者",
    "recommendations": ["建议 1", "建议 2"],
    "risks": ["风险 1", "风险 2"]
}}"""

        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位资深技术趋势分析师。请以 JSON 格式输出趋势分析结果。",
        )

        if result:
            self.logger.info("LLM trend analysis complete", technology=technology)
            return result

        return None

    async def _llm_technology_comparison(self, context: dict[str, Any]) -> dict[str, Any] | None:
        """使用 LLM 进行技术方案对比"""
        technologies = context.get("technologies", [])
        criteria = context.get("criteria", [])

        prompt = f"""你是一位资深技术架构师。请对比分析以下技术方案。

## 技术方案
{", ".join(technologies) if technologies else "无指定技术"}

## 评估标准
{", ".join(criteria) if criteria else "性能、易用性、社区支持、成熟度、成本"}

## 要求
1. 进行客观对比分析
2. 评估各方案的优劣势
3. 提供选择建议
4. 说明权衡考虑

## 输出格式 (JSON)
{{
    "technologies": {technologies},
    "matrix": {{
        "技术1": {{"性能": 85, "易用性": 80, "社区": 90, "成熟度": 85, "成本": 70}},
        "技术2": {{...}}
    }},
    "recommendation": "推荐方案",
    "rationale": "推荐理由",
    "trade_offs": ["权衡考虑 1", "权衡考虑 2"],
    "use_cases": {{
        "场景1": "推荐技术A",
        "场景2": "推荐技术B"
    }}
}}"""

        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位资深技术架构师。请以 JSON 格式输出技术对比结果。",
        )

        if result:
            self.logger.info("LLM technology comparison complete", technologies=technologies)
            return result

        return None

    async def _llm_general_research(self, context: dict[str, Any]) -> dict[str, Any] | None:
        """使用 LLM 进行通用研究"""
        topic = context.get("topic", "")

        prompt = f"""你是一位资深研究员。请针对以下主题进行研究分析。

## 研究主题
{topic}

## 要求
1. 全面分析主题
2. 提取关键发现
3. 总结核心观点

## 输出格式 (JSON)
{{
    "findings": ["发现 1", "发现 2", "发现 3"],
    "insights": ["洞察 1", "洞察 2"],
    "summary": "研究总结",
    "further_research": ["后续研究方向"]
}}"""

        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位资深研究员。请以 JSON 格式输出研究结果。",
        )

        if result:
            self.logger.info("LLM general research complete", topic=topic)
            return result

        return None

    def _simulate_literature_review(self, context: dict[str, Any]) -> dict[str, Any]:
        """模拟文献调研"""
        topic = context.get("topic", "")

        return {
            "sources": [
                {"title": f"Research on {topic}", "year": 2024, "citations": 150},
                {"title": f"Advanced {topic} Techniques", "year": 2023, "citations": 200},
            ],
            "key_findings": [
                f"关键发现 1：关于{topic}的重要发现",
                f"关键发现 2：{topic}的最新进展",
            ],
            "summary": f"完成了关于 {topic} 的文献调研",
            "references": [],
        }

    def _simulate_competitive_analysis(self, context: dict[str, Any]) -> dict[str, Any]:
        """模拟竞品分析"""
        context.get("product", "")
        competitors = context.get("competitors", [])

        return {
            "competitors": competitors,
            "strengths": ["技术优势", "用户体验", "性能优化"],
            "weaknesses": ["功能完整性", "文档完善度"],
            "opportunities": ["市场增长", "新技术应用"],
            "threats": ["竞争加剧", "技术更新快"],
        }

    def _simulate_trend_analysis(self, context: dict[str, Any]) -> dict[str, Any]:
        """模拟趋势分析"""
        technology = context.get("technology", "")

        return {
            "current_state": f"{technology} 目前处于成熟阶段",
            "emerging_trends": [
                f"{technology} 与 AI 的结合",
                f"{technology} 的云原生发展",
            ],
            "predictions": [
                "未来 1-2 年将持续增长",
                "将出现更多开源工具",
            ],
            "recommendations": [
                "建议关注最新发展",
                "可以考虑采用相关技术",
            ],
        }

    def _simulate_technology_comparison(self, context: dict[str, Any]) -> dict[str, Any]:
        """模拟技术方案对比"""
        technologies = context.get("technologies", [])

        # 生成对比矩阵
        matrix = {}
        for tech in technologies:
            matrix[tech] = {
                "performance": 85,
                "ease_of_use": 80,
                "community": 90,
                "maturity": 85,
            }

        return {
            "technologies": technologies,
            "matrix": matrix,
            "recommendation": technologies[0] if technologies else "",
            "trade_offs": ["性能 vs 易用性", "成熟度 vs 创新性"],
        }

    def _simulate_general_research(self, context: dict[str, Any]) -> dict[str, Any]:
        """模拟通用研究"""
        topic = context.get("topic", "")

        return {
            "findings": [
                f"关于{topic}的发现 1",
                f"关于{topic}的发现 2",
            ],
            "summary": f"完成了关于 {topic} 的研究",
        }
