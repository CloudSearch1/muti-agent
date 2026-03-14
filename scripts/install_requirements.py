#!/usr/bin/env python3
"""
Windows 依赖安装脚本
解决 Windows 系统上 pip 安装 requirements.txt 时的编码问题
"""

import subprocess
import sys
import os
from pathlib import Path


def check_requirements_file():
    """检查 requirements.txt 是否存在"""
    project_root = Path(__file__).parent.parent
    requirements_file = project_root / "requirements.txt"
    
    if not requirements_file.exists():
        print("❌ 错误: requirements.txt 文件不存在")
        sys.exit(1)
    
    return requirements_file


def read_requirements_with_utf8(file_path):
    """使用 UTF-8 编码读取 requirements.txt"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"✓ 成功读取 {file_path}")
        return content
    except FileNotFoundError:
        print(f"❌ 错误: 文件 {file_path} 不存在")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 读取文件时出错: {e}")
        sys.exit(1)


def parse_requirements(content):
    """解析 requirements 内容，提取有效的依赖包"""
    lines = content.strip().split('\n')
    packages = []
    
    for line in lines:
        line = line.strip()
        # 跳过空行和注释
        if not line or line.startswith('#'):
            continue
        packages.append(line)
    
    return packages


def install_packages(packages):
    """安装依赖包"""
    if not packages:
        print("⚠️  警告: 没有找到需要安装的包")
        return
    
    print(f"\n📦 准备安装 {len(packages)} 个依赖包...\n")
    
    # 一次性安装所有包
    try:
        cmd = [sys.executable, "-m", "pip", "install"] + packages
        
        # 设置环境变量强制使用 UTF-8
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        result = subprocess.run(
            cmd,
            check=True,
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        
        print("\n✅ 所有依赖安装完成!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 安装失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 安装过程中出现错误: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("Windows 依赖安装脚本")
    print("=" * 60)
    
    # 检查 requirements.txt
    requirements_file = check_requirements_file()
    
    # 读取并解析 requirements
    content = read_requirements_with_utf8(requirements_file)
    packages = parse_requirements(content)
    
    # 显示将要安装的包
    print("\n📋 将要安装的依赖包:")
    print("-" * 60)
    for i, pkg in enumerate(packages, 1):
        print(f"{i:2d}. {pkg}")
    print("-" * 60)
    
    # 确认安装
    try:
        response = input("\n是否继续安装? [Y/n]: ").strip().lower()
        if response and response not in ['y', 'yes', '是']:
            print("❌ 用户取消安装")
            sys.exit(0)
    except KeyboardInterrupt:
        print("\n❌ 用户取消安装")
        sys.exit(0)
    
    # 安装依赖
    success = install_packages(packages)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
