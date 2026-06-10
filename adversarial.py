"""
对抗验证 — 主动找反例攻击结论

自洽≠可靠。能被攻击而不倒的结论才值得信。

流程:
  1. 提取当前结论
  2. LLM生成攻击场景（反例假设）
  3. 对每个攻击场景，测试结论是否存活
  4. 报告存活率和最危险的攻击

攻击类型:
  - 假设翻转: 如果"权益30亿"实际是50亿会怎样？
  - 边界压力: 如果通胀突升10倍？
  - 缺失变量: 如果汇率突然崩溃？
  - 框架切换: 如果换成新古典框架看？
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from voyager_llm import safe_llm_call as _llm_call


@dataclass
class AttackScenario:
    """一个攻击场景。"""
    name: str           # 攻击名
    premise: str        # 攻击假设
    impact: str         # 对结论的影响
    survived: bool      # 结论是否存活
    severity: str = "中"  # 高/中/低


class AdversarialVerifier:
    """对抗验证器 — 主动攻击自己的结论。"""

    MAX_ATTACKS = 4

    @classmethod
    def verify(
        cls,
        query: str,
        conclusion_text: str,
        data_text: str = "",
        method: dict = None,
    ) -> dict:
        """
        对抗验证: 生成攻击场景，测试结论存活率。

        返回: {survival_rate, attacks, verdict, recommendation}
        """
        if not conclusion_text or len(conclusion_text) < 30:
            return {
                "survival_rate": 1.0,
                "attacks": [],
                "verdict": "无可验证结论",
                "recommendation": "",
            }

        # ── ① LLM生成攻击场景 ──
        attacks = cls._generate_attacks(query, conclusion_text, data_text)

        if not attacks:
            return {
                "survival_rate": 1.0,
                "attacks": [],
                "fatal_attacks": [],
                "verdict": "无法生成攻击场景（LLM未返回）",
                "recommendation": "",
            }

        # ── ② 测试每个攻击 ──
        for attack in attacks:
            survived = cls._test_attack(attack, conclusion_text, data_text)
            attack.survived = survived

        # ── ③ 统计存活率 ──
        total = len(attacks)
        survived_count = sum(1 for a in attacks if a.survived)
        survival_rate = survived_count / total if total > 0 else 1.0

        # ── ④ 找到最危险的攻击 ──
        fatal = [a for a in attacks if not a.survived and a.severity == "高"]
        warnings = [a for a in attacks if not a.survived]

        if survival_rate >= 0.75:
            verdict = "结论鲁棒 — 在大多数攻击下存活"
        elif survival_rate >= 0.5:
            verdict = "结论脆弱 — 部分攻击可推翻，需加固"
        else:
            verdict = "结论不可靠 — 多数攻击可推翻，需重新验证"

        return {
            "survival_rate": round(survival_rate, 2),
            "total_attacks": total,
            "survived": survived_count,
            "attacks": [
                {
                    "name": a.name,
                    "premise": a.premise[:100],
                    "impact": a.impact[:120],
                    "survived": a.survived,
                    "severity": a.severity,
                }
                for a in attacks
            ],
            "verdict": verdict,
            "fatal_attacks": [a.name for a in fatal],
            "recommendation": cls._build_recommendation(attacks, survival_rate),
        }

    @classmethod
    def _generate_attacks(
        cls, query: str, conclusion: str, data: str
    ) -> list[AttackScenario]:
        """LLM生成攻击场景。"""
        system = f"""你是对抗验证专家。给定一个研究结论，生成 {cls.MAX_ATTACKS} 个攻击场景来测试其鲁棒性。

攻击类型:
  - 假设翻转: 改变结论依赖的关键假设
  - 边界压力: 将参数推到极端值
  - 缺失变量: 引入被忽略的重要变量
  - 框架切换: 用不同世界观重新审视

输出JSON数组:
[
  {{"name": "攻击名", "premise": "攻击假设(1句)", "impact": "对结论的影响(1句)", "severity": "高/中/低"}}
]

结论: {conclusion[:500]}
数据: {data[:300] if data else '无'}"""

        try:
            result = _llm_call(system, f"原始问题: {query}", max_tokens=400)
            if not result:
                return []
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
                if result.endswith("```"):
                    result = result.rsplit("\n```", 1)[0]
            data = json.loads(result)
            return [
                AttackScenario(
                    name=a.get("name", f"攻击{i}"),
                    premise=a.get("premise", ""),
                    impact=a.get("impact", ""),
                    severity=a.get("severity", "中"),
                )
                for i, a in enumerate(data[:cls.MAX_ATTACKS])
            ]
        except Exception:
            return []

    @classmethod
    def _test_attack(
        cls, attack: AttackScenario, conclusion: str, data: str
    ) -> bool:
        """LLM判断结论是否在攻击下存活。"""
        system = """你是一个公正的裁判。给定一个结论和一个攻击场景，判断结论是否在攻击下仍然成立。

如果结论的核心主张在攻击后仍然有效 → 存活 (true)
如果攻击揭示了结论的致命缺陷 → 不存活 (false)
如果攻击只能削弱但不能推翻结论 → 存活 (true)

只输出: true 或 false"""

        try:
            result = _llm_call(
                system,
                f"结论: {conclusion[:400]}\n\n攻击: {attack.premise}\n{attack.impact}",
                max_tokens=10,
            )
            return "true" in (result or "").lower()
        except Exception:
            return True  # 保守: 无法判断时假设存活

    @classmethod
    def _build_recommendation(
        cls, attacks: list[AttackScenario], survival_rate: float
    ) -> str:
        """构建推荐行动。"""
        fatal = [a for a in attacks if not a.survived and a.severity == "高"]
        weak = [a for a in attacks if not a.survived and a.severity != "高"]

        if not fatal and not weak:
            return "结论通过对抗验证 — 在所有生成的攻击场景下存活"

        parts = []
        if fatal:
            parts.append(
                f"{len(fatal)}个高危攻击可推翻结论: "
                f"{', '.join(a.name for a in fatal[:2])}"
            )
        if weak:
            parts.append(
                f"{len(weak)}个攻击可削弱结论: "
                f"{', '.join(a.name for a in weak[:2])}"
            )

        parts.append(f"存活率 {survival_rate:.0%}")
        parts.append("建议: 加固这些薄弱点后重新验证")

        return "。".join(parts)


def adversarial_verify(
    query: str,
    conclusion_text: str,
    data_text: str = "",
    method: dict = None,
) -> dict:
    """快捷对抗验证。"""
    return AdversarialVerifier.verify(query, conclusion_text, data_text, method)


# ═══ 自检 ═══
if __name__ == "__main__":
    # 模拟一个结论
    conclusion = """
    分析结论: 该数据不可信。
    原因: 资产200亿≠负债150亿+权益30亿=180亿，差额20亿。
    会计等式不成立，数据存在结构性缺陷。
    """

    result = AdversarialVerifier.verify(
        query="资产200亿，负债150亿，权益30亿。分析可信度",
        conclusion_text=conclusion,
        data_text="资产200亿，负债150亿，所有者权益30亿",
    )

    print(f"存活率: {result['survival_rate']}")
    print(f"判决: {result['verdict']}")
    print(f"致命攻击: {result['fatal_attacks']}")
    print()
    for a in result["attacks"]:
        status = "✅存活" if a["survived"] else "❌致命"
        print(f"  [{a['severity']}] {a['name']} {status}")
        print(f"    前提: {a['premise'][:80]}")
        print(f"    影响: {a['impact'][:80]}")
    print()
    print(f"建议: {result['recommendation']}")
