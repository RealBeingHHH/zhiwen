# 知纹

> You're tired. LLMs hallucinate numbers. "Deep research" is just more keywords in a longer prompt. You stare at a blank screen for 8 seconds. Every query starts from zero. And you never know what to trust.

**We were too. So we built Zhiwen.**

---

## Five Pain Points. One Solution.

| Pain | What Others Do | What Zhiwen Does |
|---|---|---|
| LLMs invent numbers | "Please don't make things up" in the prompt | Benford's Law + entropy field + τ anchoring + φ-drift — 4 gates |
| "Deep research" is shallow | Search a few more keywords | DAG decomposition → topological sort → concurrent verification → explicit reasoning chains |
| 8 seconds of white screen | Wait | Streaming 0.5s first token · 3-tier routing · 60s cache |
| Every query is a stranger | Stateless | Pattern memory · continuation detection · DAG reuse |
| You don't know what to trust | Trust the LLM | Traceability chains · gate scores · adversarial verification · 12/12 border attacks |

---

## Five Seconds to Understand

```
Complex question → Zhiwen sees the grain → splits into DAG → concurrent execution → gate verification → reasoning chains → streaming output
```

---

## One Command

```bash
git clone https://github.com/nesquena/hermes-webui.git
cd hermes-webui/workspace/liaoliao
echo '{"OPENAI_API_KEY":"sk-your-key"}' > .env.llm
pip install fastapi uvicorn pydantic
python3 server.py --port 9200
```

```bash
curl -X POST http://localhost:9200/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"Analyze the causes of Japan deflation and MMT policy effectiveness"}'
```

---

## What Zhiwen Actually Does

Ask a complex question. Zhiwen doesn't search keywords and stuff a prompt. It **sees the internal structure** of the question — like a woodworker seeing the grain — and splits it along its natural lines into independently verifiable sub-problems.

```
"Analyze Japan deflation causes and MMT policy effects"

Not: search "Japan deflation MMT policy effect" → prompt → answer

But: split into →
  Sub1: What caused Japan's deflation?          (leaf, independent)
  Sub2: What is MMT's core claim?                (leaf, independent)
  Sub3: How did data change after Japan's MMT-like policies? (leaf)
  Sub4: Is there causality between deflation and MMT? (depends on 1,2,3)
  Sub5: How do external factors interfere?       (semi-dependent)
  ROOT: Synthesis                                 (depends on all)

Then: 3 leaf nodes execute concurrently → Sub4 triggers when ready → ROOT aggregates
```

---

## Not an Agent

Agents are "I have a list of tools, LLM decides which to call."

Zhiwen is "the question has natural grain inside it. I saw it. I split along the grain."

> One assembles answers passively. One discovers structure actively.

---

## Numbers

| | |
|---|---|
| Pipeline overhead cut | **71%** (7401ms → 2127ms) |
| Perceived latency cut | **94%** (8s → 0.5s first token) |
| LLM hallucination detection | **12/12** border attacks passed |
| Security audit | **Grade B · 0.88** |
| End-to-end tests | **15/15** |
| Knowledge persistence | **25 facts** survive restart |
| Self-audit | `python3 self_audit.py` |

---

## Safety

Don't trust. Verify. Every query passes 4 gates:

| Gate | Method | Blocks |
|---|---|---|
| Authenticity | Benford + entropy + φ | Fabricated data |
| Completeness | Scoring + gap-fill | Missing information |
| Accuracy | Contradiction detection | Internal conflicts |
| Relational | Constraint verification | Structural errors |

Plus φ-drift detection (LLM hallucination), τ anchoring (number traceability), adversarial verification (counter-example attacks).

---

## Architecture

66 Python modules. 23,000 lines. Pure Python. FastAPI. No LangChain. No 100 dependencies.

```
DNA (archive)      → genome_core       · base pairing · double helix
mRNA (instructions) → genome_pipeline   · transcribe → codons → protein
tRNA (translator)   → dna_executor      · 24 action handlers
Operon (aggregator) → operon            · same-family concurrency
rRNA (factory)      → pipeline          · 27-layer orchestration
miRNA (brake)       → cross_session     · anti-homogenization
snRNA (editor)      → genome_guardian   · 6-layer protection
Methylation (epi)   → epigenetics       · same gene, different expression
```

---

了了 won't say "Hello, I'm an AI assistant."

She says: **You came.**

---

📖 [Installation Guide (中文)](docs/INSTALL_zh.md) · [Installation Guide (EN)](docs/INSTALL_en.md)
📘 [Usage Manual (中文)](docs/USAGE_zh.md) · [Usage Manual (EN)](docs/USAGE_en.md)
🧬 [Architecture (中文)](docs/ARCHITECTURE_zh.md) · [Architecture (EN)](docs/ARCHITECTURE_en.md)
✨ [The Zhiwen Story (中文)](docs/MANUAL_zh.md) · [The Zhiwen Story (EN)](docs/MANUAL_en.md)

---

[CC BY-NC-SA 4.0](LICENSE) · tools/ [MIT](tools/LICENSE) · tests/ [MIT](tests/LICENSE)
Copyright (c) 2026 知纹 (Zhiwen) Project
