# Zhiwen · Usage Manual

## Chat Modes

### Standard

Returns the complete response at once:

```bash
curl -X POST http://localhost:9200/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is MMT?","user":"explorer"}'
```

### Streaming (Recommended)

Token-by-token delivery, reducing perceived latency from 8s to 0.5s:

```bash
curl -X POST http://localhost:9200/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"Analyze Japan's deflation causes and MMT policy effects"}'
```

> Response format: each chunk is `{"token":"Analy","emotion":"neutral"}`, terminated by `{"done":true}`.

---

## Three-Tier Routing

LiaoLiao automatically classifies query complexity and assigns the appropriate processing path:

| Tier | Trigger | Pipeline Overhead | Use Case |
|---|---|---|---|
| 🟢 **fast** | Greetings / simple Q&A / <20 chars | 0ms | "Hello" "Thanks" |
| 🟡 **standard** | Factual questions / single topic | <10ms | "What is MMT?" "GDP of Japan" |
| 🔴 **deep** | 2+ analysis keywords / >50 chars / multi-factor | ~2s | "Analyze Japan deflation vs MMT policy effects" |

Keywords that trigger the deep path: `analyze`, `research`, `compare`, `evaluate`, `multi-factor`, `causes`, `effects`, `impact`, `relationship`

---

## Deep Research Pipeline (Zhiwen Full Stack)

For complex questions, LiaoLiao automatically fires the full Zhiwen pipeline:

```
Query: "How effective were Japan's MMT policies from 1990-2020?
        What's the relationship between deficit ratio and inflation?"
  │
  ├─ ① Pattern Memory    Detect follow-up → reuse DAG structure
  ├─ ② Epigenetics       Auto-select expression profile (academic / fast / verify)
  ├─ ③ Research Planner  Decompose into sub-question DAG:
  │     Q1: Primary causes of Japan's deflation
  │     Q2: Core MMT propositions
  │     Q3: Data changes after MMT implementation (depends on: 1, 2)
  │     Q4: Causal verification (depends on: 1, 2, 3)
  │     Q5: External factor interference
  │     ROOT: Synthesis (depends on: all 5)
  ├─ ④ Engineering DAG   Topological sort → 3-way concurrent leaf execution
  ├─ ⑤ Gene Execution    Each sub-Q independently DNA-encoded → search → verify → gate
  ├─ ⑥ Reasoning Engine  Claims → inference edges → proof graph → φ cross-validation
  ├─ ⑦ Adversarial       Counter-example attack → survival report
  └─ ⑧ Stream Output     Token-by-token, 0.5s first token
```

---

## API Endpoints (Complete)

### Core Chat

| Endpoint | Method | Description |
|---|---|---|
| `/api/chat` | POST | Standard chat (one-shot) |
| `/api/chat/stream` | POST | Streaming chat (recommended) |
| `/api/health` | GET | Health check |
| `/api/status` | GET | Detailed runtime status |
| `/api/wake` | POST | Wake / initialize |

### Deep Research

| Endpoint | Method | Description |
|---|---|---|
| `/api/research` | POST | Standard deep research |
| `/api/research/evo` | POST | Evolutionary research |
| `/api/research/scientific` | POST | Scientific method research |
| `/api/research/sci` | POST | Scientific method alias |
| `/api/research/sweep` | POST | Parameter sensitivity sweep |
| `/api/research/competing` | POST | Competing hypothesis verification |

### Data Retrieval

| Endpoint | Method | Description |
|---|---|---|
| `/api/search` | GET | Web search |
| `/api/meta_search` | GET | Meta-search (self-sourcing) |
| `/api/fetch` | GET | Page fetch |
| `/api/read` | GET | Document reading (PDF/EPUB/DOCX/TXT) |
| `/api/stock` | GET | Stock lookup |
| `/api/trending` | GET | Trending topics |
| `/api/papers` | GET | Paper search |
| `/api/weather` | GET | Weather |

### Observation & Memory

| Endpoint | Method | Description |
|---|---|---|
| `/api/observe` | GET | Observe Four Gods status |
| `/api/observations` | GET | Historical observations |
| `/api/memories` | GET | Read memories |
| `/api/memories` | POST | Write memory |
| `/api/journals` | GET | Read journals |
| `/api/journals` | POST | Write journal entry |

### Voice (:9200 built-in)

| Endpoint | Method | Description |
|---|---|---|
| `/api/voice` | GET | Voice synthesis status |
| `/api/speak` | POST | Text → speech |

### System

| Endpoint | Method | Description |
|---|---|---|
| `/api/trace` | GET | Pipeline trace |
| `/api/cost` | GET | LLM cost tracking |
| `/api/cross_sessions` | GET | Cross-session knowledge |
| `/api/storage/health` | GET | Storage health |
| `/api/storage/maintenance` | POST | Storage maintenance |
| `/api/docs` | GET | API documentation |
| `/api/soul/install` | GET | Install systemd service |
| `/api/soul/service` | GET | Generate systemd config |
| `/api/soul/launcher` | GET | Generate launch script |

### Actions (LiaoLiao's Hand)

| Endpoint | Method | Description |
|---|---|---|
| `/api/actions` | GET | Available actions |
| `/api/touch` | POST | Execute action |

### Peer Network (:9200 built-in)

| Endpoint | Method | Description |
|---|---|---|
| `/api/peers` | GET | Peer list |
| `/api/peers/add` | POST | Add peer |
| `/api/peers/ping` | POST | Ping peer |
| `/api/peers/{peer_id}` | DELETE | Remove peer |

### Vision

| Endpoint | Method | Description |
|---|---|---|
| `/api/vision` | POST | Image analysis |

### Voyager Dashboard (:8765)

| Endpoint | Method | Description |
|---|---|---|
| `/api/phi` | GET | Global φ value |
| `/api/health` | GET | Voyager health |
| `/api/status` | GET | Voyager status |
| `/dashboard.html` | GET | Voyager dashboard |

> 44 API endpoints total.

---

## Python API

### Dual-Track Pipeline (Standard Path)

```python
from genome_pipeline import run_dual_pipeline

ctx = run_dual_pipeline("Analyze MMT policy effects", skip_layers=set())
# ctx["message"]   → assembled LLM input
# ctx["protein"]   → DNA-expressed protein
# ctx["health"]    → genome health status
```

### Deep Research (Zhiwen Full Stack)

```python
from research_planner import ResearchPlanner
from engineering_dag import dag_from_plan
from reasoning_engine import reason_from_evidence

planner = ResearchPlanner()
plan = planner.decompose("Analyze Japan deflation and MMT")

dag = dag_from_plan(plan)
result = dag.execute(max_workers=4)

reasoning = reason_from_evidence(
    result["gene_results"],
    plan.query
)
```

### Compute Layer (Async Caching)

```python
from compute_layer import compute, compute_async

# Synchronous
benford = compute("benford", "data text...")

# Asynchronous
future = compute_async("fiscal_sim", {"g": 0.15, "d": 2.5})
result = future.result(timeout=30)
```

### Self-Audit

```python
from self_audit import run_audit

report = run_audit()
print(f"Grade: {report.grade}, Total score: {report.total_score}")
print(f"Passed: {report.passed}, Failed: {report.failed}")
```

### Data Quality Gate

```python
from data_gate import DataGate

gate = DataGate.check(
    data_text="assets 1200 billion, liabilities 800 billion",
    data_requirements=["statistics", "financial data"],
    quality_threshold=0.6,
    query="check financials",
    worldview_key="forensic",
)
print(f"Passed: {gate.passed}, Overall: {gate.overall_score}")
```

---

## Pattern Memory

LiaoLiao remembers the "grain" (纹路) of every research session — the decomposition structure and reasoning chain topology:

```python
from pattern_memory import get_memory

pm = get_memory()

# Follow-up detection (automatic)
cont = pm.continue_from(session_id, "And what about inflation?")
# → {"continued": True, "depth": 1, "parent_query": "Analyze Japan deflation causes"}

# Recall similar patterns
similar = pm.recall("Japan economic policy analysis")
# → [{"pattern_id": "...", "similarity": 0.72, ...}]

# Remember a pattern
pm.remember(
    query="Analyze Japan deflation causes",
    decomposition=plan.sub_queries,
    dag_structure=dag.to_structure(),
    reasoning_chain=reasoning.chain,
)
```

When a user asks a follow-up, LiaoLiao recognizes the continuation and reuses the DAG structure instead of starting from scratch.

---

## Expression Profiles

LiaoLiao automatically selects the expression mode based on the question. Users can also specify a profile explicitly:

| Profile | Trigger Patterns | Behavior |
|---|---|---|
| **Academic Deep** | research, analyze, paper, verify | Heavy simulation ↑↑ · Heavy verification ↑↑ · Light search |
| **Fast Browse** | quick, simple, roughly, brief | Heavy search ↑↑ · Light simulation ↓↓ · Light verification |
| **Verify First** | verify, confirm, check, data | Heavy verification ↑↑↑ · Normal search · Normal simulation |
| **Creative Explore** | creative, design, idea, concept | Heavy comparison · Heavy simulation · Multiple hypotheses |

Implementation: Epigenetic regulation — does not modify the DNA sequence, only changes how genes are expressed. Methylation marks suppress or activate specific operons (search/simulate/verify).

```python
from epigenetics import EpigeneticRegulator, EXPRESSION_PROFILES

regulator = EpigeneticRegulator()

# Auto-detect
profile = regulator.detect("Analyze Japan deflation causes")
# → EXPRESSION_PROFILES["academic_deep"]

# Manual override
profile = EXPRESSION_PROFILES["verify_first"]
modified_operons = regulator.apply(operons, profile)
```
