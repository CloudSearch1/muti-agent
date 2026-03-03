"""
IntelliTeam CLI 命令行工具

提供便捷的项目管理命令
"""

import click
import asyncio
import sys
from pathlib import Path


@click.group()
@click.version_option(version='1.0.0', prog_name='IntelliTeam')
def cli():
    """IntelliTeam - 智能研发协作平台 CLI"""
    pass


@cli.command()
def start():
    """启动 IntelliTeam 服务"""
    from start import main
    main()


@cli.command()
@click.option('--test', '-t', is_flag=True, help='运行测试')
@click.option('--coverage', '-c', is_flag=True, help='生成覆盖率报告')
def test(test, coverage):
    """运行测试套件"""
    import pytest
    
    args = ['tests/']
    if coverage:
        args.extend(['--cov=src', '--cov-report=html'])
    
    exit_code = pytest.main(args)
    sys.exit(exit_code)


@cli.command()
@click.option('--name', '-n', default='task', help='任务名称')
@click.option('--title', '-t', required=True, help='任务标题')
@click.option('--desc', '-d', default='', help='任务描述')
def create_task(name, title, desc):
    """创建新任务"""
    import asyncio
    from src.graph import create_workflow
    
    async def run():
        workflow = create_workflow()
        result = await workflow.run(
            task_id=name,
            task_title=title,
            task_description=desc,
        )
        print(f"任务完成：{result.current_step}")
    
    asyncio.run(run())


@cli.command()
def status():
    """查看服务状态"""
    import httpx
    
    async def check():
        try:
            async with httpx.AsyncClient() as client:
                # 检查 API
                response = await client.get('http://localhost:8000/health')
                if response.status_code == 200:
                    print("✅ API 服务：运行中")
                else:
                    print("❌ API 服务：异常")
                
                # 检查 Redis
                from src.memory.short_term import ShortTermMemory
                memory = ShortTermMemory()
                await memory.connect()
                print("✅ Redis: 已连接")
                await memory.disconnect()
                
        except Exception as e:
            print(f"❌ 服务检查失败：{e}")
    
    asyncio.run(check())


@cli.command()
@click.option('--port', '-p', default=6379, help='Redis 端口')
def start_redis(port):
    """启动 Redis 容器"""
    import subprocess
    
    cmd = f'docker run -d --name intelliteam-redis -p {port}:6379 redis:7-alpine'
    print(f"执行：{cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Redis 容器已启动")
    else:
        print(f"❌ 启动失败：{result.stderr}")


@cli.command()
@click.option('--port', '-p', default=5432, help='PostgreSQL 端口')
@click.option('--password', '-P', default='password', help='数据库密码')
def start_postgres(port, password):
    """启动 PostgreSQL 容器"""
    import subprocess
    
    cmd = f'docker run -d --name intelliteam-postgres -e POSTGRES_PASSWORD={password} -p {port}:5432 postgres:15-alpine'
    print(f"执行：{cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ PostgreSQL 容器已启动")
    else:
        print(f"❌ 启动失败：{result.stderr}")


@cli.command()
def docker_up():
    """使用 docker-compose 启动所有服务"""
    import subprocess
    
    cmd = 'docker-compose up -d'
    print(f"执行：{cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ 所有服务已启动")
    else:
        print(f"❌ 启动失败：{result.stderr}")


@cli.command()
def docker_down():
    """停止所有 docker-compose 服务"""
    import subprocess
    
    cmd = 'docker-compose down'
    print(f"执行：{cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ 所有服务已停止")
    else:
        print(f"❌ 停止失败：{result.stderr}")


@cli.command()
def webui():
    """启动 Web UI 界面"""
    import subprocess
    import webbrowser
    import time
    
    print("启动 Web UI 服务器...")
    
    # 启动服务器
    server_process = subprocess.Popen(
        ['python', 'webui/server.py'],
        cwd=str(Path(__file__).parent)
    )
    
    # 等待服务器启动
    time.sleep(3)
    
    # 打开浏览器
    print("打开浏览器...")
    webbrowser.open('http://localhost:3000')
    
    print("Web UI 已启动：http://localhost:3000")
    print("按 Ctrl+C 停止服务")
    
    try:
        server_process.wait()
    except KeyboardInterrupt:
        server_process.terminate()
        print("Web UI 已停止")


@cli.command()
def docs():
    """打开 API 文档"""
    import webbrowser
    
    print("打开 API 文档：http://localhost:8000/docs")
    webbrowser.open('http://localhost:8000/docs')


@cli.command()
def clean():
    """清理缓存和临时文件"""
    import shutil
    
    paths_to_clean = [
        Path('__pycache__'),
        Path('logs'),
        Path('htmlcov'),
    ]
    
    for path in paths_to_clean:
        if path.exists():
            shutil.rmtree(path)
            print(f"✅ 已清理：{path}")
    
    print("清理完成")


if __name__ == '__main__':
    cli()
