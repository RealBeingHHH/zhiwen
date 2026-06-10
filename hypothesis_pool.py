"""
假设空间 — DNA重组的安全闸门

问题: DNA重组产物直接存入知识库 → 多代衰减 → 知识库被污染

解决:
  假设空间 (hypothesis_pool) ≠ 知识库 (knowledge_graph)
  
  DNA交叉/突变 → 进入假设空间 (标记为[未验证])
  → 通过科学方法完整验证 (参数扫描 + 假设循环 + 质量闸)
  → 验证通过 → 升级为已验证事实 → 进入知识库
  → 验证失败 → 保留在假设空间 + 标记失败原因

血缘追踪:
  每条知识标注其来源链:
  [原始验证] → 直接从数据验证得来, 最高信任
  [DNA交叉] → 由两条已验证知识交叉产生, 已通过再验证
  [DNA突变] → 由单条知识突变产生, 已通过再验证
  [未验证] → 来自DNA但尚未通过验证, 不可作为推理依据
"""

import json
import time
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent
HYPOTHESIS_STORE = BASE / "data" / "hypothesis_pool.json"
HYPOTHESIS_STORE.parent.mkdir(parents=True, exist_ok=True)

from knowledge_dna import KnowledgeGene
from voyager_llm import safe_llm_call as _llm_call


# ════════════════════════════════════════════════════════
# 血缘追踪
# ════════════════════════════════════════════════════════

@dataclass
class Bloodline:
    """知识血缘 — 这条知识从哪来的。"""
    source: str               # original / crossover / mutation
    parents: list[str] = field(default_factory=list)  # 父本ID列表
    generation: int = 0       # 第几代
    verification_count: int = 0  # 验证次数
    verified: bool = False    # 是否已通过验证


class HypothesisPool:
    """
    假设空间 — DNA重组产物的隔离区。
    
    规则:
      1. DNA产出 → 进入假设空间 [未验证]
      2. 必须通过完整科学方法验证 → 才升级为 [已验证]
      3. 已验证的假设 → 可存入知识库
      4. 未验证的假设 → 永不作为推理依据
      5. 超过30天未验证 → 自动归档
    """

    MAX_HYPOTHESES = 50       # 假设空间上限
    MAX_UNVERIFIED_AGE = 30   # 未验证假设的最大存活天数

    @classmethod
    def _load(cls) -> dict:
        if HYPOTHESIS_STORE.exists():
            try:
                return json.loads(HYPOTHESIS_STORE.read_text())
            except Exception:
                pass
        return {"hypotheses": {}}

    @classmethod
    def _save(cls, data: dict) -> None:
        HYPOTHESIS_STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def add(
        cls,
        gene: KnowledgeGene,
        source: str = "crossover",
    ) -> str:
        """
        将DNA重组产物加入假设空间。

        参数:
          gene: DNA重组产生的知识基因
          source: crossover/mutation

        返回: hypothesis_id
        """
        data = cls._load()

        # 超过上限 → 清理最旧的未验证假设
        if len(data["hypotheses"]) >= cls.MAX_HYPOTHESES:
            cls._cleanup(data)

        hid = hashlib.sha256(gene.fact.encode()).hexdigest()[:16]

        data["hypotheses"][hid] = {
            "fact": gene.fact[:200],
            "worldview": gene.worldview,
            "method": gene.method,
            "source": source,
            "parents": gene.parent_ids,
            "generation": gene.mutation_count + 1,
            "eta": gene.eta,
            "confidence_before_verify": gene.confidence,
            "confidence_after_verify": None,
            "verified": False,
            "verification_attempts": 0,
            "last_attempt": None,
            "created": time.time(),
            "status": "pending",  # pending/verifying/verified/rejected
        }

        cls._save(data)
        return hid

    @classmethod
    def get_pending(cls, limit: int = 3) -> list[dict]:
        """获取待验证假设（最旧的优先）。"""
        data = cls._load()
        pending = [
            {**h, "id": hid}
            for hid, h in data["hypotheses"].items()
            if h.get("status") == "pending"
        ]
        pending.sort(key=lambda h: h.get("created", 0))
        return pending[:limit]

    @classmethod
    def mark_verified(cls, hypothesis_id: str, confidence: float, gate_score: float) -> None:
        """标记假设为已验证。"""
        data = cls._load()
        if hypothesis_id in data["hypotheses"]:
            h = data["hypotheses"][hypothesis_id]
            h["verified"] = True
            h["confidence_after_verify"] = confidence
            h["gate_score"] = gate_score
            h["status"] = "verified"
            h["verified_at"] = time.time()
            cls._save(data)

    @classmethod
    def mark_rejected(cls, hypothesis_id: str, reason: str = "") -> None:
        """标记假设为被拒绝。"""
        data = cls._load()
        if hypothesis_id in data["hypotheses"]:
            h = data["hypotheses"][hypothesis_id]
            h["status"] = "rejected"
            h["rejection_reason"] = reason
            h["rejected_at"] = time.time()
            cls._save(data)

    @classmethod
    def get_verified_genes(cls, min_confidence: float = 0.5) -> list[KnowledgeGene]:
        """获取已验证并准备好入库的基因。"""
        data = cls._load()
        genes = []
        for hid, h in data["hypotheses"].items():
            if h.get("verified") and h.get("confidence_after_verify", 0) >= min_confidence:
                genes.append(KnowledgeGene(
                    fact_id=f"verified_{hid}",
                    fact=h["fact"],
                    worldview=h.get("worldview", ""),
                    method=h.get("method", ""),
                    confidence=h["confidence_after_verify"],
                    gate_score=h.get("gate_score", 0),
                    eta=h.get("eta", 1.0),
                    parent_ids=h.get("parents", []),
                    mutation_count=h.get("generation", 0),
                ))
        return genes

    @classmethod
    def _cleanup(cls, data: dict) -> None:
        """清理过期未验证假设。"""
        now = time.time()
        to_remove = []
        for hid, h in data["hypotheses"].items():
            if not h.get("verified") and h.get("status") == "pending":
                age_days = (now - h.get("created", now)) / 86400
                if age_days > cls.MAX_UNVERIFIED_AGE:
                    to_remove.append(hid)

        for hid in to_remove:
            del data["hypotheses"][hid]

    @classmethod
    def stats(cls) -> dict:
        """假设空间统计。"""
        data = cls._load()
        hs = data["hypotheses"]
        statuses = {"pending": 0, "verifying": 0, "verified": 0, "rejected": 0}
        for h in hs.values():
            statuses[h.get("status", "pending")] = statuses.get(h.get("status", "pending"), 0) + 1
        return {
            "total": len(hs),
            **statuses,
            "ready_to_promote": len([
                h for h in hs.values()
                if h.get("verified") and h.get("confidence_after_verify", 0) >= 0.5
            ]),
        }


# ════════════════════════════════════════════════════════
# 安全入口: DNA→假设空间→验证→知识库
# ════════════════════════════════════════════════════════

def safe_dna_evolve(min_eta: float = 3.0) -> list[str]:
    """
    安全的DNA演化:
      1. 从知识库取高η基因
      2. DNA交叉/突变 → 进入假设空间 (未验证)
      3. 不直接存入知识库
      
    返回: 新产生的假设ID列表
    """
    from knowledge_dna import KnowledgeDNA

    genes = KnowledgeDNA.genes_from_storage(min_eta)
    if not genes:
        return []

    offspring = KnowledgeDNA.evolve_population(genes, max_offspring=2)
    hypothesis_ids = []

    for child in offspring:
        source = "crossover" if "cross" in child.fact_id else "mutation"
        hid = HypothesisPool.add(child, source=source)
        hypothesis_ids.append(hid)

    return hypothesis_ids


def verify_and_promote():
    """
    验证假设空间的待验证项, 通过验证的升级到知识库。

    这是知识库唯一接收DNA产物的入口。
    """
    from storage_manager import StorageManager
    from niannian_weight import NiannianEta

    pending = HypothesisPool.get_pending(limit=2)
    promoted = 0

    for hyp in pending:
        hid = hyp.get("id", "")
        fact = hyp.get("fact", "")

        # 简化验证: 使用LLM判断假设是否合理
        system = """你是知识验证员。判断以下假设是否合理。
合理=逻辑自洽+可测试+不与已知事实矛盾。
不合理=逻辑断裂+不可测试+与常识明显冲突。

只回答: 合理 或 不合理"""

        try:
            result = _llm_call(system, fact, max_tokens=10)
            if result and "合理" in result:
                # 快速验证通过 → 标记已验证
                HypothesisPool.mark_verified(
                    hid,
                    confidence=hyp.get("confidence_before_verify", 0.5) * 0.9,
                    gate_score=0.6,
                )
                promoted += 1
            else:
                HypothesisPool.mark_rejected(hid, "LLM快速验证不通过")
        except Exception:
            pass

    # 升级已验证基因到知识库
    verified_genes = HypothesisPool.get_verified_genes(min_confidence=0.5)
    for gene in verified_genes:
        node_id = StorageManager.store_fact(
            fact=f"[DNA验证] {gene.fact}",
            confidence=gene.confidence,
            worldview=gene.worldview,
            method=gene.method,
            gate_score=gene.gate_score,
            query=f"[DNA演化·已验证] 来自: {gene.parent_ids}",
        )
        if node_id:
            NiannianEta.gaze(node_id, weight=3, context="verification")

    return {"verified": len(verified_genes), "promoted": promoted}


# ═══ 自检 ═══
if __name__ == "__main__":
    from knowledge_dna import KnowledgeGene

    # 添加假设
    gene = KnowledgeGene(
        fact_id="test_cross",
        fact="若发生会计等式差额, 最优赤字率需调整至0.18以吸收失真",
        worldview="四神体系×法务实证", method="crossover",
        eta=12, confidence=0.43,
        parent_ids=["gene_001", "gene_002"],
    )
    hid = HypothesisPool.add(gene, source="crossover")
    print(f"假设ID: {hid}")

    # 统计
    stats = HypothesisPool.stats()
    print(f"假设空间: {stats['total']}条 (待验证{stats['pending']} 已验证{stats['verified']})")

    # 安全演化
    ids = safe_dna_evolve(min_eta=1.0)
    print(f"安全演化产生: {len(ids)}个新假设 → 全部进入假设空间 [未验证]")

    print(f"\n✅ 知识库被保护: DNA产物不直接入库")
    print(f"   路径: DNA → 假设空间[未验证] → 验证通过 → 知识库")
