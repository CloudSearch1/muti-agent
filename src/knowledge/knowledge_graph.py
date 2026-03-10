"""
知识图谱模块

提供基础的实体识别和关系抽取功能。
"""

import re
import uuid
from typing import Any

import structlog

from ..llm.llm_provider import BaseProvider, get_llm
from .types import Document, Entity, Relation

logger = structlog.get_logger(__name__)

# 实体类型
ENTITY_TYPES = {
    "PERSON": "人物",
    "ORGANIZATION": "组织",
    "LOCATION": "地点",
    "DATE": "日期",
    "EVENT": "事件",
    "PRODUCT": "产品",
    "CONCEPT": "概念",
    "TECHNOLOGY": "技术",
}

# 关系类型
RELATION_TYPES = {
    "WORKS_FOR": "工作于",
    "LOCATED_IN": "位于",
    "PART_OF": "属于",
    "RELATED_TO": "相关",
    "CREATED_BY": "创建者",
    "USES": "使用",
    "DEVELOPED": "开发",
    "CONTAINS": "包含",
}


class KnowledgeGraph:
    """
    知识图谱

    提供基础的实体识别、关系抽取和图谱构建功能。

    Example:
        >>> kg = KnowledgeGraph()
        >>> entities = await kg.extract_entities(text)
        >>> relations = await kg.extract_relations(text)
        >>> graph = await kg.build_graph(documents)
    """

    def __init__(
        self,
        llm_provider: BaseProvider | None = None,
    ) -> None:
        """
        初始化知识图谱

        Args:
            llm_provider: LLM 提供者
        """
        self.llm_provider = llm_provider or get_llm()
        self.logger = logger.bind(component="knowledge_graph")

        # 存储实体和关系（内存中）
        self._entities: dict[str, Entity] = {}
        self._relations: dict[str, Relation] = {}

    async def extract_entities(
        self,
        text: str,
        entity_types: list[str] | None = None,
    ) -> list[Entity]:
        """
        提取实体

        Args:
            text: 输入文本
            entity_types: 实体类型列表（可选）

        Returns:
            实体列表
        """
        if not text or not text.strip():
            return []

        try:
            # 使用 LLM 提取实体
            prompt = self._build_entity_extraction_prompt(text, entity_types)

            response = await self.llm_provider.generate_json(
                prompt=prompt,
                temperature=0.1,
                max_tokens=1000,
            )

            # 解析响应
            entities = self._parse_entities(response)

            self.logger.debug(
                "Entities extracted",
                text_length=len(text),
                entities_count=len(entities),
            )

            return entities

        except Exception as e:
            self.logger.warning("Entity extraction failed", error=str(e))
            # 回退到简单模式
            return self._simple_entity_extraction(text)

    async def extract_relations(
        self,
        text: str,
        entities: list[Entity] | None = None,
    ) -> list[Relation]:
        """
        提取关系

        Args:
            text: 输入文本
            entities: 已识别的实体（可选）

        Returns:
            关系列表
        """
        if not text or not text.strip():
            return []

        try:
            # 如果没有提供实体，先提取
            if not entities:
                entities = await self.extract_entities(text)

            if not entities:
                return []

            # 使用 LLM 提取关系
            prompt = self._build_relation_extraction_prompt(text, entities)

            response = await self.llm_provider.generate_json(
                prompt=prompt,
                temperature=0.1,
                max_tokens=1000,
            )

            # 解析响应
            relations = self._parse_relations(response, entities)

            self.logger.debug(
                "Relations extracted",
                text_length=len(text),
                relations_count=len(relations),
            )

            return relations

        except Exception as e:
            self.logger.warning("Relation extraction failed", error=str(e))
            return []

    async def build_graph(
        self,
        documents: list[Document],
    ) -> dict[str, Any]:
        """
        构建知识图谱

        Args:
            documents: 文档列表

        Returns:
            图谱数据
        """
        all_entities: dict[str, Entity] = {}
        all_relations: list[Relation] = []

        for doc in documents:
            if not doc.content:
                continue

            try:
                # 提取实体
                entities = await self.extract_entities(doc.content)
                for entity in entities:
                    if entity.id not in all_entities:
                        all_entities[entity.id] = entity
                        self._entities[entity.id] = entity

                # 提取关系
                relations = await self.extract_relations(doc.content, entities)
                all_relations.extend(relations)
                for rel in relations:
                    self._relations[rel.id] = rel

            except Exception as e:
                self.logger.warning(
                    "Failed to process document",
                    document_id=doc.id,
                    error=str(e),
                )

        self.logger.info(
            "Knowledge graph built",
            total_entities=len(all_entities),
            total_relations=len(all_relations),
        )

        return self.get_graph_data()

    def get_graph_data(self) -> dict[str, Any]:
        """
        获取图谱数据（用于可视化）

        Returns:
            图谱数据 {nodes, edges}
        """
        nodes = []
        for entity in self._entities.values():
            nodes.append({
                "id": entity.id,
                "label": entity.name,
                "type": entity.entity_type,
                "description": entity.description,
            })

        edges = []
        for relation in self._relations.values():
            edges.append({
                "id": relation.id,
                "source": relation.source_id,
                "target": relation.target_id,
                "label": relation.relation_type,
                "description": relation.description,
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_entities": len(nodes),
                "total_relations": len(edges),
                "entity_types": self._count_by_type("entity"),
                "relation_types": self._count_by_type("relation"),
            },
        }

    def get_entity(self, entity_id: str) -> Entity | None:
        """获取实体"""
        return self._entities.get(entity_id)

    def get_relations_for_entity(self, entity_id: str) -> list[Relation]:
        """获取实体的所有关系"""
        return [
            r for r in self._relations.values()
            if r.source_id == entity_id or r.target_id == entity_id
        ]

    def search_entities(
        self,
        query: str,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> list[Entity]:
        """
        搜索实体

        Args:
            query: 搜索关键词
            entity_type: 实体类型过滤
            limit: 返回数量限制

        Returns:
            匹配的实体列表
        """
        results = []
        query_lower = query.lower()

        for entity in self._entities.values():
            # 名称匹配
            if query_lower in entity.name.lower():
                if entity_type is None or entity.entity_type == entity_type:
                    results.append(entity)
            # 描述匹配
            elif entity.description and query_lower in entity.description.lower():
                if entity_type is None or entity.entity_type == entity_type:
                    results.append(entity)

        return results[:limit]

    def clear(self) -> None:
        """清空图谱"""
        self._entities.clear()
        self._relations.clear()

    def _build_entity_extraction_prompt(
        self,
        text: str,
        entity_types: list[str] | None = None,
    ) -> str:
        """构建实体提取提示"""
        types_str = ", ".join(entity_types) if entity_types else "人物、组织、地点、事件、概念、技术"

        return f"""请从以下文本中提取实体。

文本:
{text[:2000]}

实体类型: {types_str}

请以 JSON 格式返回实体列表，格式如下:
{{
    "entities": [
        {{"name": "实体名称", "type": "实体类型", "description": "简短描述"}}
    ]
}}

只返回 JSON，不要有其他文字。"""

    def _build_relation_extraction_prompt(
        self,
        text: str,
        entities: list[Entity],
    ) -> str:
        """构建关系提取提示"""
        entity_names = [e.name for e in entities[:20]]  # 限制数量

        return f"""请从以下文本中提取实体之间的关系。

文本:
{text[:2000]}

已识别的实体: {', '.join(entity_names)}

常见关系类型: 工作于、位于、属于、相关、创建者、使用、开发、包含

请以 JSON 格式返回关系列表，格式如下:
{{
    "relations": [
        {{"source": "实体1名称", "target": "实体2名称", "type": "关系类型", "description": "简短描述"}}
    ]
}}

只返回 JSON，不要有其他文字。"""

    def _parse_entities(self, response: dict[str, Any]) -> list[Entity]:
        """解析实体响应"""
        entities = []

        entity_list = response.get("entities", [])
        if not entity_list and isinstance(response, list):
            entity_list = response

        for item in entity_list:
            if not isinstance(item, dict):
                continue

            name = item.get("name", "")
            if not name:
                continue

            entity = Entity(
                id=str(uuid.uuid4()),
                name=name,
                entity_type=item.get("type", "UNKNOWN"),
                description=item.get("description"),
            )
            entities.append(entity)

        return entities

    def _parse_relations(
        self,
        response: dict[str, Any],
        entities: list[Entity],
    ) -> list[Relation]:
        """解析关系响应"""
        relations = []
        entity_map = {e.name: e for e in entities}

        relation_list = response.get("relations", [])
        if not relation_list and isinstance(response, list):
            relation_list = response

        for item in relation_list:
            if not isinstance(item, dict):
                continue

            source_name = item.get("source", "")
            target_name = item.get("target", "")

            if not source_name or not target_name:
                continue

            source_entity = entity_map.get(source_name)
            target_entity = entity_map.get(target_name)

            if not source_entity or not target_entity:
                continue

            relation = Relation(
                id=str(uuid.uuid4()),
                source_id=source_entity.id,
                target_id=target_entity.id,
                relation_type=item.get("type", "RELATED_TO"),
                description=item.get("description"),
            )
            relations.append(relation)

        return relations

    def _simple_entity_extraction(self, text: str) -> list[Entity]:
        """简单的实体提取（基于规则）"""
        entities = []

        # 简单的模式匹配
        patterns = {
            "PERSON": r'[\u4e00-\u9fa5]{2,4}(?:说|表示|认为|指出|介绍)',
            "ORGANIZATION": r'[\u4e00-\u9fa5]+(?:公司|集团|组织|机构|部门)',
            "LOCATION": r'[\u4e00-\u9fa5]+(?:省|市|县|区|镇)',
            "DATE": r'\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2}',
        }

        for entity_type, pattern in patterns.items():
            matches = re.findall(pattern, text)
            seen = set()
            for match in matches:
                # 清理匹配结果
                name = re.sub(r'(说|表示|认为|指出|介绍|公司|集团|组织|机构|部门|省|市|县|区|镇)', '', match)
                if name and name not in seen:
                    seen.add(name)
                    entities.append(Entity(
                        id=str(uuid.uuid4()),
                        name=name,
                        entity_type=entity_type,
                    ))

        return entities

    def _count_by_type(self, target: str) -> dict[str, int]:
        """按类型统计"""
        if target == "entity":
            counts: dict[str, int] = {}
            for entity in self._entities.values():
                counts[entity.entity_type] = counts.get(entity.entity_type, 0) + 1
            return counts
        elif target == "relation":
            counts: dict[str, int] = {}
            for relation in self._relations.values():
                counts[relation.relation_type] = counts.get(relation.relation_type, 0) + 1
            return counts
        return {}
