@echo off
chcp 65001 >nul
echo ========================================
echo Docker Desktop 安装助手
echo ========================================
echo.
echo 正在启用 WSL2 功能...
echo.

dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
if %errorlevel% neq 0 (
    echo [错误] WSL 功能启用失败
    pause
    exit /b 1
)

echo.
echo 正在启用虚拟机平台...
echo.

dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
if %errorlevel% neq 0 (
    echo [错误] 虚拟机平台功能启用失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo 成功！WSL2 功能已启用
echo ========================================
echo.
echo 下一步：
echo 1. 重启电脑 (必须!)
echo 2. 重启后运行：wsl --install
echo 3. 下载 Docker Desktop
echo.
echo 下载地址:
echo https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe
echo.
pause
