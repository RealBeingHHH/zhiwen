"""
验证知识图谱 — 跨会话可溯源事实网络

节点 = 验证过的事实 (带世界观·闸分数·来源URL·σ·时间戳)
边 = 支持/矛盾/派生/等价

下次遇到同类问题:
  - 检索图谱中的已验证事实
  - 跳过已通过高闸验证的事实
  - 只验证新事实或低置信度事实

存储: JSON图文件
"""

import json
import hashlib
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

GRAPH_PATH = Path.home() / ".hermes" / "profiles" / "evopolis" / "knowledge_graph.json"
GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)


class KnowledgeGraph:
    """验证过的事实网络。"""

    @classmethod
    def _load(cls) -> dict:
        if GRAPH_PATH.exists():
            try:
                return json.loads(GRAPH_PATH.read_text())
            except Exception:
                pass
        return {"nodes": {}, "edges": []}

    @classmethod
    def _save(cls, data: dict) -> None:
        GRAPH_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def add_fact(
        cls,
        fact: str,
        worldview: str = "",
        method: str = "",
        gate_score: float = 0.0,
        sigma: float = 0.0,
        source_urls: list = None,
        query: str = "",
        adversarial_survival: float = 1.0,
    ) -> str:
        """
        添加一个验证过的事实节点。

        返回: node_id
        """
        data = cls._load()

        node_id = hashlib.sha256(fact.encode()).hexdigest()[:16]

        # 如果已存在，更新置信度
        if node_id in data["nodes"]:
            existing = data["nodes"][node_id]
            existing["verify_count"] += 1
            existing["gate_scores"].append(gate_score)
            existing["last_verified"] = time.time()
            existing["avg_gate_score"] = round(
                sum(existing["gate_scores"]) / len(existing["gate_scores"]), 2
            )
            cls._save(data)
            return node_id

        data["nodes"][node_id] = {
            "fact": fact[:200],
            "worldview": worldview,
            "method": method,
            "gate_score": gate_score,
            "sigma": sigma,
            "confidence": cls._confidence_level(gate_score, sigma),
            "source_urls": source_urls or [],
            "query": query[:100],
            "adversarial_survival": adversarial_survival,
            "verify_count": 1,
            "gate_scores": [gate_score],
            "avg_gate_score": gate_score,
            "first_verified": time.time(),
            "last_verified": time.time(),
        }

        cls._save(data)
        return node_id

    @classmethod
    def add_edge(cls, from_id: str, to_id: str, relation: str) -> None:
        """
        添加边: 支持/矛盾/派生/等价。

        relation: supports/contradicts/derives_from/equivalent_to
        """
        data = cls._load()

        if from_id not in data["nodes"] or to_id not in data["nodes"]:
            return

        # 去重
        for e in data["edges"]:
            if e["from"] == from_id and e["to"] == to_id:
                e["relation"] = relation
                cls._save(data)
                return

        data["edges"].append({
            "from": from_id,
            "to": to_id,
            "relation": relation,
            "time": time.time(),
        })
        cls._save(data)

    @classmethod
    def query_facts(
        cls,
        query: str,
        min_gate_score: float = 0.5,
        max_age_days: int = 30,
        limit: int = 5,
    ) -> list[dict]:
        """检索相关的已验证事实。"""
        data = cls._load()
        results = []

        now = time.time()
        max_age = max_age_days * 86400

        for nid, node in data["nodes"].items():
            # 时效检查
            age = now - node.get("last_verified", 0)
            if age > max_age:
                continue

            # 质量检查
            if node.get("avg_gate_score", 0) < min_gate_score:
                continue

            # 相关性检查: 事实文本或原始查询与当前查询共享关键词
            relevance = cls._relevance(query, node.get("fact", ""), node.get("query", ""))
            if relevance < 0.3:
                continue

            results.append({
                "node_id": nid,
                "fact": node["fact"][:150],
                "confidence": node.get("confidence", "?"),
                "gate_score": node.get("avg_gate_score", 0),
                "sigma": node.get("sigma", 0),
                "relevance": round(relevance, 2),
                "age_days": round(age / 86400, 1),
            })

        # 按 相关性 × 质量分 排序
        results.sort(key=lambda r: r["relevance"] * r["gate_score"], reverse=True)
        return results[:limit]

    @classmethod
    def get_fact_by_id(cls, node_id: str) -> Optional[dict]:
        """获取单个事实详情。"""
        data = cls._load()
        return data["nodes"].get(node_id)

    @classmethod
    def _confidence_level(cls, gate_score: float, sigma: float) -> str:
        if gate_score >= 0.7 and sigma < 0.3:
            return "高"
        elif gate_score >= 0.5:
            return "中"
        return "低"

    @classmethod
    def _relevance(cls, query: str, fact: str, original_query: str) -> float:
        """计算查询与事实的相关性。"""
        # 简单Jaccard: 共享词数 / 总词数
        def words(s):
            return set(s[:200].replace("。", " ").replace("，", " ").split())

        qw = words(query)
        fw = words(fact) | words(original_query)

        if not fw:
            return 0.0

        intersection = len(qw & fw)
        union = len(qw | fw)
        return intersection / max(union, 1)

    @classmethod
    def stats(cls) -> dict:
        """图谱统计。"""
        data = cls._load()
        nodes = data["nodes"]
        confidences = defaultdict(int)
        for n in nodes.values():
            confidences[n.get("confidence", "?")] += 1

        return {
            "total_nodes": len(nodes),
            "total_edges": len(data["edges"]),
            "confidences": dict(confidences),
            "methods": defaultdict(int, **{
                n.get("method", "?"): 0 for n in nodes.values()
            }),
        }


# ═══ 自检 ═══
if __name__ == "__main__":
    # 添加事实
    nid1 = KnowledgeGraph.add_fact(
        "会计等式: 资产200亿 ≠ 负债150亿 + 权益30亿, 差额20亿, 数据不可信",
        worldview="法务实证", method="forensic", gate_score=0.42, sigma=0.45,
        query="资产200亿，负债150亿，权益30亿。分析可信度",
    )
    print(f"节点1: {nid1}")

    nid2 = KnowledgeGraph.add_fact(
        "天枢τ=0.55条件下, 最优赤字率=0.15",
        worldview="四神体系", method="simulation", gate_score=0.72, sigma=0.24,
        query="MMT下最优赤字率",
    )
    print(f"节点2: {nid2}")

    # 添加边
    KnowledgeGraph.add_edge(nid2, nid1, "contradicts")

    # 查询
    results = KnowledgeGraph.query_facts("赤字率应该是多少")
    print(f"\n查询'赤字率应该是多少':")
    for r in results:
        print(f"  {r['fact'][:80]}... (相关性{r['relevance']:.2f}, 质量{r['gate_score']:.2f})")

    print(f"\n图谱统计: {KnowledgeGraph.stats()}")
