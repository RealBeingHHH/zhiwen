"""
多轮研究深化 — 了了主动追问澄清，迭代收敛

当数据缺口或矛盾被检测到时，了了不再只是报告"数据不足"，
而是主动追问用户具体的澄清问题，然后基于用户的回答重新运行管线。

模式:
  1. 检测到关键缺口 → 生成1-3个追问
  2. 问用户 → 用户回答 → 管线重跑
  3. 最多追问2轮 → 如果还不行 → 报告最佳已知结论

追问类型:
  - 数值矛盾: "资产200亿不等负债+权益，这是录入错误吗？"
  - 方法不适: "当前用empirical，但数据太散，换成simulation可以吗？"
  - 语义模糊: "你说的'效果'是指GDP增长还是通胀控制？"
  - 框架冲突: "当前走MMT框架，但你提到了新古典的假设，切换框架吗？"
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from voyager_llm import safe_llm_call as _llm_call


@dataclass
class ClarificationQuestion:
    """一个追问。"""
    question: str
    category: str       # 数值矛盾/方法选择/语义澄清/框架冲突
    options: list = field(default_factory=list)  # 可选答案
    impact: str = ""    # 这个答案会如何影响结论


class DeepRounds:
    """多轮研究深化 — 主动追问。"""

    MAX_ROUNDS = 2

    @classmethod
    def should_clarify(cls, gate_result, method: dict) -> bool:
        """判断是否需要追问用户。"""
        gate_score = getattr(gate_result, "overall_score", 1.0)
        threshold = method.get("quality_threshold", 0.6)

        # 质量闸阻断 + 有具体可问的东西 → 追问
        if gate_score < threshold:
            return True

        # 准确性特别低 → 追问
        acc = gate_result.accuracy.get("score", 1.0)
        if acc < 0.3:
            return True

        # 关系断裂 → 追问
        ri = getattr(gate_result, "relation_integrity", {})
        if isinstance(ri, dict) and ri.get("failed", 0) > 0:
            return True

        return False

    @classmethod
    def generate_questions(
        cls,
        query: str,
        gate_result,
        method: dict,
        wv: dict,
        data_text: str = "",
    ) -> list[ClarificationQuestion]:
        """
        基于当前研究状态生成追问。

        返回: 1-3个追问
        """
        gate_score = getattr(gate_result, "overall_score", 0)
        acc = gate_result.accuracy.get("score", 1.0)
        ri = getattr(gate_result, "relation_integrity", {})
        violations = ri.get("violations", []) if isinstance(ri, dict) else []

        system = f"""你是研究澄清专家。当前研究遇到数据质量问题，需要向用户追问。

研究状态:
- 质量闸: {gate_score:.2f} (阈值{method.get('quality_threshold', 0.6)})
- 准确性: {acc:.2f}
- 关系违规: {json.dumps(violations[:2], ensure_ascii=False) if violations else '无'}
- 世界观: {wv.get('worldview_name', '未知')}
- 方法: {method.get('primary', '未知')}

请生成1-3个追问，帮助澄清数据或方法论问题。
追问应该:
- 具体而非泛泛（不要问"你能提供更多数据吗"）
- 给用户选项，不只开放题
- 每个追问最后给出: [类型: 数值矛盾/方法选择/语义澄清/框架冲突]

输出格式（每行一个）:
追问1 | 类型 | 选项A,选项B,选项C"""

        try:
            result = _llm_call(system, query, max_tokens=250)
            if not result:
                return cls._fallback_questions(query, gate_result, method)

            questions = []
            for line in result.strip().split("\n"):
                parts = line.split("|")
                if len(parts) >= 2:
                    q = parts[0].strip()
                    cat = parts[1].strip() if len(parts) > 1 else "语义澄清"
                    opts = [o.strip() for o in parts[2].split(",")] if len(parts) > 2 else []
                    questions.append(ClarificationQuestion(
                        question=q, category=cat, options=opts,
                        impact="回答后系统将重新运行完整验证管线",
                    ))
            return questions[:3]
        except Exception:
            return cls._fallback_questions(query, gate_result, method)

    @classmethod
    def _fallback_questions(cls, query: str, gate_result, method: dict) -> list:
        """规则fallback追问。"""
        qs = []
        ri = getattr(gate_result, "relation_integrity", {})
        violations = ri.get("violations", []) if isinstance(ri, dict) else []

        if violations:
            v = violations[0]
            qs.append(ClarificationQuestion(
                question=f"检测到数据关系异常: {v.get('relation','?')}。这是录入错误还是特殊情况？",
                category="数值矛盾",
                options=["录入错误，我提供正确数字", "特殊情况，我解释原因"],
            ))

        if gate_result.accuracy.get("score", 1.0) < 0.4:
            qs.append(ClarificationQuestion(
                question="数据中存在较多内部矛盾。是否需要切换到其他研究方法（如模拟验证）？",
                category="方法选择",
                options=[f"换成simulation", f"保持{method.get('primary','empirical')}继续"],
            ))

        if not qs:
            qs.append(ClarificationQuestion(
                question="当前数据不足以得出可靠结论。你能提供更具体的数值来源吗？",
                category="语义澄清",
                options=["提供URL/文件", "我描述来源", "继续用现有数据"],
            ))

        return qs

    @classmethod
    def apply_clarification(
        cls,
        query: str,
        user_answer: str,
        original_data: str,
    ) -> str:
        """将用户的澄清回答合并入数据上下文，然后重新运行管线。"""
        return f"{original_data}\n\n[用户澄清]\n{user_answer}"


def should_clarify(gate_result, method: dict) -> bool:
    return DeepRounds.should_clarify(gate_result, method)


def generate_questions(query, gate_result, method, wv, data_text="") -> list:
    return DeepRounds.generate_questions(query, gate_result, method, wv, data_text)


# ═══ 自检 ═══
if __name__ == "__main__":
    from data_gate import GateResult
    gate = GateResult()
    gate.overall_score = 0.42
    gate.accuracy = {"score": 0.2, "contradiction_count": 5}
    gate.relation_integrity = {
        "score": 0.5, "passed": 0, "failed": 1,
        "violations": [{"relation": "会计恒等式", "detail": "资产≠负债+权益，差20亿"}],
    }

    if DeepRounds.should_clarify(gate, {"primary": "empirical", "quality_threshold": 0.6}):
        qs = DeepRounds.generate_questions(
            "资产200亿，负债150亿，权益30亿。可信吗？",
            gate, {"primary": "empirical", "quality_threshold": 0.6},
            {"worldview_name": "四神体系"},
        )
        for i, q in enumerate(qs):
            print(f"追问{i+1}: {q.question}")
            if q.options:
                print(f"  选项: {', '.join(q.options)}")
            print(f"  类型: {q.category}")
