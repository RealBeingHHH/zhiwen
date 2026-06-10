"""
因果追溯链 — 结论→公理的完整可审计推演路径

保证面板告诉你"各层分数是多少"。
因果追溯链告诉你"结论是怎么从公理一步步推出来的"。

每一条结论都能被追问:
  - 基于哪个公理？
  - 用了什么方法？
  - 依赖哪些数据？
  - 数据通过了哪些质量闸？
  - 链上最薄弱的环节在哪里？

格式: 公理 → 方法 → 数据 → 闸 → 结论
每一跳标注强度(强/中/弱)，弱跳就是结论的风险点。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CausalLink:
    """追溯链中的一跳。"""
    layer: str         # 公理/方法/数据/闸/结论
    content: str       # 这一步的内容
    strength: str      # 强/中/弱
    evidence: str      # 为什么判定为这个强度


@dataclass
class CausalChain:
    """一条完整的追溯链。"""
    conclusion: str                    # 结论
    links: list[CausalLink] = field(default_factory=list)
    weakest_link: str = ""             # 最薄弱环节
    overall_trust: str = "中"          # 综合可信度


class CausalTracer:
    """从研究上下文构建因果追溯链。"""

    @classmethod
    def build_trace_map(
        cls,
        wv: dict,
        method: dict,
        gate_result,
        data_text: str = "",
        contrast: Optional[dict] = None,
    ) -> str:
        """
        构建完整的因果追溯图。

        返回格式化的追溯文本，注入LLM上下文中。
        LLM应基于此追溯图，对每个结论标注其推演路径。
        """

        lines = []
        lines.append("## 🔗 因果追溯链 — 结论必须可追问")
        lines.append("")

        # ─── 公理层 ───
        wv_name = wv.get("worldview_name", "未知")
        axioms = wv.get("axioms", [])

        lines.append(f"### 公理层（{wv_name}）")
        lines.append("所有结论的起点。以下公理不可进一步简化：")
        for i, axiom in enumerate(axioms[:3]):
            lines.append(f"  A{i+1}. {axiom}")
        lines.append("")

        # 盲点
        blindspots = wv.get("blind_spots", [])
        if blindspots:
            lines.append("**此框架看不见的（盲点）**：")
            for b in blindspots[:2]:
                lines.append(f"  ◯ {b}")
            lines.append("  这些盲点意味着：在这些方向上的结论，链条本质上是断裂的。")
        lines.append("")

        # ─── 方法层 ───
        method_name = method.get("primary", "未知")
        method_reasoning = method.get("reasoning", "")
        method_reqs = method.get("data_requirements", [])

        lines.append(f"### 方法层（{method_name}）")
        lines.append(f"为什么选这个方法：{method_reasoning[:120]}")
        lines.append(f"数据需求：{', '.join(method_reqs[:4])}")
        lines.append("")
        lines.append(f"方法的强度：{cls._method_strength(method_name)}")
        lines.append(f"方法的局限：{cls._method_limitation(method_name)}")
        lines.append("")

        # ─── 数据+闸层 ───
        auth = gate_result.authenticity
        comp = gate_result.completeness
        acc = gate_result.accuracy
        ri = getattr(gate_result, "relation_integrity", {})

        gate_score = getattr(gate_result, "overall_score", 0)
        threshold = method.get("quality_threshold", 0.6)
        gate_passed = gate_score >= threshold

        lines.append(f"### 数据+质量闸层（{'✅通过' if gate_passed else '❌阻断'} {gate_score:.2f}/{threshold}）")
        lines.append("每条数据在支持结论之前，经过了以下闸门：")
        lines.append("")
        lines.append(f"  闸1 真实性 {auth.get('score',0):.1f}")
        lines.append(f"      ├ 织星φ指纹: {auth.get('voyager_score',0):.1f} (Benford+熵场+模式)")
        lines.append(f"      └ URL可追溯: {auth.get('sources_found',0)}个来源")
        lines.append(f"  闸2 完整性 {comp.get('score',0):.1f}")
        lines.append(f"      └ 覆盖 {len(comp.get('found',[]))}/{len(method_reqs)} 类需求字段")
        lines.append(f"  闸3 准确性 {acc.get('score',0):.1f}")
        lines.append(f"      └ 矛盾{acc.get('contradiction_count',0)}条")
        lines.append(f"  闸4 关系 {ri.get('score',0):.1f}")
        lines.append(f"      ├ 通过{ri.get('passed',0)}个约束")
        lines.append(f"      └ 失败{ri.get('failed',0)}个约束")

        if ri.get("violations"):
            lines.append(f"      违规详情：")
            for v in ri.get("violations", [])[:3]:
                lines.append(f"        · {v.get('relation','?')}: {v.get('detail','')[:60]}")

        lines.append("")

        # ─── 最薄弱环节分析 ───
        weakest = cls._find_weakest_link(auth, comp, acc, ri)
        lines.append(f"### ⚡ 关键风险点（追溯链最薄弱处）")
        lines.append(f"{weakest}")
        lines.append("")

        # ─── 追溯指令 ───
        lines.append("### 📐 追溯要求（回答时必须遵守）")
        lines.append("")
        lines.append("对你在回答中给出的**每一个实质性结论**，标注其追溯链：")
        lines.append("")
        lines.append("格式：")
        lines.append("```")
        lines.append("[追溯: A1→{method_name}方法→闸{通过/阻}→此结论]")
        lines.append("  公理依赖: (引用的公理编号)")
        lines.append("  数据支撑: (该结论依赖的具体数据，如'赤字率0.15来自参数扫描')")
        lines.append("  链强度: 强/中/弱 — (原因)")
        lines.append("```")
        lines.append("")
        lines.append("如果某个结论**无法**追溯到公理 — 标注「[未锚定]」。")
        lines.append("如果某个结论依赖的数据在闸门中失败 — 标注「[数据警告: 闸X不通过]」。")
        lines.append("")
        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    @classmethod
    def _method_strength(cls, method_name: str) -> str:
        strengths = {
            "simulation": "强：可反复验证、参数可控、结论有数值支撑",
            "empirical": "中：依赖真实数据，数据可得性决定结论天花板",
            "theoretical": "中：逻辑链自洽，但缺乏外部验证",
            "forensic": "强：基于数学定律(Benford/会计等式)，较少依赖主观判断",
            "comparative": "中：多假说互证，但假说质量决定结论上限",
            "synthesis": "中：广度好，但深度受单源质量制约",
        }
        return strengths.get(method_name, "中：方法的可靠性取决于具体实现")

    @classmethod
    def _method_limitation(cls, method_name: str) -> str:
        limitations = {
            "simulation": "模型假设可能偏离现实——模拟出来的最优不一定是实际最优",
            "empirical": "数据过时、样本不足、来源偏差——'有什么数据'决定'能得出什么结论'",
            "theoretical": "推理链越长，累积误差越大——每个演绎步骤都可能偏航",
            "forensic": "异常≠舞弊——需要因果推理补充",
            "comparative": "假说池的大小和多样性决定结论鲁棒性",
            "synthesis": "综合不等于准确——多源融合可能放大单源偏差",
        }
        return limitations.get(method_name, "每种方法都有其固有局限")

    @classmethod
    def _find_weakest_link(cls, auth: dict, comp: dict, acc: dict, ri: dict) -> str:
        """找出追溯链最薄弱的环节。"""
        scores = {
            "闸1 真实性(织星φ+URL)": auth.get("score", 0),
            "闸2 完整性(字段覆盖)": comp.get("score", 0),
            "闸3 准确性(交叉验证)": acc.get("score", 0),
            "闸4 关系(数学约束)": ri.get("score", 0.5),
        }
        weakest = min(scores, key=scores.get)
        weakest_score = scores[weakest]

        explanations = {
            "闸1 真实性(织星φ+URL)": (
                "数据在数学指纹上可信，但缺乏可追溯的原始来源。"
                "如果此结论依赖精确数值，请谨慎——数字的出处不可验证。"
            ),
            "闸2 完整性(字段覆盖)": (
                "方法所需的数据类型未全部覆盖。缺失的数据维度"
                "可能包含推翻当前结论的信息。"
            ),
            "闸3 准确性(交叉验证)": (
                "数据内部存在矛盾或时效性不足。不同来源/时间的数据互相冲突。"
                "依赖此数据的结论方向可能正确，但具体数值不可靠。"
            ),
            "闸4 关系(数学约束)": (
                "数据违反了基本的数学关系（如会计等式、部门平衡）。"
                "**前提错则结论不可能对**。此结论的根基有结构性缺陷。"
            ),
        }

        return f"最薄弱: {weakest} = {weakest_score:.1f}\n{explanations.get(weakest, '')}"


def causal_chain(
    wv: dict,
    method: dict,
    gate_result,
    data_text: str = "",
    contrast: Optional[dict] = None,
) -> str:
    """快捷生成因果追溯链。"""
    return CausalTracer.build_trace_map(wv, method, gate_result, data_text, contrast)


# ═══ 自检 ═══
if __name__ == "__main__":
    mock_wv = {
        "worldview_name": "法务实证",
        "axioms": [
            "所有可观测痕迹都是证据——不存在完美的掩盖",
            "Benford定律不是巧合——是对数自然规律的约束",
            "时间序列不能撒谎——前后矛盾就是断裂点",
        ],
        "blind_spots": ["非数字化对象不可达", "异常≠舞弊"],
    }
    mock_method = {
        "primary": "forensic",
        "reasoning": "检测到资产负债表不平衡",
        "data_requirements": ["原始账本", "审计记录"],
    }

    from data_gate import GateResult
    gate = GateResult()
    gate.overall_score = 0.58
    gate.authenticity = {"score": 0.65, "voyager_score": 0.61, "sources_found": 0}
    gate.completeness = {"score": 0.50, "found": ["原始账本"], "missing": ["审计记录"]}
    gate.accuracy = {"score": 0.60, "contradiction_count": 4}
    gate.relation_integrity = {
        "score": 0.50, "passed": 0, "failed": 1,
        "violations": [{"relation": "会计恒等式", "detail": "资产≠负债+权益"}],
    }

    print(CausalTracer.build_trace_map(mock_wv, mock_method, gate))
