@echo off
chcp 65001 >nul

:: 创建计划任务来安装 WSL2 Docker
schtasks /Create /TN "WSL2-Docker-Install" /TR "powershell -ExecutionPolicy Bypass -File \"%~dp0install-wsl2-docker.ps1\"" /RL HIGHEST /SC ONCE /ST 00:00 /F

:: 立即运行计划任务
schtasks /Run /TN "WSL2-Docker-Install"

echo.
echo 已启动 WSL2 Docker 安装
echo 安装将在后台运行...
echo.
