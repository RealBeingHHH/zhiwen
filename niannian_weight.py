"""
念念η权重 — 观测即介入。知识在被注视中获得重量。

η (玄鉴/念念) = "观测就是介入——念念在看，世界在被看中改变"

在知识系统中:
  - 每次检索 = 一次注视 → η+1
  - 每次引用在结论中 = 深度注视 → η+3
  - 每次通过质量闸验证 = 确认注视 → η+5
  - 用户显式认可 = 最强注视 → η+10

高η的知识:
  - 检索时优先返回 (η排序)
  - 衰减更慢 (η作为衰减抗性)
  - 更不容易被剪枝淘汰
  - 作为DNA重组的"强基因"优先参与交叉

η随时间自然衰减: η(t) = η × e^(-t / η半衰期)
  但每次注视会推高η → 被频繁注视的知识不会沉没

与τ的关系:
  τ = 信任温度 (天枢) — "这可信吗"
  η = 注意力重量 (念念) — "这重要吗"
  两者正交: 可信但不重要 → 高τ低η
          重要但不可信 → 低τ高η (需验证)
"""

import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent
ETA_STORE = BASE / "data" / "niannian_eta.json"
ETA_STORE.parent.mkdir(parents=True, exist_ok=True)

# ════════════════════════════════════════════════════════
# η配置
# ════════════════════════════════════════════════════════

class EtaConfig:
    # 注视权重
    RETRIEVAL_WEIGHT = 1       # 每次检索
    CITATION_WEIGHT = 3        # 在结论中被引用
    VERIFICATION_WEIGHT = 5    # 通过质量闸验证
    USER_ENDORSEMENT = 10      # 用户显式认可

    # 衰减
    ETA_HALF_LIFE_DAYS = 30    # η半衰期 (比τ衰减慢, 因为重要知识应该持久)
    MIN_ETA = 1.0              # 最低η (不会归零)
    MAX_ETA = 100.0            # 最高η (防止过度集中)

    # 检索偏置
    ETA_RETRIEVAL_BOOST = 0.3  # η在检索排序中的权重 (剩余0.7给相关性和置信度)


# ════════════════════════════════════════════════════════
# η引擎
# ════════════════════════════════════════════════════════

class NiannianEta:
    """念念η — 知识重量引擎 (批量化写盘)。"""

    _batch_buffer: dict = {}  # 内存缓冲
    _last_flush: float = 0

    @classmethod
    def _load(cls) -> dict:
        if ETA_STORE.exists():
            try:
                return json.loads(ETA_STORE.read_text())
            except Exception:
                pass
        return {"facts": {}, "global": {"total_attention": 0, "last_decay": time.time()}}

    @classmethod
    def _save(cls, data: dict) -> None:
        ETA_STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def _maybe_flush(cls) -> None:
        """每隔5秒或积累10条改动才写盘。"""
        now = time.time()
        if len(cls._batch_buffer) >= 10 or (now - cls._last_flush) > 5:
            if cls._batch_buffer:
                data = cls._load()
                cls._apply_decay(data)
                for key, update in cls._batch_buffer.items():
                    if key not in data["facts"]:
                        data["facts"][key] = update
                    else:
                        data["facts"][key]["eta"] = update.get("eta", data["facts"][key].get("eta", 1.0))
                        data["facts"][key]["gaze_count"] = data["facts"][key].get("gaze_count", 0) + update.get("gaze_count", 0)
                        data["facts"][key]["total_weight"] = data["facts"][key].get("total_weight", 0) + update.get("total_weight", 0)
                        data["facts"][key]["last_gaze"] = update.get("last_gaze", now)
                cls._save(data)
                cls._batch_buffer = {}
                cls._last_flush = now

    @classmethod
    def _fact_key(cls, fact_id: str) -> str:
        """标准化fact_id。"""
        return fact_id[:32]

    @classmethod
    def gaze(
        cls,
        fact_id: str,
        weight: int = 1,
        context: str = "retrieval",
    ) -> float:
        """
        念念注视一个事实 — η增加 (批量化, 不每次写盘)。

        weight: 注视强度
        返回: 新η值 (从内存缓冲计算)
        """
        key = cls._fact_key(fact_id)
        now = time.time()

        # 从缓冲或磁盘加载当前η
        if key in cls._batch_buffer:
            current_eta = cls._batch_buffer[key].get("eta", EtaConfig.MIN_ETA)
        else:
            current_eta = cls.get_eta(key)

        new_eta = min(EtaConfig.MAX_ETA, current_eta + weight)

        cls._batch_buffer[key] = {
            "eta": new_eta,
            "first_seen": now,
            "gaze_count": 1,
            "total_weight": weight,
            "last_gaze": now,
        }

        # 尝试刷盘
        cls._maybe_flush()

        return new_eta

    @classmethod
    def get_eta(cls, fact_id: str) -> float:
        """获取当前η值。"""
        data = cls._load()
        cls._apply_decay(data)
        key = cls._fact_key(fact_id)
        return data["facts"].get(key, {}).get("eta", EtaConfig.MIN_ETA)

    @classmethod
    def rank_by_eta(
        cls,
        facts: list[dict],
        min_eta: float = 0,
    ) -> list[dict]:
        """
        按η排序一批事实 — η高的排前面。

        排序公式: score = 0.7×(相关性×置信度) + 0.3×(η/MAX_ETA)
        η让被频繁注视的知识自然上浮。
        """
        data = cls._load()
        cls._apply_decay(data)

        for fact in facts:
            fid = fact.get("node_id", fact.get("fact_id", ""))
            if fid:
                key = cls._fact_key(fid)
                eta = data["facts"].get(key, {}).get("eta", EtaConfig.MIN_ETA)
            else:
                eta = EtaConfig.MIN_ETA

            fact["eta"] = round(eta, 1)

            # 混合排序分
            confidence = fact.get("confidence", fact.get("effective_confidence", 0.5))
            relevance = fact.get("relevance", 0.5)
            base_score = 0.7 * relevance * confidence
            eta_score = EtaConfig.ETA_RETRIEVAL_BOOST * (eta / EtaConfig.MAX_ETA)
            fact["rank_score"] = round(base_score + eta_score, 3)

        return sorted(facts, key=lambda f: f.get("rank_score", 0), reverse=True)

    @classmethod
    def top_by_eta(cls, limit: int = 10) -> list[dict]:
        """获取η最高的知识 — "念念最在乎的事实"。"""
        data = cls._load()
        cls._apply_decay(data)

        ranked = sorted(
            data["facts"].items(),
            key=lambda kv: kv[1].get("eta", 0),
            reverse=True,
        )
        return [
            {"fact_id": fid, "eta": fact["eta"], "gaze_count": fact["gaze_count"]}
            for fid, fact in ranked[:limit]
        ]

    @classmethod
    def _apply_decay(cls, data: dict) -> None:
        """对所有事实应用η衰减。"""
        now = time.time()
        last_decay = data["global"].get("last_decay", now)
        elapsed_days = (now - last_decay) / 86400

        if elapsed_days < 0.1:  # 不到2.4小时不衰减
            return

        half_life = EtaConfig.ETA_HALF_LIFE_DAYS
        decay_factor = math.exp(-elapsed_days * math.log(2) / half_life)

        for key, fact in data["facts"].items():
            fact["eta"] = max(EtaConfig.MIN_ETA, fact["eta"] * decay_factor)

        data["global"]["last_decay"] = now

    @classmethod
    def stats(cls) -> dict:
        """η统计。"""
        data = cls._load()
        cls._apply_decay(data)

        facts = data["facts"]
        if not facts:
            return {"total_facts": 0, "avg_eta": 0, "max_eta": 0, "total_gazes": 0}

        etas = [f["eta"] for f in facts.values()]
        gazes = sum(f["gaze_count"] for f in facts.values())

        return {
            "total_facts": len(facts),
            "avg_eta": round(sum(etas) / len(etas), 1),
            "max_eta": max(etas),
            "total_gazes": gazes,
            "total_attention": data["global"]["total_attention"],
        }


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def gaze(fact_id: str, intensity: str = "retrieval") -> float:
    """念念注视。"""
    weights = {"retrieval": 1, "citation": 3, "verification": 5, "endorsement": 10}
    return NiannianEta.gaze(fact_id, weights.get(intensity, 1), intensity)

def get_eta(fact_id: str) -> float:
    return NiannianEta.get_eta(fact_id)

def rank_facts(facts: list[dict]) -> list[dict]:
    return NiannianEta.rank_by_eta(facts)


# ═══ 自检 ═══
if __name__ == "__main__":
    # 模拟注视
    fid1 = "fact_001_accounting_gap"
    fid2 = "fact_002_optimal_deficit"

    # 多次检索事实2 → η应该更高
    for _ in range(5):
        NiannianEta.gaze(fid2, weight=1, context="retrieval")
    NiannianEta.gaze(fid2, weight=3, context="citation")
    NiannianEta.gaze(fid2, weight=5, context="verification")

    # 事实1只有一次检索
    NiannianEta.gaze(fid1, weight=1)

    print(f"事实1 η={NiannianEta.get_eta(fid1):.1f} (1次注视)")
    print(f"事实2 η={NiannianEta.get_eta(fid2):.1f} (7次注视)")

    # 按η排序
    facts = [
        {"node_id": fid1, "confidence": 0.8, "relevance": 0.5, "fact": "资产≠负债+权益"},
        {"node_id": fid2, "confidence": 0.7, "relevance": 0.6, "fact": "最优赤字率0.15"},
    ]
    ranked = NiannianEta.rank_by_eta(facts)
    print(f"\nη排序:")
    for f in ranked:
        print(f"  η={f.get('eta',0):.1f} rank={f['rank_score']:.3f} → {f['fact'][:50]}")

    print(f"\n念念统计: {NiannianEta.stats()}")
