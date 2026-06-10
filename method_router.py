"""
方法论路由器 — 研究方向决定器

在深化研究之前，先回答"用什么方法研究"。
问题 → 方法分配 → 数据需求清单

方法类型:
  empirical    — 需要真实世界数据 → 搜索+验证
  simulation   — 可建模系统 → 科学方法（假设→模拟→验证）
  theoretical  — 概念/定义推演 → 深度研究+理论拆解
  comparative  — 对比分析 → 竞争假说+交叉验证
  forensic     — 舞弊检测 → 法务会计+异常检测
  synthesis    — 综合综述 → 多源融合+叙事构建
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent

from voyager_llm import safe_llm_call as _llm_call


# ════════════════════════════════════════════════════════
# 方法定义
# ════════════════════════════════════════════════════════

@dataclass
class Methodology:
    """一种研究方法及其数据需求。"""
    name: str               # 方法名
    description: str        # 一句话说明
    data_requirements: list[str]  # 需要的数据库类型
    quality_threshold: float = 0.5  # 数据质量最低分（低于此分阻断）
    tools: list[str] = field(default_factory=list)  # 对应工具链

# 方法库
METHODOLOGIES = {
    "empirical": Methodology(
        name="实证研究",
        description="基于真实世界数据，通过搜索、统计、交叉验证得出结论",
        data_requirements=["统计数据", "官方报告", "学术论文", "时效性数据"],
        quality_threshold=0.6,
        tools=["search_web", "meta_search", "analyze", "reader"],
    ),
    "simulation": Methodology(
        name="模拟验证",
        description="构建可计算模型，通过假设→模拟→验证→改善循环探索最优解",
        data_requirements=["参数空间", "初始条件", "历史校准数据"],
        quality_threshold=0.5,
        tools=["sci_method", "fiscal_sim", "sim_adapter"],
    ),
    "theoretical": Methodology(
        name="理论推演",
        description="从公理/定理出发，进行逻辑推导和概念分析",
        data_requirements=["定义", "公理", "已有理论框架"],
        quality_threshold=0.4,
        tools=["deep_research", "decompose_query"],
    ),
    "comparative": Methodology(
        name="对比分析",
        description="生成多个互斥假说，并行验证，民主投票选最优",
        data_requirements=["对照组数据", "竞争性解释", "差异指标"],
        quality_threshold=0.6,
        tools=["competing_hypotheses", "deep_research", "analyze"],
    ),
    "forensic": Methodology(
        name="法务检测",
        description="检测数据操纵、会计异常、矛盾信号",
        data_requirements=["原始账本", "审计记录", "时序数据"],
        quality_threshold=0.7,
        tools=["forensic_accounting", "analyze"],
    ),
    "synthesis": Methodology(
        name="综合综述",
        description="多源信息融合，构建完整叙事和知识图谱",
        data_requirements=["多源文献", "历史脉络", "不同视角"],
        quality_threshold=0.5,
        tools=["deep_research", "evo_research", "synthesis"],
    ),
}


# ════════════════════════════════════════════════════════
# 路由器
# ════════════════════════════════════════════════════════

class MethodRouter:
    """问题 → 方法分配 + 数据需求清单"""

    # 方法路由缓存: 60秒内相同哈希的查询复用结果
    _cache: dict = {}
    _cache_ttl: float = 60.0

    @staticmethod
    def route(query: str) -> dict:
        """
        分析问题，分配研究方法，输出数据需求。

        返回:
          {
            "primary": str,          # 主方法名
            "secondary": [str],      # 辅助方法
            "reasoning": str,        # 分配理由
            "data_requirements": [], # 数据需求清单
            "quality_threshold": float, # 最低质量要求
            "tools": [str],          # 工具链
            "confidence": float,     # 方法分配置信度
          }
        """
        # 缓存检查: 相同查询60秒内复用
        import hashlib, time
        qhash = hashlib.md5(query.encode()).hexdigest()[:12]
        cached = MethodRouter._cache.get(qhash)
        if cached and (time.time() - cached["ts"]) < MethodRouter._cache_ttl:
            return cached["result"]

        # 先用规则快速匹配，再用LLM精化
        rule_match = MethodRouter._rule_based(query)

        # 高置信度规则匹配 → 跳过LLM (节省2s)
        if rule_match.get("confidence", 0) > 0.8:
            MethodRouter._cache[qhash] = {"ts": time.time(), "result": rule_match}
            return rule_match

        # LLM精化
        llm_match = MethodRouter._llm_refine(query, rule_match)
        result = llm_match if llm_match else rule_match
        
        MethodRouter._cache[qhash] = {"ts": time.time(), "result": result}
        return result

    @staticmethod
    def _rule_based(query: str) -> dict:
        """基于规则的快速方法匹配。"""
        q = query

        # 法务检测词
        forensic_kw = ["造假", "操纵", "舞弊", "异常", "粉饰", "做账", "假账"]
        if any(k in q for k in forensic_kw):
            return MethodRouter._build_result("forensic", "检测到法务/异常信号",
                ["原始账本", "审计记录", "时序数据"])

        # 模拟友好词
        sim_kw = ["模拟", "仿真", "演化", "优化", "最优", "改善方案"]
        if sum(1 for k in sim_kw if k in q) >= 2:
            return MethodRouter._build_result("simulation", "检测到优化/模拟需求",
                ["参数空间", "初始条件", "历史校准数据"])

        # 对比词
        comp_kw = ["对比", "比较", "哪个更", "哪个好", "区别", "选择"]
        if sum(1 for k in comp_kw if k in q) >= 2:
            return MethodRouter._build_result("comparative", "检测到对比/选择需求",
                ["对照组数据", "竞争性解释", "差异指标"])

        # 理论词
        theory_kw = ["定义", "什么是", "概念", "原理", "理论", "推导", "证明"]
        if any(k in q for k in theory_kw):
            return MethodRouter._build_result("theoretical", "检测到概念/理论需求",
                ["定义", "公理", "已有理论框架"])

        # 综合综述
        syn_kw = ["综述", "总结", "梳理", "全貌", "全景", "脉络"]
        if any(k in q for k in syn_kw):
            return MethodRouter._build_result("synthesis", "检测到综合综述需求",
                ["多源文献", "历史脉络", "不同视角"])

        # 默认：实证研究（大多数事实型问题）
        return MethodRouter._build_result("empirical", "默认实证研究路径",
            ["统计数据", "官方报告", "学术论文", "时效性数据"])

    @staticmethod
    def _llm_refine(query: str, rule_match: dict) -> Optional[dict]:
        """LLM精化方法分配。"""
        methods_desc = "\n".join([
            f"- {name}: {m.description}" for name, m in METHODOLOGIES.items()
        ])

        system = f"""你是研究方法论专家。根据问题，从以下方法中选择最合适的主方法+辅助方法。

可用方法：
{methods_desc}

当前规则匹配：{rule_match['primary']}
理由：{rule_match['reasoning']}

请输出JSON：
{{
  "primary": "方法名",
  "secondary": ["辅助方法"],
  "reasoning": "选择理由（1-2句）",
  "data_requirements": ["数据库1", "数据库2", ...],
  "confidence": 0.0-1.0
}}

只输出JSON，不要解释。"""

        try:
            result = _llm_call(system, query, max_tokens=300)
            if not result:
                return None
            # 清理可能的markdown包裹
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
                if result.endswith("```"):
                    result = result.rsplit("\n```", 1)[0]
            data = json.loads(result)

            llm_primary = data.get("primary", rule_match["primary"])
            if llm_primary not in METHODOLOGIES:
                llm_primary = rule_match["primary"]

            method = METHODOLOGIES[llm_primary]
            return {
                "primary": llm_primary,
                "secondary": data.get("secondary", []),
                "reasoning": data.get("reasoning", rule_match["reasoning"]),
                "data_requirements": data.get("data_requirements", method.data_requirements),
                "quality_threshold": method.quality_threshold,
                "tools": method.tools,
                "confidence": data.get("confidence", 0.7),
                "llm_refined": True,
            }
        except Exception:
            return None

    @staticmethod
    def _build_result(method_name: str, reasoning: str, data_reqs: list) -> dict:
        method = METHODOLOGIES[method_name]
        return {
            "primary": method_name,
            "secondary": [],
            "reasoning": reasoning,
            "data_requirements": data_reqs,
            "quality_threshold": method.quality_threshold,
            "tools": method.tools,
            "confidence": 0.8,
            "llm_refined": False,
            "method_description": method.description,
        }


def route_methodology(query: str) -> dict:
    """快捷方法路由。"""
    return MethodRouter.route(query)


# ═══ 自检 ═══
if __name__ == "__main__":
    test_queries = [
        "MMT框架下最优赤字率是多少",
        "比较扩张性财政和紧缩性财政哪个更有效",
        "什么是现代货币理论的核心定义",
        "某公司财务报表是否存在利润操纵",
        "梳理中国财政政策的历史演变",
    ]
    for q in test_queries:
        result = MethodRouter.route(q)
        print(f"\n问题: {q[:60]}")
        print(f"  方法: {result['primary']} ({result['reasoning'][:60]})")
        print(f"  数据需求: {result['data_requirements']}")
        print(f"  质量阈值: {result['quality_threshold']}")
        print(f"  置信度: {result['confidence']}")
