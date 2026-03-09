@echo off
chcp 65001 >nul
title ComfySD 服务启动器

echo ================================================
echo         ComfySD 一键启动服务
echo ================================================
echo.

:: ============================================================
:: 检查 node_modules 是否存在
:: ============================================================
if not exist "node_modules" (
    echo [错误] 未检测到 node_modules，请先运行 install.bat 安装依赖！
    pause
    exit /b 1
)

:: ============================================================
:: 检查 comfyapi.py 是否存在
:: ============================================================
if not exist "comfyapi.py" (
    echo [错误] 未找到 comfyapi.py，请确认文件完整！
    pause
    exit /b 1
)

:: ============================================================
:: 检查 server.js 是否存在
:: ============================================================
if not exist "server.js" (
    echo [错误] 未找到 server.js，请确认文件完整！
    pause
    exit /b 1
)

:: ============================================================
:: 检查 workflows 目录
:: ============================================================
if not exist "workflows" (
    echo [警告] 未找到 workflows 目录，请确认工作流文件已就位！
    pause
    exit /b 1
)

:: ============================================================
:: 检查 start_autodlart.py 是否存在
:: ============================================================
if not exist "start_autodlart.py" (
    echo [错误] 未找到 start_autodlart.py，请确认AutoDL远程开机脚本完整！
    pause
    exit /b 1
)

:: ============================================================
:: 启动 Express 静态服务（server.js） → 新窗口
:: ============================================================
echo [启动] Express 服务 (Node.js)  端口：3000
start "ComfySD - Express Server" cmd /k "node server.js"

timeout /t 2 >nul

:: ============================================================
:: 启动 FastAPI 后端（comfyapi.py） → 新窗口
:: ============================================================
echo [启动] FastAPI 服务 (Python)   端口：8000
start "ComfySD - FastAPI Backend" cmd /k "python comfyapi.py"

timeout /t 2 >nul

:: ============================================================
:: 启动 AutoDL 实例远程开机脚本（start_autodlart.py） → 新窗口
:: ============================================================
echo [启动] AutoDL 实例远程开机服务 (Python)
start "ComfySD - AutoDL Remote Start" cmd /k "python start_autodlart.py"

:: ============================================================
:: 等待服务启动后自动打开浏览器
:: ============================================================
echo.
echo [信息] 等待服务启动中...
timeout /t 4 >nul

::echo [信息] 正在打开浏览器...
::start http://localhost:3000

echo.
echo ================================================
echo  ✅ 所有服务已启动！
echo  - 前端页面：  http://localhost:3000
echo  - FastAPI：   http://localhost:8000
echo  - 健康检查：  http://localhost:8000/health
echo ================================================
echo.
echo  关闭服务请直接关闭对应的命令行窗口
echo.
pause