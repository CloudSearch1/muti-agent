"""
Agent LLM 辅助模块

提供 Agent 通用的 LLM 调用能力
"""

import json
from typing import Any

import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..llm.service import get_llm_service

logger = structlog.get_logger(__name__)


class AgentLLMHelper:
    """
    Agent LLM 辅助类

    提供统一的 LLM 调用接口，支持：
    - 结构化输出
    - JSON 解析
    - 错误处理
    - 自动重试
    """

    def __init__(
        self,
        agent_name: str,
        temperature: float = 0.3,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.agent_name = agent_name
        self.temperature = temperature
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.llm = get_llm_service()

    async def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = 4096,
    ) -> str:
        """
        生成文本响应（带自动重试）

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            生成的文本，失败返回 None
        """
        if not self.llm.is_configured():
            logger.warning(
                "LLM not configured, using fallback",
                agent=self.agent_name,
            )
            return None

        async def _generate_with_retry():
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens,
            )
            return response.content

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(multiplier=self.retry_delay, min=1, max=10),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    try:
                        return await _generate_with_retry()
                    except Exception as e:
                        logger.warning(
                            "LLM generation attempt failed",
                            agent=self.agent_name,
                            attempt=attempt.retry_state.attempt_number,
                            error=str(e),
                        )
                        raise
        except RetryError as e:
            logger.error(
                "LLM generation failed after all retries",
                agent=self.agent_name,
                attempts=self.max_retries,
                error=str(e.last_attempt.exception()),
            )
            return None
        except Exception as e:
            logger.error(
                "LLM generation failed",
                agent=self.agent_name,
                error=str(e),
            )
            return None

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = 4096,
    ) -> dict[str, Any] | None:
        """
        生成 JSON 响应

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            解析后的 JSON 对象，失败返回 None
        """
        # 添加 JSON 格式要求
        json_system = (system_prompt or "") + "\n\n请以有效的 JSON 格式输出，不要包含其他文字。"

        content = await self.generate(
            prompt=prompt,
            system_prompt=json_system,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens,
        )

        if not content:
            return None

        # 尝试解析 JSON
        try:
            # 清理可能的 markdown 代码块
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(
                "JSON parsing failed",
                agent=self.agent_name,
                error=str(e),
                content=content[:200],
            )
            return None

    async def think(
        self,
        context: dict[str, Any],
        instructions: str,
        output_format: dict[str, Any] = None,
    ) -> dict[str, Any]:
        """
        Agent 思考过程

        Args:
            context: 上下文信息
            instructions: 思考指令
            output_format: 期望的输出格式 (JSON Schema 风格)

        Returns:
            思考结果
        """
        # 构建系统提示
        system_prompt = f"""你是一个专业的 {self.agent_name}。
{instructions}

请根据提供的上下文信息进行分析和决策。"""

        # 构建用户提示
        prompt = f"""## 上下文信息
{json.dumps(context, ensure_ascii=False, indent=2)}

        ## 期望输出格式\n{json.dumps(output_format, ensure_ascii=False, indent=2) if output_format else ''}

请进行分析并输出结果："""

        result = await self.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
        )

        return result or {}

    def is_available(self) -> bool:
        """检查 LLM 是否可用"""
        return self.llm.is_configured()


# Agent 专用的 LLM Helper 工厂函数


def get_planner_llm() -> AgentLLMHelper:
    """获取 Planner Agent 的 LLM Helper"""
    return AgentLLMHelper(
        agent_name="PlannerAgent",
        temperature=0.3,  # 规划需要更确定性的输出
    )


def get_architect_llm() -> AgentLLMHelper:
    """获取 Architect Agent 的 LLM Helper"""
    return AgentLLMHelper(
        agent_name="ArchitectAgent",
        temperature=0.3,
    )


def get_coder_llm() -> AgentLLMHelper:
    """获取 Coder Agent 的 LLM Helper"""
    return AgentLLMHelper(
        agent_name="CoderAgent",
        temperature=0.2,  # 代码生成需要更确定
    )


def get_tester_llm() -> AgentLLMHelper:
    """获取 Tester Agent 的 LLM Helper"""
    return AgentLLMHelper(
        agent_name="TesterAgent",
        temperature=0.3,
    )


def get_doc_writer_llm() -> AgentLLMHelper:
    """获取 DocWriter Agent 的 LLM Helper"""
    return AgentLLMHelper(
        agent_name="DocWriterAgent",
        temperature=0.5,  # 文档可以更有创造性
    )


def get_senior_architect_llm() -> AgentLLMHelper:
    """获取 SeniorArchitect Agent 的 LLM Helper"""
    return AgentLLMHelper(
        agent_name="SeniorArchitectAgent",
        temperature=0.2,  # 架构评审需要更严谨
    )


def get_researcher_llm() -> AgentLLMHelper:
    """获取 Researcher Agent 的 LLM Helper"""
    return AgentLLMHelper(
        agent_name="ResearchAgent",
        temperature=0.4,  # 研究需要一定的创造性
    )
