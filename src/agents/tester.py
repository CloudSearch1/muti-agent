"""
TesterAgent - 测试员 Agent

职责：测试用例生成、执行测试、质量保障
"""

from datetime import datetime
from typing import Any

import structlog

from ..core.models import AgentRole, Task
from .base import BaseAgent
from .llm_helper import get_tester_llm

logger = structlog.get_logger(__name__)


class TesterAgent(BaseAgent):
    """
    测试工程师
    
    负责：
    - 编写单元测试、集成测试
    - 执行测试并生成报告
    - 缺陷跟踪和管理
    - 质量保障
    """

    ROLE = AgentRole.TESTER

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 测试员特有配置
        self.testing_framework = kwargs.get("testing_framework", "pytest")
        self.coverage_target = kwargs.get("coverage_target", 80)
        self.auto_fix = kwargs.get("auto_fix", False)

        self.logger.info("TesterAgent initialized")

    async def execute(self, task: Task) -> dict[str, Any]:
        """
        执行测试任务
        """
        self.logger.info(
            "Starting testing task",
            task_id=task.id,
            task_title=task.title,
        )

        # 获取测试输入
        code_files = task.input_data.get("code_files", [])
        requirements = task.input_data.get("requirements", [])
        test_scope = task.input_data.get("test_scope", "unit")

        # 思考测试策略
        test_plan = await self.think({
            "code_files": code_files,
            "requirements": requirements,
            "test_scope": test_scope,
        })

        # 生成测试用例
        test_cases = self._generate_test_cases(test_plan)

        # 执行测试
        test_results = await self._run_tests(test_cases)

        # 生成测试报告
        report = self._generate_report(test_results)

        # 存储到黑板
        self.put_to_blackboard(
            f"test:{task.id}",
            {
                "test_cases": test_cases,
                "results": test_results,
                "report": report,
            },
            description="测试结果",
        )

        return {
            "status": "testing_complete",
            "test_cases_created": len(test_cases),
            "passed": test_results.get("passed", 0),
            "failed": test_results.get("failed", 0),
            "coverage": test_results.get("coverage", 0),
            "report": report,
        }

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        思考测试策略
        """
        code_files = context.get("code_files", [])
        requirements = context.get("requirements", [])

        # 构建测试提示词
        prompt = self._build_testing_prompt(code_files, requirements)

        self.logger.debug("Testing prompt prepared", prompt_length=len(prompt))

        # TODO: 调用 LLM API
        # 使用模拟返回
        test_plan = self._simulate_test_plan(code_files)

        return test_plan

    def _build_testing_prompt(
        self,
        code_files: list[dict],
        requirements: list[str],
    ) -> str:
        """构建测试提示词"""
        return f"""
你是一位资深测试工程师。请为以下代码编写测试用例。

## 代码文件
{code_files}

## 需求
{chr(10).join(f"- {r}" for r in requirements)}

## 要求
1. 覆盖所有主要功能路径
2. 包含边界条件和异常情况测试
3. 遵循测试最佳实践 (AAA 模式)
4. 代码覆盖率目标：{self.coverage_target}%
5. 使用 {self.testing_framework} 框架

## 输出格式
提供完整的测试代码
"""

    def _simulate_test_plan(
        self,
        code_files: list[dict],
    ) -> dict[str, Any]:
        """
        模拟测试计划 (临时实现)
        
        TODO: 替换为真实 LLM 调用
        """
        return {
            "test_strategy": "黑盒测试 + 白盒测试",
            "test_types": ["unit", "integration", "edge_cases"],
            "priority_areas": [
                "核心业务逻辑",
                "输入验证",
                "错误处理",
            ],
        }

    def _generate_test_cases(self, test_plan: dict[str, Any]) -> list[dict[str, Any]]:
        """生成测试用例"""
        # TODO: 生成真实测试用例
        return [
            {
                "name": "test_main_function",
                "type": "unit",
                "description": "测试主函数基本功能",
                "code": "# TODO: 生成测试代码\ndef test_main_function():\n    assert True\n",
            },
            {
                "name": "test_edge_case_empty_input",
                "type": "edge_case",
                "description": "测试空输入情况",
                "code": "# TODO: 生成边界测试代码\ndef test_edge_case():\n    assert True\n",
            },
        ]

    async def _run_tests(
        self,
        test_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        执行测试用例
        
        TODO: 实现真实测试执行
        """
        # 模拟测试结果
        total = len(test_cases)
        passed = total  # 模拟全部通过

        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "skipped": 0,
            "coverage": 85.5,
            "duration_ms": 1234,
            "details": [
                {
                    "test_name": tc["name"],
                    "status": "passed",
                    "duration_ms": 100,
                }
                for tc in test_cases
            ],
        }

    def _generate_report(self, test_results: dict[str, Any]) -> dict[str, Any]:
        """生成测试报告"""
        total = test_results.get("total", 0)
        passed = test_results.get("passed", 0)

        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            "title": "测试报告",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": test_results.get("failed", 0),
                "pass_rate": f"{pass_rate:.2f}%",
                "code_coverage": f"{test_results.get('coverage', 0):.2f}%",
            },
            "status": "passed" if pass_rate >= 95 else "needs_attention",
            "recommendations": [],
        }

    async def generate_regression_tests(
        self,
        bug_report: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        根据缺陷报告生成回归测试
        
        Args:
            bug_report: 缺陷报告
            
        Returns:
            回归测试用例列表
        """
        # TODO: 实现回归测试生成
        return []
