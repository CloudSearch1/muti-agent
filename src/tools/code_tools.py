"""
代码相关工具集

提供代码生成、分析、格式化等功能
"""

import asyncio

import structlog

from .base import BaseTool, ToolParameter, ToolResult

logger = structlog.get_logger(__name__)


class CodeTools(BaseTool):
    """
    代码工具集

    提供：
    - 代码生成
    - 代码格式化
    - 代码分析
    - 代码转换
    """

    NAME = "code_tools"
    DESCRIPTION = "代码相关工具集合"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 代码格式化配置
        self.formatter = kwargs.get("formatter", "black")
        self.line_length = kwargs.get("line_length", 100)

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                description="操作类型",
                type="string",
                required=True,
                enum=["format", "analyze", "convert", "generate"],
            ),
            ToolParameter(
                name="code",
                description="代码内容",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="language",
                description="编程语言",
                type="string",
                required=False,
                default="python",
            ),
            ToolParameter(
                name="options",
                description="额外选项",
                type="object",
                required=False,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """执行代码工具"""
        action = kwargs.get("action")
        code = kwargs.get("code")
        language = kwargs.get("language", "python")
        options = kwargs.get("options", {})

        if action == "format":
            return await self._format_code(code, language, options)
        elif action == "analyze":
            return await self._analyze_code(code, language, options)
        elif action == "convert":
            return await self._convert_code(code, language, options)
        elif action == "generate":
            return await self._generate_code(options)
        else:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}",
            )

    async def _format_code(
        self,
        code: str,
        language: str,
        options: dict,
    ) -> ToolResult:
        """格式化代码 - 集成 black, prettier 等"""
        import subprocess
        import tempfile
        import os
        
        try:
            if language == "python":
                # 使用 black 格式化 Python 代码
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code)
                    temp_file = f.name
                
                try:
                    # 运行 black
                    cmd = ["black", "--quiet", temp_file]
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await process.communicate()
                    
                    # 读取格式化后的代码
                    with open(temp_file, 'r', encoding='utf-8') as f:
                        formatted_code = f.read()
                    
                    logger.info("Code formatted with black")
                    
                finally:
                    os.unlink(temp_file)
                
            elif language in ["javascript", "typescript"]:
                # 使用 prettier 格式化
                with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                    f.write(code)
                    temp_file = f.name
                
                try:
                    cmd = ["prettier", "--write", "--loglevel", "silent", temp_file]
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await process.communicate()
                    
                    with open(temp_file, 'r', encoding='utf-8') as f:
                        formatted_code = f.read()
                    
                    logger.info("Code formatted with prettier")
                    
                finally:
                    os.unlink(temp_file)
            else:
                # 其他语言，简单格式化
                formatted_code = code.strip()
                logger.info("Simple code formatting applied")
            
            return ToolResult(
                success=True,
                data={
                    "formatted_code": formatted_code,
                    "language": language,
                    "formatter": self.formatter or "auto",
                },
                metadata={
                    "original_length": len(code),
                    "formatted_length": len(formatted_code),
                    "changes": abs(len(formatted_code) - len(code)),
                },
            )
            
        except FileNotFoundError:
            logger.warning("Formatter not found, using simple formatting")
            formatted_code = code.strip()
            return ToolResult(
                success=True,
                data={
                    "formatted_code": formatted_code,
                    "language": language,
                    "formatter": "simple",
                },
                metadata={"note": "Formatter not available"},
            )
        except Exception as e:
            logger.error(f"Code formatting failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
            )

    async def _analyze_code(
        self,
        code: str,
        language: str,
        options: dict,
    ) -> ToolResult:
        """分析代码 - 集成 pylint/flake8 等"""
        import subprocess
        import tempfile
        import os
        import re
        
        try:
            if language == "python":
                # 使用 pylint 分析 Python 代码
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code)
                    temp_file = f.name
                
                try:
                    cmd = ["pylint", temp_file, "--output-format=json", "--errors-only"]
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await process.communicate()
                    
                    # 解析 pylint 输出
                    import json
                    try:
                        issues = json.loads(stdout.decode())
                    except:
                        issues = []
                    
                    # 统计
                    functions = len(re.findall(r'\bdef\s+(\w+)\s*\(', code))
                    classes = len(re.findall(r'\bclass\s+(\w+)\s*[:\(]', code))
                    lines = code.split('\n')
                    loc = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
                    
                    logger.info(f"Code analysis complete: {len(issues)} issues found")
                    
                finally:
                    os.unlink(temp_file)
                
            else:
                # 其他语言，简单分析
                lines = code.split('\n')
                functions = len(re.findall(r'\bfunction\s+(\w+)\s*\(', code))
                classes = len(re.findall(r'\bclass\s+(\w+)', code))
                loc = len([l for l in lines if l.strip()])
                issues = []
            
            # 计算复杂度（简单估算）
            complexity = "low"
            if loc > 500 or len(issues) > 10:
                complexity = "high"
            elif loc > 200 or len(issues) > 5:
                complexity = "medium"
            
            return ToolResult(
                success=True,
                data={
                    "complexity": complexity,
                    "lines_of_code": loc,
                    "total_lines": len(lines),
                    "functions": functions,
                    "classes": classes,
                    "issues": issues[:20],  # 限制数量
                    "language": language,
                },
            )
            
        except FileNotFoundError:
            logger.warning("Analysis tool not found, using basic analysis")
            lines = code.split('\n')
            return ToolResult(
                success=True,
                data={
                    "complexity": "unknown",
                    "lines_of_code": len(lines),
                    "functions": 0,
                    "classes": 0,
                    "issues": [],
                    "note": "Analysis tool not available",
                },
            )
        except Exception as e:
            logger.error(f"Code analysis failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
            )

    async def _convert_code(
        self,
        code: str,
        language: str,
        options: dict,
    ) -> ToolResult:
        """转换代码 - 使用 LLM 进行代码转换"""
        target_language = options.get("target_language", "python")
        
        # 构建转换提示词
        prompt = f"""你是一位代码转换专家。请将以下 {language} 代码转换为 {target_language}。

## 原始代码 ({language})
```{language}
{code}
```

## 要求
1. 保持功能完全一致
2. 使用 {target_language} 的最佳实践
3. 包含必要的注释
4. 遵循 {target_language} 的代码规范

## 输出格式
只提供转换后的代码，不要其他文字。"""

        try:
            # 调用 LLM 进行转换
            from ..agents.llm_helper import get_coder_llm
            llm = get_coder_llm()
            
            converted = await llm.generate(
                prompt=prompt,
                system_prompt=f"你是一位代码转换专家。请将代码从{language}转换为{target_language}。",
            )
            
            # 清理可能的 markdown 标记
            if converted:
                converted = converted.replace(f"```{target_language}", "").replace("```", "").strip()
            
            logger.info(
                "Code conversion complete",
                from_lang=language,
                to_lang=target_language,
                original_len=len(code),
                converted_len=len(converted) if converted else 0,
            )
            
            return ToolResult(
                success=True,
                data={
                    "original_language": language,
                    "target_language": target_language,
                    "converted_code": converted or code,
                    "conversion_method": "llm",
                },
            )
            
        except Exception as e:
            logger.error(f"Code conversion failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                data={
                    "original_language": language,
                    "target_language": target_language,
                    "converted_code": code,  # 返回原始代码
                    "note": "Conversion failed, returned original",
                },
            )

    async def _generate_code(
        self,
        options: dict,
    ) -> ToolResult:
        """生成代码 - 使用 LLM"""
        prompt = options.get("prompt", "")
        language = options.get("language", "python")
        requirements = options.get("requirements", "")
        
        # 构建代码生成提示词
        full_prompt = f"""你是一位资深软件工程师。请根据以下需求生成{language}代码。

## 需求
{requirements}

## 详细说明
{prompt}

## 要求
1. 生成完整、可运行的代码
2. 包含必要的导入语句
3. 包含详细的注释和文档字符串
4. 遵循{language}最佳实践
5. 包含错误处理
6. 考虑边界情况

## 输出格式
只提供代码，不要其他文字。"""

        try:
            # 调用 LLM 生成代码
            from ..agents.llm_helper import get_coder_llm
            llm = get_coder_llm()
            
            generated = await llm.generate(
                prompt=full_prompt,
                system_prompt=f"你是一位资深{language}软件工程师。请生成完整、可运行的代码。",
            )
            
            # 清理可能的 markdown 标记
            if generated:
                generated = generated.replace(f"```{language}", "").replace("```", "").strip()
            
            logger.info(
                "Code generation complete",
                language=language,
                length=len(generated) if generated else 0,
            )
            
            return ToolResult(
                success=True,
                data={
                    "generated_code": generated or "",
                    "language": language,
                    "generation_method": "llm",
                },
                metadata={
                    "prompt_length": len(prompt),
                    "requirements_length": len(requirements),
                },
            )
            
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
            )
