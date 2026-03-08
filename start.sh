#!/bin/bash

# ============================================================
# ComfySD 一键启动服务（Linux / macOS）
# ============================================================

# 颜色定义
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color（重置颜色）

echo "================================================"
echo "         ComfySD 一键启动服务"
echo "================================================"
echo ""

# ============================================================
# 检查 node_modules 是否存在
# ============================================================
if [ ! -d "node_modules" ]; then
    echo -e "${RED}[错误] 未检测到 node_modules，请先运行以下命令安装依赖：${NC}"
    echo "       npm install"
    exit 1
fi

# ============================================================
# 检查 comfyapi.py 是否存在
# ============================================================
if [ ! -f "comfyapi.py" ]; then
    echo -e "${RED}[错误] 未找到 comfyapi.py，请确认文件完整！${NC}"
    exit 1
fi

# ============================================================
# 检查 server.js 是否存在
# ============================================================
if [ ! -f "server.js" ]; then
    echo -e "${RED}[错误] 未找到 server.js，请确认文件完整！${NC}"
    exit 1
fi

# ============================================================
# 检查 workflows 目录
# ============================================================
if [ ! -d "workflows" ]; then
    echo -e "${YELLOW}[警告] 未找到 workflows 目录，请确认工作流文件已就位！${NC}"
    exit 1
fi

# ============================================================
# 确保 uploads 目录存在
# ============================================================
if [ ! -d "uploads" ]; then
    mkdir -p uploads
    echo -e "${CYAN}[信息] 已自动创建 uploads 目录${NC}"
fi

# ============================================================
# 确保 logs 目录存在
# ============================================================
if [ ! -d "logs" ]; then
    mkdir -p logs
    echo -e "${CYAN}[信息] 已自动创建 logs 目录${NC}"
fi

# ============================================================
# 检测操作系统类型（用于后续打开浏览器）
# ============================================================
OS_TYPE="$(uname -s)"

open_browser() {
    local url=$1
    case "$OS_TYPE" in
        Darwin)
            # macOS
            open "$url"
            ;;
        Linux)
            # Linux：优先使用 xdg-open，其次 gnome-open
            if command -v xdg-open &>/dev/null; then
                xdg-open "$url"
            elif command -v gnome-open &>/dev/null; then
                gnome-open "$url"
            else
                echo -e "${YELLOW}[提示] 无法自动打开浏览器，请手动访问：$url${NC}"
            fi
            ;;
        *)
            echo -e "${YELLOW}[提示] 未知系统，请手动访问：$url${NC}"
            ;;
    esac
}

# ============================================================
# 启动 Express 静态服务（server.js）→ 后台运行
# ============================================================
echo -e "${GREEN}[启动] Express 服务 (Node.js)  端口：3000${NC}"
node server.js > logs/express.log 2>&1 &
EXPRESS_PID=$!
echo -e "${CYAN}[信息] Express PID：$EXPRESS_PID${NC}"

sleep 2

# ============================================================
# 启动 FastAPI 后端（comfyapi.py）→ 后台运行
# ============================================================
echo -e "${GREEN}[启动] FastAPI 服务 (Python)   端口：8000${NC}"
python comfyapi.py > logs/fastapi.log 2>&1 &
FASTAPI_PID=$!
echo -e "${CYAN}[信息] FastAPI PID：$FASTAPI_PID${NC}"

# ============================================================
# 将 PID 写入文件，方便 stop.sh 停止服务
# ============================================================
echo "$EXPRESS_PID" > .express.pid
echo "$FASTAPI_PID" > .fastapi.pid

# ============================================================
# 等待服务启动后自动打开浏览器
# ============================================================
echo ""
echo -e "${CYAN}[信息] 等待服务启动中...${NC}"
sleep 4

echo -e "${CYAN}[信息] 正在打开浏览器...${NC}"
open_browser "http://localhost:3000"

echo ""
echo "================================================"
echo -e "${GREEN} ✅ 所有服务已启动！${NC}"
echo "  - 前端页面：  http://localhost:3000"
echo "  - FastAPI：   http://localhost:8000"
echo "  - 健康检查：  http://localhost:8000/health"
echo "================================================"
echo ""
echo -e "${YELLOW}  日志文件：${NC}"
echo "  - Express 日志：  logs/express.log"
echo "  - FastAPI 日志：  logs/fastapi.log"
echo ""
echo -e "${YELLOW}  停止服务请运行：bash stop.sh${NC}"
echo "  或手动终止进程："
echo "    kill $EXPRESS_PID   # 停止 Express"
echo "    kill $FASTAPI_PID   # 停止 FastAPI"
echo ""

# ============================================================
# 保持脚本前台运行，Ctrl+C 时自动停止所有子进程
# ============================================================
trap "echo '';echo -e '${RED}[停止] 正在关闭所有服务...${NC}'; kill $EXPRESS_PID $FASTAPI_PID 2>/dev/null; echo -e '${GREEN}[完成] 服务已全部停止。${NC}'; exit 0" SIGINT SIGTERM

echo -e "${CYAN}  按 Ctrl+C 可停止所有服务${NC}"
echo ""

# 等待子进程（任意一个退出则提示）
wait $EXPRESS_PID $FASTAPI_PID