#!/usr/bin/env python3
"""
IntelliTeam 自动化部署脚本

用途：
- 一键部署到生产环境
- 配置管理
- 服务启动/停止
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime


class Colors:
    """终端颜色"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """打印标题"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{Colors.ENDC}\n")


def print_success(text):
    """打印成功信息"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    """打印错误信息"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_info(text):
    """打印信息"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def run_command(command, shell=True, check=True):
    """运行命令"""
    try:
        result = subprocess.run(
            command,
            shell=shell,
            check=check,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def check_dependencies():
    """检查依赖"""
    print_header("检查依赖")
    
    dependencies = {
        'python': 'Python 3.11+',
        'git': 'Git',
        'docker': 'Docker (可选)',
        'docker-compose': 'Docker Compose (可选)',
    }
    
    all_ok = True
    
    for cmd, name in dependencies.items():
        exists, _ = run_command(f"{cmd} --version", check=False)
        if exists:
            print_success(f"{name} 已安装")
        else:
            if cmd in ['docker', 'docker-compose']:
                print_info(f"{name} 未安装 (可选)")
            else:
                print_error(f"{name} 未安装")
                all_ok = False
    
    return all_ok


def setup_environment():
    """配置环境"""
    print_header("配置环境")
    
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if not env_file.exists() and env_example.exists():
        print_info("创建 .env 文件...")
        import shutil
        shutil.copy(env_example, env_file)
        print_success(".env 文件已创建")
        print_info("请编辑 .env 文件配置 API Key 和其他参数")
    else:
        print_success(".env 文件已存在")
    
    # 创建日志目录
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    print_success("日志目录已创建")
    
    # 创建数据目录
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    print_success("数据目录已创建")


def install_dependencies():
    """安装依赖"""
    print_header("安装依赖")
    
    print_info("正在安装 Python 依赖...")
    success, output = run_command(f"{sys.executable} -m pip install -r requirements.txt")
    
    if success:
        print_success("依赖安装完成")
    else:
        print_error("依赖安装失败")
        print(output)
        return False
    
    return True


def run_tests():
    """运行测试"""
    print_header("运行测试")
    
    print_info("正在运行测试套件...")
    success, output = run_command(f"{sys.executable} -m pytest tests/ -v --tb=short")
    
    if success:
        print_success("所有测试通过")
    else:
        print_error("部分测试失败")
    
    return success


def build_docker():
    """构建 Docker 镜像"""
    print_header("构建 Docker 镜像")
    
    print_info("正在构建 Docker 镜像...")
    success, output = run_command("docker-compose build")
    
    if success:
        print_success("Docker 镜像构建完成")
    else:
        print_error("Docker 镜像构建失败")
        print(output)
    
    return success


def start_services():
    """启动服务"""
    print_header("启动服务")
    
    print_info("正在启动 Docker 服务...")
    success, output = run_command("docker-compose up -d")
    
    if success:
        print_success("服务启动成功")
        print_info("访问地址:")
        print("  - API: http://localhost:8000")
        print("  - Web UI: http://localhost:3000")
        print("  - Docs: http://localhost:8000/docs")
    else:
        print_error("服务启动失败")
        print(output)
    
    return success


def stop_services():
    """停止服务"""
    print_header("停止服务")
    
    print_info("正在停止 Docker 服务...")
    success, output = run_command("docker-compose down")
    
    if success:
        print_success("服务已停止")
    else:
        print_error("服务停止失败")
    
    return success


def show_status():
    """显示状态"""
    print_header("服务状态")
    
    # Docker 状态
    success, output = run_command("docker-compose ps")
    if success:
        print(output)
    
    # Git 状态
    print_info("\nGit 状态:")
    success, output = run_command("git status --short")
    if success and output.strip():
        print(output)
    elif success:
        print("工作区干净")


def deploy_production():
    """生产环境部署"""
    print_header("生产环境部署")
    
    print_warning("⚠️  警告：这将部署到生产环境！")
    response = input("确认部署？(yes/no): ")
    
    if response.lower() != 'yes':
        print_info("部署已取消")
        return
    
    # 1. 检查依赖
    if not check_dependencies():
        print_error("依赖检查失败")
        return
    
    # 2. 安装依赖
    if not install_dependencies():
        print_error("依赖安装失败")
        return
    
    # 3. 运行测试
    if not run_tests():
        print_error("测试未通过，无法部署")
        return
    
    # 4. 构建 Docker
    if not build_docker():
        print_error("Docker 构建失败")
        return
    
    # 5. 启动服务
    if not start_services():
        print_error("服务启动失败")
        return
    
    print_header("部署完成")
    print_success("IntelliTeam 已成功部署！")
    print_info("访问地址:")
    print("  - API: http://localhost:8000")
    print("  - Web UI: http://localhost:3000")
    print("  - Docs: http://localhost:8000/docs")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='IntelliTeam 部署脚本')
    parser.add_argument(
        'command',
        choices=['install', 'test', 'build', 'start', 'stop', 'status', 'deploy'],
        help='命令'
    )
    
    args = parser.parse_args()
    
    commands = {
        'install': lambda: (setup_environment(), install_dependencies()),
        'test': run_tests,
        'build': build_docker,
        'start': start_services,
        'stop': stop_services,
        'status': show_status,
        'deploy': deploy_production,
    }
    
    if args.command in commands:
        commands[args.command]()
    else:
        print_error(f"未知命令：{args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
