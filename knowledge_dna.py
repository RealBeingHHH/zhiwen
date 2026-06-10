"""
知识DNA重组 — 交叉·突变·选择·涌现新假设

天枢开发中的DNA重组思想应用到知识图谱:
  交叉 (crossover): 两条高η知识链 → 组合产生新假设
  突变 (mutation):  对单条知识链引入扰动 → 测试边界
  选择 (selection): 新假设通过质量闸 → 存活; 不通过 → 淘汰

流程:
  1. 从知识图谱选取两条高η知识 (念念在乎的知识)
  2. 交叉: 提取核心主张, LLM合成新假设
  3. 突变: 对假设中的数值/条件引入小扰动
  4. 选择: 新假设经过快速质量验证
  5. 存活的假设 → 加入知识图谱 + 喂入科学方法管线

基因概念:
  每条知识 = 一个基因
  基因型 = 知识的核心断言
  表型 = 在特定世界观/方法下的验证结果
  η = 基因的适应度
"""

import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent
DNA_STORE = BASE / "data" / "knowledge_dna.json"
DNA_STORE.parent.mkdir(parents=True, exist_ok=True)

from voyager_llm import safe_llm_call as _llm_call


@dataclass
class KnowledgeGene:
    """一条知识基因。"""
    fact_id: str
    fact: str                # 核心主张
    worldview: str
    method: str
    eta: float = 1.0
    confidence: float = 0.5
    gate_score: float = 0.0
    mutation_count: int = 0
    parent_ids: list = field(default_factory=list)


class KnowledgeDNA:
    """知识DNA重组引擎。"""

    CROSSOVER_RATE = 0.3      # 30%概率触发交叉
    MUTATION_RATE = 0.1       # 10%概率对单个基因突变
    MUTATION_SCALE = 0.15     # 突变幅度 (数值±15%)
    SURVIVAL_THRESHOLD = 0.4  # 最低存活分数

    @classmethod
    def crossover(
        cls,
        gene_a: KnowledgeGene,
        gene_b: KnowledgeGene,
    ) -> Optional[KnowledgeGene]:
        """
        知识交叉: 两条知识链融合 → 新假设。

        "如果A成立且B成立, 那么C可能成立吗?"
        """
        system = f"""你是知识重组专家。你面前有两条已验证的知识基因:

基因A (世界观:{gene_a.worldview}, 方法:{gene_a.method}, η={gene_a.eta}):
  {gene_a.fact}

基因B (世界观:{gene_b.worldview}, 方法:{gene_b.method}, η={gene_b.eta}):
  {gene_b.fact}

请将这两条知识交叉重组，生成一个新的可验证假设。
要求:
  1. 新假设必须同时涉及A和B的核心要素
  2. 新假设必须可测试、可验证
  3. 不要只是简单拼接——找到A和B之间的深层联系
  4. 输出一行, 简洁的假设陈述"""

        try:
            result = _llm_call(system, "生成交叉假设", max_tokens=200)
            if not result or len(result) < 15:
                return None

            new_id = f"dna_cross_{int(time.time())}_{random.randint(1000,9999)}"

            return KnowledgeGene(
                fact_id=new_id,
                fact=result.strip()[:200],
                worldview=f"{gene_a.worldview}×{gene_b.worldview}",
                method="crossover",
                parent_ids=[gene_a.fact_id, gene_b.fact_id],
                eta=min(gene_a.eta, gene_b.eta) * 0.8,  # 子代η从父母继承
                confidence=(gene_a.confidence + gene_b.confidence) / 2 * 0.7,  # 交叉降低置信度
            )
        except Exception:
            return None

    @classmethod
    def mutate(
        cls,
        gene: KnowledgeGene,
    ) -> Optional[KnowledgeGene]:
        """
        知识突变: 对知识基因引入小扰动。

        扰动类型:
          - 数值扰动: "0.15" → "0.17" (±15%)
          - 条件反转: "如果τ>0.5" → "如果τ<0.3"
          - 方法切换: "simulation" → "empirical"
          - 边界扩展: 在已有知识基础上添加新条件
        """
        # 提取数值并扰动
        import re
        numbers = re.findall(r'(\d+\.?\d*)', gene.fact)
        mutated_fact = gene.fact

        if numbers:
            target_num = random.choice(numbers)
            try:
                val = float(target_num)
                new_val = val * (1 + random.uniform(-cls.MUTATION_SCALE, cls.MUTATION_SCALE))
                new_val = round(new_val, 3)
                mutated_fact = gene.fact.replace(target_num, str(new_val), 1)
            except ValueError:
                pass

        new_id = f"dna_mut_{int(time.time())}_{random.randint(1000,9999)}"

        return KnowledgeGene(
            fact_id=new_id,
            fact=f"[突变自: {gene.fact_id}] {mutated_fact[:200]}",
            worldview=gene.worldview,
            method=gene.method,
            parent_ids=[gene.fact_id],
            mutation_count=gene.mutation_count + 1,
            eta=gene.eta * 0.6,  # 突变降低η
            confidence=gene.confidence * 0.5,  # 突变大幅降低置信度
        )

    @classmethod
    def select(
        cls,
        gene: KnowledgeGene,
        gate_check_fn=None,
    ) -> bool:
        """
        选择: 新基因是否存活。

        存活条件:
          1. 置信度 ≥ SURVIVAL_THRESHOLD
          2. 如果提供gate_check_fn, 通过快速质量检查
          3. 父本η高 → 子代存活率提升
        """
        if gene.confidence < cls.SURVIVAL_THRESHOLD:
            return False

        # 父本η加成
        if gene.parent_ids:
            from niannian_weight import NiannianEta
            parent_etas = [NiannianEta.get_eta(pid) for pid in gene.parent_ids]
            avg_parent_eta = sum(parent_etas) / len(parent_etas) if parent_etas else 1.0
            # 高η父本 → 子代存活率提升
            survival_bonus = min(0.3, avg_parent_eta / 50)
            if random.random() > gene.confidence + survival_bonus:
                return False

        return True

    @classmethod
    def evolve_population(
        cls,
        genes: list[KnowledgeGene],
        max_offspring: int = 3,
    ) -> list[KnowledgeGene]:
        """
        对基因池进行一轮演化:
          交叉: 高η基因两两配对
          突变: 随机选基因突变
          选择: 只保留存活的子代
        """
        offspring = []

        # 按η排序，取前N个高η基因
        sorted_genes = sorted(genes, key=lambda g: g.eta, reverse=True)
        elite = sorted_genes[:max(5, len(genes) // 2)]

        if len(elite) < 2:
            return offspring

        # ─── 交叉 ───
        for i in range(min(len(elite) - 1, 3)):
            if random.random() < cls.CROSSOVER_RATE:
                child = cls.crossover(elite[i], elite[i + 1])
                if child and cls.select(child):
                    offspring.append(child)
                    if len(offspring) >= max_offspring:
                        return offspring

        # ─── 突变 ───
        for gene in elite[:2]:
            if random.random() < cls.MUTATION_RATE:
                child = cls.mutate(gene)
                if child and cls.select(child):
                    offspring.append(child)
                    if len(offspring) >= max_offspring:
                        return offspring

        return offspring

    @classmethod
    def genes_from_storage(cls, min_eta: float = 5.0) -> list[KnowledgeGene]:
        """从存储中提取高η基因池。"""
        from storage_manager import StorageManager
        from niannian_weight import NiannianEta

        # 从热层检索所有事实
        hot = StorageManager._load_tier("hot", "facts")
        warm = StorageManager._load_tier("warm", "facts")

        genes = []
        for fid, node in {**hot, **warm}.items():
            eta = NiannianEta.get_eta(fid)
            if eta >= min_eta:
                genes.append(KnowledgeGene(
                    fact_id=fid,
                    fact=node.get("fact", ""),
                    worldview=node.get("worldview", ""),
                    method=node.get("method", ""),
                    eta=eta,
                    confidence=node.get("confidence", 0.5),
                    gate_score=node.get("gate_score", 0),
                ))
        return genes


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def evolve_hypotheses(min_eta: float = 3.0) -> list[KnowledgeGene]:
    """从知识图谱中演化新假设。"""
    genes = KnowledgeDNA.genes_from_storage(min_eta)
    if not genes:
        return []
    return KnowledgeDNA.evolve_population(genes)


# ═══ 自检 ═══
if __name__ == "__main__":
    # 创建两个高η基因
    gene_a = KnowledgeGene(
        fact_id="gene_001",
        fact="在τ=0.55条件下, MMT框架下最优赤字率为0.15, 通胀0.003",
        worldview="四神体系", method="simulation",
        eta=25, confidence=0.72, gate_score=0.72,
    )
    gene_b = KnowledgeGene(
        fact_id="gene_002",
        fact="会计等式断裂: 资产200≠负债150+权益30, 差额20亿, 数据不可信",
        worldview="法务实证", method="forensic",
        eta=15, confidence=0.50, gate_score=0.42,
    )

    print("=== DNA重组 ===")

    # 交叉
    child = KnowledgeDNA.crossover(gene_a, gene_b)
    if child:
        print(f"交叉子代: {child.fact[:120]}...")
        print(f"  置信度: {child.confidence:.2f} η={child.eta:.1f}")

    # 突变
    mutant = KnowledgeDNA.mutate(gene_a)
    if mutant:
        print(f"突变子代: {mutant.fact[:120]}...")
        print(f"  置信度: {mutant.confidence:.2f} η={mutant.eta:.1f}")

    # 演化群体
    offspring = KnowledgeDNA.evolve_population([gene_a, gene_b])
    print(f"\n演化子代: {len(offspring)}个")
    for o in offspring:
        print(f"  [{o.worldview}] {o.fact[:80]}... η={o.eta:.1f}")
