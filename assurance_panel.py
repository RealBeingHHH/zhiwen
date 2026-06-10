"""
研究保证面板 — 将所有验证层结果汇总为可读的保证证书

在回答前显式呈现每一层验证的结果，让用户看到:
  - 研究不是凭空开始的（有世界观声明）
  - 方法不是随便选的（有方法论路由）
  - 数据不是盲信的（有四层质量闸）
  - 关系不是假设的（有完整性验证）
  - 模拟不是暗箱的（有模拟自检）
  - 框架不是独断的（有世界观对比）

面板格式: 紧凑的 Markdown 层级结构
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

BASE = Path(__file__).parent


@dataclass
class AssuranceReport:
    """汇总所有验证层的结果。"""
    # 世界观
    worldview_name: str = ""
    worldview_blindspots: list = field(default_factory=list)
    worldview_conflicts: list = field(default_factory=list)

    # 方法论
    method_name: str = ""
    method_reasoning: str = ""
    data_requirements: list = field(default_factory=list)

    # 数据质量闸
    gate_score: float = 0.0
    gate_threshold: float = 0.0
    authenticity_score: float = 0.0
    voyager_score: float = 0.0
    completeness_score: float = 0.0
    accuracy_score: float = 0.0
    relation_score: float = 0.0
    sources_count: int = 0
    contradictions: int = 0

    # 关系完整性
    relation_passed: int = 0
    relation_failed: int = 0
    relation_violations: list = field(default_factory=list)

    # 科学方法
    sim_rounds: int = 0
    sim_best_score: float = 0.0
    sim_converged: bool = False
    sim_integrity_passed: bool = True

    # 世界观对比
    has_contrast: bool = False
    contrast_wv: str = ""

    # 综合
    overall_confidence: str = "中"


class AssurancePanel:
    """生成研究保证面板。"""

    @classmethod
    def build(cls, report: AssuranceReport) -> str:
        """
        构建保证面板 Markdown。

        返回格式化的面板文本，注入 LLM 上下文中。
        """

        lines = []
        lines.append("## 🔍 研究保证面板")
        lines.append("")

        # ─── 世界观 ───
        lines.append(f"**🌌 世界观**: {report.worldview_name}")
        if report.worldview_blindspots:
            lines.append(f"  盲点关注: {', '.join(report.worldview_blindspots[:2])}")
        if report.worldview_conflicts:
            conflict_names = [c.get('name', c) if isinstance(c, dict) else c for c in report.worldview_conflicts]
            lines.append(f"  框架冲突: {', '.join(conflict_names[:2])}")
        lines.append("")

        # ─── 方法论 ───
        lines.append(f"**🧭 研究方法**: {report.method_name}")
        if report.method_reasoning:
            lines.append(f"  选择理由: {report.method_reasoning[:80]}")
        if report.data_requirements:
            lines.append(f"  数据需求: {', '.join(report.data_requirements[:4])}")
        lines.append("")

        # ─── 数据质量四闸 ───
        gate_status = "✅ 通过" if report.gate_score >= report.gate_threshold else "❌ 阻断"
        lines.append(f"**🔍 数据质量闸**: {gate_status} (综合 {report.gate_score:.2f}/{report.gate_threshold})")
        lines.append(
            f"  ├ 真实性 {report.authenticity_score:.1f} "
            f"(织星φ={report.voyager_score:.1f}, 来源{report.sources_count}个)"
        )
        lines.append(
            f"  ├ 完整性 {report.completeness_score:.1f} "
            f"(覆盖{len(report.data_requirements)}类需求字段)"
        )
        lines.append(
            f"  ├ 准确性 {report.accuracy_score:.1f} "
            f"(矛盾{report.contradictions}条)"
        )
        lines.append(
            f"  └ 关系 {report.relation_score:.1f} "
            f"(通过{report.relation_passed}/失败{report.relation_failed}个约束)"
        )

        # 关系违规详情
        if report.relation_violations:
            for v in report.relation_violations[:2]:
                lines.append(f"     ⚠ {v.get('relation', '?')}: {v.get('detail', '')[:60]}")

        lines.append("")

        # ─── 科学方法 ───
        if report.sim_rounds > 0:
            conv = "✅ 已收敛" if report.sim_converged else "🔄 未收敛"
            integrity = "✅" if report.sim_integrity_passed else "⚠️"
            lines.append(f"**🔬 模拟验证**: {report.sim_rounds}轮, 最佳G={report.sim_best_score:.1f}, {conv}, 完整性{integrity}")
            lines.append("")

        # ─── 世界观对比 ───
        if report.has_contrast:
            lines.append(f"**⚖️ 世界观对比**: 已激活 (vs {report.contrast_wv})")
            lines.append("")

        # ─── 综合置信度 ───
        confidence_map = {
            "高": "🟢 高 — 多源交叉验证一致，关系约束全部通过",
            "中": "🟡 中 — 部分数据缺口或框架冲突，结论有保留",
            "低": "🔴 低 — 数据质量不足或关系断裂，结论仅供参考",
        }
        lines.append(f"**📊 综合置信度**: {confidence_map.get(report.overall_confidence, report.overall_confidence)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    @classmethod
    def build_annotation(cls, report: AssuranceReport) -> str:
        """构建保证面板的详细注释 — 逐层解释每个分数的含义。"""
        lines = []
        lines.append("## 📋 保证面板详细说明")
        lines.append("")

        # 世界观
        wv_descs = {
            "四神体系": "了了的原生世界观。研究从τ(天枢·信任锚)、φ(织星·系统间隔)、η(玄鉴·观测介入)展开。理论先行——公理→定理→推导→工程。盲点：纯主观体验不可达。",
            "现代货币理论 (MMT)": "主权货币政府不受税收约束。从部门平衡、功能性财政出发。盲点：外币债务国家、汇率危机。",
            "新古典经济学": "理性个体在约束下优化，市场趋向均衡。基于数学建模+计量验证。盲点：权力不对称、非线性临界点。",
            "法务实证": "数据不说谎——但人会。基于异常检测、统计指纹(Benford)、会计勾稽。盲点：异常≠舞弊。",
            "系统思维": "整体大于部分之和。关注涌现、反馈、相变。盲点：精确数值预测困难。",
            "科学经验主义": "可证伪+可重复=可靠知识。盲点：不可重复事件、意义维度。",
        }
        lines.append(f"**🌌 {report.worldview_name}**: {wv_descs.get(report.worldview_name, '')}")
        if report.worldview_blindspots:
            lines.append(f"  盲点: {', '.join(report.worldview_blindspots[:2])}")
        lines.append("")

        # 方法论
        method_descs = {
            "empirical": "实证研究——依赖真实世界数据，搜索+统计+交叉验证。适合'是什么'。局限性：数据可得性决定天花板。",
            "simulation": "模拟验证——假设→模拟→验证→改善循环。适合'最优是什么'。局限性：模型假设可能偏离现实。",
            "theoretical": "理论推演——从公理/定理出发逻辑推导。适合'为什么'。局限性：推理链越长累积误差越大。",
            "comparative": "对比分析——多假说并行验证+民主投票。适合'哪个更好'。局限性：假说质量决定结论上限。",
            "forensic": "法务检测——异常检测+统计指纹+会计勾稽。适合'是否可信'。局限性：异常≠舞弊，需因果推理。",
            "synthesis": "综合综述——多源融合+叙事构建+知识图谱。适合'全貌'。局限性：综合质量受单源质量制约。",
        }
        lines.append(f"**🧭 {report.method_name}**: {method_descs.get(report.method_name, '')}")
        lines.append("")

        # 四闸详解
        gate_passed = report.gate_score >= report.gate_threshold
        lines.append(f"**🔍 数据质量闸**: {'✅ 通过' if gate_passed else '❌ 阻断'} ({report.gate_score:.2f}/{report.gate_threshold})")
        lines.append("")

        # 真实性
        lines.append(f"  ① 真实性 {report.authenticity_score:.1f} — 织星φ分析({report.voyager_score:.1f}) + URL辅证")
        if report.voyager_score >= 0.7:
            lines.append("     数学指纹(Benford+熵场+模式)正常，数据在统计意义上可信")
        elif report.voyager_score >= 0.5:
            lines.append("     数学指纹基本正常，部分指标轻微偏离——建议关注偏离指标")
        else:
            lines.append("     数学指纹异常——数据可能经过人为编造或修改，请谨慎使用")
        if report.sources_count == 0:
            lines.append("     无URL来源——数据不可追溯复现")
        lines.append("")

        # 完整性
        lines.append(f"  ② 完整性 {report.completeness_score:.1f} — 方法所需数据库覆盖度")
        lines.append(f"     覆盖了{len(report.data_requirements)}类需求字段——缺失的每一类都可能改变结论")
        lines.append("")

        # 准确性
        lines.append(f"  ③ 准确性 {report.accuracy_score:.1f} — 交叉验证+时效+矛盾检测")
        if report.contradictions > 0:
            lines.append(f"     检测到{report.contradictions}条内部矛盾——不同来源/时间的数据互相冲突")
        else:
            lines.append("     未检测到明显矛盾")
        lines.append("")

        # 关系
        lines.append(f"  ④ 关系完整性 {report.relation_score:.1f} — 数学约束验证")
        lines.append(f"     {report.relation_passed}通过/{report.relation_failed}失败")
        if report.relation_failed > 0:
            lines.append("     ⚠ 关系断裂=前提错误——前提错则结论不可能对")
            for v in report.relation_violations[:2]:
                lines.append(f"     - {v.get('relation','?')}: {v.get('detail','')[:80]}")
        lines.append("")

        # 模拟
        if report.sim_rounds > 0:
            lines.append(f"**🔬 模拟验证**: {report.sim_rounds}轮, G={report.sim_best_score:.1f}, {'✅收敛' if report.sim_converged else '🔄未收敛'}")
            lines.append("")

        # 对比
        if report.has_contrast:
            lines.append(f"**⚖️ 世界观对比**: 已激活 vs {report.contrast_wv}——公理层差异可能导致完全不同的结论")
            lines.append("")

        # 综合置信度
        conf_map = {
            "高": "多源一致，关系全过——结论可作为决策参考（仍须注意世界观盲点）。",
            "中": "部分缺口或冲突——结论方向可靠，具体数值需保留。建议补充数据后使用。",
            "低": "数据不足或关系断裂——结论仅指示可能方向，不可作为决策依据。需重新收集数据。",
        }
        lines.append(f"**📊 综合置信度: {report.overall_confidence}** — {conf_map.get(report.overall_confidence, '')}")
        lines.append("")
        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    @classmethod
    def build_full(cls, report: AssuranceReport) -> str:
        """面板 + 详细注释。"""
        return f"{cls.build(report)}\n{cls.build_annotation(report)}"

    @classmethod
    def from_chat_context_full(
        cls,
        wv: dict,
        method: dict,
        gate_result,
        contrast: Optional[dict] = None,
        sim_result: Optional[dict] = None,
    ) -> str:
        """面板 + 详细注释。"""
        report = cls._build_report(wv, method, gate_result, contrast, sim_result)
        return cls.build_full(report)

    @classmethod
    def _build_report(
        cls,
        wv: dict,
        method: dict,
        gate_result,
        contrast: Optional[dict] = None,
        sim_result: Optional[dict] = None,
    ) -> AssuranceReport:
        """构建AssuranceReport数据对象。"""
        report = AssuranceReport()

        # 世界观
        report.worldview_name = wv.get("worldview_name", "")
        report.worldview_blindspots = [b[:30] for b in wv.get("blind_spots", [])]
        report.worldview_conflicts = wv.get("conflicts", [])

        # 方法论
        report.method_name = method.get("primary", "")
        report.method_reasoning = method.get("reasoning", "")
        report.data_requirements = method.get("data_requirements", [])

        # 数据质量闸
        report.gate_score = getattr(gate_result, "overall_score", 0)
        report.gate_threshold = method.get("quality_threshold", 0.6)
        report.authenticity_score = gate_result.authenticity.get("score", 0)
        report.voyager_score = gate_result.authenticity.get("voyager_score", 0)
        report.completeness_score = gate_result.completeness.get("score", 0)
        report.accuracy_score = gate_result.accuracy.get("score", 0)

        ri = getattr(gate_result, "relation_integrity", {})
        report.relation_score = ri.get("score", 0)
        report.relation_passed = ri.get("passed", 0)
        report.relation_failed = ri.get("failed", 0)
        report.relation_violations = ri.get("violations", [])

        report.sources_count = gate_result.authenticity.get("sources_found", 0)
        report.contradictions = gate_result.accuracy.get("contradiction_count", 0)

        # 科学方法
        if sim_result:
            report.sim_rounds = sim_result.get("rounds", 0)
            report.sim_best_score = sim_result.get("best_score", 0)
            report.sim_converged = sim_result.get("converged", False)

        # 世界观对比
        if contrast and not contrast.get("skip"):
            report.has_contrast = True
            report.contrast_wv = contrast.get("comparison_wv", "")

        # 综合置信度判定
        if report.gate_score >= report.gate_threshold and report.relation_failed == 0:
            report.overall_confidence = "高"
        elif report.gate_score >= 0.4:
            report.overall_confidence = "中"
        else:
            report.overall_confidence = "低"

        return report

    @classmethod
    def from_chat_context(
        cls,
        wv: dict,
        method: dict,
        gate_result,
        contrast: Optional[dict] = None,
        sim_result: Optional[dict] = None,
    ) -> str:
        """从 chat 流程中已有的数据快速构建保证面板（仅面板，不含注释）。"""
        report = cls._build_report(wv, method, gate_result, contrast, sim_result)
        return cls.build(report)


def assurance_panel(
    wv: dict,
    method: dict,
    gate_result,
    contrast: Optional[dict] = None,
    sim_result: Optional[dict] = None,
) -> str:
    """快捷生成保证面板。"""
    return AssurancePanel.from_chat_context(wv, method, gate_result, contrast, sim_result)


# ═══ 自检 ═══
if __name__ == "__main__":
    # 模拟 chat 流程中的数据
    mock_wv = {
        "worldview_name": "法务实证",
        "blind_spots": ["非数字化对象不可达", "可能滥用复杂性"],
        "conflicts": [{"name": "naive_empiricism"}],
    }
    mock_method = {
        "primary": "forensic",
        "reasoning": "检测到会计异常信号",
        "data_requirements": ["原始账本", "审计记录", "时序数据"],
        "quality_threshold": 0.7,
    }

    # 模拟 GateResult
    from data_gate import GateResult
    mock_gate = GateResult()
    mock_gate.overall_score = 0.58
    mock_gate.authenticity = {"score": 0.65, "voyager_score": 0.61, "sources_found": 2}
    mock_gate.completeness = {"score": 0.75, "found": ["原始账本", "时序数据"], "missing": ["审计记录"]}
    mock_gate.accuracy = {"score": 0.70, "contradiction_count": 4}
    mock_gate.relation_integrity = {
        "score": 0.50, "passed": 3, "failed": 1,
        "violations": [{"relation": "会计恒等式", "detail": "资产≠负债+权益"}],
    }

    mock_contrast = {"skip": False, "comparison_wv": "四神体系"}
    mock_sim = {"rounds": 2, "best_score": 7.42, "converged": True}

    panel = AssurancePanel.from_chat_context(
        mock_wv, mock_method, mock_gate, mock_contrast, mock_sim
    )
    print(panel)
