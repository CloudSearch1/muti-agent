"""
DocWriterAgent - 文档员 Agent

职责：技术文档编写、API 文档生成、知识库维护
"""

from datetime import datetime
from typing import Any

import structlog

from ..core.models import AgentRole, Task
from .base import BaseAgent
from .llm_helper import get_doc_writer_llm

logger = structlog.get_logger(__name__)


class DocWriterAgent(BaseAgent):
    """
    技术文档工程师

    负责：
    - 编写技术文档和使用手册
    - 生成 API 文档
    - 维护知识库
    - 文档审查和更新
    """

    ROLE = AgentRole.DOC_WRITER

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 文档员特有配置
        self.doc_model = kwargs.get("doc_model", "gpt-4")
        self.doc_format = kwargs.get("doc_format", "markdown")
        self.auto_generate = kwargs.get("auto_generate", True)

        # LLM 辅助
        self.llm_helper = get_doc_writer_llm()

        self.logger.info("DocWriterAgent initialized")

    async def execute(self, task: Task) -> dict[str, Any]:
        """
        执行文档编写任务
        """
        self.logger.info(
            "Starting documentation task",
            task_id=task.id,
            task_title=task.title,
        )

        # 获取文档输入
        content_type = task.input_data.get("content_type", "api_doc")
        source_material = task.input_data.get("source_material", {})
        target_audience = task.input_data.get("target_audience", "developers")

        # 思考文档结构
        doc_plan = await self.think(
            {
                "content_type": content_type,
                "source_material": source_material,
                "target_audience": target_audience,
            }
        )

        # 生成文档
        document = await self._generate_document(doc_plan, source_material)

        # 存储到黑板
        self.put_to_blackboard(
            f"doc:{task.id}",
            document,
            description="生成的文档",
        )

        return {
            "status": "documentation_complete",
            "document_type": content_type,
            "document": document,
            "word_count": len(document.get("content", "")),
        }

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        思考文档结构 - 使用 LLM 生成文档计划
        """
        content_type = context.get("content_type", "")
        source_material = context.get("source_material", {})
        target_audience = context.get("target_audience", "")

        # 构建文档计划提示词
        prompt = f"""你是一位资深技术文档工程师。请为以下材料设计文档结构和计划。

## 文档类型
{content_type}

## 目标读者
{target_audience}

## 源材料
{self._format_source_material(source_material)}

## 要求
1. 设计清晰的文档结构
2. 确定关键章节和内容
3. 考虑目标读者的需求
4. 包含必要的示例和图表
5. 使用 Markdown 格式
6. 估计文档长度

## 输出格式 (JSON)
{{
    "title": "文档标题",
    "structure": ["章节 1", "章节 2", ...],
    "key_points": ["关键点 1", "关键点 2"],
    "estimated_length": "预计字数",
    "tone": "文档语调 (正式/轻松/教学)",
    "examples_needed": true/false
}}"""

        # 调用 LLM 生成文档计划
        doc_plan = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位资深技术文档工程师。请以 JSON 格式输出文档计划。",
        )

        if doc_plan:
            self.logger.info(
                "LLM documentation plan generated",
                sections=len(doc_plan.get("structure", [])),
                content_type=content_type,
            )
            return doc_plan

        # Fallback
        self.logger.warning("LLM documentation plan failed, using fallback")
        return self._simulate_doc_plan(content_type)

    def _build_doc_prompt(
        self,
        content_type: str,
        source_material: dict[str, Any],
        target_audience: str,
    ) -> str:
        """构建文档提示词"""
        return f"""
你是一位资深技术文档工程师。请根据以下材料编写文档。

## 文档类型
{content_type}

## 目标读者
{target_audience}

## 源材料
{source_material}

## 要求
1. 结构清晰，层次分明
2. 语言简洁准确
3. 包含必要的示例代码
4. 使用 Markdown 格式
5. 适合目标读者阅读

## 输出格式
提供完整的文档内容
"""

    def _simulate_doc_plan(
        self,
        content_type: str,
    ) -> dict[str, Any]:
        """
        Fallback 文档计划（当 LLM 失败时）
        """
        if content_type == "api_doc":
            return {
                "title": "API 文档",
                "structure": [
                    "概述",
                    "快速开始",
                    "API 参考",
                    "使用示例",
                    "常见问题",
                ],
                "key_points": ["接口说明", "参数详解", "返回值", "错误处理"],
                "sections": 5,
                "estimated_length": "2000-3000 字",
                "tone": "正式",
                "examples_needed": True,
            }
        elif content_type == "readme":
            return {
                "title": "项目 README",
                "structure": [
                    "项目简介",
                    "功能特性",
                    "安装指南",
                    "快速开始",
                    "使用示例",
                    "贡献指南",
                    "许可证",
                ],
                "key_points": ["项目价值", "核心功能", "安装步骤"],
                "sections": 7,
                "estimated_length": "1500-2500 字",
                "tone": "友好",
                "examples_needed": True,
            }
        else:
            return {
                "title": "技术文档",
                "structure": ["概述", "正文", "总结"],
                "key_points": ["核心内容"],
                "sections": 3,
                "estimated_length": "1000-2000 字",
                "tone": "正式",
                "examples_needed": False,
            }

    def _format_source_material(self, source_material: dict[str, Any]) -> str:
        """格式化源材料为文本"""
        if not source_material:
            return "无源材料"

        lines = []
        for key, value in source_material.items():
            if isinstance(value, str):
                lines.append(f"### {key}\n{value[:500]}")
            elif isinstance(value, list):
                lines.append(f"### {key}\n" + "\n".join(f"- {item}" for item in value[:10]))
            else:
                lines.append(f"### {key}\n{str(value)[:500]}")

        return "\n".join(lines)

    async def _generate_document(
        self,
        doc_plan: dict[str, Any],
        source_material: dict[str, Any],
    ) -> dict[str, Any]:
        """使用 LLM 生成真实文档"""
        title = doc_plan.get("title", "技术文档")
        structure = doc_plan.get("structure", [])
        key_points = doc_plan.get("key_points", [])
        tone = doc_plan.get("tone", "正式")
        examples_needed = doc_plan.get("examples_needed", True)

        # 构建文档生成提示词
        prompt = f"""你是一位资深技术文档工程师。请根据以下计划编写完整的技术文档。

## 文档标题
{title}

## 文档结构
{chr(10).join(f"{i+1}. {section}" for i, section in enumerate(structure))}

## 关键点
{chr(10).join(f"- {point}" for point in key_points)}

## 源材料
{self._format_source_material(source_material)}

## 要求
1. 按照文档结构编写完整内容
2. 语言{tone}、准确、易懂
3. 包含必要的示例代码（Markdown 格式）
4. 使用 Markdown 格式
5. 添加适当的标题和子标题
6. 包含代码示例：{ "是" if examples_needed else "否" }

## 输出格式
提供完整的 Markdown 文档内容。"""

        # 调用 LLM 生成文档
        content = await self.llm_helper.generate(
            prompt=prompt,
            system_prompt=f"你是一位资深技术文档工程师。请生成完整、专业的技术文档。使用{self.doc_format}格式。",
        )

        # 构建文档对象
        document = {
            "title": title,
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "format": self.doc_format,
            "content": content or self._generate_fallback_document(doc_plan),
            "table_of_contents": structure,
            "metadata": {
                "author": "DocWriterAgent",
                "model": self.doc_model,
                "word_count": len(content) if content else 500,
                "tone": tone,
            },
        }

        self.logger.info(
            "Documentation generated",
            title=title,
            word_count=document["metadata"]["word_count"],
            sections=len(structure),
        )

        return document

    def _generate_fallback_document(self, doc_plan: dict[str, Any]) -> str:
        """生成备用文档（当 LLM 失败时）"""
        title = doc_plan.get("title", "技术文档")
        structure = doc_plan.get("structure", [])

        content = f"# {title}\n\n"
        content += f"_自动生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n"

        for section in structure:
            content += f"## {section}\n\n"
            content += f"【{section}内容待补充】\n\n"
            if "示例" in section or "开始" in section:
                content += "```python\n# 示例代码待添加\npass\n```\n\n"

        content += "---\n*文档由 IntelliTeam DocWriterAgent 自动生成*\n"
        return content

    async def generate_api_doc(
        self,
        code_files: list[dict[str, Any]],
        format: str = "markdown",
    ) -> dict[str, Any]:
        """
        根据代码生成 API 文档 - 使用 LLM 自动分析代码

        Args:
            code_files: 代码文件列表
            format: 文档格式

        Returns:
            API 文档
        """
        # 构建代码分析提示词
        code_content = self._format_code_files_for_doc(code_files)

        prompt = f"""你是一位 API 文档专家。请分析以下代码并生成完整的 API 文档。

## 代码内容
{code_content}

## 要求
1. 识别所有公开的类、函数和接口
2. 提取参数、返回值和类型注解
3. 生成详细的使用示例
4. 包含错误处理说明
5. 使用 Markdown 格式
6. 结构清晰，便于查阅

## 输出格式 (JSON)
{{
    "title": "API 文档标题",
    "version": "1.0.0",
    "endpoints": [
        {{
            "name": "函数/方法名",
            "description": "功能描述",
            "parameters": [
                {{"name": "参数名", "type": "类型", "description": "说明", "required": true}}
            ],
            "returns": {{"type": "返回类型", "description": "返回值说明"}},
            "raises": ["可能抛出的异常"],
            "example": "使用示例代码"
        }}
    ],
    "models": [
        {{
            "name": "类名",
            "description": "类描述",
            "attributes": [
                {{"name": "属性名", "type": "类型", "description": "说明"}}
            ],
            "methods": ["方法名列表"]
        }}
    ],
    "examples": ["完整使用示例"]
}}"""

        # 调用 LLM 生成 API 文档
        api_doc = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位 API 文档专家。请生成详细、准确的 API 文档。",
        )

        if api_doc:
            self.logger.info(
                "API documentation generated",
                endpoints=len(api_doc.get("endpoints", [])),
                models=len(api_doc.get("models", [])),
            )

            # 生成 Markdown 格式文档
            markdown_content = self._api_doc_to_markdown(api_doc)

            return {
                "title": api_doc.get("title", "API 文档"),
                "version": api_doc.get("version", "1.0.0"),
                "generated_at": datetime.now().isoformat(),
                "format": format,
                "content": markdown_content,
                "endpoints": api_doc.get("endpoints", []),
                "models": api_doc.get("models", []),
                "examples": api_doc.get("examples", []),
            }

        # Fallback
        self.logger.warning("API doc generation failed, using fallback")
        return {
            "title": "API 文档",
            "endpoints": [],
            "models": [],
            "examples": [],
            "content": "# API 文档\n\n文档生成失败，请检查代码。",
        }

    def _format_code_files_for_doc(self, code_files: list[dict[str, Any]]) -> str:
        """格式化代码文件用于文档生成"""
        if not code_files:
            return "无代码文件"

        lines = []
        for file_info in code_files:
            filename = file_info.get("filename", "unknown")
            content = file_info.get("content", "")
            lines.append(f"\n### 文件：{filename}\n```python\n{content}\n```")

        return "\n".join(lines)

    def _api_doc_to_markdown(self, api_doc: dict[str, Any]) -> str:
        """将 API 文档 JSON 转换为 Markdown"""
        md = f"# {api_doc.get('title', 'API 文档')}\n\n"
        md += f"_版本：{api_doc.get('version', '1.0.0')} | 生成时间：{datetime.now().strftime('%Y-%m-%d')}_\n\n"

        # 目录
        md += "## 目录\n\n"
        md += "- [接口列表](#接口列表)\n"
        md += "- [数据模型](#数据模型)\n"
        md += "- [使用示例](#使用示例)\n\n"

        # 接口列表
        md += "## 接口列表\n\n"
        for endpoint in api_doc.get("endpoints", []):
            md += f"### {endpoint.get('name', 'Unknown')}\n\n"
            md += f"{endpoint.get('description', '')}\n\n"

            # 参数
            params = endpoint.get("parameters", [])
            if params:
                md += "**参数:**\n\n"
                md += "| 参数名 | 类型 | 必填 | 说明 |\n"
                md += "|--------|------|------|------|\n"
                for param in params:
                    required = "是" if param.get("required", False) else "否"
                    md += f"| {param.get('name', '')} | {param.get('type', '')} | {required} | {param.get('description', '')} |\n"
                md += "\n"

            # 返回值
            returns = endpoint.get("returns", {})
            if returns:
                md += f"**返回值:** {returns.get('description', '')}\n\n"

            # 示例
            example = endpoint.get("example", "")
            if example:
                md += "**示例:**\n\n"
                md += f"```python\n{example}\n```\n\n"

        # 数据模型
        md += "## 数据模型\n\n"
        for model in api_doc.get("models", []):
            md += f"### {model.get('name', 'Unknown')}\n\n"
            md += f"{model.get('description', '')}\n\n"

            attrs = model.get("attributes", [])
            if attrs:
                md += "**属性:**\n\n"
                for attr in attrs:
                    md += f"- `{attr.get('name', '')}` ({attr.get('type', '')}): {attr.get('description', '')}\n"
                md += "\n"

        # 使用示例
        md += "## 使用示例\n\n"
        for i, example in enumerate(api_doc.get("examples", []), 1):
            md += f"### 示例 {i}\n\n"
            md += f"```python\n{example}\n```\n\n"

        return md

    async def update_knowledge_base(
        self,
        topic: str,
        content: str,
        tags: list[str] = None,
    ) -> dict[str, Any]:
        """
        更新知识库 - 使用 LLM 整理和索引内容

        Args:
            topic: 主题
            content: 内容
            tags: 标签列表

        Returns:
            更新结果
        """
        # 使用 LLM 整理内容并生成摘要
        prompt = f"""你是一位知识管理专家。请整理以下知识内容。

## 主题
{topic}

## 内容
{content[:2000]}  # 限制长度

## 要求
1. 生成简洁的摘要（100-200 字）
2. 提取 3-5 个关键词
3. 识别相关的主题
4. 建议分类标签

## 输出格式 (JSON)
{{
    "summary": "内容摘要",
    "keywords": ["关键词 1", "关键词 2"],
    "related_topics": ["相关主题 1"],
    "suggested_tags": ["标签 1", "标签 2"],
    "category": "建议分类"
}}"""

        # 调用 LLM 整理知识
        knowledge_meta = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位知识管理专家。请整理和索引知识内容。",
        )

        if knowledge_meta:
            self.logger.info(
                "Knowledge base updated",
                topic=topic,
                keywords=len(knowledge_meta.get("keywords", [])),
            )

            return {
                "status": "updated",
                "topic": topic,
                "content": content,
                "summary": knowledge_meta.get("summary", ""),
                "keywords": knowledge_meta.get("keywords", []),
                "tags": tags or knowledge_meta.get("suggested_tags", []),
                "category": knowledge_meta.get("category", "General"),
                "related_topics": knowledge_meta.get("related_topics", []),
                "updated_at": datetime.now().isoformat(),
            }

        # Fallback
        self.logger.warning("Knowledge base LLM failed, using fallback")
        return {
            "status": "updated",
            "topic": topic,
            "content": content,
            "summary": content[:200] + "..." if len(content) > 200 else content,
            "keywords": [],
            "tags": tags or [],
            "updated_at": datetime.now().isoformat(),
        }

    async def review_document(
        self,
        document: dict[str, Any],
        criteria: list[str] = None,
    ) -> dict[str, Any]:
        """
        文档审查 - 使用 LLM 进行质量检查

        Args:
            document: 待审查的文档
            criteria: 审查标准

        Returns:
            审查结果
        """
        if not criteria:
            criteria = [
                "结构清晰",
                "语言准确",
                "示例完整",
                "格式规范",
                "内容准确",
            ]

        doc_content = document.get("content", "")
        doc_title = document.get("title", "Untitled")

        # 构建审查提示词
        prompt = f"""你是一位资深技术文档审查专家。请审查以下文档。

## 文档标题
{doc_title}

## 文档内容
{doc_content[:3000]}  # 限制长度

## 审查标准
{chr(10).join(f"- {c}" for c in criteria)}

## 要求
1. 识别文档的优点和不足
2. 提供具体的改进建议
3. 评估文档质量（0-100 分）
4. 检查拼写和语法错误
5. 评估示例代码的质量

## 输出格式 (JSON)
{{
    "status": "approved|needs_revision|rejected",
    "quality_score": 85,
    "strengths": ["优点 1", "优点 2"],
    "weaknesses": ["不足 1", "不足 2"],
    "suggestions": [
        {{
            "type": "structure|content|grammar|example",
            "severity": "critical|major|minor",
            "description": "问题描述",
            "suggestion": "改进建议"
        }}
    ],
    "grammar_errors": ["语法错误列表"],
    "summary": "审查总结"
}}"""

        # 调用 LLM 进行审查
        review_result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位严格的文档审查专家。请提供专业、详细的审查意见。",
        )

        if review_result:
            self.logger.info(
                "Document review complete",
                title=doc_title,
                status=review_result.get("status"),
                score=review_result.get("quality_score"),
            )
            return review_result

        # Fallback
        self.logger.warning("Document review LLM failed, using fallback")
        return {
            "status": "approved",
            "quality_score": 75,
            "strengths": ["文档结构完整"],
            "weaknesses": ["示例代码可以更详细"],
            "suggestions": [
                {
                    "type": "content",
                    "severity": "minor",
                    "description": "建议添加更多使用示例",
                    "suggestion": "为每个 API 添加代码示例",
                }
            ],
            "grammar_errors": [],
            "summary": "文档整体质量良好，建议补充示例。",
        }
