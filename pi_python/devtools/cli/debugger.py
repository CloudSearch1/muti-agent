"""
PI-Python 调试工具

提供 Agent 执行追踪和调试功能
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class TraceEvent:
    """追踪事件"""
    
    timestamp: float
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "type": self.type,
            "data": self.data
        }


class DebugTracer:
    """Agent 执行追踪器
    
    用于记录和分析 Agent 的执行过程，生成调试报告
    """
    
    def __init__(self, output_dir: Path | None = None):
        """
        初始化追踪器
        
        Args:
            output_dir: 输出目录（默认为 ./debug_logs）
        """
        self.output_dir = output_dir or Path.cwd() / "debug_logs"
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        self.trace_id = f"trace_{int(time.time())}_{id(self)}"
        self.events: list[TraceEvent] = []
        self.start_time = time.time()
        
        # 统计信息
        self.stats = {
            "tool_calls": 0,
            "errors": 0,
            "llm_calls": 0,
            "total_tokens": 0
        }
    
    def enable_for_agent(self, agent: Any) -> None:
        """
        为 Agent 启用追踪
        
        Args:
            agent: Agent 实例
        """
        
        async def trace_event(event: Any) -> None:
            """追踪 Agent 事件"""
            if not hasattr(event, 'type'):
                return
            
            # 创建追踪事件
            trace_event = TraceEvent(
                timestamp=time.time(),
                type=event.type,
                data=self._serialize_event(event)
            )
            
            self.events.append(trace_event)
            
            # 更新统计
            self._update_stats(event)
            
            # 实时写入文件（避免内存占用过大）
            if len(self.events) % 10 == 0:
                self._write_trace()
        
        # 订阅 Agent 事件
        agent.subscribe(trace_event)
    
    def _serialize_event(self, event: Any) -> dict[str, Any]:
        """
        序列化事件
        
        Args:
            event: Agent 事件
            
        Returns:
            序列化后的字典
        """
        data = {}
        
        # 复制事件属性
        for attr_name in dir(event):
            if attr_name.startswith('_'):
                continue
            
            try:
                attr_value = getattr(event, attr_name)
                
                # 跳过方法
                if callable(attr_value):
                    continue
                
                # 序列化值
                data[attr_name] = self._serialize_value(attr_value)
            
            except Exception as e:
                data[attr_name] = f"<无法序列化: {e}>"
        
        return data
    
    def _serialize_value(self, value: Any) -> Any:
        """
        序列化值
        
        Args:
            value: 任意值
            
        Returns:
            序列化后的值
        """
        if value is None:
            return None
        
        if isinstance(value, (str, int, float, bool)):
            return value
        
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(item) for item in value]
        
        if isinstance(value, dict):
            return {
                k: self._serialize_value(v)
                for k, v in value.items()
            }
        
        if hasattr(value, '__dict__'):
            return self._serialize_value(value.__dict__)
        
        return str(value)
    
    def _update_stats(self, event: Any) -> None:
        """
        更新统计信息
        
        Args:
            event: Agent 事件
        """
        event_type = getattr(event, 'type', '')
        
        if event_type == "tool_execution_start":
            self.stats["tool_calls"] += 1
        
        elif event_type == "error":
            self.stats["errors"] += 1
        
        elif event_type == "turn_start":
            self.stats["llm_calls"] += 1
        
        # 尝试提取 token 使用
        if hasattr(event, 'data') and isinstance(event.data, dict):
            if 'usage' in event.data:
                usage = event.data['usage']
                if isinstance(usage, dict):
                    self.stats["total_tokens"] += usage.get('total_tokens', 0)
    
    def _write_trace(self) -> None:
        """写入追踪文件"""
        try:
            trace_file = self.output_dir / f"{self.trace_id}.json"
            
            with open(trace_file, "w", encoding="utf-8") as f:
                json.dump({
                    "trace_id": self.trace_id,
                    "start_time": self.start_time,
                    "end_time": time.time(),
                    "stats": self.stats,
                    "events": [e.to_dict() for e in self.events]
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"写入追踪文件失败: {e}")
    
    def generate_report(self) -> Path:
        """
        生成调试报告
        
        Returns:
            报告文件路径
        """
        # 确保所有事件已写入
        self._write_trace()
        
        # 生成 Markdown 报告
        return self._generate_markdown_report()
    
    def _generate_markdown_report(self) -> Path:
        """
        生成 Markdown 格式的调试报告
        
        Returns:
            报告文件路径
        """
        report_file = self.output_dir / f"{self.trace_id}_report.md"
        
        # 分析执行流程
        execution_flow = self._analyze_execution_flow()
        
        # 生成报告内容
        report_content = f"""# Agent 执行调试报告

**追踪 ID**: `{self.trace_id}`  
**执行时间**: {time.time() - self.start_time:.2f} 秒  
**事件总数**: {len(self.events)}

## 统计摘要

| 指标 | 数值 |
|------|------|
| LLM 调用次数 | {self.stats['llm_calls']} |
| 工具调用次数 | {self.stats['tool_calls']} |
| 错误次数 | {self.stats['errors']} |
| 总 Token 数 | {self.stats['total_tokens']} |

## 执行流程

```mermaid
{execution_flow}
```

## 详细事件日志

| 时间戳 | 事件类型 | 描述 |
|--------|----------|------|
"""
        
        # 添加事件详情
        for event in self.events:
            description = self._format_event_description(event)
            timestamp = event.timestamp - self.start_time
            
            report_content += (
                f"| {timestamp:.2f}s | {event.type} | {description} |\n"
            )
        
        # 错误详情（如果有）
        if self.stats["errors"] > 0:
            report_content += "\n## 错误详情\n\n"
            
            for event in self.events:
                if event.type == "error":
                    error_msg = event.data.get('error', '未知错误')
                    report_content += f"- **{event.timestamp:.2f}s**: {error_msg}\n"
        
        # 写入文件
        try:
            report_file.write_text(report_content, encoding="utf-8")
        except Exception as e:
            print(f"生成报告失败: {e}")
        
        return report_file
    
    def _analyze_execution_flow(self) -> str:
        """
        分析执行流程，生成 Mermaid 图
        
        Returns:
            Mermaid 图定义
        """
        flow = "flowchart TD\n"
        flow += "    Start([开始]) --> UserInput[用户输入]\n"
        flow += "    UserInput --> AgentStart[Agent 启动]\n"
        flow += "    AgentStart --> TurnStart[回合开始]\n"
        flow += "    TurnStart --> LLMCall[LLM 调用]\n"
        
        # 检查是否有工具调用
        tool_events = [e for e in self.events if e.type == "tool_execution_start"]
        
        if tool_events:
            flow += "    LLMCall --> MessageUpdate[消息更新]\n"
            
            # 添加工具调用节点
            for i, _ in enumerate(tool_events, 1):
                flow += f"    MessageUpdate --> Tool{i}[执行工具 {i}]\n"
                flow += f"    Tool{i} --> Tool{i}End[工具 {i} 完成]\n"
                
                if i < len(tool_events):
                    flow += f"    Tool{i}End --> Tool{i+1}\n"
                else:
                    flow += f"    Tool{i}End --> TurnEnd[回合结束]\n"
        else:
            flow += "    LLMCall --> TurnEnd[回合结束]\n"
        
        # 检查是否有错误
        error_events = [e for e in self.events if e.type == "error"]
        if error_events:
            flow += "    LLMCall --> Error[发生错误]\n"
            flow += "    Error --> TurnEnd\n"
        
        flow += "    TurnEnd --> AgentEnd([Agent 结束])\n"
        
        return flow
    
    def _format_event_description(self, event: TraceEvent) -> str:
        """
        格式化事件描述
        
        Args:
            event: 追踪事件
            
        Returns:
            描述字符串
        """
        if event.type == "tool_execution_start":
            tool_name = event.data.get('tool_name', 'unknown')
            return f"执行工具: {tool_name}"
        
        elif event.type == "error":
            error_msg = event.data.get('error', '未知错误')
            return f"错误: {error_msg[:50]}..."
        
        elif event.type == "message_update":
            delta = event.data.get('delta', '')
            if delta:
                return f"消息更新: {delta[:50]}..."
            return "消息更新"
        
        elif event.type == "turn_start":
            return "开始新回合"
        
        elif event.type == "turn_end":
            return "回合结束"
        
        else:
            # 其他事件类型
            return event.type.replace("_", " ").title()


def enable_debug_mode(agent: Any, output_dir: Path | None = None) -> DebugTracer:
    """
    为 Agent 启用调试模式
    
    Args:
        agent: Agent 实例
        output_dir: 输出目录
        
    Returns:
        DebugTracer 实例
    """
    tracer = DebugTracer(output_dir)
    tracer.enable_for_agent(agent)
    return tracer
