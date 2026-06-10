"""
成本面板 — LLM token使用追踪

每层LLM调用记录: tokens_in(估), tokens_out, 耗时
累计成本按 DeepSeek 定价: ~$0.28/1M input, ~$1.10/1M output
"""

import json, time, math
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent
COST_FILE = BASE / "data" / "llm_costs.jsonl"

# DeepSeek V3 定价 (per 1M tokens, USD)
PRICING = {"input": 0.27, "output": 1.10}


class CostTracker:
    _session_calls: list = []

    @classmethod
    def record(cls, layer: str, chars_in: int, chars_out: int, duration_ms: float) -> None:
        tok_in = max(1, chars_in // 3)
        tok_out = max(1, chars_out // 3)
        cost = (tok_in / 1e6 * PRICING["input"] + tok_out / 1e6 * PRICING["output"])

        cls._session_calls.append({
            "layer": layer, "time": time.time(),
            "tokens_in": tok_in, "tokens_out": tok_out,
            "cost_usd": round(cost, 6), "duration_ms": round(duration_ms, 1),
        })

    @classmethod
    def session_total(cls) -> dict:
        if not cls._session_calls:
            return {"calls": 0, "total_cost": 0}
        by_layer = defaultdict(lambda: {"count": 0, "cost": 0, "tokens": 0})
        for c in cls._session_calls:
            l = c["layer"]
            by_layer[l]["count"] += 1
            by_layer[l]["cost"] += c["cost_usd"]
            by_layer[l]["tokens"] += c["tokens_in"] + c["tokens_out"]

        total_cost = sum(c["cost_usd"] for c in cls._session_calls)
        return {
            "calls": len(cls._session_calls),
            "total_cost_usd": round(total_cost, 4),
            "total_cost_rmb": round(total_cost * 7.2, 2),
            "by_layer": {k: {"calls": v["count"], "cost": round(v["cost"], 4),
                              "tokens": v["tokens"]}
                         for k, v in sorted(by_layer.items(), key=lambda x: -x[1]["cost"])},
        }

    @classmethod
    def flush_session(cls) -> None:
        cls._session_calls = []

    @classmethod
    def historical(cls) -> dict:
        if not COST_FILE.exists():
            return {"total_cost": 0, "sessions": 0}
        total = 0
        count = 0
        with open(COST_FILE) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    total += d.get("total_cost_usd", 0)
                    count += 1
                except:
                    pass
        return {"total_cost_usd": round(total, 4), "sessions": count}

    @classmethod
    def save_session(cls) -> None:
        summary = cls.session_total()
        summary["time"] = time.time()
        with open(COST_FILE, "a") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")


# ═══ 自检 ═══
if __name__ == "__main__":
    CostTracker.record("worldview", chars_in=500, chars_out=200, duration_ms=120)
    CostTracker.record("sci_method", chars_in=2000, chars_out=400, duration_ms=450)
    CostTracker.record("llm_response", chars_in=3000, chars_out=800, duration_ms=600)
    print(json.dumps(CostTracker.session_total(), indent=2, ensure_ascii=False))
