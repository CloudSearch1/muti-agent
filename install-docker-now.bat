@echo off
chcp 65001 >nul
title Docker Desktop 安装程序

echo.
echo ========================================
echo   Docker Desktop 安装程序
echo ========================================
echo.
echo 正在启动 Docker Desktop 安装程序...
echo.
echo 注意：需要确认 UAC 弹窗
echo.

start "" "%TEMP%\DockerDesktopInstaller.exe" install --quiet --noreboot

echo.
echo [OK] 安装程序已启动
echo.
echo 安装完成后请：
echo 1. 启动 Docker Desktop
echo 2. 登录 Docker Hub
echo 3. 等待初始化完成
echo.
pause
