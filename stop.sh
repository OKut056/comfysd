#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "================================================"
echo "         ComfySD 停止服务"
echo "================================================"

stop_service() {
    local pid_file=$1
    local name=$2
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo -e "${GREEN}[停止] $name (PID: $PID) 已关闭${NC}"
        else
            echo -e "${RED}[提示] $name 进程不存在（可能已停止）${NC}"
        fi
        rm -f "$pid_file"
    else
        echo -e "${RED}[提示] 未找到 $name 的 PID 文件${NC}"
    fi
}

stop_service ".express.pid" "Express"
stop_service ".fastapi.pid" "FastAPI"

echo ""
echo -e "${GREEN}✅ 所有服务已停止。${NC}"