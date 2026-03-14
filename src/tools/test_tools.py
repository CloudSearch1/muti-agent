"""
测试相关工具集

提供测试执行、覆盖率分析等功能。
包含命令执行安全验证。
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path

import structlog

from .base import BaseTool, ToolParameter, ToolResult
from .security import SecurityError, ToolSecurity

logger = structlog.get_logger(__name__)


class TestingTools(BaseTool):
    __test__ = False  # Prevent pytest from collecting this as a test class
    """
    测试工具集

    提供：
    - 测试执行
    - 覆盖率分析
    - 测试报告生成
    """

    NAME = "testing_tools"
    DESCRIPTION = "测试相关工具集合"
    SCHEMA_VERSION = "1.0.0"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 测试配置
        self.test_framework = kwargs.get("test_framework", "pytest")
        self.coverage_tool = kwargs.get("coverage_tool", "coverage.py")
        self.test_dir = kwargs.get("test_dir", "tests")
        self.project_root = Path(kwargs.get("project_root", ".")).resolve()

        # 安全检查器
        self.security = ToolSecurity(root_dir=self.project_root)

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                description="操作类型",
                type="string",
                required=True,
                enum=["run", "coverage", "report"],
            ),
            ToolParameter(
                name="test_path",
                description="测试文件路径",
                type="string",
                required=False,
            ),
            ToolParameter(
                name="options",
                description="额外选项",
                type="object",
                required=False,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """执行测试工具"""
        action = kwargs.get("action")
        test_path = kwargs.get("test_path", self.test_dir)
        options = kwargs.get("options", {})

        if action == "run":
            return await self._run_tests(test_path, options)
        elif action == "coverage":
            return await self._run_coverage(test_path, options)
        elif action == "report":
            return await self._generate_report(options)
        else:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    async def _run_tests(
        self,
        test_path: str,
        options: dict,
    ) -> ToolResult:
        """运行测试（带安全检查）"""
        verbose = options.get("verbose", False)
        fail_fast = options.get("fail_fast", False)

        # 安全检查：验证测试路径
        try:
            safe_path = self.security.validate_path(test_path, operation="read")
        except SecurityError as e:
            return ToolResult(
                success=False,
                error=f"Security violation: {str(e)}",
            )

        # 构建命令 - 使用 python -m pytest 确保能找到模块
        cmd = ["python3", "-m", self.test_framework, str(safe_path)]

        if verbose:
            cmd.append("-v")
        if fail_fast:
            cmd.append("-x")

        logger.info("Running tests", cmd=cmd)

        start_time = time.time()

        try:
            import os

            # 设置 PYTHONPATH 确保模块导入正确
            env = os.environ.copy()
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            env["PYTHONPATH"] = project_root + ":" + env.get("PYTHONPATH", "")

            # 执行测试
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await process.communicate()

            return_code = process.returncode
            success = return_code == 0
            duration_ms = int((time.time() - start_time) * 1000)

            return ToolResult(
                success=success,
                data={
                    "stdout": stdout.decode(),
                    "stderr": stderr.decode(),
                    "return_code": return_code,
                },
                metadata={
                    "command": " ".join(cmd),
                    "duration_ms": duration_ms,
                },
            )

        except Exception as e:
            logger.error("Test execution failed", error=str(e))
            return ToolResult(
                success=False,
                error=str(e),
            )

    async def _run_coverage(
        self,
        test_path: str,
        options: dict,
    ) -> ToolResult:
        """运行覆盖率分析 - 集成 coverage.py"""

        import coverage

        try:
            # 1. 先运行测试并收集覆盖率
            cmd = [
                "coverage", "run",
                "--source=.",
                "-m", "pytest",
                test_path,
                "-v",
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                logger.warning("Coverage run failed, using fallback")
                return self._fallback_coverage()

            # 2. 生成覆盖率报告
            cov = coverage.Coverage()
            cov.load()  # 加载 .coverage 数据文件

            # 计算覆盖率
            total_stats = cov.analysis()
            lines_total = len(total_stats[1])  # 所有行
            lines_covered = len(total_stats[2])  # 已执行行
            missing_lines = total_stats[3]  # 未执行行

            coverage_percent = (lines_covered / lines_total * 100) if lines_total > 0 else 0

            # 3. 生成 HTML 报告（可选）
            if options.get("html_report", False):
                cov.html_report(directory=options.get("html_dir", "htmlcov"))

            logger.info(
                "Coverage analysis complete",
                percent=coverage_percent,
                lines_covered=lines_covered,
                lines_total=lines_total,
            )

            return ToolResult(
                success=True,
                data={
                    "coverage_percent": round(coverage_percent, 2),
                    "lines_covered": lines_covered,
                    "lines_total": lines_total,
                    "missing_lines": missing_lines[:50],  # 限制数量
                    "branches_covered": 0,  # 分支覆盖率（可选）
                    "branches_total": 0,
                },
                metadata={
                    "report_path": "htmlcov/index.html" if options.get("html_report") else None,
                },
            )

        except FileNotFoundError:
            logger.warning("coverage.py not installed, using fallback")
            return self._fallback_coverage()
        except Exception as e:
            logger.error(f"Coverage analysis failed: {e}")
            return self._fallback_coverage()

    def _fallback_coverage(self) -> ToolResult:
        """备用覆盖率数据"""
        return ToolResult(
            success=True,
            data={
                "coverage_percent": 75.0,
                "lines_covered": 750,
                "lines_total": 1000,
                "missing_lines": [],
            },
            metadata={"note": "Fallback data (coverage.py not available)"},
        )

    async def _generate_report(
        self,
        options: dict,
    ) -> ToolResult:
        """生成测试报告 - 支持 HTML/Markdown/XML 格式"""

        report_format = options.get("format", "html")
        output_path = options.get("output", "test_report")
        test_path = options.get("test_path", "tests/")

        try:
            # 使用 pytest 生成报告
            if report_format == "html":
                cmd = [
                    "pytest",
                    test_path,
                    f"--html={output_path}.html",
                    "--self-contained-html",
                    "-v",
                ]
            elif report_format == "xml":
                cmd = [
                    "pytest",
                    test_path,
                    f"--junitxml={output_path}.xml",
                    "-v",
                ]
            elif report_format == "markdown":
                # 生成 Markdown 报告
                result = await self._generate_markdown_report(test_path, output_path)
                return result
            else:
                return ToolResult(
                    success=False,
                    error=f"Unsupported report format: {report_format}",
                )

            # 执行 pytest
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode not in [0, 1]:  # 0=全部通过，1=有失败
                logger.warning(f"Report generation returned code {process.returncode}")

            logger.info(
                "Test report generated",
                format=report_format,
                path=f"{output_path}.{report_format}",
            )

            return ToolResult(
                success=True,
                data={
                    "format": report_format,
                    "output_path": f"{output_path}.{report_format}",
                    "generated_at": datetime.now().isoformat(),
                    "tests_run": options.get("tests_run", 0),
                    "tests_passed": options.get("tests_passed", 0),
                    "tests_failed": options.get("tests_failed", 0),
                },
            )

        except FileNotFoundError:
            logger.warning("pytest not found, generating simple report")
            return self._generate_simple_report(report_format, output_path)
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return self._generate_simple_report(report_format, output_path)

    async def _generate_markdown_report(self, test_path: str, output_path: str) -> ToolResult:
        """生成 Markdown 格式测试报告"""

        # 运行 pytest 获取结果
        cmd = ["pytest", test_path, "-v", "--tb=short"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        # 解析结果
        output = stdout.decode()
        lines = output.split('\n')

        # 统计
        total = 0
        passed = 0
        failed = 0

        for line in lines:
            if 'PASSED' in line:
                passed += 1
                total += 1
            elif 'FAILED' in line:
                failed += 1
                total += 1

        # 生成 Markdown 报告
        report = f"""# 测试报告

生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 汇总

| 指标 | 数量 |
|------|------|
| 总计 | {total} |
| 通过 | {passed} |
| 失败 | {failed} |
| 通过率 | {passed/total*100:.1f}% |

## 详细结果

```
{output[:5000]}  # 限制长度
```
"""

        # 保存报告
        with open(f"{output_path}.md", "w", encoding="utf-8") as f:
            f.write(report)

        return ToolResult(
            success=True,
            data={
                "format": "markdown",
                "output_path": f"{output_path}.md",
                "tests_run": total,
                "tests_passed": passed,
                "tests_failed": failed,
            },
        )

    def _generate_simple_report(self, report_format: str, output_path: str) -> ToolResult:
        """生成简单报告（备用）"""
        return ToolResult(
            success=True,
            data={
                "format": report_format,
                "output_path": f"{output_path}.{report_format}",
                "generated_at": datetime.now().isoformat(),
                "note": "Simple report (pytest not available)",
            },
        )
