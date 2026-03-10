"""
Pi 结果聚合器

职责：
- 结果收集
- 质量评估
- 冲突解决
- 结果聚合

版本: 1.0.0
"""

from datetime import datetime
from typing import Any

import structlog

from .types import (
    ConflictResolution,
    PiTaskInfo,
    ResultEvaluation,
)

logger = structlog.get_logger(__name__)


class ResultEvaluator:
    """
    结果评估器

    评估任务执行结果的质量

    使用方式:
        evaluator = ResultEvaluator()
        evaluation = await evaluator.evaluate(task, result)
    """

    def __init__(self):
        """初始化结果评估器"""
        self._evaluations: dict[str, ResultEvaluation] = {}

        logger.info("ResultEvaluator initialized")

    async def evaluate(
        self,
        task: PiTaskInfo,
        result: dict[str, Any],
        agent_id: str,
    ) -> ResultEvaluation:
        """
        评估任务结果

        Args:
            task: 任务信息
            result: 任务结果
            agent_id: Agent ID

        Returns:
            评估结果
        """
        # 计算各项指标
        quality_score = await self._calculate_quality_score(task, result)
        completeness = self._calculate_completeness(task, result)
        accuracy = await self._calculate_accuracy(task, result)

        # 识别问题
        issues = self._identify_issues(result, quality_score)

        # 生成改进建议
        suggestions = self._generate_suggestions(issues, quality_score)

        # 创建评估结果
        evaluation = ResultEvaluation(
            task_id=task.id,
            agent_id=agent_id,
            quality_score=quality_score,
            completeness=completeness,
            accuracy=accuracy,
            issues=issues,
            suggestions=suggestions,
        )

        # 存储评估结果
        self._evaluations[task.id] = evaluation

        logger.info(
            "Task result evaluated",
            task_id=task.id,
            quality_score=quality_score,
            completeness=completeness,
            accuracy=accuracy,
        )

        return evaluation

    async def _calculate_quality_score(
        self,
        task: PiTaskInfo,
        result: dict[str, Any],
    ) -> float:
        """
        计算质量分数

        基于以下指标：
        1. 输出结构完整性
        2. 错误处理
        3. 代码/内容质量
        """
        score = 0.0

        # 检查结果是否为空
        if not result:
            return 0.0

        # 结构完整性 (40%)
        if isinstance(result, dict):
            expected_keys = ["status", "output", "data"]
            present_keys = sum(1 for k in expected_keys if k in result)
            score += (present_keys / len(expected_keys)) * 40
        else:
            score += 20  # 非字典结果给一半分

        # 错误处理 (30%)
        if "error" not in result:
            score += 30
        elif result.get("error") is None:
            score += 30

        # 内容质量 (30%)
        content = result.get("output") or result.get("data") or result
        if content:
            if isinstance(content, str):
                score += min(30, len(content) / 10)  # 基于长度
            elif isinstance(content, (dict, list)):
                score += 30  # 结构化内容满分
            else:
                score += 15

        return min(100.0, score)

    def _calculate_completeness(
        self,
        task: PiTaskInfo,
        result: dict[str, Any],
    ) -> float:
        """
        计算完整度

        检查结果是否满足任务需求
        """
        if not result:
            return 0.0

        # 检查基本输出
        if isinstance(result, dict):
            completeness = 0.0

            # 状态字段
            if "status" in result:
                completeness += 0.3

            # 输出内容
            if result.get("output") or result.get("data"):
                completeness += 0.5

            # 元数据
            if result.get("metadata"):
                completeness += 0.2

            return min(1.0, completeness)

        # 非字典结果
        return 0.5 if result else 0.0

    async def _calculate_accuracy(
        self,
        task: PiTaskInfo,
        result: dict[str, Any],
    ) -> float:
        """
        计算准确度

        验证结果是否正确
        """
        if not result:
            return 0.0

        # 基本检查
        accuracy = 0.5  # 默认给一半分

        # 检查状态
        if isinstance(result, dict):
            if result.get("status") in ["success", "completed", "done"]:
                accuracy += 0.3
            elif result.get("status") in ["error", "failed"]:
                accuracy -= 0.3

            # 检查是否有错误信息
            if result.get("error"):
                accuracy -= 0.2

        return max(0.0, min(1.0, accuracy))

    def _identify_issues(
        self,
        result: dict[str, Any],
        quality_score: float,
    ) -> list[str]:
        """识别问题"""
        issues = []

        if quality_score < 50:
            issues.append("Quality score is below acceptable threshold")

        if not result:
            issues.append("Empty result")
            return issues

        if isinstance(result, dict):
            if "error" in result and result["error"]:
                issues.append(f"Error in result: {result['error']}")

            if not result.get("output") and not result.get("data"):
                issues.append("No output data in result")

        return issues

    def _generate_suggestions(
        self,
        issues: list[str],
        quality_score: float,
    ) -> list[str]:
        """生成改进建议"""
        suggestions = []

        if quality_score < 50:
            suggestions.append("Consider reviewing the task requirements and implementation")

        if "Empty result" in issues:
            suggestions.append("Ensure the agent produces output for this task type")

        if any("Error" in issue for issue in issues):
            suggestions.append("Improve error handling in the agent implementation")

        if "No output data in result" in issues:
            suggestions.append("Add structured output data to the result")

        return suggestions

    def get_evaluation(self, task_id: str) -> ResultEvaluation | None:
        """获取评估结果"""
        return self._evaluations.get(task_id)


class ConflictResolver:
    """
    冲突解决器

    处理多个 Agent 执行相同任务产生的结果冲突

    使用方式:
        resolver = ConflictResolver()
        resolution = await resolver.resolve(task_id, results)
    """

    def __init__(self):
        """初始化冲突解决器"""
        self._resolutions: dict[str, ConflictResolution] = {}

        logger.info("ConflictResolver initialized")

    async def resolve(
        self,
        task_id: str,
        results: list[dict[str, Any]],
        strategy: str = "majority",
    ) -> ConflictResolution:
        """
        解决结果冲突

        Args:
            task_id: 任务 ID
            results: 冲突的结果列表
            strategy: 解决策略

        Returns:
            冲突解决结果
        """
        if not results:
            return ConflictResolution(
                task_id=task_id,
                resolution_strategy=strategy,
                final_result={},
            )

        # 根据策略选择最终结果
        if strategy == "majority":
            final_result = await self._resolve_by_majority(results)
        elif strategy == "best_quality":
            final_result = await self._resolve_by_quality(results)
        elif strategy == "merge":
            final_result = await self._resolve_by_merge(results)
        else:
            final_result = results[0]  # 默认取第一个

        # 创建解决记录
        resolution = ConflictResolution(
            task_id=task_id,
            conflicting_results=results,
            resolution_strategy=strategy,
            final_result=final_result,
        )

        # 存储解决结果
        self._resolutions[task_id] = resolution

        logger.info(
            "Conflict resolved",
            task_id=task_id,
            strategy=strategy,
            results_count=len(results),
        )

        return resolution

    async def _resolve_by_majority(
        self,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """多数投票解决"""
        if len(results) == 1:
            return results[0]

        # 统计结果相似度
        result_counts: dict[str, int] = {}
        result_map: dict[str, dict[str, Any]] = {}

        for result in results:
            # 简化结果用于比较
            key = str(sorted(result.items()) if isinstance(result, dict) else result)
            result_counts[key] = result_counts.get(key, 0) + 1
            result_map[key] = result

        # 选择出现次数最多的
        max_count = max(result_counts.values())
        for key, count in result_counts.items():
            if count == max_count:
                return result_map[key]

        return results[0]

    async def _resolve_by_quality(
        self,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """选择质量最好的结果"""
        if len(results) == 1:
            return results[0]

        # 简单质量评分
        def get_quality_score(result: dict[str, Any]) -> float:
            if not isinstance(result, dict):
                return 0.0

            score = 0.0
            if "status" in result and result["status"] in ["success", "completed"]:
                score += 0.3
            if "output" in result or "data" in result:
                score += 0.4
            if "error" not in result or not result.get("error"):
                score += 0.3

            return score

        # 选择质量最高的
        best_result = max(results, key=get_quality_score)
        return best_result

    async def _resolve_by_merge(
        self,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """合并结果"""
        if len(results) == 1:
            return results[0]

        merged: dict[str, Any] = {}

        for result in results:
            if isinstance(result, dict):
                for key, value in result.items():
                    if key not in merged:
                        merged[key] = value
                    elif isinstance(merged[key], dict) and isinstance(value, dict):
                        merged[key].update(value)
                    elif isinstance(merged[key], list) and isinstance(value, list):
                        merged[key].extend(value)

        return merged

    def get_resolution(self, task_id: str) -> ConflictResolution | None:
        """获取解决结果"""
        return self._resolutions.get(task_id)


class ResultAggregator:
    """
    结果聚合器

    收集、评估和聚合多个 Agent 的执行结果

    使用方式:
        aggregator = ResultAggregator()
        aggregator.collect(task_id, agent_id, result)
        final_result = await aggregator.aggregate(task_id)
    """

    def __init__(self):
        """初始化结果聚合器"""
        self._results: dict[str, list[dict[str, Any]]] = {}
        self._evaluator = ResultEvaluator()
        self._resolver = ConflictResolver()

        logger.info("ResultAggregator initialized")

    def collect(
        self,
        task_id: str,
        agent_id: str,
        result: dict[str, Any],
    ) -> None:
        """
        收集结果

        Args:
            task_id: 任务 ID
            agent_id: Agent ID
            result: 执行结果
        """
        if task_id not in self._results:
            self._results[task_id] = []

        self._results[task_id].append({
            "agent_id": agent_id,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        })

        logger.debug(
            "Result collected",
            task_id=task_id,
            agent_id=agent_id,
        )

    async def evaluate_all(
        self,
        task: PiTaskInfo,
    ) -> list[ResultEvaluation]:
        """
        评估所有结果

        Args:
            task: 任务信息

        Returns:
            评估结果列表
        """
        collected = self._results.get(task.id, [])
        evaluations = []

        for entry in collected:
            evaluation = await self._evaluator.evaluate(
                task,
                entry["result"],
                entry["agent_id"],
            )
            evaluations.append(evaluation)

        return evaluations

    async def aggregate(
        self,
        task: PiTaskInfo,
        strategy: str = "best_quality",
    ) -> dict[str, Any]:
        """
        聚合结果

        Args:
            task: 任务信息
            strategy: 聚合策略

        Returns:
            聚合后的最终结果
        """
        collected = self._results.get(task.id, [])

        if not collected:
            logger.warning("No results to aggregate", task_id=task.id)
            return {"status": "no_results", "task_id": task.id}

        # 如果只有一个结果，直接返回
        if len(collected) == 1:
            return collected[0]["result"]

        # 评估所有结果
        evaluations = await self.evaluate_all(task)

        # 检查是否有冲突
        results = [c["result"] for c in collected]
        has_conflict = self._check_conflict(results)

        if has_conflict:
            # 解决冲突
            resolution = await self._resolver.resolve(task.id, results, strategy)
            final_result = resolution.final_result
        else:
            # 无冲突，选择最佳结果
            best_idx = max(
                range(len(evaluations)),
                key=lambda i: evaluations[i].quality_score,
            )
            final_result = results[best_idx]

        # 添加聚合信息
        final_result["_aggregation"] = {
            "total_results": len(collected),
            "had_conflict": has_conflict,
            "strategy": strategy,
            "best_quality_score": max(e.quality_score for e in evaluations),
            "avg_quality_score": sum(e.quality_score for e in evaluations) / len(evaluations),
        }

        logger.info(
            "Results aggregated",
            task_id=task.id,
            total_results=len(collected),
            had_conflict=has_conflict,
        )

        return final_result

    def _check_conflict(self, results: list[dict[str, Any]]) -> bool:
        """检查结果是否存在冲突"""
        if len(results) <= 1:
            return False

        # 简单检查：结果是否完全相同
        first = results[0]
        for result in results[1:]:
            if result != first:
                return True

        return False

    def get_collected_results(self, task_id: str) -> list[dict[str, Any]]:
        """获取收集的结果"""
        return self._results.get(task_id, [])

    def clear_results(self, task_id: str) -> int:
        """
        清除结果

        Args:
            task_id: 任务 ID

        Returns:
            清除的结果数
        """
        if task_id in self._results:
            count = len(self._results[task_id])
            del self._results[task_id]
            return count
        return 0

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        total_tasks = len(self._results)
        total_results = sum(len(r) for r in self._results.values())

        return {
            "total_tasks": total_tasks,
            "total_results": total_results,
            "evaluations": len(self._evaluator._evaluations),
            "resolutions": len(self._resolver._resolutions),
        }


# 全局单例
_result_aggregator: ResultAggregator | None = None


def get_result_aggregator() -> ResultAggregator:
    """获取结果聚合器单例"""
    global _result_aggregator
    if _result_aggregator is None:
        _result_aggregator = ResultAggregator()
    return _result_aggregator


__all__ = [
    "ResultEvaluator",
    "ConflictResolver",
    "ResultAggregator",
    "get_result_aggregator",
]
