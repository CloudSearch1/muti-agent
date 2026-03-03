@echo off
chcp 65001 >nul
echo ========================================
echo OpenClaw 自启动验证
echo ========================================
echo.
echo 正在检查计划任务...
schtasks /Query /TN "OpenClaw Gateway" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] OpenClaw 计划任务已创建
    echo.
    echo 正在测试服务状态...
    openclaw gateway status >nul 2>&1
    if %errorlevel% equ 0 (
        echo [OK] OpenClaw 服务运行正常
        echo.
        echo ========================================
        echo   自启动配置验证成功!
        echo ========================================
        echo.
        echo OpenClaw 已配置为开机自启动
        echo 下次开机后会自动运行
        echo.
    ) else (
        echo [警告] 服务未运行，尝试启动...
        openclaw gateway start
        echo [OK] OpenClaw 已启动
    )
) else (
    echo [错误] 计划任务不存在
    echo 正在创建...
    openclaw gateway install
    echo [OK] 已创建开机自启动
)
echo.
pause
