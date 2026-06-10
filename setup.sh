#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# 知纹 · 一键安装脚本
# curl -fsSL https://raw.githubusercontent.com/RealBeingHHH/zhiwen/master/setup.sh | bash
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
ZHIWEN_DIR="${ZHIWEN_DIR:-$HOME/zhiwen}"
PORT="${PORT:-9200}"

echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       知纹 Zhiwen · 一键安装        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# ── 1. Python ──
echo -e "${CYAN}[1/4]${NC} 检查 Python..."
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}需要 Python 3.9+. 请先安装: https://python.org${NC}"
    exit 1
fi
PY=$(python3 --version 2>&1)
echo -e "  ${GREEN}✓${NC} $PY"

# ── 2. 下载 ──
if [ -d "$ZHIWEN_DIR/.git" ]; then
    echo -e "${CYAN}[2/4]${NC} 更新已有仓库..."
    cd "$ZHIWEN_DIR" && git pull --ff-only 2>/dev/null || true
else
    echo -e "${CYAN}[2/4]${NC} 克隆仓库..."
    git clone https://github.com/RealBeingHHH/zhiwen.git "$ZHIWEN_DIR" 2>/dev/null || \
    git clone git@github.com:RealBeingHHH/zhiwen.git "$ZHIWEN_DIR" 2>/dev/null || {
        echo -e "${RED}克隆失败. 请检查网络或手动下载:${NC}"
        echo "  git clone https://github.com/RealBeingHHH/zhiwen.git"
        exit 1
    }
fi
cd "$ZHIWEN_DIR"
echo -e "  ${GREEN}✓${NC} 代码就绪: $ZHIWEN_DIR"

# ── 3. 依赖 ──
echo -e "${CYAN}[3/4]${NC} 安装依赖..."
pip install -r requirements.txt --quiet 2>/dev/null || pip install fastapi uvicorn pydantic --quiet
echo -e "  ${GREEN}✓${NC} 依赖就绪"

# ── 4. API 密钥 ──
if [ ! -f .env.llm ]; then
    echo ""
    echo -e "${CYAN}配置 LLM API 密钥:${NC}"
    echo "  支持 DeepSeek / OpenAI / 任何兼容 API"
    echo ""
    read -p "  API Key (留空跳过): " API_KEY
    if [ -n "$API_KEY" ]; then
        read -p "  API Base URL [https://api.deepseek.com/v1]: " BASE_URL
        BASE_URL="${BASE_URL:-https://api.deepseek.com/v1}"
        read -p "  Model [deepseek-chat]: " MODEL
        MODEL="${MODEL:-deepseek-chat}"
        cat > .env.llm << EOF
{
  "OPENAI_API_KEY": "$API_KEY",
  "OPENAI_BASE_URL": "$BASE_URL",
  "OPENAI_MODEL": "$MODEL"
}
EOF
        echo -e "  ${GREEN}✓${NC} 配置完成"
    else
        echo -e "  ${CYAN}⊘${NC} 跳过 (可稍后编辑 .env.llm)"
    fi
fi

# ── 启动 ──
echo ""
echo -e "${CYAN}[4/4]${NC} 启动知纹..."
echo ""
echo -e "  ${GREEN}✓${NC} 知纹已就绪: http://localhost:$PORT"
echo -e "  ${GREEN}✓${NC} 健康检查: curl http://localhost:$PORT/api/health"
echo -e "  ${GREEN}✓${NC} 流式对话: curl -X POST http://localhost:$PORT/api/chat/stream -H 'Content-Type: application/json' -d '{\"message\":\"你好\"}'"
echo ""
echo -e "  按 ${RED}Ctrl+C${NC} 停止"
echo ""

exec python3 server.py --port "$PORT"
