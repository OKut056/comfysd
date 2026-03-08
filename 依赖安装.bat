@echo off
chcp 65001 >nul
title ComfySD 安装器

echo ================================================
echo         ComfySD 一键安装依赖
echo ================================================
echo.

:: ============================================================
:: 检查 Node.js 是否安装
:: ============================================================
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Node.js，请先安装 Node.js！
    echo 下载地址：https://nodejs.org/
    pause
    exit /b 1
)

:: ============================================================
:: 检查 Python 是否安装
:: ============================================================
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python！
    echo 下载地址：https://www.python.org/
    pause
    exit /b 1
)

echo [✅] Node.js 和 Python 环境检测通过！
echo.

:: ============================================================
:: 创建必要目录
:: ============================================================
if not exist "uploads" (
    mkdir uploads
    echo [信息] 已创建 uploads 目录
)
if not exist "workflows" (
    mkdir workflows
    echo [警告] 已创建 workflows 目录，请确认工作流 JSON 文件已放入！
)

:: ============================================================
:: 安装 Node.js 依赖
:: ============================================================
echo [信息] 正在安装 Node.js 依赖（npm install）...
call npm install
if %errorlevel% neq 0 (
    echo [错误] npm install 失败，请检查 package.json 是否存在！
    pause
    exit /b 1
)
echo [✅] Node.js 依赖安装完成！
echo.

:: ============================================================
:: 安装 Python 依赖
:: ============================================================
echo [信息] 正在安装 Python 依赖（pip install）...
pip install fastapi uvicorn requests python-multipart
if %errorlevel% neq 0 (
    echo [错误] pip install 失败，请检查网络或 pip 是否可用！
    pause
    exit /b 1
)
echo [✅] Python 依赖安装完成！
echo.

echo ================================================
echo  ✅ 所有依赖安装完成！
echo  请运行 start.bat 启动服务
echo ================================================
echo.
pause