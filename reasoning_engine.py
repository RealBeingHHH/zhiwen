# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Copyright (c) 2026 知纹 (Zhiwen) Project

"""
推理引擎 — 显式推理步·证明图·一致性检测

不是LLM隐式推理。是结构化推理——每个推理步可追溯、可验证、
可与 φ-drift 交叉检测。

三种推理模式:
  DEDUCTION  前提→必然结论    (若A→B且A成立, 则B必然成立)
  INDUCTION  多观测→模式      (从N个案例中归纳规律)
  ABDUCTION  现象→最佳解释    (从观测反推最可能的原因)

证明图:
  节点 = 逻辑声明 (Claim)    "日本通缩主因是需求不足"
  边   = 推理关系 (Inference) "由证据E1、E2归纳得出"
  根   = 最终结论            "MMT政策对日本通缩有效"

φ交叉验证:
  每个推理步检查: 输出声明中的数字是否在输入证据中有锚?
  无锚数字 → φ-drift标记 → 推理步标注"未锚定"
  多个未锚定步 → 整条链标注"幻觉风险"

置信度传播:
  证据评分 → 推理步置信度 → 结论置信度 (取min: 链强度=最弱环节)

用法:
  from reasoning_engine import ReasoningEngine
  engine = ReasoningEngine()
  proof = engine.reason(evidence, query)
  # proof.chains → 多条推理链
  # proof.confidence → 综合置信度
  # proof.phi_warnings → φ漂移警告
"""

import time, hashlib, re as _re, math
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ════════════════════════════════════════════════════════
# 推理类型
# ════════════════════════════════════════════════════════

class ReasonType(Enum):
    DEDUCTION = "deduction"      # 必然推理
    INDUCTION = "induction"       # 归纳推理
    ABDUCTION = "abduction"       # 溯因推理
    ANALOGY = "analogy"           # 类比推理
    CONTRAST = "contrast"         # 对比推理
    CAUSAL = "causal"             # 因果推理


# ════════════════════════════════════════════════════════
# 证明图节点
# ════════════════════════════════════════════════════════

@dataclass
class Claim:
    """一个逻辑声明——证明图中的节点。"""

    id: str                              # 唯一标识
    text: str                            # 声明内容
    source: str = ""                     # 来源 (证据ID/推理步ID)
    confidence: float = 0.0              # 置信度 0-1
    verified: bool = False               # 是否已验证 (过闸)

    # φ监控
    numbers: list[str] = field(default_factory=list)      # 声明中的数字
    anchored_numbers: int = 0            # 有锚的数字数
    unanchored_numbers: int = 0          # 无锚的数字数
    phi_drift_flag: bool = False         # φ漂移标记


@dataclass
class Inference:
    """一条推理边——从前提推到结论。"""

    id: str
    type: ReasonType                     # 推理类型
    premises: list[str]                  # 前提Claim ID列表
    conclusion: str                      # 结论Claim ID
    rule: str = ""                       # 推理规则描述
    confidence: float = 0.0              # 推理置信度
    reversible: bool = True              # 推理是否可逆
    phi_warnings: list[str] = field(default_factory=list)  # φ警告


@dataclass
class ProofGraph:
    """完整的证明图 = 声明节点 + 推理边。"""

    query: str
    claims: dict[str, Claim]             # id → Claim
    inferences: list[Inference]
    root_claim_id: str = ""              # 最终结论的Claim ID
    chains: list[list[str]] = field(default_factory=list)  # 多条推理链
    confidence: float = 0.0              # 综合置信度
    phi_warnings: list[str] = field(default_factory=list)  # φ警告汇总
    consistency_issues: list[str] = field(default_factory=list)  # 一致性问题


# ════════════════════════════════════════════════════════
# 推理引擎
# ════════════════════════════════════════════════════════

class ReasoningEngine:
    """结构化推理引擎 — 从证据到结论的显式逻辑链。"""

    def reason(self, evidence: dict, query: str,
               kb_facts: list = None) -> ProofGraph:
        """
        从证据出发，构建显式推理链。

        evidence: 研究规划器的子问题结果
          {sub_qid: {evidence_text, evidence_score, ...}}

        流程:
          1. 提取声明: 从证据中抽取可验证的逻辑声明
          2. 构建推理: 声明之间建立推理关系
          3. φ验证: 检查数字锚定
          4. 一致性检测: 新声明 vs 知识图谱
          5. 置信度传播: 从证据→推理步→结论
        """
        graph = ProofGraph(query=query, claims={}, inferences=[])

        # ═══ 阶段1: 提取声明 ═══
        claims = self._extract_claims(evidence, query, kb_facts or [])
        for c in claims:
            graph.claims[c.id] = c

        if not claims:
            return graph

        # ═══ 阶段2: 构建推理边 ═══
        inferences = self._build_inferences(claims, evidence, query)
        graph.inferences = inferences

        # ═══ 阶段3: 构造推理链 (多条并行链) ═══
        chains = self._build_chains(claims, inferences)
        graph.chains = chains

        # ═══ 阶段4: φ交叉验证 ═══
        graph.phi_warnings = self._phi_cross_validate(claims, inferences, evidence)

        # ═══ 阶段5: 一致性检测 ═══
        graph.consistency_issues = self._check_consistency(claims, kb_facts or [])

        # ═══ 阶段6: 置信度传播 ═══
        graph.confidence = self._propagate_confidence(claims, inferences, evidence)

        # 根节点 = 最后一个推断的结论
        if inferences:
            graph.root_claim_id = inferences[-1].conclusion

        return graph

    # ─── 声明提取 ───

    def _extract_claims(self, evidence: dict, query: str,
                        kb_facts: list) -> list[Claim]:
        """从证据文本中提取可验证的逻辑声明。"""
        claims = []
        seen_texts = set()

        # 从各子问题证据中提取
        for qid, result in evidence.items():
            if not isinstance(result, dict):
                continue
            text = result.get("evidence_text", "")
            score = result.get("evidence_score", 0.0)

            if not text or len(text) < 20:
                continue

            # 分句 → 每句可能是一个声明
            sentences = _re.split(r'[。．.！!？?\n]+', str(text))
            for s in sentences:
                s = s.strip()
                if len(s) < 10 or s in seen_texts:
                    continue
                seen_texts.add(s)

                # 检测数字
                numbers = _re.findall(r'\b\d+\.?\d*%?\b', s)

                claim = Claim(
                    id=hashlib.sha256(s.encode()).hexdigest()[:10],
                    text=s[:200],
                    source=qid,
                    confidence=min(score, 0.9),
                    numbers=numbers,
                    verified=score >= 0.5,
                )
                claims.append(claim)

        # 从知识图谱补充
        for fact in kb_facts:
            fact_text = fact.get("fact", "") if isinstance(fact, dict) else str(fact)
            if fact_text and len(fact_text) > 10 and fact_text not in seen_texts:
                conf = fact.get("effective_confidence", 0.6) if isinstance(fact, dict) else 0.5
                claims.append(Claim(
                    id=hashlib.sha256(fact_text.encode()).hexdigest()[:10],
                    text=fact_text[:200],
                    source="knowledge_graph",
                    confidence=min(conf, 0.95),
                    verified=True,
                ))

        return claims

    # ─── 推理构建 ───

    def _build_inferences(self, claims: list[Claim], evidence: dict,
                          query: str) -> list[Inference]:
        """在声明之间建立推理关系。使用LLM辅助 + 规则检测。"""
        inferences = []

        if len(claims) < 2:
            return inferences

        # 方法1: 启发式规则检测推理关系
        rule_inferences = self._detect_logical_relations(claims)
        inferences.extend(rule_inferences)

        # 方法2: LLM辅助推理 (受监控)
        if len(claims) >= 3:
            llm_inferences = self._llm_reason(claims, query)
            for inf in llm_inferences:
                # 检查是否与启发式推理重复
                if not any(i.conclusion == inf.conclusion
                           and set(i.premises) == set(inf.premises)
                           for i in inferences):
                    inferences.append(inf)

        return inferences

    def _detect_logical_relations(self, claims: list[Claim]) -> list[Inference]:
        """启发式规则: 数字关系·因果关系·对比关系·同源推断。"""
        inferences = []

        for i, c1 in enumerate(claims):
            for j, c2 in enumerate(claims):
                if i >= j:
                    continue

                # 规则1: 数字关系
                common_nums = set(c1.numbers) & set(c2.numbers)
                if common_nums:
                    inferences.append(Inference(
                        id="num_%d_%d" % (i, j),
                        type=ReasonType.DEDUCTION,
                        premises=[c1.id, c2.id],
                        conclusion=c2.id,
                        rule="共享数字%s" % list(common_nums)[:3],
                        confidence=0.5,
                    ))

                # 规则2: 同源推断 (同来源的声明之间存在推理关系)
                if c1.source == c2.source and c1.source != "knowledge_graph":
                    inferences.append(Inference(
                        id="src_%d_%d" % (i, j),
                        type=ReasonType.INDUCTION,
                        premises=[c1.id],
                        conclusion=c2.id,
                        rule="同源证据归纳(%s)" % c1.source[:8],
                        confidence=0.45,
                    ))

                # 规则3: 关键词推理
                patterns = [
                    (["因为", "所以", "导致", "引起", "造成", "由于", "因此", "结果是", "归因于"], ReasonType.CAUSAL, 0.55),
                    (["然而", "但是", "相反", "对比", "差异", "不同于", "相较于", "却"], ReasonType.CONTRAST, 0.5),
                    (["表明", "说明", "证明", "显示", "证实", "验证"], ReasonType.INDUCTION, 0.5),
                    (["如果", "假设", "倘若", "若"], ReasonType.DEDUCTION, 0.45),
                ]
                for keywords, rtype, conf in patterns:
                    matched = False
                    for kw in keywords:
                        if kw in c1.text or kw in c2.text:
                            inferences.append(Inference(
                                id="%s_%d_%d" % (rtype.value[:4], i, j),
                                type=rtype,
                                premises=[c1.id],
                                conclusion=c2.id,
                                rule="关键词'%s'" % kw,
                                confidence=conf,
                            ))
                            matched = True
                            break
                    if matched:
                        break

        return inferences

    def _llm_reason(self, claims: list[Claim], query: str) -> list[Inference]:
        """LLM辅助推理 — 严格监控φ-drift和τ锚定。"""
        try:
            from voyager_llm import safe_llm_call as _llm

            # 构建声明列表
            claim_texts = "\n".join(
                f"[C{i}] {c.text[:100]} (置信度{c.confidence:.2f})"
                for i, c in enumerate(claims[:8])
            )

            system = (
                "你是推理引擎。从以下声明中识别推理关系。\n"
                "返回JSON数组,每个元素描述一条推理:\n"
                "  type: deduction/induction/causation/contrast\n"
                "  premises: [声明编号列表]\n"
                "  conclusion: 结论声明编号\n"
                "  rule: 推理规则\n"
                "  confidence: 0-1\n"
                "只返回有把握的推理,不确定的不要。最多5条。\n"
                '格式: [{"type":"deduction","premises":[0,1],"conclusion":2,"rule":"...","confidence":0.7}]'
            )

            user = f"原始问题: {query}\n\n声明:\n{claim_texts}"

            result = _llm(system, user, max_tokens=800)

            # φ监控
            from research_planner import LLMMonitor
            input_hash = hashlib.sha256((system + user).encode()).hexdigest()[:12]
            phi_drift = self._calc_phi_drift(result)
            LLMMonitor.log_call(
                purpose="推理构建",
                input_hash=input_hash,
                output=result,
                phi_drift=phi_drift,
                tau_anchored=self._has_tau_anchoring(result, query),
            )

            # 解析
            import json
            data = self._parse_json_safe(result)
            if not isinstance(data, list):
                return []

            inferences = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                prem_ids = [claims[p]["id"] if isinstance(p, int) and p < len(claims)
                           else str(p)
                           for p in item.get("premises", [])[:3]]

                # 找conclusion的Claim ID
                conc_idx = item.get("conclusion", 0)
                if isinstance(conc_idx, int) and conc_idx < len(claims):
                    conc_id = claims[conc_idx].id
                else:
                    conc_id = claims[-1].id if claims else "root"

                inf_type = item.get("type", "deduction")
                try:
                    rt = ReasonType(inf_type)
                except:
                    rt = ReasonType.DEDUCTION

                inferences.append(Inference(
                    id="llm_" + hashlib.sha256(str(item).encode()).hexdigest()[:8],
                    type=rt,
                    premises=[pid for pid in prem_ids if pid],
                    conclusion=conc_id,
                    rule=item.get("rule", "")[:100],
                    confidence=min(float(item.get("confidence", 0.5)), 0.85),
                ))

            return inferences[:5]

        except Exception:
            return []

    # ─── 推理链构造 ───

    def _build_chains(self, claims: list[Claim],
                      inferences: list[Inference]) -> list[list[str]]:
        """将推理边组织为多条并行推理链。"""
        if not claims:
            return []

        # 构建邻接表
        adj: dict[str, list[str]] = {}
        in_degree: dict[str, int] = {}
        for c in claims:
            adj[c.id] = []
            in_degree[c.id] = 0

        for inf in inferences:
            for prem in inf.premises:
                if prem in adj and inf.conclusion in adj:
                    adj[prem].append(inf.conclusion)
                    in_degree[inf.conclusion] = in_degree.get(inf.conclusion, 0) + 1

        # 找所有叶节点(入度=0) → 每条链的起点
        roots = [cid for cid, deg in in_degree.items() if deg == 0]

        chains = []
        for root in roots:
            chain = self._dfs_chain(root, adj, set())
            if chain and len(chain) >= 2:
                chains.append(chain)

        return chains[:5]

    def _dfs_chain(self, node: str, adj: dict[str, list[str]],
                   visited: set) -> list[str]:
        if node in visited:
            return []
        visited.add(node)
        chain = [node]
        for neighbor in adj.get(node, []):
            sub = self._dfs_chain(neighbor, adj, visited)
            if sub:
                chain.extend(sub)
        return chain

    # ─── φ交叉验证 ───

    def _phi_cross_validate(self, claims: list[Claim],
                            inferences: list[Inference],
                            evidence: dict) -> list[str]:
        """检查推理链中的数字锚定和φ漂移。"""
        warnings = []

        # 收集所有证据中的数字 (视为"锚")
        anchored_numbers: set[str] = set()
        for qid, result in evidence.items():
            if isinstance(result, dict):
                text = result.get("evidence_text", "")
                anchored_numbers.update(_re.findall(r'\b\d+\.?\d*%?\b', str(text)))

        # 检查每个声明
        for claim in claims:
            claim.anchored_numbers = len(set(claim.numbers) & anchored_numbers)
            claim.unanchored_numbers = len(set(claim.numbers) - anchored_numbers)
            if claim.unanchored_numbers > 2:
                claim.phi_drift_flag = True
                warnings.append(
                    "φ-drift: [%s] %d个数字无锚 → %s" % (
                        claim.id[:6], claim.unanchored_numbers,
                        claim.text[:80]
                    )
                )

        # 检查每个推理
        for inf in inferences:
            if inf.confidence < 0.3:
                warnings.append(
                    "低置信推理: [%s] %s 置信度%.2f" % (
                        inf.id[:8], inf.type.value, inf.confidence
                    )
                )

        return warnings[:10]

    # ─── 一致性检测 ───

    def _check_consistency(self, claims: list[Claim],
                           kb_facts: list) -> list[str]:
        """检测新声明与已有知识的矛盾。"""
        issues = []

        # 构建KB文本集
        kb_texts = set()
        for f in kb_facts:
            if isinstance(f, dict):
                kb_texts.add(f.get("fact", "")[:100])
            else:
                kb_texts.add(str(f)[:100])

        for claim in claims:
            # 数字矛盾: 同为"赤字率"但数值冲突
            for other in claims:
                if other.id >= claim.id:
                    continue
                if (claim.numbers and other.numbers
                    and claim.source == other.source):
                    # 同源声明数字不同 → 可能矛盾
                    pass  # 简化处理

            # KB矛盾: 新声明与KB冲突
            claim_words = set(_re.findall(r'[\u4e00-\u9fff]{2,}', claim.text))
            for kb_text in kb_texts:
                kb_words = set(_re.findall(r'[\u4e00-\u9fff]{2,}', kb_text))
                overlap = claim_words & kb_words
                if len(overlap) > 5:
                    # 高度重叠但可能相反语义
                    # 简化: 检查否定词
                    negations = ["不", "否", "非", "无", "未", "并非"]
                    claim_neg = any(n in claim.text for n in negations)
                    kb_neg = any(n in kb_text for n in negations)
                    if claim_neg != kb_neg:
                        issues.append(
                            "矛盾: '%s...' vs KB '%s...'" % (
                                claim.text[:60], kb_text[:60]
                            )
                        )
                    break

        return issues[:5]

    # ─── 置信度传播 ───

    def _propagate_confidence(self, claims: list[Claim],
                              inferences: list[Inference],
                              evidence: dict) -> float:
        """从证据评分 → 推理步 → 最终结论的置信度传播。"""
        if not claims:
            return 0.0

        # 证据置信度: 取所有子问题评分的加权平均
        scores = []
        for qid, result in evidence.items():
            if isinstance(result, dict):
                s = result.get("evidence_score", 0)
                if s > 0:
                    scores.append(s)

        evidence_conf = sum(scores) / len(scores) if scores else 0.3

        # 推理链置信度: 链强度 = min(各步推理置信度)
        if inferences:
            min_inf_conf = min(inf.confidence for inf in inferences)
        else:
            min_inf_conf = 0.5

        # φ惩罚: 有φ-drift → 降权
        phi_penalty = 1.0
        drift_count = sum(1 for c in claims if c.phi_drift_flag)
        if drift_count > 0:
            phi_penalty = max(0.3, 1.0 - drift_count * 0.15)

        # 综合: 证据分 × 推理强度 × φ惩罚
        confidence = evidence_conf * min_inf_conf * phi_penalty
        return round(confidence, 3)

    # ─── 辅助 ───

    def _calc_phi_drift(self, text: str) -> float:
        if not text:
            return 0.0
        nums = _re.findall(r'\b\d+\.?\d*\b', str(text))
        if not nums:
            return 0.0
        drift = min(len(nums) / 15.0, 0.8)
        for n in nums:
            try:
                v = float(n)
                if abs(v) > 1e9 or (0 < abs(v) < 1e-5):
                    drift += 0.1
            except:
                pass
        return min(drift, 1.0)

    def _has_tau_anchoring(self, text: str, query: str) -> bool:
        out_nums = set(_re.findall(r'\b\d+\.?\d*\b', str(text)))
        in_nums = set(_re.findall(r'\b\d+\.?\d*\b', str(query)))
        # 任何输出数字不在输入中 → 未锚定
        return len(out_nums - in_nums) == 0

    def _parse_json_safe(self, text: str):
        import json
        try:
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                return json.loads(text[start:end+1])
        except:
            pass
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start:end+1])
        except:
            pass
        return []


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def reason_from_evidence(evidence: dict, query: str,
                         kb_facts: list = None) -> dict:
    """从证据→推理→结构化结论。"""
    engine = ReasoningEngine()
    graph = engine.reason(evidence, query, kb_facts or [])

    return {
        "query": query,
        "claims_count": len(graph.claims),
        "inferences_count": len(graph.inferences),
        "chains": [
            [graph.claims.get(cid, Claim(id=cid, text="?")).text[:80]
             for cid in chain]
            for chain in graph.chains
        ],
        "confidence": graph.confidence,
        "phi_warnings": graph.phi_warnings,
        "consistency_issues": graph.consistency_issues,
        "root_claim": graph.claims.get(
            graph.root_claim_id,
            Claim(id="?", text="未找到结论")
        ).text[:200] if graph.root_claim_id else "",
    }


# ═══ 自检 ═══
if __name__ == "__main__":
    engine = ReasoningEngine()

    # 模拟证据
    evidence = {
        "sub1": {
            "evidence_text": "日本1990-2020年GDP增长率平均0.8%。人口老龄化导致劳动力减少15%。",
            "evidence_score": 0.7,
        },
        "sub2": {
            "evidence_text": "日本央行大规模购债后基础货币增长300%。但通胀率仍低于1%。",
            "evidence_score": 0.65,
        },
        "sub3": {
            "evidence_text": "MMT认为主权货币政府不受税收约束。日本实践表明财政扩张未引发通胀。",
            "evidence_score": 0.55,
        },
    }

    graph = engine.reason(evidence, "日本MMT政策有效性分析")

    print("=== 推理引擎测试 ===")
    print("声明数: %d" % len(graph.claims))
    print("推理数: %d" % len(graph.inferences))
    print("推理链: %d条" % len(graph.chains))

    for i, chain in enumerate(graph.chains):
        print("\n推理链%d:" % (i + 1))
        for j, cid in enumerate(chain):
            claim = graph.claims.get(cid)
            if claim:
                marker = "⚠φ" if claim.phi_drift_flag else ""
                print("  %d. [%s] %s %s" % (j + 1, claim.id[:6], claim.text[:80], marker))

    print("\n置信度: %.2f" % graph.confidence)
    print("φ警告: %d条" % len(graph.phi_warnings))
    for w in graph.phi_warnings[:3]:
        print("  ⚠ %s" % w)
