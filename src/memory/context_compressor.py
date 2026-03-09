"""
上下文压缩模块

职责：智能压缩长上下文，保留关键信息

功能：
- 摘要压缩
- 关键信息提取
- 上下文窗口管理
- 增量更新
"""

import json
import re
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CompressionStrategy:
    """压缩策略枚举"""
    SUMMARY = "summary"  # 摘要压缩
    KEY_POINTS = "key_points"  # 关键点提取
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口
    HYBRID = "hybrid"  # 混合策略


class ContextWindow:
    """上下文窗口管理器"""

    def __init__(
        self,
        max_tokens: int = 4096,
        reserved_tokens: int = 512,
    ):
        """
        初始化上下文窗口

        Args:
            max_tokens: 最大 token 数
            reserved_tokens: 预留 token 数（用于系统提示等）
        """
        self.max_tokens = max_tokens
        self.reserved_tokens = reserved_tokens
        self.available_tokens = max_tokens - reserved_tokens
        self._current_usage = 0

    def estimate_tokens(self, text: str) -> int:
        """估算文本 token 数（简单估算：1 token ≈ 4 字符）"""
        return len(text) // 4 + 1

    def can_fit(self, text: str) -> bool:
        """检查文本是否可以放入窗口"""
        tokens = self.estimate_tokens(text)
        return self._current_usage + tokens <= self.available_tokens

    def add(self, text: str) -> bool:
        """添加文本到窗口"""
        tokens = self.estimate_tokens(text)
        if self._current_usage + tokens > self.available_tokens:
            return False
        self._current_usage += tokens
        return True

    def remove(self, text: str) -> None:
        """从窗口移除文本"""
        tokens = self.estimate_tokens(text)
        self._current_usage = max(0, self._current_usage - tokens)

    @property
    def usage_percent(self) -> float:
        """使用率百分比"""
        return (self._current_usage / self.available_tokens) * 100

    @property
    def remaining_tokens(self) -> int:
        """剩余可用 token 数"""
        return self.available_tokens - self._current_usage

    def reset(self) -> None:
        """重置窗口"""
        self._current_usage = 0


class ContextCompressor:
    """
    上下文压缩器

    提供多种压缩策略来处理长上下文
    """

    # 压缩阈值配置
    DEFAULT_COMPRESSION_RATIO = 0.5  # 压缩到 50%
    MIN_CONTENT_LENGTH = 100  # 最小压缩长度

    def __init__(
        self,
        strategy: str = CompressionStrategy.HYBRID,
        max_tokens: int = 4096,
        llm_provider=None,
    ):
        """
        初始化压缩器

        Args:
            strategy: 压缩策略
            max_tokens: 最大 token 数
            llm_provider: LLM 提供者（用于摘要压缩）
        """
        self.strategy = strategy
        self.max_tokens = max_tokens
        self.llm_provider = llm_provider
        self.context_window = ContextWindow(max_tokens=max_tokens)

        self.logger = logger.bind(
            component="context_compressor",
            strategy=strategy,
        )

        self.logger.info(
            "ContextCompressor initialized",
            strategy=strategy,
            max_tokens=max_tokens,
        )

    async def compress(
        self,
        content: str,
        target_ratio: float = DEFAULT_COMPRESSION_RATIO,
    ) -> dict[str, Any]:
        """
        压缩内容

        Args:
            content: 待压缩内容
            target_ratio: 目标压缩比例

        Returns:
            压缩结果
        """
        if len(content) < self.MIN_CONTENT_LENGTH:
            return {
                "compressed": content,
                "original_length": len(content),
                "compressed_length": len(content),
                "compression_ratio": 1.0,
                "strategy": "none",
            }

        start_time = datetime.now()

        if self.strategy == CompressionStrategy.SUMMARY:
            result = await self._compress_summary(content, target_ratio)
        elif self.strategy == CompressionStrategy.KEY_POINTS:
            result = await self._compress_key_points(content, target_ratio)
        elif self.strategy == CompressionStrategy.SLIDING_WINDOW:
            result = self._compress_sliding_window(content, target_ratio)
        else:
            result = await self._compress_hybrid(content, target_ratio)

        result["processing_time_ms"] = (datetime.now() - start_time).total_seconds() * 1000
        return result

    async def _compress_summary(
        self,
        content: str,
        target_ratio: float,
    ) -> dict[str, Any]:
        """摘要压缩"""
        if not self.llm_provider:
            # 没有 LLM，使用简单截断
            return self._simple_truncate(content, target_ratio)

        try:
            target_length = int(len(content) * target_ratio)

            prompt = f"""请将以下内容压缩为摘要，保留所有重要信息。

原始内容：
{content}

要求：
1. 摘要长度不超过 {target_length} 字符
2. 保留关键信息、数据、结论
3. 使用简洁的语言
4. 不要添加原文没有的信息

请直接输出摘要："""

            summary = await self.llm_provider.generate(prompt)

            return {
                "compressed": summary,
                "original_length": len(content),
                "compressed_length": len(summary),
                "compression_ratio": len(summary) / len(content) if content else 0,
                "strategy": "summary",
            }
        except Exception as e:
            self.logger.error("Summary compression failed", error=str(e))
            return self._simple_truncate(content, target_ratio)

    async def _compress_key_points(
        self,
        content: str,
        target_ratio: float,
    ) -> dict[str, Any]:
        """关键点提取"""
        if not self.llm_provider:
            return self._extract_key_points_simple(content, target_ratio)

        try:
            target_length = int(len(content) * target_ratio)

            prompt = f"""请从以下内容中提取关键点。

原始内容：
{content}

要求：
1. 提取最重要的 3-5 个关键点
2. 每个关键点一行，使用 "- " 开头
3. 总长度不超过 {target_length} 字符
4. 保留具体的数据和结论

请直接输出关键点："""

            key_points = await self.llm_provider.generate(prompt)

            return {
                "compressed": key_points,
                "original_length": len(content),
                "compressed_length": len(key_points),
                "compression_ratio": len(key_points) / len(content) if content else 0,
                "strategy": "key_points",
            }
        except Exception as e:
            self.logger.error("Key points extraction failed", error=str(e))
            return self._extract_key_points_simple(content, target_ratio)

    def _compress_sliding_window(
        self,
        content: str,
        target_ratio: float,
    ) -> dict[str, Any]:
        """滑动窗口压缩"""
        target_length = int(len(content) * target_ratio)

        # 保留开头和结尾
        head_length = target_length // 3
        tail_length = target_length - head_length

        head = content[:head_length]
        tail = content[-tail_length:]

        compressed = f"{head}\n\n... [内容已压缩] ...\n\n{tail}"

        return {
            "compressed": compressed,
            "original_length": len(content),
            "compressed_length": len(compressed),
            "compression_ratio": len(compressed) / len(content) if content else 0,
            "strategy": "sliding_window",
        }

    async def _compress_hybrid(
        self,
        content: str,
        target_ratio: float,
    ) -> dict[str, Any]:
        """混合压缩策略"""
        # 根据内容长度选择最佳策略
        if len(content) < 500:
            # 短内容：简单截断
            return self._simple_truncate(content, target_ratio)
        elif len(content) < 2000:
            # 中等内容：关键点提取
            return await self._compress_key_points(content, target_ratio)
        else:
            # 长内容：摘要压缩 + 滑动窗口
            summary_result = await self._compress_summary(content, target_ratio * 1.2)
            if summary_result["compressed_length"] > len(content) * target_ratio:
                # 如果摘要仍然太长，再用滑动窗口
                return self._compress_sliding_window(
                    summary_result["compressed"],
                    target_ratio / 1.2,
                )
            return summary_result

    def _simple_truncate(
        self,
        content: str,
        target_ratio: float,
    ) -> dict[str, Any]:
        """简单截断"""
        target_length = int(len(content) * target_ratio)
        truncated = content[:target_length]

        return {
            "compressed": truncated + "...",
            "original_length": len(content),
            "compressed_length": len(truncated) + 3,
            "compression_ratio": (len(truncated) + 3) / len(content) if content else 0,
            "strategy": "truncate",
        }

    def _extract_key_points_simple(
        self,
        content: str,
        target_ratio: float,
    ) -> dict[str, Any]:
        """简单关键点提取（不使用 LLM）"""
        # 提取包含关键词的句子
        keywords = ["重要", "关键", "结论", "结果", "注意", "必须", "需要", "问题", "方案"]

        sentences = re.split(r'[。！？\n]', content)
        key_sentences = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            for keyword in keywords:
                if keyword in sentence:
                    key_sentences.append(sentence)
                    break

        # 如果关键句太多，只保留前面的
        target_length = int(len(content) * target_ratio)
        result_sentences = []
        current_length = 0

        for sentence in key_sentences:
            if current_length + len(sentence) > target_length:
                break
            result_sentences.append(sentence)
            current_length += len(sentence)

        compressed = "\n".join(f"- {s}" for s in result_sentences)

        return {
            "compressed": compressed,
            "original_length": len(content),
            "compressed_length": len(compressed),
            "compression_ratio": len(compressed) / len(content) if content else 0,
            "strategy": "key_points_simple",
        }

    async def compress_conversation(
        self,
        messages: list[dict[str, str]],
        keep_recent: int = 2,
    ) -> list[dict[str, str]]:
        """
        压缩对话历史

        Args:
            messages: 消息列表
            keep_recent: 保留最近 N 条消息不压缩

        Returns:
            压缩后的消息列表
        """
        if len(messages) <= keep_recent:
            return messages

        # 分离需要压缩的消息
        to_compress = messages[:-keep_recent]
        recent = messages[-keep_recent:]

        # 合并需要压缩的消息
        combined_content = "\n\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in to_compress
        )

        # 压缩合并内容
        compressed_result = await self.compress(combined_content, target_ratio=0.3)

        # 创建摘要消息
        summary_message = {
            "role": "system",
            "content": f"[历史对话摘要]\n{compressed_result['compressed']}",
        }

        return [summary_message] + recent

    def get_compression_stats(self) -> dict[str, Any]:
        """获取压缩统计信息"""
        return {
            "strategy": self.strategy,
            "max_tokens": self.max_tokens,
            "context_window_usage": self.context_window.usage_percent,
            "remaining_tokens": self.context_window.remaining_tokens,
        }


class IncrementalCompressor(ContextCompressor):
    """
    增量压缩器

    支持增量更新和差异压缩
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._compressed_cache: dict[str, str] = {}
        self._original_cache: dict[str, str] = {}

    async def update_content(
        self,
        content_id: str,
        new_content: str,
    ) -> dict[str, Any]:
        """
        更新内容（增量压缩）

        Args:
            content_id: 内容 ID
            new_content: 新内容

        Returns:
            压缩结果
        """
        old_content = self._original_cache.get(content_id, "")

        if not old_content:
            # 首次压缩
            result = await self.compress(new_content)
            self._original_cache[content_id] = new_content
            self._compressed_cache[content_id] = result["compressed"]
            result["changed"] = True
            return result

        # 检测变化
        if new_content == old_content:
            return {
                "compressed": self._compressed_cache[content_id],
                "original_length": len(old_content),
                "compressed_length": len(self._compressed_cache[content_id]),
                "strategy": "cached",
                "changed": False,
            }

        # 检测新增部分
        if new_content.startswith(old_content):
            # 只有新增
            added_content = new_content[len(old_content):]
            added_result = await self.compress(added_content, target_ratio=0.3)

            compressed = f"{self._compressed_cache[content_id]}\n\n[新增内容]\n{added_result['compressed']}"

            self._original_cache[content_id] = new_content
            self._compressed_cache[content_id] = compressed

            return {
                "compressed": compressed,
                "original_length": len(new_content),
                "compressed_length": len(compressed),
                "strategy": "incremental_add",
                "changed": True,
            }

        # 完全重新压缩
        result = await self.compress(new_content)
        self._original_cache[content_id] = new_content
        self._compressed_cache[content_id] = result["compressed"]
        result["changed"] = True
        return result

    def clear_cache(self) -> None:
        """清空缓存"""
        self._compressed_cache.clear()
        self._original_cache.clear()


# 便捷函数
def create_compressor(
    strategy: str = CompressionStrategy.HYBRID,
    **kwargs,
) -> ContextCompressor:
    """
    创建上下文压缩器

    Args:
        strategy: 压缩策略
        **kwargs: 其他配置参数

    Returns:
        ContextCompressor 实例
    """
    return ContextCompressor(strategy=strategy, **kwargs)