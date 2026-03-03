@echo off
chcp 65001 >nul
echo ========================================
echo   GitHub 推送助手
echo ========================================
echo.
echo 正在推送到 GitHub...
echo.
echo 注意：将会弹出 GitHub 登录窗口
echo.
echo 请登录：
echo 1. 输入 GitHub 用户名
echo 2. 输入 Personal Access Token
echo.
echo 获取 Token: https://github.com/settings/tokens
echo.

cd /d "%~dp0"
git push -u origin main

echo.
if %errorlevel% equ 0 (
    echo ========================================
    echo   推送成功！
    echo ========================================
    echo.
    echo 查看仓库：https://github.com/CloudSearch1/muti-agent
) else (
    echo ========================================
    echo   推送失败
    echo ========================================
    echo.
    echo 请检查：
    echo 1. 网络连接
    echo 2. GitHub 用户名和密码
    echo 3. Token 权限是否正确
)

pause
