@echo off
chcp 65001 >nul
title Docker Desktop 自动安装程序

echo.
echo ========================================
echo   Docker Desktop 自动安装程序
echo ========================================
echo.
echo [1/5] 正在启用 WSL2 功能...
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] WSL2 功能已启用
) else (
    echo [失败] WSL2 功能启用失败，错误代码：%errorlevel%
    goto :error
)

echo.
echo [2/5] 正在启用虚拟机平台...
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] 虚拟机平台已启用
) else (
    echo [失败] 虚拟机平台启用失败，错误代码：%errorlevel%
    goto :error
)

echo.
echo [3/5] 正在下载 WSL2 内核更新...
powershell -Command "Invoke-WebRequest -Uri 'https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi' -OutFile '%TEMP%\wsl_update.msi' -UseBasicParsing" >nul 2>&1
if exist "%TEMP%\wsl_update.msi" (
    echo [OK] WSL2 内核更新下载完成
) else (
    echo [警告] WSL2 内核更新下载失败，可手动下载
)

echo.
echo [4/5] 正在设置 WSL 默认版本...
wsl --set-default-version 2 >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] WSL 默认版本设置为 2
) else (
    echo [警告] WSL 版本设置失败，重启后重试
)

echo.
echo [5/5] 正在下载 Docker Desktop...
powershell -Command "Invoke-WebRequest -Uri 'https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe' -OutFile '%TEMP%\DockerDesktopInstaller.exe' -UseBasicParsing" >nul 2>&1
if exist "%TEMP%\DockerDesktopInstaller.exe" (
    echo [OK] Docker Desktop 下载完成
    echo.
    echo 准备安装 Docker Desktop...
    echo.
    echo 注意：安装程序将启动，请按提示完成安装
    echo.
    pause
    start "" "%TEMP%\DockerDesktopInstaller.exe"
) else (
    echo [失败] Docker Desktop 下载失败
    echo.
    echo 请手动下载:
    echo https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe
)

echo.
echo ========================================
echo   安装准备完成！
echo ========================================
echo.
echo 下一步操作:
echo 1. 重启电脑 (必须!)
echo 2. 重启后启动 Docker Desktop
echo 3. 首次启动需要登录 Docker Hub
echo.
echo 是否立即重启？
set /p restart="输入 Y 重启，或按任意键退出："
if /i "%restart%"=="Y" (
    echo.
    echo 正在重启...
    shutdown /r /t 5
) else (
    echo.
    echo 请手动重启电脑以完成安装
)

goto :end

:error
echo.
echo ========================================
echo   安装失败
echo ========================================
echo.
echo 请检查:
echo 1. 是否以管理员身份运行
echo 2. 系统是否为 Windows 10 64 位
echo 3. 是否启用了虚拟化
echo.

:end
pause
