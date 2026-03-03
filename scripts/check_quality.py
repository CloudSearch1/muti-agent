"""
代码质量检查脚本

用途:
- 运行代码检查 (ruff, mypy)
- 代码格式化 (black)
- 生成质量报告
"""

import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], description: str) -> bool:
    """运行命令并返回结果"""
    print(f"\n{'=' * 60}")
    print(f"  {description}")
    print(f"{'=' * 60}")
    print(f"运行：{' '.join(command)}\n")
    
    result = subprocess.run(command, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"[OK] {description} 通过")
        return True
    else:
        print(f"[FAIL] {description} 失败")
        print(result.stdout)
        print(result.stderr)
        return False


def check_ruff() -> bool:
    """运行 Ruff 代码检查"""
    return run_command(
        [sys.executable, "-m", "ruff", "check", "src/", "tests/"],
        "Ruff 代码检查"
    )


def check_mypy() -> bool:
    """运行 MyPy 类型检查"""
    return run_command(
        [sys.executable, "-m", "mypy", "src/"],
        "MyPy 类型检查"
    )


def format_code() -> bool:
    """格式化代码"""
    return run_command(
        [sys.executable, "-m", "black", "--check", "src/", "tests/"],
        "Black 代码格式化检查"
    )


def fix_code() -> bool:
    """自动修复代码"""
    print("\n自动修复代码问题...\n")
    
    # Ruff 自动修复
    subprocess.run(
        [sys.executable, "-m", "ruff", "check", "src/", "tests/", "--fix"],
        capture_output=True,
    )
    
    # Black 格式化
    subprocess.run(
        [sys.executable, "-m", "black", "src/", "tests/"],
        capture_output=True,
    )
    
    print("✓ 代码修复完成")
    return True


def generate_report() -> None:
    """生成质量报告"""
    print("\n" + "=" * 60)
    print("  代码质量报告")
    print("=" * 60)
    
    # 统计代码行数
    src_dir = Path("src")
    total_lines = 0
    total_files = 0
    
    for py_file in src_dir.rglob("*.py"):
        total_files += 1
        total_lines += len(py_file.read_text().splitlines())
    
    print(f"\n源代码统计:")
    print(f"  - Python 文件：{total_files}")
    print(f"  - 总代码行数：{total_lines}")
    print(f"  - 平均每文件：{total_lines // max(total_files, 1)} 行")
    
    # 测试统计
    test_dir = Path("tests")
    test_files = len(list(test_dir.glob("*.py")))
    
    print(f"\n测试统计:")
    print(f"  - 测试文件：{test_files}")
    
    print("\n" + "=" * 60)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='代码质量检查工具')
    parser.add_argument('--fix', action='store_true', help='自动修复问题')
    parser.add_argument('--report', action='store_true', help='生成报告')
    parser.add_argument('--all', action='store_true', help='运行所有检查')
    
    args = parser.parse_args()
    
    results = []
    
    if args.fix or args.all:
        results.append(fix_code())
    
    if args.all or True:  # 默认运行检查
        results.append(check_ruff())
        results.append(format_code())
    
    if args.report or args.all:
        generate_report()
    
    # 总结
    print("\n" + "=" * 60)
    if all(results):
        print("✓ 所有检查通过！")
    else:
        print(f"✗ {results.count(False)} 个检查失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
