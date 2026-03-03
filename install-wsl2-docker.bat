@echo off
chcp 65001 >nul
title WSL2 Docker 自动安装

echo.
echo ========================================
echo   WSL2 Docker 自动安装
echo ========================================
echo.

echo [1/5] 正在安装 Ubuntu...
wsl --install -d Ubuntu --no-launch >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Ubuntu 已下载
) else (
    echo [警告] Ubuntu 可能已安装
)

echo.
echo [2/5] 等待 Ubuntu 安装完成...
timeout /t 30 /nobreak >nul

echo.
echo [3/5] 正在启动 Ubuntu 进行初始化...
wsl -d Ubuntu -e bash -c "exit 0" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Ubuntu 初始化完成
) else (
    echo [失败] Ubuntu 初始化失败
    pause
    exit /b 1
)

echo.
echo [4/5] 正在安装 Docker Engine...
wsl -d Ubuntu -e bash -c "
    # 更新包列表
    apt-get update -qq
    
    # 安装 Docker
    apt-get install -y -qq docker.io docker-compose
    
    # 启动 Docker 服务
    service docker start
    
    # 测试 Docker
    docker --version
    
    # 添加当前用户到 docker 组
    usermod -aG docker \$USER
" >nul 2>&1

if %errorlevel% equ 0 (
    echo [OK] Docker Engine 安装完成
) else (
    echo [失败] Docker 安装失败
    pause
    exit /b 1
)

echo.
echo [5/5] 验证 Docker...
wsl -d Ubuntu -e bash -c "docker run --rm hello-world" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Docker 运行正常
) else (
    echo [警告] Docker 测试失败，但安装完成
)

echo.
echo ========================================
echo   完成！
echo ========================================
echo.
echo Docker 已安装到 WSL2 (Ubuntu)
echo.
echo 使用命令:
echo   wsl -d Ubuntu docker --version
echo   wsl -d Ubuntu docker ps
echo.
echo 启动 Redis:
echo   wsl -d Ubuntu docker run -d --name redis -p 6379:6379 redis:7-alpine
echo.
pause
