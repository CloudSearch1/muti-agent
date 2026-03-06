"""
运行所有测试

用法:
    python scripts/run_tests.py
    python scripts/run_tests.py --coverage
    python scripts/run_tests.py --benchmark
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_tests(coverage: bool = False, verbose: bool = False):
    """运行测试"""
    cmd = [sys.executable, "-m", "pytest", "tests/"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing",
        ])
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def run_benchmark():
    """运行性能基准测试"""
    cmd = [sys.executable, "tests/benchmark.py"]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def run_specific_test(test_path: str):
    """运行特定测试"""
    cmd = [sys.executable, "-m", "pytest", test_path, "-v"]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="运行测试")
    parser.add_argument("--coverage", action="store_true", help="生成覆盖率报告")
    parser.add_argument("--benchmark", action="store_true", help="运行性能基准测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("test", nargs="?", help="特定测试文件")
    
    args = parser.parse_args()
    
    if args.benchmark:
        sys.exit(run_benchmark())
    elif args.test:
        sys.exit(run_specific_test(args.test))
    else:
        sys.exit(run_tests(coverage=args.coverage, verbose=args.verbose))


if __name__ == "__main__":
    main()
