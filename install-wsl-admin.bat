@echo off
chcp 65001 >nul
title WSL Ubuntu Installation - Admin Required

echo ========================================
echo   WSL Ubuntu Installation
echo ========================================
echo.
echo [1/4] Enabling WSL feature...
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
echo.

echo [2/4] Enabling Virtual Machine Platform...
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
echo.

echo [3/4] Setting WSL default version to 2...
wsl --set-default-version 2
echo.

echo [4/4] Installing Ubuntu...
echo This will take 10-20 minutes...
wsl --install -d Ubuntu
echo.

echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo IMPORTANT: A RESTART IS REQUIRED!
echo.
echo After restart:
echo   1. Open Ubuntu from Start Menu
echo   2. Create username and password
echo   3. Install Docker: apt-get install -y docker.io
echo.

set /p restart="Restart now? (Y/N): "
if /i "%restart%"=="Y" (
    shutdown /r /t 0
)

pause
