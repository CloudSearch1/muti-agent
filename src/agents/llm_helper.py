"""
Agent LLM 辅助模块

提供 Agent 通用的 LLM 调用能力

日志级别规范:
- DEBUG: LLM 调用参数、响应详情
- INFO: 正常的 LLM 调用流程
- WARNING: 重试、配置缺失、可恢复问题
- ERROR: 调用失败、JSON 解析错误
"""

import json
from typing import Any

import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..llm.service import get_llm_service
from ..utils.text import clean_json_from_markdown

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
        """
        初始化 Agent LLM Helper

        Args:
            agent_name: Agent 名称，用于日志记录
            temperature: 温度参数 (0.0-2.0)，默认 0.3
            max_retries: 最大重试次数 (0-10)，默认 3
            retry_delay: 重试延迟秒数 (0.1-60.0)，默认 1.0

        Raises:
            ValueError: 当参数超出有效范围时
        """
        # 参数边界验证
        if not agent_name or not agent_name.strip():
            raise ValueError("agent_name cannot be empty")
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(
                f"temperature must be between 0.0 and 2.0, got {temperature}"
            )
        if not 0 <= max_retries <= 10:
            raise ValueError(
                f"max_retries must be between 0 and 10, got {max_retries}"
            )
        if not 0.1 <= retry_delay <= 60.0:
            raise ValueError(
                f"retry_delay must be between 0.1 and 60.0 seconds, got {retry_delay}"
            )

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
            temperature: 温度参数 (0.0-2.0)
            max_tokens: 最大 token 数 (1-32768)

        Returns:
            生成的文本，失败返回 None

        Raises:
            ValueError: 当参数无效时
        """
        # 参数边界验证
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")
        if max_tokens < 1 or max_tokens > 32768:
            raise ValueError(
                f"max_tokens must be between 1 and 32768, got {max_tokens}"
            )
        if temperature is not None and not 0.0 <= temperature <= 2.0:
            raise ValueError(
                f"temperature must be between 0.0 and 2.0, got {temperature}"
            )

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
                        result = await _generate_with_retry()
                        logger.debug(
                            "LLM generation successful",
                            agent=self.agent_name,
                            attempt=attempt.retry_state.attempt_number,
                        )
                        return result
                    except Exception as e:
                        # 重试使用 WARNING 级别
                        logger.warning(
                            "LLM generation attempt failed, retrying",
                            agent=self.agent_name,
                            attempt=attempt.retry_state.attempt_number,
                            max_attempts=self.max_retries,
                            error=str(e),
                        )
                        raise
        except RetryError as e:
            # 所有重试失败使用 ERROR 级别
            logger.error(
                "LLM generation failed after all retries",
                agent=self.agent_name,
                attempts=self.max_retries,
                error=str(e.last_attempt.exception()),
                suggestion="Check LLM service availability and API configuration",
            )
            return None
        except Exception as e:
            logger.error(
                "LLM generation failed unexpectedly",
                agent=self.agent_name,
                error=str(e),
                error_type=type(e).__name__,
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
            temperature: 温度参数 (0.0-2.0)
            max_tokens: 最大 token 数 (1-32768)

        Returns:
            解析后的 JSON 对象，失败返回 None
        """
        # 参数验证在 generate 方法中进行
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
            cleaned = clean_json_from_markdown(content)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(
                "JSON parsing failed",
                agent=self.agent_name,
                error=str(e),
                content_preview=content[:200] if len(content) > 200 else content,
                content_length=len(content)
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
    """
    获取 Planner Agent 的 LLM Helper

    Planner Agent 负责任务规划和分解，使用较低的温度 (0.3)
    以获得更确定性的规划输出。

    Returns:
        AgentLLMHelper: 配置好的 LLM Helper 实例
    """
    return AgentLLMHelper(
        agent_name="PlannerAgent",
        temperature=0.3,  # 规划需要更确定性的输出
    )


def get_architect_llm() -> AgentLLMHelper:
    """
    获取 Architect Agent 的 LLM Helper

    Architect Agent 负责系统架构设计，使用较低的温度 (0.3)
    以确保架构设计的一致性。

    Returns:
        AgentLLMHelper: 配置好的 LLM Helper 实例
    """
    return AgentLLMHelper(
        agent_name="ArchitectAgent",
        temperature=0.3,
    )


def get_coder_llm() -> AgentLLMHelper:
    """
    获取 Coder Agent 的 LLM Helper

    Coder Agent 负责代码生成，使用最低的温度 (0.2)
    以确保代码生成的准确性和一致性。

    Returns:
        AgentLLMHelper: 配置好的 LLM Helper 实例
    """
    return AgentLLMHelper(
        agent_name="CoderAgent",
        temperature=0.2,  # 代码生成需要更确定
    )


def get_tester_llm() -> AgentLLMHelper:
    """
    获取 Tester Agent 的 LLM Helper

    Tester Agent 负责测试用例生成，使用中等温度 (0.3)
    平衡确定性和测试覆盖的多样性。

    Returns:
        AgentLLMHelper: 配置好的 LLM Helper 实例
    """
    return AgentLLMHelper(
        agent_name="TesterAgent",
        temperature=0.3,
    )


def get_doc_writer_llm() -> AgentLLMHelper:
    """
    获取 DocWriter Agent 的 LLM Helper

    DocWriter Agent 负责文档编写，使用较高温度 (0.5)
    允许更有创造性的文档表达。

    Returns:
        AgentLLMHelper: 配置好的 LLM Helper 实例
    """
    return AgentLLMHelper(
        agent_name="DocWriterAgent",
        temperature=0.5,  # 文档可以更有创造性
    )


def get_senior_architect_llm() -> AgentLLMHelper:
    """
    获取 SeniorArchitect Agent 的 LLM Helper

    SeniorArchitect Agent 负责架构评审，使用最低温度 (0.2)
    确保评审结果的严谨性和一致性。

    Returns:
        AgentLLMHelper: 配置好的 LLM Helper 实例
    """
    return AgentLLMHelper(
        agent_name="SeniorArchitectAgent",
        temperature=0.2,  # 架构评审需要更严谨
    )


def get_researcher_llm() -> AgentLLMHelper:
    """
    获取 Researcher Agent 的 LLM Helper

    Research Agent 负责研究和信息收集，使用中等温度 (0.4)
    平衡研究结果的准确性和探索的多样性。

    Returns:
        AgentLLMHelper: 配置好的 LLM Helper 实例
    """
    return AgentLLMHelper(
        agent_name="ResearchAgent",
        temperature=0.4,  # 研究需要一定的创造性
    )
