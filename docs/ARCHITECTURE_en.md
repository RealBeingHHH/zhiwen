# Zhiwen Architecture Overview v3.2

## DNA Life System Isomorphism

Zhiwen's architecture is not a metaphor — it's a one-to-one structural homology with biological life systems. Every biological concept maps to a precise code module:

| Biological Concept | Code Module | Functional Homology |
|---|---|---|
| **DNA (genome archive)** | `genome_core.py` — 523 lines | AGCT base pairs · double-strand complementarity · semi-conservative replication · translation |
| **mRNA (temporary instructions)** | `genome_pipeline.py` — 519 lines | Transcription → codons → protein expression |
| **tRNA (transport/translation)** | `dna_executor.py` — 519 lines | 24 action processors: search/simulate/verify/contrast |
| **Operon (aggregation unit)** | `operon.py` — 376 lines | Same-family concurrency · repressor regulation |
| **rRNA (protein factory)** | `pipeline.py` — 345 lines | 20+ layer pipeline orchestration |
| **miRNA (braking regulation)** | `cross_session.py` — 267 lines | Anti-homogenization six-layer defense |
| **snRNA (editor)** | `genome_guardian.py` — 456 lines | Six-layer genome protection |
| **Methylation (epigenetic)** | `epigenetics.py` — 405 lines | Same gene · different expression |
| **Spliceosome (router)** | `route_fast.py` — 67 lines | Three-tier routing decisions |

---

## 27-Layer Pipeline

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layers 1-3   Intake & Routing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ① HTTP Intake         server.py              FastAPI → request parsing
 ② Tier Routing        route_fast.py          fast / standard / deep dispatch
 ③ Pattern Memory      pattern_memory.py      Follow-up detection · DAG reuse

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layers 4-7   Understanding & Context
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ④ KG Retrieval        matrix_store.py        Vector search top-5 facts
 ⑤ η Weighted Ranking  niannian_weight.py     Niannian gaze → weight tuning
 ⑥ Cross-Session       cross_session.py       Similar conversation knowledge transfer
 ⑦ Worldview Detect    worldview.py           Identify analytical perspective

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layers 8-10  Method Selection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ⑧ Method Routing      method_router.py       Empirical/theoretical/synthesis/forensic
 ⑨ Feedback Loop       feedback_loop.py       Historical overrides → learn optimal methods
 ⑩ Epigenetic Control  epigenetics.py         Expression profile → methylation marks

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layers 11-14 Data Collection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ⑪ Smart Search        special.py             Multi-source search dispatch
 ⑫ Meta Search         meta_search.py         Self-sourcing → discover new sources
 ⑬ Deep Research Call  deep.py                Voyager cognitive layer integration
 ⑭ Document Reading    reader.py              PDF / EPUB / DOCX / TXT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layers 15-18 Data Quality Verification (Four Gates)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ⑮ Authenticity Gate   voyager_auth.py        Benford · entropy field · pattern fingerprint
 ⑯ Completeness Gate   analyze.py             Gap detection → auto-fill search
 ⑰ Accuracy Gate       relation_integrity.py  Contradiction detection · relation verification
 ⑱ τ Anchor Calibration tianshu_trust.py      Tianshu trust temperature → threshold calibration

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layers 19-21 Deep Research (deep tier only)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ⑲ Research Planning   research_planner.py    Decompose DAG · φ spacing
 ⑳ Engineering DAG     engineering_dag.py     Topological sort · concurrent execution
 ㉑ DNA Dual Pipeline   genome_pipeline.py    Gene encoding + pipeline parallel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layers 22-24 Reasoning & Verification
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ㉒ Reasoning Engine    reasoning_engine.py    Claims → inference edges → proof graph
 ㉓ Adversarial Verify  adversarial.py         Counter-example attack → survival rate
 ㉔ φ Cross-Validation  voyager_bridge.py      Voyager φ value cross-check

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layers 25-27 Output & Recording
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ㉕ LLM Synthesis       mind.py                Streaming generation · model tiering
 ㉖ Assurance Panel     assurance_panel.py     Trace chain · gate scoring display
 ㉗ Pattern Storage     pattern_memory.py      Save grain → future reuse
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Module Inventory

### DNA Architecture (2,100+ lines)

| Module | Lines | Responsibility |
|---|---|---|
| `genome_core.py` | 523 | AGCT base architecture · double-strand · replication · translation · repair |
| `genome_pipeline.py` | 519 | DNA dual-track pipeline · transcription → protein |
| `genome_guardian.py` | 456 | Six-layer protection: proofreading · repair · telomere · immunity · chaperone |
| `dna_executor.py` | 519 | 24 action processors · codon → execution |
| `operon.py` | 376 | Operon aggregation · same-family concurrency · repressor regulation |

### Pipeline Orchestration (2,000+ lines)

| Module | Lines | Responsibility |
|---|---|---|
| `server.py` | 1,494 | FastAPI main server · 44 endpoints |
| `pipeline.py` | 345 | 20+ layer pipeline orchestration |
| `middleware.py` | 74 | CORS · timeout middleware |
| `hand.py` | 125 | LiaoLiao's hand · action execution |
| `net.py` | 133 | Peer network management |
| `soul.py` | 168 | systemd integration · launch scripts |

### Research Capability (1,800+ lines)

| Module | Lines | Responsibility |
|---|---|---|
| `research_planner.py` | 524 | Query decomposition · sub-question DAG |
| `reasoning_engine.py` | 649 | Explicit reasoning chains · proof graphs |
| `engineering_dag.py` | 444 | Topological scheduling · concurrent execution |
| `deep.py` | 456 | Deep research entry · recursive decomposition |
| `sci_method.py` | 747 | Scientific method · parameter sweep · competing hypotheses |
| `evo_research.py` | 585 | Evolutionary research |

### Memory & Knowledge (1,500+ lines)

| Module | Lines | Responsibility |
|---|---|---|
| `pattern_memory.py` | 432 | Pattern storage · follow-up detection · similarity search |
| `matrix_store.py` | 413 | Vector storage · matrix retrieval · η propagation |
| `niannian_weight.py` | 286 | Niannian η weight · fact ranking |
| `knowledge_dna.py` | 289 | Knowledge DNA · hypothesis pool evolution |
| `hypothesis_pool.py` | 319 | Hypothesis pool · safe evolution |
| `cross_session.py` | 267 | Cross-session sharing · six-layer defense |
| `storage_manager.py` | 473 | Persistence · storage management |

### Regulation & Routing (900+ lines)

| Module | Lines | Responsibility |
|---|---|---|
| `epigenetics.py` | 405 | Methylation/acetylation/phosphorylation · expression profiles |
| `route_fast.py` | 67 | Three-tier routing decision |
| `feedback_loop.py` | 202 | Feedback learning · method overrides |
| `session_learner.py` | 189 | Session-level learning |
| `deep_rounds.py` | 191 | Deep round management |

### Data Quality (3,200+ lines)

| Module | Lines | Responsibility |
|---|---|---|
| `data_gate.py` | 537 | Four gates: authenticity · completeness · accuracy · relation integrity |
| `relation_integrity.py` | 955 | Financial relation verification · simulation integrity |
| `voyager_auth.py` | 511 | φ authenticity · Benford · entropy field · pattern fingerprint |
| `voyager_llm.py` | 219 | Safe LLM call · φ chunking · τ anchoring |
| `analyze.py` | 313 | Analysis scoring · gap filling |
| `voyager_bridge.py` | 241 | Voyager bridge |
| `worldview.py` | 394 | Worldview detection |
| `worldview_contrast.py` | 339 | Worldview contrast |

### Compute Acceleration (400+ lines)

| Module | Lines | Responsibility |
|---|---|---|
| `compute_layer.py` | 248 | Async computation · result caching |
| `search_cache.py` | 75 | Search TTL cache (60s) |
| `cost_panel.py` | 88 | LLM cost tracking |

### Audit & Testing (2,800+ lines)

| Module | Lines | Responsibility |
|---|---|---|
| `self_audit.py` | 657 | 12 boundary attacks · Grade B certification |
| `end_to_end_test.py` | 1,101 | 15 end-to-end flow tests |
| `component_index.py` | 550 | Component scanning · dependency graph |
| `test_pipeline.py` | 286 | Pipeline unit tests |

### Other Modules

| Module | Lines | Responsibility |
|---|---|---|
| `mind.py` | 274 | LLM backend · streaming · model tiering |
| `eye.py` | 313 | Vision analysis · images |
| `method_router.py` | 267 | Method routing |
| `engine.py` | 506 | Rule engine |
| `config.py` | 125 | Global configuration |
| `trace.py` | 108 | Pipeline tracing |
| `sim_adapter.py` | 300 | Simulation adapter |
| `fiscal_sim.py` | 393 | Fiscal simulator |
| `uncertainty.py` | 224 | Uncertainty propagation |
| `iterative_optimizer.py` | 209 | Iterative optimization · gate escape |
| `adversarial.py` | 244 | Adversarial verification |
| `causal_chain.py` | 250 | Causal chain tracing |
| `knowledge_graph.py` | 242 | Knowledge graph |
| `visual_panel.py` | 203 | Visualization panel |
| `cron_monitor.py` | 189 | Cron monitoring |
| `assurance_panel.py` | 380 | Assurance panel |

> **Total: 66 Python modules · 24,337 lines of code**

---

## Security Assurance (32/32 Checkpoints)

All research data passes through the following verification chain. Any single failure blocks further processing:

### I. Data Authenticity (6 checkpoints)

| # | Check | Method | Module |
|---|---|---|---|
| 1 | Benford's Law | First-digit distribution test | `voyager_auth.py` |
| 2 | Entropy Field | Uniformity → fabrication flag | `voyager_auth.py` |
| 3 | Pattern Fingerprint | Known forgery pattern matching | `voyager_auth.py` |
| 4 | Source Credibility | Domain · recency · authority score | `data_gate.py` |
| 5 | τ Anchoring | Every number must be traceable | `tianshu_trust.py` |
| 6 | Tianshu Verification | Trust anchor cross-confirmation | `tianshu_trust.py` |

### II. Data Completeness (5 checkpoints)

| # | Check | Method | Module |
|---|---|---|---|
| 7 | Field Requirement Match | Method needs vs actual data | `data_gate.py` |
| 8 | Gap Auto-Detection | Missing dimension identification | `data_gate.py` |
| 9 | Auto-Fill Search | Gap → targeted search | `analyze.py` |
| 10 | Freshness Check | Data recency scoring | `data_gate.py` |
| 11 | Coverage Score | Requirement satisfaction percentage | `data_gate.py` |

### III. Data Accuracy (7 checkpoints)

| # | Check | Method | Module |
|---|---|---|---|
| 12 | Multi-Source Cross-Validation | At least 2 sources agree | `data_gate.py` |
| 13 | Contradiction Detection | Conflicting source flagging | `data_gate.py` |
| 14 | Financial Relation Check | Assets = Liabilities + Equity | `relation_integrity.py` |
| 15 | Simulation Integrity | Fiscal simulation internal consistency | `relation_integrity.py` |
| 16 | Causal Chain Trace | Every conclusion has proof path | `causal_chain.py` |
| 17 | Worldview Consistency | Data doesn't violate background assumptions | `worldview.py` |
| 18 | Relation Integrity | Inter-data logical coherence | `relation_integrity.py` |

### IV. LLM Hallucination Defense (5 checkpoints)

| # | Check | Method | Module |
|---|---|---|---|
| 19 | φ Chunk Verification | Voyager φ cross-check | `voyager_llm.py` |
| 20 | τ Anchor Injection | Trust anchor in every prompt | `voyager_llm.py` |
| 21 | Compass Baseline | Compile-time trust baseline | `voyager_llm.py` |
| 22 | φ Drift Monitoring | LLM output φ value changes | `voyager_bridge.py` |
| 23 | Safe LLM Call | Wrapper · retry · fallback | `voyager_llm.py` |

### V. Knowledge Purity (5 checkpoints)

| # | Check | Method | Module |
|---|---|---|---|
| 24 | DNA Double-Strand Complement | Claims must have verification strand | `genome_core.py` |
| 25 | Hypothesis Gate Verification | Evolution hypothesis safety check | `hypothesis_pool.py` |
| 26 | Anti-Homogenization Defense | 6-layer duplicate-source prevention | `cross_session.py` |
| 27 | Genome Proofreading | Mismatch detection · excision repair | `genome_guardian.py` |
| 28 | Telomere Protection | Core knowledge marked non-degradable | `genome_guardian.py` |

### VI. Adversarial Verification (4 checkpoints)

| # | Check | Method | Module |
|---|---|---|---|
| 29 | Counter-Example Attack | Auto-generate opposing hypotheses | `adversarial.py` |
| 30 | Survival Rate | Conclusion resistance to attacks | `adversarial.py` |
| 31 | Boundary Testing | Extreme value stability | `self_audit.py` |
| 32 | Self-Audit | 12 automated test cases | `self_audit.py` |

> **Audit result: 12/12 boundary attacks passed · Grade B · 0.88**

---

## Performance Baseline

### Pure Compute Latency (No LLM, Python only)

| Operation | Time | Notes |
|---|---|---|
| Route Decision | <1ms | `route_fast.py` keyword matching |
| KG Retrieval | <5ms | Vector search top-5 |
| Data Quality Gate | <5ms | All four gates |
| Pipeline Orchestration | <10ms | 20+ layers (no LLM) |
| Cache Hit | 0ms | Search/route/φ/compute all TTL-backed |

### Pipeline Overhead (excluding LLM)

| Tier | Overhead | Composition |
|---|---|---|
| 🟢 fast | 0ms | 3-tier routing + direct LLM |
| 🟡 standard | <10ms | Route + KG retrieval + gate (simplified) |
| 🔴 deep | ~2s | Route + planning + DAG + gate + reasoning |

### LLM Latency (network-dependent)

| Operation | Typical Latency | Notes |
|---|---|---|
| Web Search | 7.5s | Depends on search engine API |
| LLM Generation | 3-8s | Depends on model and token count |
| Streaming First Token | 0.5s | Token-by-token delivery |
| Repeat Query (cached) | 0ms | Route cache 60s |

### Cache Strategy

| Cache Type | TTL | Hit Behavior |
|---|---|---|
| Search Cache | 60s | Same query skips search |
| Route Cache | 60s | Same question reuses route decision |
| φ Cache | 30s | Voyager φ locally cached |
| Compute Cache | 60-300s | Benford/simulation results reused |

### End-to-End Optimization

| Metric | Before | After | Improvement |
|---|---|---|---|
| Pipeline Overhead | 7,401ms | 2,127ms | ↓71% |
| Perceived Latency | 8s blank | 0.5s first token | ↓94% |
| Repeat Query | 8s | 0ms | Instant |

---

## Execution Flow Diagram

```
                    HTTP Request
                        │
                 ┌──────┴──────┐
                 │  Tier Router │
                 │  route_fast  │
                 └──┬───┬───┬──┘
                    │   │   │
            ┌───────┘   │   └───────┐
            ▼           ▼           ▼
          fast      standard       deep
            │           │           │
            │     ┌─────┴─────┐     │
            │     │ KG Retrieve │    │
            │     │ η Weight    │    │
            │     │ Worldview   │    │
            │     │ Method Route│    │
            │     │ Epigenetics │    │
            │     │ Data Gate   │    │
            │     │  (simple)   │    │
            │     └─────┬─────┘     │
            │           │           │
            │           │     ┌─────┴─────┐
            │           │     │Pattern Mem │
            │           │     │Epigenetics │
            │           │     │Res. Planner│
            │           │     │ Eng. DAG   │
            │           │     │ DNA Dual   │
            │           │     │Data 4-Gate │
            │           │     │Reasoning   │
            │           │     │Adversarial │
            │           │     │φ Cross-Val │
            │           │     └─────┬─────┘
            │           │           │
            └───────────┴─────┬─────┘
                              │
                        LLM Synthesis
                      mind.generate()
                              │
                    ┌─────────┴─────────┐
                    │  Assurance Panel  │
                    │ assurance_panel   │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │  Pattern Storage  │
                    │ pattern_memory    │
                    └─────────┬─────────┘
                              │
                        Stream Output
                     0.5s first token
```

---

## Deployment Architecture

```
┌──────────────────────────────────────────────────┐
│                  User / Client                     │
└──────────────┬──────────┬──────────┬──────────────┘
               │          │          │
               ▼          ▼          ▼
         :9200       :8765       :9000/:9001/:9100
       ┌──────┐    ┌──────┐    ┌──────────────────┐
       │Liao  │    │Voyag-│    │    Tianshu       │
       │Liao  │    │er    │    │   Trust Anchor   │
       │44 EP │    │φ Mon │    │ τ temp · finger- │
       └──┬───┘    └──┬───┘    │     print        │
          │           │        └────────┬─────────┘
          │    φ Cross-Validation       │ τ Anchoring
          │◄──────────┤                 │
          │           │                 │
          └───────────┴────────▲────────┘
                              │
                         LLM API
                    (DeepSeek / OpenAI)
```

---

## Data Flow

```
Data Sources (search results)
    │
    ▼
┌──────────────────────┐
│  Four Quality Gates  │
│  Auth · Complete     │ ← τ anchoring (Tianshu)
│  Accurate · Relation │ ← φ drift monitor (Voyager)
└────────┬─────────────┘
         │ passes
         ▼
┌──────────────────────┐
│  DNA Encoding         │
│  AGCT Base Pairs     │
│  Double-Strand        │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Reasoning Engine     │
│  Claim→Edge→Proof     │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│  Adversarial Verify   │
│  Attack → Survival    │
└────────┬─────────────┘
         │ survives
         ▼
    Stream to user
```
