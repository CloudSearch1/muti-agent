"""
流式响应模块

支持 LLM 流式输出，降低感知延迟
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


class StreamingGenerator:
    """
    流式生成器

    功能:
    - 支持异步流式输出
    - SSE (Server-Sent Events) 格式
    - 进度追踪
    """

    def __init__(self):
        self._total_chunks = 0
        self._sent_chunks = 0

    async def generate_stream(
        self,
        llm_generator: AsyncIterator[str],
        send_progress: bool = True,
    ) -> AsyncIterator[str]:
        """
        生成流式响应

        Args:
            llm_generator: LLM 流式生成器
            send_progress: 是否发送进度

        Yields:
            SSE 格式的数据块
        """
        self._total_chunks = 0
        self._sent_chunks = 0

        try:
            # 发送开始事件
            if send_progress:
                yield self._format_sse("start", {"status": "started"})

            # 流式输出
            async for chunk in llm_generator:
                self._total_chunks += 1
                self._sent_chunks += 1

                # 发送数据块
                yield self._format_sse("content", {"content": chunk})

                # 发送进度（每 10 个块）
                if send_progress and self._sent_chunks % 10 == 0:
                    yield self._format_sse("progress", {
                        "chunks_sent": self._sent_chunks,
                    })

            # 发送结束事件
            if send_progress:
                yield self._format_sse("end", {
                    "status": "completed",
                    "total_chunks": self._total_chunks,
                })

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield self._format_sse("error", {
                "status": "error",
                "message": str(e),
            })

    def _format_sse(self, event: str, data: Any) -> str:
        """格式化 SSE 消息"""
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "total_chunks": self._total_chunks,
            "sent_chunks": self._sent_chunks,
        }


class LLMStreamAdapter:
    """
    LLM 流式适配器

    将普通 LLM 调用转换为流式输出
    """

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    async def stream_generate(
        self,
        prompt: str,
        model: str = "default",
        chunk_size: int = 10,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        流式生成

        Args:
            prompt: 提示词
            model: 模型名称
            chunk_size: 块大小（字符数）
            **kwargs: 其他参数

        Yields:
            文本块
        """
        # 检查 LLM 是否支持流式
        if hasattr(self.llm_provider, 'generate_stream'):
            async for chunk in self.llm_provider.generate_stream(prompt, **kwargs):
                yield chunk
        else:
            # 降级：完整生成后分块
            full_response = await self.llm_provider.generate(prompt, **kwargs)

            # 分块发送
            for i in range(0, len(full_response), chunk_size):
                chunk = full_response[i:i + chunk_size]
                yield chunk
                await asyncio.sleep(0.01)  # 模拟流式延迟


def create_streaming_endpoint(
    app: FastAPI,
    path: str,
    handler: Callable,
):
    """
    创建流式 API 端点

    用法:
        async def generate_handler(prompt: str):
            llm = get_llm()
            async for chunk in llm.generate_stream(prompt):
                yield chunk

        create_streaming_endpoint(app, "/api/v1/generate/stream", generate_handler)
    """
    @app.get(path)
    async def streaming_endpoint(prompt: str):
        generator = StreamingGenerator()

        async def stream_wrapper():
            async for chunk in handler(prompt):
                yield generator._format_sse("content", {"content": chunk})

        return StreamingResponse(
            stream_wrapper(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Nginx 不缓冲
            },
        )


# 装饰器：流式响应
def streaming_response(event_name: str = "content"):
    """
    装饰器：将函数转换为流式响应

    用法:
        @streaming_response()
        async def generate(prompt: str) -> AsyncIterator[str]:
            async for chunk in llm.generate_stream(prompt):
                yield chunk
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            generator = StreamingGenerator()

            async def stream_wrapper():
                async for chunk in func(*args, **kwargs):
                    yield generator._format_sse(event_name, {"content": chunk})

            return StreamingResponse(
                stream_wrapper(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

        return wrapper
    return decorator


# 前端示例代码
STREAMING_FRONTEND_EXAMPLE = """
// 前端 SSE 客户端示例
const eventSource = new EventSource('/api/v1/generate/stream?prompt=xxx');

eventSource.addEventListener('content', (event) => {
    const data = JSON.parse(event.data);
    console.log('Content:', data.content);
    // 追加到显示区域
    outputDiv.textContent += data.content;
});

eventSource.addEventListener('progress', (event) => {
    const data = JSON.parse(event.data);
    console.log('Progress:', data.chunks_sent);
    // 更新进度条
    progressBar.value = data.chunks_sent;
});

eventSource.addEventListener('end', (event) => {
    const data = JSON.parse(event.data);
    console.log('Completed:', data.total_chunks);
    eventSource.close();
});

eventSource.addEventListener('error', (event) => {
    const data = JSON.parse(event.data);
    console.error('Error:', data.message);
    eventSource.close();
});
"""


# WebSocket 流式支持
class WebSocketStreamer:
    """
    WebSocket 流式推送

    比 SSE 更灵活，支持双向通信
    """

    def __init__(self, websocket):
        self.websocket = websocket
        self._closed = False

    async def send_chunk(self, content: str, metadata: dict | None = None):
        """发送数据块"""
        if self._closed:
            return

        message = {
            "type": "chunk",
            "content": content,
            **(metadata or {}),
        }

        await self.websocket.send_json(message)

    async def send_progress(self, progress: float, total: int | None = None):
        """发送进度"""
        message = {
            "type": "progress",
            "progress": progress,
            "total": total,
        }

        await self.websocket.send_json(message)

    async def send_complete(self, metadata: dict | None = None):
        """发送完成消息"""
        message = {
            "type": "complete",
            **(metadata or {}),
        }

        await self.websocket.send_json(message)

    async def send_error(self, error: str):
        """发送错误消息"""
        message = {
            "type": "error",
            "error": error,
        }

        await self.websocket.send_json(message)

    async def close(self):
        """关闭连接"""
        self._closed = True
        await self.websocket.close()

    async def stream_from_generator(
        self,
        generator: AsyncIterator[str],
        send_progress: bool = True,
    ):
        """从生成器流式推送"""
        chunk_count = 0

        try:
            async for chunk in generator:
                chunk_count += 1
                await self.send_chunk(chunk)

                if send_progress and chunk_count % 10 == 0:
                    await self.send_progress(chunk_count)

            await self.send_complete({"total_chunks": chunk_count})

        except Exception as e:
            await self.send_error(str(e))

        finally:
            await self.close()
