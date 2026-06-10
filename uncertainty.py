"""
不确定性量化 — 从"中"到"0.62±0.08"

当前: 综合置信度 = 高/中/低（三档，无法比较两个结论的可信度差异）
目标: 每个闸门分数的误差贡献 → 加权传播 → 数值化置信区间

核心公式:
  总不确定性 σ_total = √( Σ w_i × (1 - s_i)² )
  其中 s_i = 闸i的分数 (0-1), w_i = 闸i的权重
  置信度 = 1 - σ_total

  最终结论值 = 标称值 ± (标称值 × σ_total)
"""

import math
from dataclasses import dataclass


@dataclass
class UncertaintyBounds:
    """不确定性量化结果。"""
    nominal_value: float = 0.0     # 标称值
    sigma: float = 0.0             # 标准不确定度
    lower_bound: float = 0.0       # 下界 (95%CI ≈ nominal - 2σ)
    upper_bound: float = 0.0       # 上界
    confidence: float = 0.0        # 置信度 (0-1)
    level: str = "中"             # 高/中/低
    breakdown: dict = None         # 各闸门的误差贡献


class UncertaintyPropagator:
    """
    不确定性传播器。
    
    将四个质量闸门的分数转换为数值化的不确定性边界。
    """

    # 各闸门的不确定性权重
    DEFAULT_WEIGHTS = {
        "authenticity": 0.30,    # 真实性
        "completeness": 0.20,    # 完整性
        "accuracy": 0.30,        # 准确性
        "relation": 0.20,        # 关系完整性
    }

    # 额外不确定性来源
    EXTRA_SOURCES = {
        "simulation_model": 0.05,   # 模型假设偏差
        "llm_reasoning": 0.08,      # LLM推理偏差
        "sampling": 0.03,           # 样本不足
    }

    @classmethod
    def quantify(
        cls,
        gate_result,
        nominal_value: float = 1.0,
        has_simulation: bool = False,
    ) -> UncertaintyBounds:
        """
        量化结论的不确定性。

        参数:
          gate_result: DataGate.check() 的结果
          nominal_value: 结论的标称值（如最优赤字率=0.15）
          has_simulation: 是否使用了模拟

        返回: UncertaintyBounds
        """
        auth = gate_result.authenticity.get("score", 0.5)
        comp = gate_result.completeness.get("score", 0.5)
        acc = gate_result.accuracy.get("score", 0.5)
        ri = getattr(gate_result, "relation_integrity", {})
        rel = ri.get("score", 0.5) if isinstance(ri, dict) else 0.5

        # ── 逐闸计算误差贡献 ──
        contributions = {}
        total_variance = 0

        # 真实性: 1 - score 是误差
        auth_err = 1.0 - auth
        contributions["真实性"] = {
            "score": auth,
            "error": round(auth_err, 3),
            "weight": cls.DEFAULT_WEIGHTS["authenticity"],
            "contribution": round(cls.DEFAULT_WEIGHTS["authenticity"] * auth_err ** 2, 4),
        }
        total_variance += contributions["真实性"]["contribution"]

        # 完整性
        comp_err = 1.0 - comp
        contributions["完整性"] = {
            "score": comp,
            "error": round(comp_err, 3),
            "weight": cls.DEFAULT_WEIGHTS["completeness"],
            "contribution": round(cls.DEFAULT_WEIGHTS["completeness"] * comp_err ** 2, 4),
        }
        total_variance += contributions["完整性"]["contribution"]

        # 准确性
        acc_err = 1.0 - acc
        contributions["准确性"] = {
            "score": acc,
            "error": round(acc_err, 3),
            "weight": cls.DEFAULT_WEIGHTS["accuracy"],
            "contribution": round(cls.DEFAULT_WEIGHTS["accuracy"] * acc_err ** 2, 4),
        }
        total_variance += contributions["准确性"]["contribution"]

        # 关系完整性
        rel_err = 1.0 - rel
        contributions["关系完整性"] = {
            "score": rel,
            "error": round(rel_err, 3),
            "weight": cls.DEFAULT_WEIGHTS["relation"],
            "contribution": round(cls.DEFAULT_WEIGHTS["relation"] * rel_err ** 2, 4),
        }
        total_variance += contributions["关系完整性"]["contribution"]

        # 额外来源
        if has_simulation:
            total_variance += cls.EXTRA_SOURCES["simulation_model"] ** 2
            contributions["模拟模型偏差"] = {
                "score": 1 - cls.EXTRA_SOURCES["simulation_model"],
                "error": cls.EXTRA_SOURCES["simulation_model"],
                "contribution": round(cls.EXTRA_SOURCES["simulation_model"] ** 2, 4),
            }

        total_variance += cls.EXTRA_SOURCES["llm_reasoning"] ** 2
        contributions["LLM推理偏差"] = {
            "score": 1 - cls.EXTRA_SOURCES["llm_reasoning"],
            "error": cls.EXTRA_SOURCES["llm_reasoning"],
            "contribution": round(cls.EXTRA_SOURCES["llm_reasoning"] ** 2, 4),
        }

        # ── 计算总不确定度 ──
        sigma = math.sqrt(total_variance)
        confidence = max(0.0, 1.0 - sigma)

        # 95% 置信区间
        lower = nominal_value * (1 - 2 * sigma)
        upper = nominal_value * (1 + 2 * sigma)

        # 置信度等级
        if confidence >= 0.8:
            level = "高"
        elif confidence >= 0.5:
            level = "中"
        else:
            level = "低"

        # ── 找出最大误差源 ──
        max_source = max(contributions.items(),
                        key=lambda kv: kv[1]["contribution"])

        return UncertaintyBounds(
            nominal_value=nominal_value,
            sigma=round(sigma, 4),
            lower_bound=round(lower, 4),
            upper_bound=round(upper, 4),
            confidence=round(confidence, 3),
            level=level,
            breakdown={
                "total_variance": round(total_variance, 5),
                "sigma": round(sigma, 4),
                "confidence": round(confidence, 3),
                "contributions": contributions,
                "max_error_source": max_source[0],
                "max_error_contribution": max_source[1]["contribution"],
            },
        )

    @classmethod
    def format_for_display(cls, bounds: UncertaintyBounds, label: str = "") -> str:
        """格式化为可读的置信区间字符串。"""
        if bounds.nominal_value == 1.0:
            # 无具体数值 → 只显示置信度
            return (f"{label}置信度 {bounds.confidence:.2f} "
                    f"(σ={bounds.sigma:.3f}, {bounds.level})")

        return (
            f"{label}{bounds.nominal_value:.3f} ± {bounds.sigma:.3f} "
            f"[{bounds.lower_bound:.3f}, {bounds.upper_bound:.3f}] "
            f"({bounds.level}置信度 {bounds.confidence:.2f})"
        )


def quantify_uncertainty(
    gate_result,
    nominal_value: float = 1.0,
    has_simulation: bool = False,
) -> UncertaintyBounds:
    """快捷不确定性量化。"""
    return UncertaintyPropagator.quantify(gate_result, nominal_value, has_simulation)


# ═══ 自检 ═══
if __name__ == "__main__":
    from data_gate import GateResult

    # 好数据
    gate_good = GateResult()
    gate_good.authenticity = {"score": 0.85, "voyager_score": 0.9, "sources_found": 3}
    gate_good.completeness = {"score": 0.80}
    gate_good.accuracy = {"score": 0.75}
    gate_good.relation_integrity = {"score": 0.70, "passed": 3, "failed": 0}

    bounds = UncertaintyPropagator.quantify(gate_good, nominal_value=0.15, has_simulation=True)
    print("=== 好数据: 赤字率最优值 ===")
    print(UncertaintyPropagator.format_for_display(bounds, "最优赤字率 = "))
    print(f"最大误差源: {bounds.breakdown['max_error_source']}")

    # 差数据
    gate_bad = GateResult()
    gate_bad.authenticity = {"score": 0.50}
    gate_bad.completeness = {"score": 0.40}
    gate_bad.accuracy = {"score": 0.20}
    gate_bad.relation_integrity = {"score": 0.50, "passed": 0, "failed": 2}

    bounds2 = UncertaintyPropagator.quantify(gate_bad, nominal_value=0.15, has_simulation=False)
    print("\n=== 差数据: 赤字率最优值 ===")
    print(UncertaintyPropagator.format_for_display(bounds2, "最优赤字率 = "))
    print(f"最大误差源: {bounds2.breakdown['max_error_source']}")
    print(f"σ={bounds2.sigma:.3f} — 不确定性是标称值的 {bounds2.sigma*100:.0f}%")
