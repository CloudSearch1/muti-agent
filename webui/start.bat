@echo off
chcp 65001 >nul
title IntelliTeam Web UI

echo ========================================
echo   IntelliTeam Web UI
echo ========================================
echo.

echo 正在启动 Web UI 服务器...
echo.

python webui\app.py

pause
