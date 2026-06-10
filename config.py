"""
了了统一配置 — 消除硬编码

所有路径/端口/阈值集中管理。
部署时只需修改此文件或设置环境变量。
"""

import os
from pathlib import Path

# ════════════════════════════════════════════════════════
# 路径 — 环境变量优先, 回退默认值
# ════════════════════════════════════════════════════════

WORKSPACE = Path(os.environ.get("LIAOLIAO_WORKSPACE", "/mnt/d/hermes-webui/workspace"))
VOYAGER_PATH = Path(os.environ.get("VOYAGER_PATH", str(WORKSPACE / "voyager")))
EVOLUTION_PATH = Path(os.environ.get("EVOLUTION_PATH", str(WORKSPACE / "evolution")))
LIAOLIAO_DIR = Path(os.environ.get("LIAOLIAO_DIR", str(WORKSPACE / "liaoliao")))
DATA_DIR = LIAOLIAO_DIR / "data"

# ════════════════════════════════════════════════════════
# 服务端口
# ════════════════════════════════════════════════════════

LIAOLIAO_PORT = int(os.environ.get("LIAOLIAO_PORT", "9200"))
TIANSHU_PORT = int(os.environ.get("TIANSHU_PORT", "9000"))
TIANSHU2_PORT = int(os.environ.get("TIANSHU2_PORT", "9001"))
DINGQING_PORT = int(os.environ.get("DINGQING_PORT", "9100"))
VOYAGER_PORT = int(os.environ.get("VOYAGER_PORT", "8765"))

TIANSHU_URL = os.environ.get("TIANSHU_URL", f"http://localhost:{TIANSHU_PORT}")
TIANSHU2_URL = os.environ.get("TIANSHU2_URL", f"http://localhost:{TIANSHU2_PORT}")
DINGQING_URL = os.environ.get("DINGQING_URL", f"http://localhost:{DINGQING_PORT}")

# ════════════════════════════════════════════════════════
# 天枢
# ════════════════════════════════════════════════════════

TIANSHU_FINGERPRINTS = {
    "守": os.environ.get("TIANSHU_FP_SHOU", "6eb232a36f693a54"),
    "二": os.environ.get("TIANSHU_FP_ER", "4481662f9c4a8b5e"),
}
TIANSHU_REF_TAU = float(os.environ.get("TIANSHU_REF_TAU", "0.55"))
TIANSHU_CACHE_TTL = int(os.environ.get("TIANSHU_CACHE_TTL", "300"))

# ════════════════════════════════════════════════════════
# 质量闸阈值
# ════════════════════════════════════════════════════════

AUTHENTICITY_THRESHOLD = float(os.environ.get("GATE_AUTH", "0.6"))
COMPLETENESS_THRESHOLD = float(os.environ.get("GATE_COMP", "0.5"))
ACCURACY_THRESHOLD = float(os.environ.get("GATE_ACC", "0.6"))
RELATION_THRESHOLD = float(os.environ.get("GATE_REL", "0.5"))
DEFAULT_GATE_THRESHOLD = float(os.environ.get("GATE_DEFAULT", "0.6"))

# 权重
GATE_WEIGHTS = {
    "authenticity": 0.30,
    "completeness": 0.20,
    "accuracy": 0.30,
    "relation": 0.20,
}

# ════════════════════════════════════════════════════════
# 存储
# ════════════════════════════════════════════════════════

STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", str(Path.home() / ".hermes/profiles/evopolis/storage")))
HOT_MAX_AGE_DAYS = int(os.environ.get("HOT_AGE", "7"))
WARM_MAX_AGE_DAYS = int(os.environ.get("WARM_AGE", "30"))
MAX_CONTEXT_FACTS = int(os.environ.get("MAX_CONTEXT_FACTS", "3"))
MAX_CONTEXT_CHARS = int(os.environ.get("MAX_CONTEXT_CHARS", "600"))
HALLUCINATION_WARN_NODES = int(os.environ.get("WARN_NODES", "300"))
HALLUCINATION_CRITICAL_NODES = int(os.environ.get("CRITICAL_NODES", "500"))

# ════════════════════════════════════════════════════════
# 念念η
# ════════════════════════════════════════════════════════

ETA_HALF_LIFE_DAYS = int(os.environ.get("ETA_HALF_LIFE", "30"))
ETA_MIN = float(os.environ.get("ETA_MIN", "1.0"))
ETA_MAX = float(os.environ.get("ETA_MAX", "100.0"))
ETA_GAZE_WEIGHTS = {
    "retrieval": 1,
    "citation": 3,
    "verification": 5,
    "endorsement": 10,
}

# ════════════════════════════════════════════════════════
# LLM
# ════════════════════════════════════════════════════════

LLM_MAX_TOKENS_DEFAULT = int(os.environ.get("LLM_MAX_TOKENS", "300"))
LLM_CHUNK_SIZE = int(os.environ.get("LLM_CHUNK_SIZE", "1200"))
LLM_PRICING = {"input": 0.27, "output": 1.10}  # USD/1M tokens
LLM_EFFECTIVE_WINDOW = int(os.environ.get("LLM_WINDOW", "8000"))

# ════════════════════════════════════════════════════════
# DNA演化
# ════════════════════════════════════════════════════════

DNA_CROSSOVER_RATE = float(os.environ.get("DNA_CROSSOVER", "0.3"))
DNA_MUTATION_RATE = float(os.environ.get("DNA_MUTATION", "0.1"))
DNA_SURVIVAL_THRESHOLD = float(os.environ.get("DNA_SURVIVAL", "0.4"))
DNA_MIN_ETA = float(os.environ.get("DNA_MIN_ETA", "3.0"))
DNA_MAINTENANCE_PROB = float(os.environ.get("DNA_MAINT_PROB", "0.1"))

# ════════════════════════════════════════════════════════
# 织星LLM安全
# ════════════════════════════════════════════════════════

VOYAGER_LLM_VERIFY_NUMBERS = os.environ.get("VOYAGER_VERIFY_NUMBERS", "true").lower() in ("true", "1", "yes")
VOYAGER_LLM_MAX_CHUNK = int(os.environ.get("VOYAGER_CHUNK", "1200"))


# ════════════════════════════════════════════════════════
# 导出
# ════════════════════════════════════════════════════════

def show():
    """打印当前配置。"""
    import json
    config = {k: str(v) for k, v in globals().items() if k.isupper() and not k.startswith("_")}
    print(json.dumps(config, indent=2, ensure_ascii=False))
