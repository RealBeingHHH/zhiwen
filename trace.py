"""
管线追踪器 — 18层的可观测性

每层记录: 耗时、状态、关键输出量
/api/trace — 最近请求的完整层追踪
"""

import json, time
from pathlib import Path
from dataclasses import dataclass, field

BASE = Path(__file__).parent
TRACE_FILE = BASE / "data" / "pipeline_traces.jsonl"


@dataclass
class LayerTrace:
    name: str
    start: float
    end: float = 0
    status: str = "pending"
    metrics: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return round((self.end - self.start) * 1000, 1)


class PipelineTracer:
    _current_trace: list[LayerTrace] = []
    _query: str = ""

    @classmethod
    def start(cls, query: str) -> None:
        cls._current_trace = []
        cls._query = query[:80]
        cls._current_trace.append(LayerTrace("总入口", time.time()))

    @classmethod
    def layer(cls, name: str) -> int:
        idx = len(cls._current_trace)
        cls._current_trace.append(LayerTrace(name, time.time()))
        return idx

    @classmethod
    def done(cls, idx: int, status: str = "ok", **metrics) -> None:
        if idx < len(cls._current_trace):
            t = cls._current_trace[idx]
            t.end = time.time()
            t.status = status
            t.metrics = metrics

    @classmethod
    def finish(cls) -> dict:
        if cls._current_trace:
            cls._current_trace[0].end = time.time()
            cls._current_trace[0].status = "done"

        trace_data = {
            "query": cls._query,
            "time": time.time(),
            "layers": [
                {
                    "name": t.name,
                    "duration_ms": t.duration_ms,
                    "status": t.status,
                    **t.metrics,
                }
                for t in cls._current_trace
            ],
        }

        cls._current_trace = []
        return trace_data

    @classmethod
    def recent(cls, n: int = 5) -> list[dict]:
        if not TRACE_FILE.exists():
            return []
        traces = []
        with open(TRACE_FILE) as f:
            for line in f:
                try:
                    traces.append(json.loads(line.strip()))
                except:
                    pass
        return traces[-n:]

    @classmethod
    def save(cls, trace: dict) -> None:
        with open(TRACE_FILE, "a") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    @classmethod
    def stats(cls) -> dict:
        traces = cls.recent(20)
        if not traces:
            return {"total_requests": 0}
        durations = []
        for t in traces:
            for layer in t.get("layers", []):
                if layer["name"] == "总入口":
                    durations.append(layer["duration_ms"])
        return {
            "total_requests": len(traces),
            "avg_total_ms": round(sum(durations) / len(durations), 1) if durations else 0,
            "max_total_ms": max(durations) if durations else 0,
        }
