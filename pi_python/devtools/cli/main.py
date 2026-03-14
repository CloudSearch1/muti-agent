"""
PI-Python CLI 入口

提供交互式编程助手和各种开发工具
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from ... import Agent, AgentState, get_model
from ...agent.tools import BashTool, ReadFileTool, WriteFileTool
from .repl import ReplSession


app = typer.Typer(help="PI-Python 开发工具套件")
console = Console()


@app.command()
def start(
    model: str = typer.Option(
        "openai/gpt-4o", "--model", "-m",
        help="模型名称 (格式: provider/model-id)"
    ),
    skills_dir: Optional[Path] = typer.Option(
        None, "--skills", "-s",
        help="技能目录路径"
    ),
    debug: bool = typer.Option(
        False, "--debug", "-d",
        help="启用调试模式"
    ),
    system_prompt: Optional[str] = typer.Option(
        None, "--system", "-sp",
        help="自定义系统提示词"
    )
):
    """启动交互式编程助手"""
    
    # 解析模型
    try:
        provider, model_id = model.split("/", 1)
    except ValueError:
        console.print("[red]错误：模型格式不正确，请使用 provider/model-id 格式[/red]")
        raise typer.Exit(1)
    
    # 创建 Agent
    try:
        agent = Agent(
            initial_state=AgentState(
                system_prompt=system_prompt or _get_default_system_prompt(),
                model=get_model(provider, model_id),
                tools=[BashTool(), ReadFileTool(), WriteFileTool()],
                messages=[]
            ),
            skills_dir=skills_dir,
            auto_match_skills=True
        )
    except Exception as e:
        console.print(f"[red]创建 Agent 失败: {e}[/red]")
        raise typer.Exit(1)
    
    # 设置调试模式
    tracer = None
    if debug:
        from .debugger import enable_debug_mode
        tracer = enable_debug_mode(agent)
        console.print("[yellow]调试模式已启用[/yellow]")
    
    # 显示启动信息
    console.print(Panel.fit(
        f"[bold green]PI-Python 编程助手已启动[/bold green]\n"
        f"模型: {model}\n"
        f"技能目录: {skills_dir or '无'}\n"
        f"调试模式: {'开启' if debug else '关闭'}",
        title="欢迎使用"
    ))
    
    # 启动 REPL
    repl = ReplSession(agent, console, debug=debug, tracer=tracer)
    try:
        asyncio.run(repl.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]检测到中断，正在退出...[/yellow]")
    finally:
        if tracer:
            report_file = tracer.generate_report()
            console.print(f"[green]调试报告已生成: {report_file}[/green]")


@app.command()
def new_skill(
    name: str = typer.Argument(..., help="技能名称"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="输出目录（默认: ./skills）"
    )
):
    """创建新的技能模板"""
    
    template_dir = Path(__file__).parent.parent / "templates"
    template_file = template_dir / "skill.md.template"
    
    if not template_file.exists():
        console.print("[red]错误：找不到技能模板文件[/red]")
        raise typer.Exit(1)
    
    # 读取模板
    try:
        template = template_file.read_text(encoding="utf-8")
    except Exception as e:
        console.print(f"[red]读取模板失败: {e}[/red]")
        raise typer.Exit(1)
    
    # 替换变量
    skill_content = template.replace("{{SKILL_NAME}}", name)
    
    # 确定输出路径
    output_dir = output or Path.cwd() / "skills"
    try:
        output_dir.mkdir(exist_ok=True, parents=True)
    except Exception as e:
        console.print(f"[red]创建输出目录失败: {e}[/red]")
        raise typer.Exit(1)
    
    output_file = output_dir / f"{name}.skill.md"
    
    # 写入文件
    try:
        output_file.write_text(skill_content, encoding="utf-8")
        console.print(f"[green]✓[/green] 技能模板已创建: {output_file}")
    except Exception as e:
        console.print(f"[red]写入文件失败: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def new_extension(
    name: str = typer.Argument(..., help="扩展名称"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="输出目录（默认: ./extensions）"
    )
):
    """创建新的扩展模板"""
    
    template_dir = Path(__file__).parent.parent / "templates"
    template_file = template_dir / "extension.py.template"
    
    if not template_file.exists():
        console.print("[red]错误：找不到扩展模板文件[/red]")
        raise typer.Exit(1)
    
    # 读取模板
    try:
        template = template_file.read_text(encoding="utf-8")
    except Exception as e:
        console.print(f"[red]读取模板失败: {e}[/red]")
        raise typer.Exit(1)
    
    # 替换变量
    extension_content = template.replace("{{EXTENSION_NAME}}", name)
    
    # 确定输出路径
    output_dir = output or Path.cwd() / "extensions"
    try:
        output_dir.mkdir(exist_ok=True, parents=True)
    except Exception as e:
        console.print(f"[red]创建输出目录失败: {e}[/red]")
        raise typer.Exit(1)
    
    output_file = output_dir / f"{name}.py"
    
    # 写入文件
    try:
        output_file.write_text(extension_content, encoding="utf-8")
        console.print(f"[green]✓[/green] 扩展模板已创建: {output_file}")
    except Exception as e:
        console.print(f"[red]写入文件失败: {e}[/red]")
        raise typer.Exit(1)


def _get_default_system_prompt() -> str:
    """获取默认系统提示词"""
    return """你是一个专业的编程助手，帮助用户完成各种开发任务。

你可以使用以下工具：
- bash: 执行 shell 命令
- file: 读写文件

请用中文回复，保持专业和友好。在回复中：
1. 先理解用户的需求
2. 提供清晰的解决方案
3. 必要时提供代码示例
4. 解释关键步骤和原理
5. 询问是否需要进一步帮助"""


if __name__ == "__main__":
    app()
