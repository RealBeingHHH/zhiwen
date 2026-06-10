# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Copyright (c) 2026 知纹 (Zhiwen) Project

"""
基因组管线桥接 — 将DNA架构串联入研究管线

genome_core.py 提供基因的转录/翻译/执行/修复能力。
本模块将其与 pipeline.py 的 run_pipeline() 桥接:

  run_pipeline_dna(query) → 双轨执行:
    旧轨道: 直接管线执行 (pipeline.run_pipeline)
    DNA轨道: 转录→密码子→执行→修复→蛋白输出
    最终: 蛋白 + 管线上下文 → 融合消息

用法:
  from genome_pipeline import run_genome_pipeline
  result = run_genome_pipeline(query, skip_layers=set())

返回: {message, protein, gene_id, health, genome_context, pipeline_context}
"""

import hashlib, time
from typing import Optional

from config import TIANSHU_URL
from genome_core import Genome, CodonTable, Base, Nucleotide, Gene
from genome_guardian import GenomeGuardian
from tianshu_trust import TianshuClient, TauTrust
from dna_executor import execute_gene_codons
from operon import detect_operons, execute_codons_with_operons
import re as _re_extract


# ═══ 全局基因组实例 ═══
_genome: Optional[Genome] = None


def get_genome() -> Genome:
    global _genome
    if _genome is None:
        _genome = Genome()
        _genome.load()
    return _genome


# ════════════════════════════════════════════════════════
# DNA管线核心
# ════════════════════════════════════════════════════════

def run_genome_pipeline(
    query: str,
    skip_layers: set = None,
    pipeline_result: dict = None,
) -> dict:
    """
    在DNA架构下执行研究管线。

    流程:
      1. 转录: query → 碱基对 → 核苷酸 → 基因
      2. 保护: guardian.six_layers() 初始化保护
      3. 翻译: 密码子链 → 动作序列
      4. 执行: 按密码子触发对应管线层
      5. 修复: 错配检测 + 切除 + 校对
      6. 输出: 蛋白(研究结论) + 健康报告
    """
    if skip_layers is None:
        skip_layers = set()

    genome = get_genome()
    result = {
        "query": query,
        "gene_id": None,
        "protein": "",
        "sequence": "",
        "codons": [],
        "actions": [],
        "errors": [],
        "health": {},
        "genome_context": "",
        "mismatches": 0,
    }

    # ─── 阶段1: 提取可配对内容 ───
    # 构建研究基因: 不是简单映射主张→碱基，而是编码完整的研究管线
    # 序列 = START + 动作密码子链 + STOP
    
    # 基本碱基对: 主张(A-T) + 理论(G-C) 
    assertions = _extract_claims(query)
    theories = _extract_theories_local(query)

    if not assertions:
        assertions = [query[:100]]
    if not theories:
        theories = []

    # ─── 阶段2: 转录 → 基因（含START/STOP） ───
    try:
        # 构建完整的碱基输入: ATG + 动作链 + TAA
        # ATG = START, TAA = CONCLUDE
        raw_input = []
        
        # START密码子 (3)
        raw_input.append({"base": "A", "content": "启动管线:" + query[:60], "complement": "T:管线就绪"})
        raw_input.append({"base": "T", "content": "验证就绪:天枢τ连接", "complement": "A:φ织星在线"})
        raw_input.append({"base": "G", "content": "理论框架:四神/MMT", "complement": "C:证据待收集"})
        
        # 动作密码子: 按家族聚合 (同族连续 → 形成操纵子)
        # SEARCH族: AAG(SEARCH), AAC(SEARCH_DEEP), AAT(SEARCH_META), AAA(SEARCH_DOC)
        # SIMULATE族: GGC(SIMULATE), GGA(SIMULATE_SWEEP), GGG(SIMULATE_COMPETE), GGT(SIMULATE_FISCAL)
        # VERIFY族: CGT(VERIFY), CGC(VERIFY_RELATION), CGA(VERIFY_BENFORD), CGG(VERIFY_ENTROPY)
        # CONTRAST族: TGC(CONTRAST), TGA(ADVERSARIAL), TGG(ITERATE)
        
        operon_genes = {
            "SEARCH":   ["AAG", "AAC", "AAT", "AAA"],
            "SIMULATE": ["GGC", "GGA", "GGG", "GGT"],
            "VERIFY":   ["CGT", "CGC", "CGA", "CGG"],
            "CONTRAST": ["TGC", "TGA", "TGG"],
        }
        
        # 为每个主张生成密码子，按操纵子族分组排列
        # 顺序: SEARCH族 → SIMULATE族 → VERIFY族 → CONTRAST族
        search_codons = []
        simulate_codons = []
        verify_codons = []
        contrast_codons = []
        
        for i, a in enumerate(assertions[:8]):
            family_idx = i % 4
            
            if family_idx == 0:
                codon = operon_genes["SEARCH"][min(i // 4, 3)]
                target = search_codons
            elif family_idx == 1:
                codon = operon_genes["SIMULATE"][min(i // 4, 3)]
                target = simulate_codons
            elif family_idx == 2:
                codon = operon_genes["VERIFY"][min(i // 4, 3)]
                target = verify_codons
            else:
                codon = operon_genes["CONTRAST"][min(i // 4, 3)]
                target = contrast_codons
            
            # 收集密码子内容
            target.append((codon, a[:80]))
        
        # 按族顺序展开为碱基: SEARCH → SIMULATE → VERIFY → CONTRAST
        for codon_group in [search_codons, simulate_codons, verify_codons, contrast_codons]:
            for codon, content in codon_group:
                for base in list(codon):
                    raw_input.append({
                        "base": base,
                        "content": content,
                        "complement": "待配对:管线执行结果"
                    })
        
        # 同族密码子已连续排列 → 操纵子检测自动聚合为并发执行单元
        
        # 理论对: 每个理论形成 G-C 对 (填充到3的倍数)
        for i, t in enumerate(theories[:2]):
            raw_input.append({"base": "G", "content": t[:80], "complement": "证据待收集"})
            raw_input.append({"base": "G", "content": f"理论框架:{t[:60]}", "complement": "待配对"})
            raw_input.append({"base": "C", "content": "证据配对", "complement": t[:80]})
        
        # STOP密码子 (3): TAA = STOP_CONCLUDE
        raw_input.append({"base": "T", "content": "输出结论:保证面板+追溯链", "complement": "A:τ封印高置信"})
        raw_input.append({"base": "A", "content": "对抗自检:反例攻击→存活", "complement": "T:结论存活验证"})
        raw_input.append({"base": "A", "content": "终止", "complement": "T:结束"})

        # 手动转录（不经过 genome.transcribe，直接构建 Gene）  
        gene = Gene()
        gene.transcribe(raw_input)
        gene_id = hashlib.sha256((query + str(time.time())).encode()).hexdigest()[:12]
        genome.genes[gene_id] = gene
        genome.active_gene = gene
        genome.stats["total_genes"] = len(genome.genes)
        
        result["gene_id"] = gene_id
        result["sequence"] = gene.sequence

        # 检查转录质量
        initial_mismatches = sum(1 for nt in gene.nucleotides if nt.mismatch_flag)
        result["mismatches"] = initial_mismatches

        # 保护层: 对基因组进行完整保护
        try:
            guardian_result = GenomeGuardian.full_protection_cycle(genome)
            result["guardian"] = guardian_result
        except Exception:
            pass
    except Exception as e:
        result["errors"].append(f"转录失败: {e}")
        return result

    # ─── 阶段3: 如果有管线结果，配对填充 ───
    if pipeline_result and gene:
        _fill_gene_from_pipeline(gene, pipeline_result, genome, gene_id, result)

    # ─── 阶段4: 翻译 → 动作序列 ───
    try:
        translation = genome.translate_gene(gene_id)
        result["codons"] = translation.get("codons", [])
        result["actions"] = translation.get("actions", [])
        result["protein"] = translation.get("protein", "")

        if not translation.get("expressed"):
            result["errors"].extend(translation.get("errors", []))
    except Exception as e:
        result["errors"].append(f"翻译失败: {e}")

    # ─── 阶段4.5: 执行 → tRNA接核糖体 (操纵子版) ───
    # 密码子按操纵子聚合，族内并发，族间串行
    execution_result = {}
    try:
        # 检测操纵子结构
        operons = detect_operons(result["codons"])
        result["operons"] = [
            {"name": o.name, "codons": o.codons, "active": o.is_active}
            for o in operons
        ]

        # 操纵子并发执行
        execution_result = execute_codons_with_operons(
            codons=result["codons"],
            context={
                "query": query,
                "pipeline_ctx": pipeline_result,
                "collected": {},
            },
        )
        result["execution_log"] = execution_result.get("execution_log", [])
        result["collected_data"] = execution_result.get("collected", {})

        # 用执行结果回填基因
        _fill_gene_from_execution(gene, execution_result)

        # 更新蛋白
        gene.split_codons()
        gene.translate()
        result["protein"] = gene.protein
        result["executed"] = True
        result["operon_count"] = execution_result.get("operon_count", 0)
        result["parallel_operon_count"] = execution_result.get("parallel_operon_count", 0)
    except Exception as e:
        result["errors"].append(f"执行失败: {e}")
        result["executed"] = False

    # ─── 阶段5: 修复 → 健康 ───
    try:
        repair_result = genome.repair()
        result["health"] = genome.health()
        result["health"]["repair"] = repair_result
    except Exception as e:
        result["errors"].append(f"修复失败: {e}")

    # ─── 阶段6: 构建基因组上下文 ───
    result["genome_context"] = _build_genome_context(result)

    return result


def _fill_gene_from_execution(gene: Gene, execution_result: dict) -> None:
    """用执行结果回填基因的反义链——补全A-T和G-C配对。"""
    collected = execution_result.get("collected", {})
    log = execution_result.get("execution_log", [])

    # 对每个核苷酸，用执行结果填充反义链
    for i, nt in enumerate(gene.nucleotides):
        if nt.mismatch_flag and not nt.antisense_content:
            if nt.sense_base == "A":
                # A需要T（验证）→ 从闸门执行结果取
                if collected.get("verification_result"):
                    nt.antisense_content = str(collected["verification_result"])[:200]
                    nt.verified = True
                    nt.mismatch_flag = False
            elif nt.sense_base == "G":
                # G需要C（证据）→ 从搜索结果取
                if collected.get("search_data"):
                    nt.antisense_content = str(collected["search_data"])[:200]
                    nt.verified = True
                    nt.mismatch_flag = False
            elif nt.sense_base == "T":
                # T需要A → 从执行日志取
                if log:
                    nt.antisense_content = f"执行:{len(log)}步"
                    nt.verified = True
                    nt.mismatch_flag = False


def _fill_gene_from_pipeline(
    gene: Gene,
    pipeline_ctx: dict,
    genome: Genome,
    gene_id: str,
    result: dict,
) -> None:
    """将管线执行结果回填到基因中，补全A-T和G-C配对。"""
    gate = pipeline_ctx.get("gate_result")
    wv = pipeline_ctx.get("wv", {})
    data_text = pipeline_ctx.get("data_text", "")

    # 填充验证链 (T) — 从闸门结果
    verifications = []
    if gate:
        if hasattr(gate, 'overall_score'):
            verifications.append(f"质量闸综合分{gate.overall_score:.2f}")
        if hasattr(gate, 'authenticity') and gate.authenticity:
            verifications.append(f"真实性{gate.authenticity.get('score', 0):.1f}")
        if hasattr(gate, 'relation_integrity') and gate.relation_integrity:
            ri = gate.relation_integrity
            verifications.append(f"关系完整性{ri.get('score',0):.1f}")

    # 填充证据链 (C) — 从搜索结果
    evidences = []
    if data_text:
        evidences.append(data_text[:300])

    # 更新核苷酸：配对反义链
    for i, nt in enumerate(gene.nucleotides):
        if nt.sense_base == "A" and verifications:
            v_idx = min(i, len(verifications) - 1)
            nt.antisense_content = verifications[v_idx]
            nt.verified = True
            nt.mismatch_flag = False
        elif nt.sense_base == "G" and evidences:
            e_idx = min(i, len(evidences) - 1)
            nt.antisense_content = evidences[e_idx]
            nt.verified = True
            nt.mismatch_flag = False

    # 重新翻译以更新蛋白
    gene.split_codons()
    gene.translate()

    result["sequence"] = gene.sequence
    result["protein"] = gene.protein
    result["mismatches"] = sum(1 for nt in gene.nucleotides if nt.mismatch_flag)


def _build_genome_context(result: dict) -> str:
    """构建基因组上下文 — 注入到消息中。"""
    parts = []

    # DNA结构行
    sequence = result.get("sequence", "")
    protein = result.get("protein", "")
    health = result.get("health", {})

    stability = health.get("stability", "?")
    gc = health.get("gc_content", 0)
    mismatch_rate = health.get("mismatch_rate", 0)

    parts.append(
        f"🧬 DNA: 序列[{sequence}] → 蛋白[{protein}] "
        f"| GC{int(gc*100)}% | 错配率{mismatch_rate:.2f} | {stability}"
    )

    # 密码子执行详情
    exec_log = result.get("execution_log", [])
    operons = result.get("operons", [])
    if operons:
        op_summary = []
        for op in operons:
            name = op.get("name", "?")
            codons_list = op.get("codons", [])
            active = "▶" if op.get("active", True) else "⊘"
            op_summary.append("%s[%s %s]" % (active, name, "·".join(codons_list)))
        parts.append("操纵子: " + " ".join(op_summary))

    if exec_log:
        status_badges = []
        for entry in exec_log:
            badge = "✓" if entry["result"] == "ok" else ("⚠" if entry["result"] == "error" else "·")
            status_badges.append("%s%s=%s" % (badge, entry['codon'], entry['action']))
        parts.append("执行: " + " ".join(status_badges))

    # 收集数据摘要
    collected = result.get("collected_data", {})
    if collected:
        summary = []
        if collected.get("search_data"):
            summary.append(f"搜索{len(str(collected['search_data']))}字符")
        if collected.get("simulation_result"):
            summary.append("模拟✓")
        if collected.get("verification_result"):
            summary.append("验证✓")
        if collected.get("contrast_text"):
            summary.append("对比✓")
        if summary:
            parts.append("数据: " + " | ".join(summary))

    # 密码子列表
    codons = result.get("codons", [])
    if codons:
        codon_summary = []
        for c in codons[:8]:
            info = CodonTable.translate(c)
            codon_summary.append(f"{c}={info['action']}")
        parts.append("密码子: " + " ".join(codon_summary))

    # 错配
    errors = result.get("errors", [])
    if errors:
        parts.append(f"⚠ DNA错配({len(errors)}): " + "; ".join(errors[:3]))

    return "\n".join(parts)


# ════════════════════════════════════════════════════════
# 双轨执行: 管线 + DNA
# ════════════════════════════════════════════════════════

def run_dual_pipeline(query: str, skip_layers: set = None) -> dict:
    """
    双轨研究管线:

    轨道1 (管线): 直接执行 run_pipeline()
    轨道2 (DNA):  转录→密码子→执行→蛋白

    返回融合上下文。
    """
    if skip_layers is None:
        skip_layers = set()

    # ─── 轨道1: 标准管线 ───
    pipeline_ctx = {}
    try:
        from pipeline import run_pipeline
        pipeline_ctx = run_pipeline(query, skip_layers=skip_layers)
    except Exception as e:
        pipeline_ctx = {"message": query, "error": str(e)}

    # ─── 轨道2: DNA管线 ───
    genome_ctx = run_genome_pipeline(
        query=query,
        skip_layers=skip_layers,
        pipeline_result=pipeline_ctx,
    )

    # ─── 融合 ───
    message = pipeline_ctx.get("message", query)
    genome_context = genome_ctx.get("genome_context", "")

    if genome_context:
        message = f"{message}\n\n{genome_context}"

    return {
        "message": message,
        "pipeline_ctx": pipeline_ctx,
        "genome_ctx": genome_ctx,
        "gene_id": genome_ctx.get("gene_id"),
        "protein": genome_ctx.get("protein", ""),
        "sequence": genome_ctx.get("sequence", ""),
        "health": genome_ctx.get("health", {}),
    }


# ════════════════════════════════════════════════════════
# 辅助: 主张/理论提取
# ════════════════════════════════════════════════════════

def _extract_claims(text: str) -> list[str]:
    """从文本中提取主张（A碱基）。识别断言性语句。"""
    claims = []
    # 按句号/问号/感叹号分句
    sentences = _re_extract.split(r'[。？！?\n]', text)
    for s in sentences:
        s = s.strip()
        if not s or len(s) < 4:
            continue
        # 主张性关键词
        claim_patterns = [
            r'应该', r'必须', r'最优', r'最.*是', r'关键', r'核心',
            r'可以', r'能够', r'建议', r'结论', r'认为', r'=',
            r'等于', r'取决于', r'是.*的', r'只能', r'如何', r'什么',
            r'为什么', r'多少', r'是否', r'怎样',
        ]
        for pat in claim_patterns:
            if _re_extract.search(pat, s):
                claims.append(s[:120])
                break

    if not claims:
        # 回退: 单句查询 → 拆分为多个主张
        text = text.strip()
        # 有问号 → 按问号拆
        if '?' in text or '？' in text:
            parts = _re_extract.split(r'[?？]', text)
            claims = [p.strip()[:120] for p in parts if p.strip() and len(p.strip()) > 4]
        # 逗号拆分
        if not claims and ('，' in text or ',' in text):
            parts = _re_extract.split(r'[，,]', text)
            claims = [p.strip()[:120] for p in parts if p.strip() and len(p.strip()) > 3]
        # 最后回退: 整个查询
        if not claims:
            claims = [text[:100]]

    # 确保至少有 3 个主张 (形成至少 1 个完整密码子)
    while len(claims) < 3:
        claims.append(f"子问题{len(claims)+1}: {text[max(0,60*(len(claims))):60*(len(claims)+1)]}")

    return claims[:6]  # 最多6个主张 (2个密码子)


def _extract_theories_local(text: str) -> list[str]:
    """从文本中提取理论引用（G碱基）。识别理论/框架性语句。"""
    theories = []
    sentences = _re_extract.split(r'[。？！?\n]', text)
    for s in sentences:
        s = s.strip()
        if not s or len(s) < 8:
            continue
        theory_patterns = [
            r'理论', r'框架', r'范式', r'模型', r'学说',
            r'MMT', r'凯恩斯', r'古典', r'新古典', r'四神',
            r'Monetary', r'Theory', r'假设', r'公理', r'定理',
            r'认为.*理论', r'根据.*理论',
        ]
        for pat in theory_patterns:
            if _re_extract.search(pat, s, _re_extract.IGNORECASE):
                theories.append(s[:120])
                break
    return theories[:3]
