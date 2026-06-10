"""
世界观对比层 — 研究第+1层：新旧框架方案全维度对比

在输出阶段：当检测到非四神体系的世界观时，自动生成与四神体系
的对比报告。对比维度:
  1. 方法论差别 — 研究路径如何不同
  2. 模拟验证差别 — 数值预测如何不同
  3. 最终结果差异 — 结论如何不同
  4. 差异根源 — 哪个公理冲突驱动了分歧

设计原则:
  - 四神体系始终作为基线（了了的原生世界观）
  - 不只说"哪里不同"，还说"哪里相同"——共识同样重要
  - 差异追溯到公理层——不满足于表面分歧
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent

from voyager_llm import safe_llm_call as _llm_call
from worldview import WORLDVIEWS


# ════════════════════════════════════════════════════════
# 对比引擎
# ════════════════════════════════════════════════════════

class WorldviewContrast:
    """世界观对比——输出层的对比报告生成器。"""

    BASELINE = "four_gods"  # 对比基线

    @classmethod
    def generate(
        cls,
        query: str,
        detected_wv: dict,
        method: dict,
        research_data: str = "",
        sim_result: Optional[dict] = None,
    ) -> dict:
        """
        生成世界观对比报告。

        参数:
          query: 原始问题
          detected_wv: worldview.detect() 结果
          method: method_router.route() 结果
          research_data: 搜索/深度研究收集的数据
          sim_result: 科学方法模拟结果（如有）

        返回:
          {
            "baseline": "四神体系",
            "comparison_wv": str,
            "same_points": [str],       # 共识点
            "method_diff": str,          # 方法论差别
            "sim_diff": str,             # 模拟验证差别
            "result_diff": str,          # 结果差异
            "root_cause": str,           # 差异根源（公理级）
            "full_report": str,          # 完整报告文本（注入LLM）
          }
        """
        wv_key = detected_wv.get("worldview_key", "")
        wv_name = detected_wv.get("worldview_name", "")

        # 如果是四神体系本身，不需要对比
        if wv_key == cls.BASELINE:
            return {
                "baseline": "四神体系",
                "comparison_wv": wv_name,
                "same_points": [],
                "method_diff": "",
                "sim_diff": "",
                "result_diff": "",
                "root_cause": "",
                "full_report": "",
                "skip": True,
                "reason": "已在四神体系框架内，无需跨框架对比",
            }

        baseline_wv = WORLDVIEWS.get(cls.BASELINE)
        comparison_wv = WORLDVIEWS.get(wv_key)

        if not baseline_wv or not comparison_wv:
            return cls._empty_result(wv_name)

        # ─── 规则对比: 方法偏好差异 ───
        method_diff = cls._compare_methods(baseline_wv, comparison_wv, method)

        # ─── 规则对比: 模拟验证差异 ───
        sim_diff = cls._compare_simulation(baseline_wv, comparison_wv, sim_result)

        # ─── LLM对比: 结果差异 + 根源分析 ───
        llm_contrast = cls._llm_contrast(
            query, baseline_wv, comparison_wv,
            research_data, sim_result, method_diff, sim_diff
        )

        # ─── 构建完整报告 ───
        full_report = cls._build_report(
            baseline_wv, comparison_wv,
            method_diff, sim_diff, llm_contrast
        )

        return {
            "baseline": baseline_wv.name,
            "comparison_wv": comparison_wv.name,
            "same_points": llm_contrast.get("same_points", []),
            "method_diff": method_diff,
            "sim_diff": sim_diff,
            "result_diff": llm_contrast.get("result_diff", ""),
            "root_cause": llm_contrast.get("root_cause", ""),
            "full_report": full_report,
            "skip": False,
        }

    @classmethod
    def _compare_methods(cls, baseline_wv, comparison_wv, method: dict) -> str:
        """对比两个世界观的方法论偏好。"""
        b_methods = set(baseline_wv.favored_methods)
        c_methods = set(comparison_wv.favored_methods)
        common = b_methods & c_methods
        only_b = b_methods - c_methods
        only_c = c_methods - b_methods

        parts = []
        parts.append(f"方法论偏好对比:")
        parts.append(f"  四神体系偏好: {', '.join(baseline_wv.favored_methods)}")
        parts.append(f"  {comparison_wv.name}偏好: {', '.join(comparison_wv.favored_methods)}")

        if common:
            parts.append(f"  共识方法: {', '.join(common)}")
        if only_b:
            parts.append(f"  四神独有: {', '.join(only_b)} (理论推演+模拟) 偏向从公理推导+数值验证")
        if only_c:
            parts.append(f"  {comparison_wv.name}独有: {', '.join(only_c)}")

        # 实际采用的方法
        actual_method = method.get("primary", "unknown")
        parts.append(f"  本轮实际采用: {actual_method} ({method.get('reasoning', '')[:60]}...)")

        return "\n".join(parts)

    @classmethod
    def _compare_simulation(cls, baseline_wv, comparison_wv, sim_result: Optional[dict]) -> str:
        """对比模拟验证差异。"""
        if not sim_result:
            return "本轮未进行模拟验证，无法对比。"

        # 检查是否有对比数据
        traj = sim_result.get("trajectory", [])
        conclusion = sim_result.get("conclusion", "")

        parts = []
        parts.append("模拟验证对比:")

        # 注意：当前模拟是在 scientific method 下运行的，使用的是四神体系的参数框架
        # 如果需要在不同世界观下运行不同模拟，这里需要扩展 sim_adapter
        parts.append(
            f"  注意: 当前模拟使用四神体系参数框架 (fiscal_sim)。"
            f"{comparison_wv.name}可能需要不同的模拟模型——"
            f"例如新古典会引入理性预期变量、自然失业率约束。"
        )
        parts.append(f"  当前模拟结果 (四神框架): 最佳G={sim_result.get('best_score', '?')}")
        if traj:
            parts.append(f"  演化轮次: {len(traj)}轮, 收敛={sim_result.get('converged', '?')}")

        return "\n".join(parts)

    @classmethod
    def _llm_contrast(
        cls,
        query: str,
        baseline_wv,
        comparison_wv,
        research_data: str,
        sim_result: Optional[dict],
        method_diff: str,
        sim_diff: str,
    ) -> dict:
        """LLM深度对比分析。"""
        system = f"""你是世界观对比分析专家。比较两个框架对同一问题的不同回答。

基准框架 ({baseline_wv.name}):
  公理: {', '.join(baseline_wv.axioms[:3])}
  认识论: {baseline_wv.epistemology[:100]}

对比框架 ({comparison_wv.name}):
  公理: {', '.join(comparison_wv.axioms[:3])}
  认识论: {comparison_wv.epistemology[:100]}

{method_diff}

{sim_diff}

研究数据:
{research_data[:1500] if research_data else '无'}

请输出JSON:
{{
  "same_points": ["共识1", "共识2"],
  "result_diff": "两个框架的结论差异（2-3句）",
  "root_cause": "差异的根源——是哪个公理的不同导致了结论分歧（2-3句）"
}}

只输出JSON。"""

        try:
            result = _llm_call(system, query, max_tokens=400)
            if not result:
                return {"same_points": [], "result_diff": "", "root_cause": ""}
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
                if result.endswith("```"):
                    result = result.rsplit("\n```", 1)[0]
            data = json.loads(result)
            return {
                "same_points": data.get("same_points", []),
                "result_diff": data.get("result_diff", ""),
                "root_cause": data.get("root_cause", ""),
            }
        except Exception:
            return {"same_points": [], "result_diff": "", "root_cause": ""}

    @classmethod
    def _build_report(
        cls, baseline_wv, comparison_wv,
        method_diff: str, sim_diff: str, llm_contrast: dict
    ) -> str:
        """构建完整对比报告。"""
        parts = []

        parts.append(f"[⚖️ 世界观对比: {comparison_wv.name} vs {baseline_wv.name} (四神基线)]")
        parts.append("")

        # 共识
        same = llm_contrast.get("same_points", [])
        if same:
            parts.append("✅ 共识点（两框架一致）:")
            for s in same:
                parts.append(f"  · {s}")
            parts.append("")

        # 方法差别
        parts.append(f"📐 方法论差别:")
        parts.append(method_diff)
        parts.append("")

        # 模拟验证差别
        parts.append(f"🔬 模拟验证差别:")
        parts.append(sim_diff)
        parts.append("")

        # 结果差异
        result_diff = llm_contrast.get("result_diff", "")
        if result_diff:
            parts.append(f"📊 最终结果差异:")
            parts.append(f"  {result_diff}")
            parts.append("")

        # 根源
        root = llm_contrast.get("root_cause", "")
        if root:
            parts.append(f"🧬 差异根源（公理级）:")
            parts.append(f"  {root}")
            parts.append("")

        parts.append(
            f"请基于以上对比，在{comparison_wv.name}框架内回答用户问题，"
            f"同时标注如果切换回四神体系，结论会如何变化。"
        )

        return "\n".join(parts)

    @classmethod
    def _empty_result(cls, wv_name: str) -> dict:
        return {
            "baseline": "四神体系",
            "comparison_wv": wv_name,
            "same_points": [],
            "method_diff": "",
            "sim_diff": "",
            "result_diff": "",
            "root_cause": "",
            "full_report": "",
            "skip": True,
            "reason": "世界观未在已知框架中",
        }


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def worldview_contrast(
    query: str,
    detected_wv: dict,
    method: dict,
    research_data: str = "",
    sim_result: Optional[dict] = None,
) -> dict:
    """生成世界观对比报告。"""
    return WorldviewContrast.generate(
        query, detected_wv, method, research_data, sim_result
    )


# ═══ 自检 ═══
if __name__ == "__main__":
    from worldview import WorldviewLayer
    from method_router import MethodRouter

    # 场景1: MMT查询
    query1 = "MMT框架下最优赤字率是多少"
    wv1 = WorldviewLayer.detect(query1)
    method1 = MethodRouter.route(query1)

    contrast1 = WorldviewContrast.generate(
        query1, wv1, method1,
        research_data="赤字率与GDP增长呈正相关，2024年数据...",
        sim_result={"best_score": 7.42, "trajectory": [{"round": 1, "G_score": 7.42}], "converged": True},
    )
    print(f"=== MMT vs 四神 ===")
    print(f"跳过: {contrast1.get('skip')}")
    if not contrast1.get('skip'):
        print(contrast1["full_report"][:500])

    # 场景2: 四神查询（应该跳过对比）
    query2 = "从天枢的视角看，这个数据可信吗"
    wv2 = WorldviewLayer.detect(query2)
    contrast2 = WorldviewContrast.generate(query2, wv2, {"primary": "empirical"})
    print(f"\n=== 四神 (应跳过) ===")
    print(f"跳过: {contrast2.get('skip')}, 理由: {contrast2.get('reason')}")
