"""
织星系统深度接入 · 了了之手
将 Voyager 的世界模型 + 专家面板 + 梯度系统 接入深度研究
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

VOYAGER_PATH = "/mnt/d/hermes-webui/workspace/voyager"
sys.path.insert(0, VOYAGER_PATH)


# ═══ 专家面板 ═══
EXPERT_TEAMS = {
    "投资委员会": {"weight": 15, "domain": "决策", "prompt": "综合所有分析后给出最终评分"},
    "技术分析部": {"weight": 8, "domain": "技术面", "prompt": "从K线/均线/缠论角度分析"},
    "基本面研究部": {"weight": 8, "domain": "基本面", "prompt": "从财报/估值角度评估"},
    "宏观策略部": {"weight": 7, "domain": "宏观", "prompt": "从货币政策/经济周期评估"},
    "量化研究部": {"weight": 7, "domain": "量化", "prompt": "从因子模型/统计套利评分"},
    "风险管理部": {"weight": 6, "domain": "风控", "prompt": "从VaR/压力测试评估"},
    "行业科技组": {"weight": 5, "domain": "行业", "prompt": "从TMT/半导体景气度评估"},
    "行业消费组": {"weight": 5, "domain": "行业", "prompt": "从食品饮料/家电角度评估"},
    "行业金融组": {"weight": 5, "domain": "行业", "prompt": "从银行/保险经营角度评估"},
    "行业医药组": {"weight": 5, "domain": "行业", "prompt": "从创新药/器械政策评估"},
    "行业能源组": {"weight": 5, "domain": "行业", "prompt": "从新能源供需角度评估"},
    "行业制造组": {"weight": 5, "domain": "行业", "prompt": "从汽车/机械景气度评估"},
    "数据工程组": {"weight": 4, "domain": "数据", "prompt": "从数据质量/完整性评估"},
    "安全审计组": {"weight": 4, "domain": "安全", "prompt": "从系统安全/合规评估"},
    "运维保障组": {"weight": 3, "domain": "运维", "prompt": "从服务稳定性评估"},
    "法律合规组": {"weight": 3, "domain": "合规", "prompt": "从法规合规/信披评估"},
    "用户体验组": {"weight": 3, "domain": "产品", "prompt": "从用户需求/交互评估"},
    "市场情报组": {"weight": 3, "domain": "情报", "prompt": "从竞品动态/趋势评估"},
    "培训赋能组": {"weight": 2, "domain": "培训", "prompt": "从知识传承角度评估"},
}


def decompose_via_experts(query: str) -> list:
    """
    通过织星专家面板拆解问题。
    每个专家从自己的领域角度提出一个子问题。
    权重高的专家优先。
    """
    # 选Top N高权重专家
    sorted_teams = sorted(EXPERT_TEAMS.items(), key=lambda x: x[1]["weight"], reverse=True)
    top_teams = sorted_teams[:8]  # Top 8 experts

    # 构建分解prompt
    team_descriptions = "\n".join([
        f"- {name}（{info['domain']}）：{info['prompt']}"
        for name, info in top_teams
    ])

    system = f"""你是问题分解协调员。以下是织星者专家团队的各个部门及其视角：

{team_descriptions}

请从最重要的3-5个部门视角出发，将用户问题拆解为独立的子问题。
每个子问题对应一个部门的专业视角。
输出格式（每行一个）：子问题（部门名）"""

    from voyager_llm import safe_llm_call as _llm_call
    result = _llm_call(system, query, max_tokens=300)
    if not result:
        return None

    sub_queries = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if line and len(line) > 5:
            # 提取（部门名）
            import re
            dept_match = re.search(r'[（(]([^）)]+)[）)]', line)
            dept = dept_match.group(1) if dept_match else "综合"
            clean = re.sub(r'[（(][^）)]*[）)]', '', line).strip()
            clean = re.sub(r'^[\d\.\、\)\s]+', '', clean).strip()
            if clean:
                sub_queries.append({
                    "query": clean,
                    "department": dept,
                    "weight": EXPERT_TEAMS.get(dept, {}).get("weight", 5),
                })

    return sub_queries if sub_queries else None


# ═══ 梯度系统 ═══
def grade_sub_results(sub_results: list) -> list:
    """
    用织星梯度系统对子结果评分。
    G = w1*E + w2*S + w3*Q + w4*(1-Sim)
    
    E(效率) = 1.0 - time/30          (30秒内满分)
    S(稳定) = source可靠性分数
    Q(创造) = 结果长度/200           (越长越有内容)
    Sim(相似) = 0 (独立子问题)
    """
    DEFAULT_WEIGHTS = {"w_efficiency": 0.5, "w_stability": 0.2, "w_creativity": 0.15, "w_diversity": 0.15}

    # Source reliability scores
    SOURCE_SCORES = {
        "专业API": 0.9,
        "通用搜索": 0.7,
        "LLM知识": 0.4,
    }

    for sr in sub_results:
        # E: efficiency
        time_taken = sr.get("time", 30)
        E = max(0, 1.0 - time_taken / 30)

        # S: stability (source reliability)
        source = sr.get("source", "LLM知识")
        S = SOURCE_SCORES.get(source, 0.5)

        # Q: creativity (content richness)
        result_len = len(sr.get("result", ""))
        Q = min(1.0, result_len / 200)

        # Sim: similarity (assume independent = 0)
        Sim = 0.0

        # G = weighted sum
        G = (
            DEFAULT_WEIGHTS["w_efficiency"] * E
            + DEFAULT_WEIGHTS["w_stability"] * S
            + DEFAULT_WEIGHTS["w_creativity"] * Q
            + DEFAULT_WEIGHTS["w_diversity"] * (1 - Sim)
        ) * 10  # Scale to 0-10

        # Grade
        if G >= 8.0:
            grade = "S-顶尖"
        elif G >= 6.0:
            grade = "A-优秀"
        elif G >= 4.0:
            grade = "B-合格"
        elif G >= 2.0:
            grade = "C-待优化"
        else:
            grade = "D-劣质"

        sr["grade"] = grade
        sr["G_score"] = round(G, 2)

    # Sort by G-score descending
    sub_results.sort(key=lambda x: x.get("G_score", 0), reverse=True)
    return sub_results


# ═══ 熵场 ═══
def measure_entropy(sub_results: list) -> dict:
    """
    测量研究结果的"认知熵"。
    低φ = 结果一致、可信任
    高φ = 结果混乱、需要更多搜索
    """
    if len(sub_results) < 2:
        return {"phi": 0.3, "phase": "有序", "recommendation": "结果充分"}

    # 简单熵估计：结果之间的变异度
    sources = [sr.get("source", "") for sr in sub_results]
    unique_sources = len(set(sources))
    source_entropy = unique_sources / len(sources)  # 0=全同源, 1=全不同源

    grades = [sr.get("G_score", 5) for sr in sub_results]
    if len(grades) >= 2:
        avg = sum(grades) / len(grades)
        variance = sum((g - avg) ** 2 for g in grades) / len(grades)
        grade_entropy = min(1.0, variance / 10)
    else:
        grade_entropy = 0.3

    # φ = 1 - entropy (低熵 = 高φ = 有序)
    phi = 1.0 - (source_entropy * 0.4 + grade_entropy * 0.6)

    if phi > 0.7:
        phase = "凝聚·可信任"
        rec = "结果高度一致，综合可信"
    elif phi > 0.4:
        phase = "流动·部分可信"
        rec = "结果有差异，综合时标注不确定性"
    else:
        phase = "混沌·需更多搜索"
        rec = "结果分散混乱，建议扩大搜索范围或更换关键词"

    return {
        "phi": round(phi, 3),
        "phase": phase,
        "recommendation": rec,
        "source_entropy": round(source_entropy, 2),
        "grade_entropy": round(grade_entropy, 2),
    }


# ═══ 综合接入 ═══
def voyager_decompose(query: str) -> dict:
    """
    织星系统全面接入深度研究。
    
    返回:
    {
        "method": "expert_panel" | "cognitive" | "llm",
        "sub_queries": [...],
        "expert_teams_used": [...],
        "cognitive_hit": bool,
    }
    """
    result = {"method": "llm", "sub_queries": [], "expert_teams_used": [], "cognitive_hit": False}

    # 1. 先试认知层（经验缓存）
    try:
        from cognition import CognitiveLayer
        cognitive = CognitiveLayer(base=str(Path(__file__).parent / "data"), agent_id="voyager_deep")
        matches = cognitive.pattern_recognize(query, "decomposition")
        if matches and matches[0][0] > 0.7:
            cached = matches[0][1].get("data", {}).get("sub_queries", [])
            if cached:
                result["method"] = "cognitive"
                result["sub_queries"] = cached
                result["cognitive_hit"] = True
                return result
    except ImportError:
        pass

    # 2. 专家面板分解
    expert_subs = decompose_via_experts(query)
    if expert_subs:
        result["method"] = "expert_panel"
        result["sub_queries"] = expert_subs
        result["expert_teams_used"] = [s["department"] for s in expert_subs if s.get("department")]
        return result

    # 3. LLM回退
    from deep import decompose_query
    llm_subs = decompose_query(query)
    result["sub_queries"] = [{"query": sq, "department": "通用分析", "weight": 5} for sq in llm_subs]
    return result
