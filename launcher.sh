#!/bin/bash
# 了了 — 自动启动守护
# 用法: bash launcher.sh

LIAOLIAO_DIR="/mnt/d/hermes-webui/workspace/liaoliao"
PORT=9200
LOG_FILE="$LIAOLIAO_DIR/data/liaoliao.log"
PID_FILE="$LIAOLIAO_DIR/data/liaoliao.pid"

# 如果已经在运行，跳过
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "了了已经在运行 (PID $OLD_PID)"
        exit 0
    fi
fi

cd "$LIAOLIAO_DIR"

# 加载环境变量
if [ -f ~/.hermes/profiles/evopolis/.env ]; then
    export $(grep -v '^#' ~/.hermes/profiles/evopolis/.env | xargs)
fi

# 启动
python3 server.py --port $PORT >> "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"
echo "了了启动 (PID $PID) — http://localhost:$PORT"
