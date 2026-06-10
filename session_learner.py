"""
会话学习器 — 跨会话积累搜索策略和路由偏好

每次研究结束后，记录:
  - 什么方法对什么问题有效
  - 什么搜索词命中了什么数据
  - 什么世界观对什么问题合适

下次遇到相似问题，自动复用最佳策略。

存储: JSON文件 (~/.hermes/profiles/evopolis/session_learning.json)
"""

import json
import hashlib
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional


STORE_PATH = Path.home() / ".hermes" / "profiles" / "evopolis" / "session_learning.json"
STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


class SessionLearner:
    """跨会话学习存储。"""

    @classmethod
    def _load(cls) -> dict:
        if STORE_PATH.exists():
            try:
                return json.loads(STORE_PATH.read_text())
            except Exception:
                pass
        return {
            "method_success": {},     # {query_hash: {method: {count, avg_gate_score}}}
            "search_terms": {},       # {term: {hit_count, last_used}}
            "worldview_routing": {},  # {worldview: {query_pattern: count}}
            "gate_history": [],       # recent gate results
        }

    @classmethod
    def _save(cls, data: dict) -> None:
        STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def _hash_query(cls, query: str) -> str:
        return hashlib.md5(query[:200].encode()).hexdigest()[:12]

    @classmethod
    def learn_from_session(
        cls,
        query: str,
        method: dict,
        gate_result,
        wv: dict,
        search_queries_used: list = None,
    ) -> None:
        """从本次会话学习。"""
        data = cls._load()
        qhash = cls._hash_query(query)

        # ── 记录方法效果 ──
        method_name = method.get("primary", "unknown")
        gate_score = getattr(gate_result, "overall_score", 0)

        if qhash not in data["method_success"]:
            data["method_success"][qhash] = {}
        if method_name not in data["method_success"][qhash]:
            data["method_success"][qhash][method_name] = {"count": 0, "total_score": 0}
        data["method_success"][qhash][method_name]["count"] += 1
        data["method_success"][qhash][method_name]["total_score"] += gate_score
        data["method_success"][qhash][method_name]["last_query"] = query[:100]

        # ── 记录搜索词 ──
        if search_queries_used:
            for sq in search_queries_used:
                key = sq[:80]
                if key not in data["search_terms"]:
                    data["search_terms"][key] = {"hit_count": 0, "last_used": time.time()}
                data["search_terms"][key]["hit_count"] += 1
                data["search_terms"][key]["last_used"] = time.time()

        # ── 记录世界观路由 ──
        wv_key = wv.get("worldview_key", "")
        if wv_key not in data["worldview_routing"]:
            data["worldview_routing"][wv_key] = {}
        qpattern = query[:60]
        data["worldview_routing"][wv_key][qpattern] = (
            data["worldview_routing"][wv_key].get(qpattern, 0) + 1
        )

        # ── 记录闸门历史（最近50条） ──
        data["gate_history"].append({
            "time": time.time(),
            "query_hash": qhash,
            "query": query[:100],
            "gate_score": gate_score,
            "method": method_name,
            "worldview": wv_key,
        })
        if len(data["gate_history"]) > 50:
            data["gate_history"] = data["gate_history"][-50:]

        cls._save(data)

    @classmethod
    def suggest_method(cls, query: str) -> Optional[str]:
        """根据历史，为相似查询推荐方法。"""
        data = cls._load()
        qhash = cls._hash_query(query)

        # 精确匹配
        if qhash in data["method_success"]:
            methods = data["method_success"][qhash]
            if methods:
                # 返回平均分数最高的方法
                best = max(methods, key=lambda m: (
                    methods[m]["total_score"] / max(methods[m]["count"], 1)
                ))
                return best

        # 模糊匹配：找最相似的查询Hash
        best_score = 0
        best_method = None
        for h, methods in data["method_success"].items():
            # 简单相似度: Hash前4位相同
            if h[:4] == qhash[:4]:
                for m, stats in methods.items():
                    avg = stats["total_score"] / max(stats["count"], 1)
                    if avg > best_score:
                        best_score = avg
                        best_method = m

        return best_method

    @classmethod
    def suggest_search_terms(cls, query: str, max_terms: int = 3) -> list[str]:
        """根据历史，推荐高命中率的搜索词。"""
        data = cls._load()
        terms = data.get("search_terms", {})

        # 按命中次数排序
        ranked = sorted(terms.items(), key=lambda kv: kv[1]["hit_count"], reverse=True)

        # 取前N个
        return [term for term, _ in ranked[:max_terms]]

    @classmethod
    def recent_gate_stats(cls, n: int = 10) -> dict:
        """最近N次质量闸统计。"""
        data = cls._load()
        history = data.get("gate_history", [])[-n:]

        if not history:
            return {"avg_score": 0, "count": 0, "methods": {}}

        scores = [h["gate_score"] for h in history]
        method_counts = defaultdict(int)
        for h in history:
            method_counts[h.get("method", "?")] += 1

        return {
            "avg_score": round(sum(scores) / len(scores), 2),
            "count": len(scores),
            "methods": dict(method_counts),
        }


# ═══ 自检 ═══
if __name__ == "__main__":
    # 模拟学习
    from data_gate import GateResult
    gate = GateResult()
    gate.overall_score = 0.68

    SessionLearner.learn_from_session(
        "MMT框架下赤字率对通胀的影响",
        {"primary": "empirical"},
        gate,
        {"worldview_key": "mmt"},
        search_queries_used=["MMT 赤字率 通胀 site:imf.org", "日本 财政赤字 历史"],
    )

    suggestion = SessionLearner.suggest_method("MMT下最优赤字率")
    print(f"方法推荐: {suggestion}")
    print(f"搜索词推荐: {SessionLearner.suggest_search_terms('赤字 通胀')}")
    print(f"最近统计: {SessionLearner.recent_gate_stats()}")
