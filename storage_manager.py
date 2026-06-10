"""
存储管理器 — 分层存储 + 上下文预算 + 衰减剪枝

问题: 追加式JSON会无限膨胀 → 检索注入LLM上下文时超过注意力窗口 → 幻觉
解决:
  1. 热/温/冷三层 — 按置信度和时效自动分层
  2. 上下文预算 — 硬限制每次注入LLM的存储数据量
  3. 事实合并 — 相似节点归并，减少冗余
  4. 衰减剪枝 — 低置信+过期→归档，不删除
  5. 健康监控 — 追踪增长曲线，预警阈值

存储位置: ~/.hermes/profiles/evopolis/storage/
  hot/   — 最近7天, 高置信度 (活跃检索源)
  warm/  — 7-30天, 中置信度 (检索但降权)
  cold/  — 30天+, 低置信度 (不自动注入, 可手动查询)
"""

import json
import hashlib
import time
import math
from collections import defaultdict
from pathlib import Path
from typing import Optional

STORAGE_ROOT = Path.home() / ".hermes" / "profiles" / "evopolis" / "storage"
for tier in ["hot", "warm", "cold"]:
    (STORAGE_ROOT / tier).mkdir(parents=True, exist_ok=True)

# ════════════════════════════════════════════════════════
# 配置
# ════════════════════════════════════════════════════════

class StorageConfig:
    # 分层阈值
    HOT_MAX_AGE_DAYS = 7       # 热层: 7天内
    WARM_MAX_AGE_DAYS = 30     # 温层: 30天内
    # 超过30天 → 冷层

    # 上下文预算 (每次注入LLM的最大值)
    MAX_CONTEXT_FACTS = 3       # 最多注入3条事实
    MAX_CONTEXT_CHARS = 600     # 最多注入600字符
    MAX_CONTEXT_TOKENS_EST = 200  # ~200 tokens

    # 衰减配置
    DECAY_HALF_LIFE_DAYS = 14  # 半衰期14天 (每14天置信度减半)
    MIN_CONFIDENCE_FOR_HOT = 0.5  # 低于此置信度不进热层
    PRUNE_CONFIDENCE = 0.2     # 低于此置信度且过期 → 冷归档

    # 合并配置
    MERGE_SIMILARITY = 0.7     # Jaccard相似度 > 0.7 → 合并

    # 健康告警
    WARN_NODE_COUNT = 300      # 节点数超过此值告警
    CRITICAL_NODE_COUNT = 500  # 节点数超过此值严重告警


# ════════════════════════════════════════════════════════
# 核心管理
# ════════════════════════════════════════════════════════

class StorageManager:
    """分层存储 + 衰减 + 预算控制。"""

    @classmethod
    def _tier_path(cls, tier: str, category: str) -> Path:
        return STORAGE_ROOT / tier / f"{category}.json"

    @classmethod
    def _load_tier(cls, tier: str, category: str) -> dict:
        path = cls._tier_path(tier, category)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return {}

    @classmethod
    def _save_tier(cls, tier: str, category: str, data: dict) -> None:
        path = cls._tier_path(tier, category)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # ─── 写入 ───

    @classmethod
    def store_fact(
        cls,
        fact: str,
        confidence: float,
        worldview: str = "",
        method: str = "",
        gate_score: float = 0,
        sigma: float = 0,
        query: str = "",
        source_urls: list = None,
    ) -> str:
        """
        存储一个验证事实，自动分配到合适的层级。

        返回: node_id
        """
        node_id = hashlib.sha256(fact.encode()).hexdigest()[:16]
        now = time.time()

        # 确定层级
        if confidence >= StorageConfig.MIN_CONFIDENCE_FOR_HOT:
            tier = "hot"
        elif confidence >= StorageConfig.PRUNE_CONFIDENCE:
            tier = "warm"
        else:
            tier = "cold"

        data = cls._load_tier(tier, "facts")

        if node_id in data:
            # 更新已有节点
            existing = data[node_id]
            existing["verify_count"] = existing.get("verify_count", 0) + 1
            existing["last_verified"] = now
            existing["confidence"] = max(existing.get("confidence", 0), confidence)
            existing["gate_score"] = max(existing.get("gate_score", 0), gate_score)
        else:
            data[node_id] = {
                "fact": fact[:200],
                "worldview": worldview,
                "method": method,
                "confidence": confidence,
                "gate_score": gate_score,
                "sigma": sigma,
                "source_urls": source_urls or [],
                "query": query[:100],
                "verify_count": 1,
                "first_stored": now,
                "last_verified": now,
                "tier": tier,
            }

        cls._save_tier(tier, "facts", data)
        return node_id

    @classmethod
    def store_method_record(
        cls,
        query_hash: str,
        method: str,
        gate_score: float,
        query: str = "",
    ) -> None:
        """存储方法效果记录。"""
        data = cls._load_tier("hot", "methods")

        if query_hash not in data:
            data[query_hash] = {}
        if method not in data[query_hash]:
            data[query_hash][method] = {"count": 0, "total_score": 0, "last_used": 0}
        data[query_hash][method]["count"] += 1
        data[query_hash][method]["total_score"] += gate_score
        data[query_hash][method]["last_used"] = time.time()
        data[query_hash][method]["query"] = query[:80]

        cls._save_tier("hot", "methods", data)

    # ─── 检索 (带预算控制) ───

    @classmethod
    def retrieve_facts(
        cls,
        query: str,
        min_confidence: float = 0.4,
        max_results: int = None,
    ) -> list[dict]:
        """
        检索相关事实，严格控制上下文预算。

        检索顺序: hot → warm (cold不自动注入)
        硬限制: MAX_CONTEXT_FACTS 条, MAX_CONTEXT_CHARS 字符
        """
        if max_results is None:
            max_results = StorageConfig.MAX_CONTEXT_FACTS

        results = []

        # 从热层检索
        hot_data = cls._load_tier("hot", "facts")
        results.extend(cls._search_tier(hot_data, query, min_confidence))

        # 从温层检索（如果热层不足）
        if len(results) < max_results:
            warm_data = cls._load_tier("warm", "facts")
            results.extend(cls._search_tier(warm_data, query, min_confidence))

        # 应用衰减
        results = [cls._apply_decay(r) for r in results]

        # 排序: 置信度 × 相关性
        results.sort(
            key=lambda r: r.get("effective_confidence", 0) * r.get("relevance", 0),
            reverse=True,
        )

        # 应用上下文预算: 数量限制
        results = results[:max_results]

        # 应用上下文预算: 字符限制
        total_chars = 0
        budgeted = []
        for r in results:
            fact_text = r.get("fact", "")[:150]
            if total_chars + len(fact_text) > StorageConfig.MAX_CONTEXT_CHARS:
                break
            budgeted.append(r)
            total_chars += len(fact_text)

        return budgeted

    @classmethod
    def retrieve_method_suggestion(cls, query: str) -> Optional[str]:
        """检索方法建议（仅热层）。"""
        hot_data = cls._load_tier("hot", "methods")
        qhash = hashlib.md5(query[:200].encode()).hexdigest()[:12]

        if qhash in hot_data:
            methods = hot_data[qhash]
            if methods:
                best = max(methods, key=lambda m: (
                    methods[m]["total_score"] / max(methods[m]["count"], 1)
                ))
                return best

        return None

    @classmethod
    def _search_tier(cls, data: dict, query: str, min_confidence: float) -> list[dict]:
        """在单层中搜索。"""
        results = []
        for nid, node in data.items():
            if node.get("confidence", 0) < min_confidence:
                continue
            relevance = cls._relevance(query, node.get("fact", ""), node.get("query", ""))
            if relevance < 0.2:
                continue
            results.append({**node, "node_id": nid, "relevance": relevance})
        return results

    @classmethod
    def _apply_decay(cls, node: dict) -> dict:
        """应用时间衰减: 置信度随时间指数下降。"""
        now = time.time()
        age_days = (now - node.get("last_verified", now)) / 86400
        half_life = StorageConfig.DECAY_HALF_LIFE_DAYS

        # 衰减公式: effective = confidence × 2^(-age/half_life)
        decay_factor = 2 ** (-age_days / half_life)
        effective_confidence = node.get("confidence", 0.5) * decay_factor

        return {**node, "effective_confidence": round(effective_confidence, 3), "age_days": round(age_days, 1)}

    @classmethod
    def _relevance(cls, query: str, fact: str, original_query: str) -> float:
        """Jaccard相似度。"""
        def words(s):
            return set(s[:200].replace("。", " ").replace("，", " ").split())
        qw = words(query)
        fw = words(fact) | words(original_query)
        if not fw:
            return 0.0
        return len(qw & fw) / max(len(qw | fw), 1)

    # ─── 维护: 合并+剪枝+归档 ───

    @classmethod
    def maintenance(cls) -> dict:
        """
        运行存储维护:
          1. 合并相似节点
          2. 衰减过期节点层级 (hot→warm→cold)
          3. 剪枝极低置信度节点到冷层
        """
        stats = {
            "merged": 0,
            "demoted": 0,
            "pruned": 0,
            "hot_nodes": 0,
            "warm_nodes": 0,
            "cold_nodes": 0,
        }

        # ① 热层 → 温层迁移 (超过7天)
        stats = cls._promote_demote("hot", "warm", StorageConfig.HOT_MAX_AGE_DAYS, stats)

        # ② 温层 → 冷层迁移 (超过30天)
        stats = cls._promote_demote("warm", "cold", StorageConfig.WARM_MAX_AGE_DAYS, stats)

        # ③ 热/温层中低置信度 → 冷层
        for tier in ["hot", "warm"]:
            data = cls._load_tier(tier, "facts")
            cold_data = cls._load_tier("cold", "facts")
            to_move = []
            for nid, node in data.items():
                if node.get("confidence", 0) < StorageConfig.PRUNE_CONFIDENCE:
                    cold_data[nid] = {**node, "tier": "cold", "archived_at": time.time()}
                    to_move.append(nid)
                    stats["pruned"] += 1
            for nid in to_move:
                del data[nid]
            if to_move:
                cls._save_tier(tier, "facts", data)
                cls._save_tier("cold", "facts", cold_data)

        # ④ 合并相似节点
        stats = cls._merge_similar("hot", stats)
        stats = cls._merge_similar("warm", stats)

        # 统计
        for tier in ["hot", "warm", "cold"]:
            data = cls._load_tier(tier, "facts")
            stats[f"{tier}_nodes"] = len(data)

        return stats

    @classmethod
    def _promote_demote(
        cls, from_tier: str, to_tier: str, max_age_days: int, stats: dict
    ) -> dict:
        """按年龄迁移节点。"""
        from_data = cls._load_tier(from_tier, "facts")
        to_data = cls._load_tier(to_tier, "facts")
        now = time.time()
        to_move = []

        for nid, node in from_data.items():
            age_days = (now - node.get("last_verified", now)) / 86400
            if age_days > max_age_days:
                to_data[nid] = {**node, "tier": to_tier}
                to_move.append(nid)
                stats["demoted"] += 1

        for nid in to_move:
            del from_data[nid]

        if to_move:
            cls._save_tier(from_tier, "facts", from_data)
            cls._save_tier(to_tier, "facts", to_data)

        return stats

    @classmethod
    def _merge_similar(cls, tier: str, stats: dict) -> dict:
        """合并相似节点。"""
        data = cls._load_tier(tier, "facts")
        if len(data) < 2:
            return stats

        keys = list(data.keys())
        merged = set()

        for i in range(len(keys)):
            if keys[i] in merged:
                continue
            for j in range(i + 1, len(keys)):
                if keys[j] in merged:
                    continue
                sim = cls._relevance(
                    data[keys[i]].get("fact", ""),
                    data[keys[j]].get("fact", ""),
                    ""
                )
                if sim > StorageConfig.MERGE_SIMILARITY:
                    # 合并到置信度更高的节点
                    if data[keys[i]]["confidence"] >= data[keys[j]]["confidence"]:
                        survivor, victim = keys[i], keys[j]
                    else:
                        survivor, victim = keys[j], keys[i]

                    data[survivor]["verify_count"] += data[victim].get("verify_count", 1)
                    data[survivor]["confidence"] = max(
                        data[survivor]["confidence"],
                        data[victim]["confidence"],
                    )
                    merged.add(victim)
                    stats["merged"] += 1

        for nid in merged:
            del data[nid]

        if merged:
            cls._save_tier(tier, "facts", data)

        return stats

    # ─── 健康报告 ───

    @classmethod
    def health_report(cls) -> dict:
        """存储健康报告。"""
        hot = cls._load_tier("hot", "facts")
        warm = cls._load_tier("warm", "facts")
        cold = cls._load_tier("cold", "facts")
        methods = cls._load_tier("hot", "methods")

        total_nodes = len(hot) + len(warm) + len(cold)
        total_size = 0
        for tier in ["hot", "warm", "cold"]:
            for cat in ["facts", "methods"]:
                path = cls._tier_path(tier, cat)
                if path.exists():
                    total_size += path.stat().st_size

        # 风险级别
        if total_nodes >= StorageConfig.CRITICAL_NODE_COUNT:
            risk = "critical"
        elif total_nodes >= StorageConfig.WARN_NODE_COUNT:
            risk = "warning"
        else:
            risk = "healthy"

        # 上下文注入占比
        est_injection_tokens = StorageConfig.MAX_CONTEXT_TOKENS_EST
        effective_window = 8000
        injection_ratio = est_injection_tokens / effective_window

        return {
            "total_nodes": total_nodes,
            "hot_nodes": len(hot),
            "warm_nodes": len(warm),
            "cold_nodes": len(cold),
            "method_records": len(methods),
            "total_size_kb": round(total_size / 1024, 1),
            "risk_level": risk,
            "context_injection_ratio": round(injection_ratio, 3),
            "context_budget": {
                "max_facts": StorageConfig.MAX_CONTEXT_FACTS,
                "max_chars": StorageConfig.MAX_CONTEXT_CHARS,
                "max_tokens_est": StorageConfig.MAX_CONTEXT_TOKENS_EST,
            },
            "recommendation": (
                "正常" if risk == "healthy"
                else "建议运行 maintenance() 清理" if risk == "warning"
                else "紧急: 需立即维护, 节点数已超临界值"
            ),
        }


# ═══ 自检 ═══
if __name__ == "__main__":
    # 模拟大量存储
    print("=== 存储健康 (初始) ===")
    report = StorageManager.health_report()
    print(f"节点: {report['total_nodes']} (热{report['hot_nodes']} 温{report['warm_nodes']} 冷{report['cold_nodes']})")
    print(f"风险: {report['risk_level']}")
    print(f"上下文注入占比: {report['context_injection_ratio']:.1%}")

    # 存储事实
    StorageManager.store_fact(
        "MMT下最优赤字率=0.15 (τ=0.55)", confidence=0.7,
        worldview="四神体系", method="simulation", gate_score=0.72, sigma=0.24,
    )
    StorageManager.store_fact(
        "会计等式断裂: 资产200≠负债150+权益30", confidence=0.5,
        worldview="法务实证", method="forensic", gate_score=0.42, sigma=0.45,
    )

    # 检索
    facts = StorageManager.retrieve_facts("赤字率应该是多少")
    print(f"\n检索'赤字率': {len(facts)}条 (预算限制{StorageConfig.MAX_CONTEXT_FACTS}条)")
    for f in facts:
        print(f"  {f['fact'][:80]} (置信度{f['effective_confidence']:.2f})")

    print(f"\n=== 存储健康 (最终) ===")
    report = StorageManager.health_report()
    print(f"节点: {report['total_nodes']} (热{report['hot_nodes']} 温{report['warm_nodes']} 冷{report['cold_nodes']})")
    print(f"建议: {report['recommendation']}")
