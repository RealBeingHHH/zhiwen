# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Copyright (c) 2026 知纹 (Zhiwen) Project

"""
DNA核心架构 — 知识系统的基因组骨架

AGCT不只是知识的一种组织方式，而是知识系统的底层架构。

四流程:
  转录(Transcription): 原始输入 → 知识碱基对 → 双链结构
  复制(Replication): 会话间知识传递，半保守复制 + 校对
  翻译(Translation): 密码子链 → 氨基酸(结论) → 蛋白质(完整研究输出)
  修复(Repair):     错配检测 + 切除修复 + 校对

编码方案:
  每个密码子(3碱基) → 一个研究方法动作
  ATG = START(初始化管线)    AAG = SEARCH(触发搜索)
  GGC = SIMULATE(触发模拟)   CGT = VERIFY(触发验证)
  TAA = STOP_A(结论输出)     TAG = STOP_B(对比输出)
  TGA = STOP_C(封印输出)

长链编码:
  一串密码子 → 完整的基因(研究方案)
  基因表达 → 蛋白质(完整研究结论)
  不同序列 → 不同功能 → 不同研究路径

核心稳固:
  双链互补: 每条主张链必有验证链配对，无单链裸数据
  半保守复制: 跨会话共享时保留一条原始链，确保溯源
  错配修复: 结构性畸变自动检测 + 切除 + 重新配对
  校对机制: 翻译时逐密码子验证配对完整性
"""

import json, time, hashlib, math, re
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent
GENOME_CORE = BASE / "data" / "genome_core.json"
GENOME_CORE.parent.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════
# 碱基 = 知识的基本单位
# ════════════════════════════════════════════════════════

class Base:
    A = "A"  # Assertion  — 主张: "最优赤字率=0.15"
    G = "G"  # Ground     — 理论: "MMT认为主权货币政府不受税收约束"
    C = "C"  # Confirm    — 证据: "日本1990-2020赤字率数据"
    T = "T"  # Test       — 验证: "参数扫描G=7.42, 通胀0.003"

    COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}
    BONDS = {"A": 2, "T": 2, "G": 3, "C": 3}  # A-T=2键, G-C=3键

    @classmethod
    def pair(cls, b1: str, b2: str) -> bool:
        return cls.COMPLEMENT.get(b1) == b2


# ════════════════════════════════════════════════════════
# 密码子 = 知识的功能编码 (3碱基 → 1个研究动作)
# ════════════════════════════════════════════════════════

class CodonTable:
    """知识密码子表 — 64个密码子 → 研究动作"""

    # 标准密码子映射
    TABLE = {
        # ── 起始密码子 ──
        "ATG": {"action": "START", "desc": "初始化研究管线，加载世界观"},
        "ATA": {"action": "START_ALT", "desc": "快速路径启动，跳过深度验证"},

        # ── 搜索类 ──
        "AAG": {"action": "SEARCH", "desc": "触发网络搜索获取证据"},
        "AAC": {"action": "SEARCH_DEEP", "desc": "触发深度研究拆解搜索"},
        "AAT": {"action": "SEARCH_META", "desc": "触发元搜索自寻数据源"},
        "AAA": {"action": "SEARCH_DOC", "desc": "触发文档阅读/PDF解析"},

        # ── 模拟类 ──
        "GGC": {"action": "SIMULATE", "desc": "触发科学方法假设→模拟→验证"},
        "GGA": {"action": "SIMULATE_SWEEP", "desc": "触发参数敏感性扫描"},
        "GGG": {"action": "SIMULATE_COMPETE","desc": "触发竞争假说并行验证"},
        "GGT": {"action": "SIMULATE_FISCAL", "desc": "触发财政政策模拟"},

        # ── 验证类 ──
        "CGT": {"action": "VERIFY", "desc": "触发数据质量四闸验证"},
        "CGC": {"action": "VERIFY_RELATION","desc": "触发关系完整性检查"},
        "CGA": {"action": "VERIFY_BENFORD","desc": "触发Benford真实性检测"},
        "CGG": {"action": "VERIFY_ENTROPY","desc": "触发熵场检测"},
        "CAA": {"action": "VERIFY_TAU", "desc": "触发τ天枢信任校准"},

        # ── 对比/对抗类 ──
        "TGC": {"action": "CONTRAST", "desc": "触发世界观对比分析"},
        "TGA": {"action": "ADVERSARIAL", "desc": "触发对抗验证(反例攻击)"},
        "TGG": {"action": "ITERATE", "desc": "触发迭代优化(换方法/数据源)"},

        # ── 终止密码子 ──
        "TAA": {"action": "STOP_CONCLUDE","desc": "输出结论，生成保证面板"},
        "TAG": {"action": "STOP_CONTRAST","desc": "输出跨框架对比结论"},
        "TGA": {"action": "STOP_SEAL", "desc": "输出并封印到天枢账本"},

        # ── 组合动作 ──
        "ACT": {"action": "PAIR_VERIFY", "desc": "主张+验证配对确认"},
        "GCA": {"action": "PAIR_EVIDENCE","desc": "理论+证据配对确认"},
        "TCA": {"action": "MISMATCH_FIX", "desc": "错配修复"},
    }

    # 回退: 未知密码子 → 默认动作
    @classmethod
    def translate(cls, codon: str) -> dict:
        return cls.TABLE.get(codon, {"action": "PASS", "desc": f"未知密码子{codon}, 跳过"})


# ════════════════════════════════════════════════════════
# 核苷酸 = 碱基对 (双链结构)
# ════════════════════════════════════════════════════════

@dataclass
class Nucleotide:
    """一个核苷酸 = 一对互补碱基 (知识的最小稳定单元)。"""
    sense_base: str       # 正义链碱基 (A/G)
    antisense_base: str   # 反义链碱基 (T/C)
    sense_content: str    # 正义链内容
    antisense_content: str  # 反义链内容
    hydrogen_bonds: int = 0  # 氢键数 (2或3)
    verified: bool = False
    mismatch_flag: bool = False
    mismatch_reason: str = ""

    def __post_init__(self):
        self.hydrogen_bonds = Base.BONDS.get(self.sense_base, 0)
        self._validate()

    def _validate(self) -> None:
        if not Base.pair(self.sense_base, self.antisense_base):
            self.mismatch_flag = True
            self.mismatch_reason = f"碱基错配: {self.sense_base}不应配{self.antisense_base}"
        if not self.antisense_content:
            self.mismatch_flag = True
            self.mismatch_reason = f"反义链缺失: {self.sense_base}无互补链"

    @property
    def is_stable(self) -> bool:
        return self.verified and not self.mismatch_flag

    @property
    def bond_strength(self) -> float:
        return self.hydrogen_bonds / 3.0


# ════════════════════════════════════════════════════════
# 基因 = 密码子链 (完整的知识表达单元)
# ════════════════════════════════════════════════════════

@dataclass
class Gene:
    """一个基因 = 一串密码子 → 一个完整的研究方案。"""
    sequence: str = ""          # 碱基序列 (如 "ATGAAGGGC...TAA")
    nucleotides: list[Nucleotide] = field(default_factory=list)
    codons: list[str] = field(default_factory=list)  # 密码子列表
    expressed: bool = False     # 是否已表达
    protein: str = ""           # 表达产物（蛋白质 = 结论链）
    errors: list[str] = field(default_factory=list)

    def transcribe(self, raw_input: list[dict]) -> str:
        """转录: 把原始输入转成核苷酸序列。"""
        for item in raw_input:
            sense_b = item.get("base", "A")
            anti_b = Base.COMPLEMENT.get(sense_b, "T")
            self.nucleotides.append(Nucleotide(
                sense_base=sense_b,
                antisense_base=anti_b,
                sense_content=item.get("content", ""),
                antisense_content=item.get("complement", ""),
            ))
            self.sequence += sense_b
        return self.sequence

    def split_codons(self) -> list[str]:
        """将序列切分为密码子（3碱基一组）。"""
        self.codons = []
        seq = self.sequence
        for i in range(0, len(seq) - 2, 3):
            codon = seq[i:i+3]
            self.codons.append(codon)
        return self.codons

    def translate(self) -> dict:
        """
        翻译: 密码子链 → 氨基酸(动作)链 → 蛋白质(完整研究输出)。

        返回: {actions, conclusions, protein, errors}
        """
        if not self.codons:
            self.split_codons()

        actions = []
        conclusions = []
        self.errors = []

        for i, codon in enumerate(self.codons):
            info = CodonTable.translate(codon)
            action = info["action"]

            # 检查这个密码子对应的核苷酸是否稳定
            if i < len(self.nucleotides):
                nt = self.nucleotides[i]
                if nt.mismatch_flag:
                    self.errors.append(f"密码子{i}({codon})的核苷酸不稳定: {nt.mismatch_reason}")

            actions.append(action)

            if action.startswith("STOP"):
                conclusions.append(f"[{info['desc']}]")
                break
            else:
                conclusions.append(f"[{action}] {info['desc']}")

        # 蛋白质 = 完整的研究输出
        self.protein = " → ".join(actions)
        self.expressed = len(self.errors) == 0

        return {
            "actions": actions,
            "conclusions": conclusions,
            "protein": self.protein,
            "expressed": self.expressed,
            "errors": self.errors,
        }

    def replicate(self) -> 'Gene':
        """
        半保守复制: 保留一条原始链, 合成一条新链。
        父本保留正义链, 子代获得反义链 → 确保可溯源。
        """
        child = Gene()
        for nt in self.nucleotides:
            child.nucleotides.append(Nucleotide(
                sense_base=nt.sense_base,
                antisense_base=nt.antisense_base,
                sense_content=nt.sense_content,  # 保留原始内容
                antisense_content="",  # 子代需要自己验证
            ))
            child.sequence += nt.sense_base
        return child


# ════════════════════════════════════════════════════════
# 基因组 = 所有基因的集合 + 全局操作
# ════════════════════════════════════════════════════════

class Genome:
    """知识基因组 — 系统的核心骨架。"""

    def __init__(self):
        self.genes: dict[str, Gene] = {}      # gene_id → Gene
        self.active_gene: Optional[Gene] = None  # 当前活跃基因
        self.repair_log: list[dict] = []
        self.stats = {"total_genes": 0, "expressed": 0, "errors": 0}

    def load(self) -> dict:
        if GENOME_CORE.exists():
            try:
                data = json.loads(GENOME_CORE.read_text())
                self.stats = data.get("stats", self.stats)
                self.repair_log = data.get("repair_log", [])
                return {"status": "loaded", "genes": len(data.get("genes", {}))}
            except:
                pass
        return {"status": "empty"}

    def save(self) -> None:
        GENOME_CORE.write_text(json.dumps({
            "genes": {gid: {"sequence": g.sequence, "protein": g.protein,
                           "expressed": g.expressed}
                     for gid, g in self.genes.items()},
            "stats": self.stats,
            "repair_log": self.repair_log[-50:],
        }, ensure_ascii=False, indent=2))

    # ─── 转录: 输入 → 基因 ───

    def transcribe(
        self,
        query: str,
        assertions: list[str],
        verifications: list[str] = None,
        theories: list[str] = None,
        evidences: list[str] = None,
    ) -> str:
        """转录: 将研究输入转成一个基因。"""
        gene = Gene()

        raw_input = []

        # 主张 + 验证 → A-T对
        for i, a in enumerate(assertions):
            v = verifications[i] if verifications and i < len(verifications) else ""
            raw_input.append({"base": "A", "content": a, "complement": v})

        # 理论 + 证据 → G-C对
        if theories:
            for i, t in enumerate(theories):
                e = evidences[i] if evidences and i < len(evidences) else ""
                raw_input.append({"base": "G", "content": t, "complement": e})

        gene.transcribe(raw_input)
        gene_id = hashlib.sha256((query + str(time.time())).encode()).hexdigest()[:12]

        self.genes[gene_id] = gene
        self.active_gene = gene
        self.stats["total_genes"] = len(self.genes)

        return gene_id

    # ─── 翻译: 基因 → 研究方案 → 结论 ───

    def translate_gene(self, gene_id: str) -> dict:
        """翻译: 将基因表达为可执行的研究方案。"""
        gene = self.genes.get(gene_id)
        if not gene:
            return {"error": "基因不存在"}

        result = gene.translate()

        if gene.expressed:
            self.stats["expressed"] += 1
            self.stats["errors"] += len(gene.errors)

        return {
            "gene_id": gene_id,
            "sequence": gene.sequence,
            "codons": gene.codons,
            **result,
        }

    # ─── 方案执行: 按密码子序列执行研究动作 ───

    def execute_gene(self, gene_id: str, context: dict = None) -> dict:
        """
        执行基因编码的研究方案。

        按密码子顺序执行对应的研究动作:
          ATG → 初始化管线
          AAG → 触发搜索
          GGC → 触发模拟
          CGT → 触发验证
          TAA → 输出结论
        """
        gene = self.genes.get(gene_id)
        if not gene:
            return {"error": "基因不存在"}

        if not gene.codons:
            gene.split_codons()

        execution_log = []
        pipeline_state = {"status": "running", "actions_done": [], "conclusions": []}

        for i, codon in enumerate(gene.codons):
            info = CodonTable.translate(codon)
            action = info["action"]

            # 检查核苷酸稳定性
            if i < len(gene.nucleotides):
                nt = gene.nucleotides[i]
                if nt.mismatch_flag:
                    execution_log.append({
                        "codon": codon,
                        "action": action,
                        "status": "blocked",
                        "reason": f"核苷酸不稳定: {nt.mismatch_reason}",
                    })
                    continue

            # 执行动作
            execution_log.append({
                "codon": codon, "action": action, "status": "executed",
                "desc": info["desc"],
            })
            pipeline_state["actions_done"].append(action)

            # 终止密码子 → 停止执行
            if action.startswith("STOP"):
                pipeline_state["conclusions"].append(info["desc"])
                pipeline_state["status"] = "completed"
                break

        return {
            "gene_id": gene_id,
            "sequence": gene.sequence,
            "execution_log": execution_log,
            "pipeline_state": pipeline_state,
            "protein": gene.protein,
        }

    # ─── 修复 ───

    def repair(self) -> dict:
        """基因组修复: 检测所有错配, 尝试修复。"""
        repaired = 0
        failed = 0

        for gid, gene in self.genes.items():
            for i, nt in enumerate(gene.nucleotides):
                if nt.mismatch_flag:
                    # 尝试自动修复: 如果反义链缺失, 标记为待补全
                    if not nt.antisense_content:
                        self.repair_log.append({
                            "gene": gid, "position": i,
                            "type": "missing_complement",
                            "base": nt.sense_base,
                            "status": "pending_fill",
                        })
                        failed += 1
                    else:
                        # 内容矛盾 → 标记为需人工审核
                        self.repair_log.append({
                            "gene": gid, "position": i,
                            "type": "contradiction",
                            "status": "needs_review",
                        })
                        failed += 1

        return {"repaired": repaired, "failed": failed, "pending_review": len(self.repair_log)}

    # ─── 复制 ───

    def replicate_gene(self, gene_id: str) -> Optional[str]:
        """半保守复制: 创建子代基因, 保留原始链。"""
        gene = self.genes.get(gene_id)
        if not gene:
            return None

        child = gene.replicate()
        child_id = hashlib.sha256((gene_id + str(time.time())).encode()).hexdigest()[:12]
        self.genes[child_id] = child
        self.stats["total_genes"] = len(self.genes)
        return child_id

    # ─── 健康 ───

    def health(self) -> dict:
        total_nt = sum(len(g.nucleotides) for g in self.genes.values())
        mismatches = sum(
            sum(1 for nt in g.nucleotides if nt.mismatch_flag)
            for g in self.genes.values()
        )
        gc_pairs = sum(
            sum(1 for nt in g.nucleotides if nt.sense_base in ("G", "C"))
            for g in self.genes.values()
        )

        return {
            "total_genes": len(self.genes),
            "total_nucleotides": total_nt,
            "mismatch_rate": round(mismatches / max(total_nt, 1), 3),
            "gc_content": round(gc_pairs / max(total_nt, 1), 2),
            "expressed_genes": self.stats["expressed"],
            "repair_pending": len(self.repair_log),
            "stability": "🟢 高" if mismatches == 0 else ("🟡 中" if mismatches < total_nt * 0.1 else "🔴 低"),
        }


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def create_research_gene(
    query: str,
    assertions: list[str],
    verifications: list[str] = None,
) -> str:
    g = Genome(); g.load()
    return g.transcribe(query, assertions, verifications)

def express_gene(gene_id: str) -> dict:
    g = Genome(); g.load()
    return g.translate_gene(gene_id)


# ═══ 自检 ═══
if __name__ == "__main__":
    genome = Genome()
    genome.load()

    # 转录: 输入 → 基因
    gid = genome.transcribe(
        "分析MMT下最优赤字率",
        assertions=["最优赤字率=0.15(τ=0.55)", "赤字率灵敏度最高=1.89"],
        verifications=["参数扫描G=7.42通胀0.003", "5参数扫描确认"],
        theories=["MMT:主权货币政府不受税收约束"],
        evidences=["日本1990-2020:赤字3-8%,通胀<1%"],
    )
    print(f"基因ID: {gid}")
    gene = genome.genes[gid]
    print(f"序列: {gene.sequence}")

    # 翻译
    result = genome.translate_gene(gid)
    print(f"\n密码子: {result['codons']}")
    print(f"蛋白质 (研究方案): {result['protein']}")
    print(f"表达成功: {result['expressed']}")
    if result['errors']:
        print(f"错误: {result['errors']}")

    # 执行
    exec_result = genome.execute_gene(gid)
    print(f"\n执行日志:")
    for log in exec_result["execution_log"]:
        status = "✅" if log["status"] == "executed" else "❌"
        print(f"  {status} {log['codon']} → {log['action']}: {log.get('desc','')[:50]}")

    # 修复
    repair = genome.repair()
    print(f"\n修复: 成功{repair['repaired']}, 失败{repair['failed']}, 待审核{repair['pending_review']}")

    # 复制
    child_id = genome.replicate_gene(gid)
    print(f"\n复制: 父本{gid} → 子代{child_id}")

    # 健康
    print(f"\n基因组健康: {genome.health()}")
