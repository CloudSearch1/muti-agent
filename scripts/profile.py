"""
性能分析脚本

用途:
- 分析代码性能
- 识别性能瓶颈
- 生成性能报告
"""

import cProfile
import pstats
import io
import sys
from pathlib import Path
from contextlib import contextmanager


@contextmanager
def profile_function(output_file: str = "profile_stats.txt"):
    """性能分析上下文管理器"""
    pr = cProfile.Profile()
    pr.enable()
    
    try:
        yield pr
    finally:
        pr.disable()
        
        # 生成报告
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats(50)  # 显示前 50 个函数
        
        # 保存到文件
        output_path = Path(output_file)
        output_path.write_text(s.getvalue())
        
        print(f"性能分析报告已保存到：{output_path}")
        print("\n前 20 个最耗时的函数:")
        print(s.getvalue()[:2000])


def analyze_imports():
    """分析导入时间"""
    import time
    
    print("分析模块导入时间...\n")
    
    modules = [
        'src.api.main',
        'src.agents.planner',
        'src.agents.architect',
        'src.graph.workflow',
        'src.tools.registry',
    ]
    
    for module_name in modules:
        start = time.time()
        try:
            __import__(module_name)
            elapsed = time.time() - start
            print(f"  {module_name}: {elapsed:.3f}s")
        except ImportError as e:
            print(f"  {module_name}: 导入失败 - {e}")


def analyze_memory():
    """分析内存使用"""
    try:
        import tracemalloc
    except ImportError:
        print("tracemalloc 不可用")
        return
    
    print("\n分析内存使用...\n")
    
    tracemalloc.start()
    
    # 导入主要模块
    from src.graph import create_workflow
    from src.agents.planner import PlannerAgent
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print(f"  当前内存：{current / 1024 / 1024:.2f} MB")
    print(f"  峰值内存：{peak / 1024 / 1024:.2f} MB")


def analyze_workflow_performance():
    """分析工作流性能"""
    print("\n分析工作流性能...\n")
    
    import asyncio
    import time
    from src.graph import create_workflow
    
    async def benchmark():
        workflow = create_workflow()
        
        start = time.time()
        
        # 创建工作流（不实际执行）
        workflow.compile()
        
        elapsed = time.time() - start
        print(f"  工作流编译时间：{elapsed:.3f}s")
    
    asyncio.run(benchmark())


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='性能分析工具')
    parser.add_argument('--imports', action='store_true', help='分析导入时间')
    parser.add_argument('--memory', action='store_true', help='分析内存使用')
    parser.add_argument('--workflow', action='store_true', help='分析工作流性能')
    parser.add_argument('--profile', action='store_true', help='完整性能分析')
    parser.add_argument('--all', action='store_true', help='运行所有分析')
    
    args = parser.parse_args()
    
    if args.all or args.imports:
        analyze_imports()
    
    if args.all or args.memory:
        analyze_memory()
    
    if args.all or args.workflow:
        analyze_workflow_performance()
    
    if args.profile:
        print("\n运行完整性能分析...\n")
        with profile_function():
            # 运行一些示例代码
            analyze_imports()
            analyze_memory()
            analyze_workflow_performance()
    
    print("\n性能分析完成！")


if __name__ == "__main__":
    main()
