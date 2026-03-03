@echo off
chcp 65001 >nul
title WSL2 Ubuntu Installation

echo ========================================
echo   WSL2 Ubuntu Installation
echo ========================================
echo.

echo [1/5] Checking WSL status...
wsl --status
echo.

echo [2/5] Setting WSL default version to 2...
wsl --set-default-version 2
echo.

echo [3/5] Installing Ubuntu 22.04...
echo This may take 10-20 minutes...
echo.
wsl --install --distribution Ubuntu
echo.

echo [4/5] Verifying installation...
wsl --list --verbose
echo.

echo [5/5] Installation complete!
echo.
echo ========================================
echo   Next Steps:
echo ========================================
echo.
echo 1. Start Ubuntu: wsl -d Ubuntu
echo 2. Create username and password
echo 3. Install Docker: apt-get install -y docker.io
echo.

pause
