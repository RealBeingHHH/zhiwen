# Zhiwen · Installation Guide

## System Requirements

| Component | Minimum | Notes |
|---|---|---|
| Python | 3.9+ | Primary runtime |
| pip | 21.0+ | Package manager |
| Git | 2.0+ | Clone the repo |
| WSL2 | Any version | Required for Windows (native runtime environment) |
| Disk | 500MB | Code + data + cache |

---

## Three-Step Setup

### ① Clone

```bash
git clone https://github.com/nesquena/hermes-webui.git
cd hermes-webui/workspace/liaoliao
```

### ② Install Dependencies

```bash
# Core
pip install fastapi uvicorn pydantic aiofiles

# Optional: document reading
pip install pymupdf python-docx openpyxl  # PDF / Word / Excel parsing
```

### ③ Configure LLM API

Create `.env.llm`:

```bash
cat > .env.llm << 'EOF'
{
  "OPENAI_API_KEY": "sk-you...here",
  "OPENAI_BASE_URL": "https://api.deepseek.com/v1",
  "OPENAI_MODEL": "deepseek-chat",
  "LLM_MODEL_FAST": "deepseek-chat",
  "LLM_MODEL_STANDARD": "deepseek-v4-pro",
  "LLM_MODEL_DEEP": "deepseek-v4-pro"
}
EOF
```

---

## LLM Backend Options

| Backend | `OPENAI_BASE_URL` | Recommended |
|---|---|---|
| **DeepSeek** | `https://api.deepseek.com/v1` | ⭐ Recommended |
| **OpenAI** | `https://api.openai.com/v1` | Compatible |
| Any OpenAI-compatible API | Set to the provider's endpoint | Flexible |

Model tiering:

| Variable | Route Level | Default |
|---|---|---|
| `LLM_MODEL_FAST` | Greetings, small talk | Same as `OPENAI_MODEL` |
| `LLM_MODEL_STANDARD` | Factual Q&A | Same as `OPENAI_MODEL` |
| `LLM_MODEL_DEEP` | Complex research | Same as `OPENAI_MODEL` |

---

## Starting the Services

### LiaoLiao (Main server :9200)

```bash
cd /mnt/d/hermes-webui/workspace/liaoliao
python3 server.py --port 9200
```

Automatic warm-up on startup:
- φ cache prefetch (saves 1.7s on first query)
- Method router pre-cache
- Matrix index construction

### Voyager (Dashboard :8765)

```bash
cd /mnt/d/hermes-webui/workspace/voyager
python3 serve.py --port 8765
```

### Tianshu (Trust Anchor :9000 :9001 :9100)

```bash
cd /opt/tianshu
python3 api.py --port 9000
```

---

## Verify Installation

```bash
# ① Health check
curl http://localhost:9200/api/health
# → {"status":"ok","name":"了了","version":"2.0.0","backend":"openai"}

# ② Standard chat
curl -X POST http://localhost:9200/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'
# → {"reply":"你来了。","emotion":"warm",...}

# ③ Streaming chat (recommended)
curl -X POST http://localhost:9200/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"Analyze Japan MMT policy effects"}'
# → Token-by-token streaming, 0.5s first token

# ④ Voyager φ value
curl http://localhost:8765/api/phi
# → {"global_phi":0.01,"agent_count":1}

# ⑤ Self-audit
python3 self_audit.py
# → 12/12 passed · Grade B · 0.88
```

---

## Directory Layout

```
liaoliao/
├── server.py             Main server (FastAPI, 1494 lines, 44 endpoints)
├── mind.py               LLM backend (streaming support)
├── pipeline.py           Pipeline orchestrator (20+ layers)
├── genome_pipeline.py    DNA dual-track pipeline
├── research_planner.py   Research planner (query decomposition)
├── reasoning_engine.py   Reasoning engine (explicit inference chains)
├── engineering_dag.py    Engineering DAG (topological scheduling)
├── compute_layer.py      Compute layer (async + TTL cache)
├── data_gate.py          Data quality gates (4-layer verification)
├── genome_core.py        DNA core (AGCT base architecture)
├── genome_guardian.py    Genome six-layer protection
├── epigenetics.py        Epigenetics (expression profile switching)
├── pattern_memory.py     Pattern memory (follow-up detection)
├── self_audit.py         Self-audit (12 boundary attacks)
├── end_to_end_test.py    End-to-end tests (15 cases)
├── component_index.py    Component index generator
├── data/                 Runtime data (rebuildable on restart)
├── docs/                 Documentation
├── skills/               Skill definitions
└── journal/              Journal storage
```

---

## FAQ

### `ModuleNotFoundError: No module named 'xxx'`

Run from the `liaoliao/` directory: `python3 server.py --port 9200`. The current directory is automatically on the Python path.

### First query is slow (>10s)

Expected. Warm-up handles some caching, but the first search and LLM call still incur API latency. Subsequent queries (cache hits) are significantly faster.

### Voyager φ read fails

Check that `python3 serve.py --port 8765` is running. φ reads have a 2s timeout and 30s cache; Voyager unavailability does not affect the main server.

### Relation integrity checks not triggering

Ensure data text uses Chinese financial compact format (`资产XXX亿 负债XXX亿`). For short texts, set `worldview_key="forensic"`.

### API key not working

Verify `.env.llm` is valid JSON. Ensure `OPENAI_API_KEY` is >20 characters. `OPENAI_BASE_URL` must start with `https://`.

### Port already in use

```bash
# Check what's using the port
lsof -i :9200
# Use a different port
python3 server.py --port 9201
```
