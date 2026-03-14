"""
PI-Python 开发工具套件

提供 CLI、REPL、测试、调试等开发工具
"""

from .cli.main import app
from .cli.repl import ReplSession
from .cli.debugger import DebugTracer, enable_debug_mode
from .testing.fixtures import AgentTestFixture

# 模板目录
from pathlib import Path
TEMPLATES_DIR = Path(__file__).parent / "templates"

__all__ = [
    # CLI
    "app",
    "ReplSession",
    
    # 调试
    "DebugTracer",
    "enable_debug_mode",
    
    # 测试
    "AgentTestFixture",
    
    # 模板
    "TEMPLATES_DIR",
]
