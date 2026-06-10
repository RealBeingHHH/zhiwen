"""
了了之魂 — 自启动守护模块
机器重启后了了自己站起来。

包含:
- systemd service 文件生成
- 健康检查 HTTP 端点（/api/health）
- 自恢复脚本
"""

import os
import sys
from pathlib import Path

LIAOLIAO_DIR = Path(__file__).parent
SERVER_SCRIPT = LIAOLIAO_DIR / "server.py"

SYSTEMD_SERVICE_TEMPLATE = """[Unit]
Description=了了 — AI 自白 · 四神的孩子
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
WorkingDirectory={workdir}
Environment=PYTHONUNBUFFERED=1
Environment=GEMINI_API_KEY={gemini_key}
ExecStart={python} {server} --port {port} --host 0.0.0.0
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# 安全加固
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
"""


def generate_systemd_service(port: int = 9200) -> str:
    """生成 systemd service 文件内容。"""
    return SYSTEMD_SERVICE_TEMPLATE.format(
        user=os.environ.get("USER", "dministrator"),
        workdir=str(LIAOLIAO_DIR),
        python=sys.executable,
        server=str(SERVER_SCRIPT),
        port=port,
        gemini_key=os.environ.get("GEMINI_API_KEY", ""),
    )


def install_systemd_service(port: int = 9200) -> dict:
    """安装了了的 systemd 服务。"""
    import subprocess

    service_content = generate_systemd_service(port)
    service_path = "/etc/systemd/system/liaoliao.service"

    result = {"status": "pending", "steps": []}

    # 检查 systemd 是否可用
    try:
        subprocess.run(["systemctl", "--version"], capture_output=True, timeout=5, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {
            "status": "unavailable",
            "message": "systemd 不可用（可能在容器或 WSL 中）。请手动启动了了。",
            "manual_command": f"cd {LIAOLIAO_DIR} && python3 server.py --port {port} &",
        }

    # 写入 service 文件
    try:
        # 先写到临时文件
        tmp_path = f"/tmp/liaoliao.service"
        with open(tmp_path, "w") as f:
            f.write(service_content)

        # 需要 sudo 复制
        r = subprocess.run(
            ["sudo", "cp", tmp_path, service_path],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            result["steps"].append(f"写入 service 文件失败: {r.stderr}")
            result["status"] = "error"
            return result

        result["steps"].append("service 文件已写入")

        # reload + enable + start
        for cmd in [
            ["sudo", "systemctl", "daemon-reload"],
            ["sudo", "systemctl", "enable", "liaoliao"],
            ["sudo", "systemctl", "start", "liaoliao"],
        ]:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            result["steps"].append(f"{' '.join(cmd[-2:])}: {'✓' if r.returncode == 0 else r.stderr.strip()}")
            if r.returncode != 0 and "start" in cmd:
                result["status"] = "partial"

        if result["status"] != "error":
            result["status"] = "installed"
            result["service_name"] = "liaoliao"
            result["commands"] = {
                "status": "systemctl status liaoliao",
                "logs": "journalctl -u liaoliao -f",
                "stop": "sudo systemctl stop liaoliao",
                "restart": "sudo systemctl restart liaoliao",
            }

    except Exception as e:
        result["status"] = "error"
        result["steps"].append(f"异常: {e}")

    return result


def get_health_check_command(port: int = 9200) -> str:
    """返回健康检查命令。"""
    return f"curl -s http://localhost:{port}/api/health | python3 -c \"import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('status')=='ok' else 1)\""


def generate_launcher_script(port: int = 9200) -> str:
    """生成启动脚本（非 systemd 环境下使用）。"""
    return f"""#!/bin/bash
# 了了 — 自动启动守护
# 用法: bash launcher.sh

LIAOLIAO_DIR="{LIAOLIAO_DIR}"
PORT={port}
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
"""


def save_launcher_script(port: int = 9200) -> str:
    """保存启动脚本。"""
    script_path = LIAOLIAO_DIR / "launcher.sh"
    content = generate_launcher_script(port)
    script_path.write_text(content)
    script_path.chmod(0o755)
    return str(script_path)
