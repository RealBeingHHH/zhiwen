"""
了了之思 · 分析层 — 搜索结果的分析管道

搜索 → 提取(数字·日期·实体) → 交叉验证 → 矛盾标记 → 置信度 → 分析报告
"""

import json
import os
import re
import time
from collections import defaultdict
from typing import Optional

from web import extract_date_from_text, freshness_score, DEEPSEEK_CUTOFF
from voyager_llm import safe_llm_call as _llm_call


def extract_numbers(text: str) -> list[dict]:
    """从文本中提取数字及其上下文。"""
    patterns = [
        # 带单位的数字
        (r'(\d+[\.\d]*)\s*(万亿|亿|万|%)', 'value_unit'),
        (r'(\d+[\.\d]*)\s*(元|美元|万元|亿元)', 'value_currency'),
        # 百分比
        (r'([+-]?\d+[\.\d]*%)', 'percentage'),
        # 纯数字（较大，可能是统计值）
        (r'(\d{2,}[\.\d]*)', 'number'),
    ]
    results = []
    seen = set()
    for pat, ntype in patterns:
        for m in re.finditer(pat, text):
            val = m.group(0) if ntype != 'value_unit' and ntype != 'value_currency' else m.group(1) + m.group(2)
            if val in seen:
                continue
            seen.add(val)
            # 取上下文
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            ctx = text[start:end].replace('\n', ' ').strip()
            results.append({"value": val, "type": ntype, "context": ctx})
    return results[:20]


def extract_entities(text: str) -> list[str]:
    """提取关键实体（公司名、人名、地名、产品名等）。"""
    # 简单规则：大写开头的中文词或英文专有名词
    entities = set()
    # 公司名
    for pat in [r'([\u4e00-\u9fff]{2,6}(?:公司|集团|银行|基金|证券))',
                r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)']:
        for m in re.findall(pat, text):
            if len(m) > 1:
                entities.add(m)
    return list(entities)[:10]


def cross_validate(results: list[dict]) -> dict:
    """
    交叉验证：对比不同来源的数据。
    返回矛盾点和共识点。
    """
    if len(results) < 2:
        return {"contradictions": [], "consensus": [], "source_count": len(results)}

    # 收集所有数字
    all_numbers = []
    for r in results:
        content = r.get("result", r.get("content", ""))
        nums = extract_numbers(content)
        for n in nums:
            n["source"] = r.get("source", r.get("query", "unknown"))
            all_numbers.append(n)

    # 检查一致性和矛盾
    contradictions = []
    consensus = []

    # 按数值类型分组
    by_type = defaultdict(list)
    for n in all_numbers:
        by_type[n["type"]].append(n)

    for ntype, nums in by_type.items():
        if len(nums) < 2:
            continue
        # 提取数值部分
        values = []
        for n in nums:
            try:
                v = float(re.sub(r'[^\d\.\-]', '', n["value"]))
                values.append((v, n))
            except ValueError:
                continue

        if len(values) < 2:
            continue

        values.sort(key=lambda x: x[0])
        vmin, vmax = values[0][0], values[-1][0]

        # 偏差超过20% → 矛盾
        if vmin > 0 and (vmax - vmin) / vmin > 0.2:
            contradictions.append({
                "metric": ntype,
                "values": [f"{v[1]['value']} ({v[1]['source']})" for v in values],
                "range": f"{vmin:.2f} ~ {vmax:.2f}",
                "variance": f"{(vmax-vmin)/vmin*100:.0f}%",
            })
        elif vmin > 0:
            consensus.append({
                "metric": ntype,
                "values": [f"{v[1]['value']} ({v[1]['source']})" for v in values],
                "agreement": "high",
            })

    return {
        "contradictions": contradictions[:5],
        "consensus": consensus[:5],
        "source_count": len(results),
        "number_count": len(all_numbers),
    }


def data_completeness(results: list[dict], query: str) -> dict:
    """评估数据完整度。"""
    if not results:
        return {"score": 0.0, "level": "无数据", "missing": ["所有"]}

    total_len = sum(len(r.get("result", r.get("content", ""))) for r in results)
    sources = len(set(r.get("source", "?") for r in results))
    has_numbers = any(re.search(r'\d+', r.get("result", r.get("content", ""))) for r in results)
    has_dates = any(extract_date_from_text(r.get("result", r.get("content", ""))) for r in results)

    # 评分
    score = 0.0
    missing = []
    if sources >= 2:
        score += 0.3
    else:
        missing.append("多源验证不足")
    if total_len > 500:
        score += 0.3
    else:
        missing.append("数据量不足")
    if has_numbers:
        score += 0.2
    else:
        missing.append("无具体数字")
    if has_dates:
        score += 0.2
    else:
        missing.append("无日期信息")

    if score >= 0.8:
        level = "充分"
    elif score >= 0.5:
        level = "部分"
    elif score >= 0.3:
        level = "不足"
    else:
        level = "极少"

    return {"score": round(score, 2), "level": level, "missing": missing,
            "sources": sources, "has_numbers": has_numbers, "has_dates": has_dates}


def analyze_results(search_context: str, query: str) -> str:
    """
    分析搜索结果，生成结构化分析报告。
    这个报告会注入到LLM prompt中，让了了基于分析而非原始数据回答。
    """
    if not search_context or len(search_context) < 20:
        return "无数据可供分析"

    # 提取数字和实体
    numbers = extract_numbers(search_context)
    entities = extract_entities(search_context)
    dates = extract_date_from_text(search_context)

    # 用LLM做深度分析
    analysis_prompt = f"""你是数据分析师。分析以下搜索结果，提炼关键发现。

要求：
1. 提取所有具体数字，标注其含义
2. 如果有多条数据，做对比
3. 标注数据的时效性（日期）
4. 指出数据缺口——哪些该有的数据没有
5. 给数据可信度评分（0-10）

搜索结果：
{search_context[:2500]}

请以简洁的要点形式输出分析，不要冗长。"""

    analysis = _llm_call(analysis_prompt, query, max_tokens=500)

    # 提取的数字汇总
    num_summary = ""
    if numbers:
        unique_nums = {}
        for n in numbers[:8]:
            unique_nums[n["value"]] = n["context"][:80]
        num_summary = "提取数据: " + " | ".join(
            f"{v}: {c[:50]}" for v, c in list(unique_nums.items())[:6]
        )

    # 构建分析报告
    parts = ["[数据分析报告]"]
    if entities:
        parts.append(f"关键实体: {', '.join(entities[:8])}")
    if num_summary:
        parts.append(num_summary)
    if dates:
        parts.append(f"数据时效: {dates}")
    if analysis:
        parts.append(f"\n[深度分析]\n{analysis}")
    parts.append(f"\n[数据截止提示] DeepSeek训练数据截止{DEEPSEEK_CUTOFF}，可能有更新信息未包含。")

    return "\n".join(parts)


def analyze_and_score(search_context: str, query: str) -> dict:
    """一站式：分析 + 交叉验证 + 完整度评估。"""
    results = [{"source": "search", "result": search_context}]

    validation = cross_validate(results) if len(search_context) > 100 else {"contradictions": [], "consensus": [], "source_count": 0}
    completeness = data_completeness(results, query)
    analysis = analyze_results(search_context, query)

    # 检测数据缺口 → 生成补充查询
    gap_queries = []
    if completeness["score"] < 0.6:
        gap_queries = generate_gap_queries(query, analysis, completeness["missing"])

    return {
        "analysis": analysis,
        "validation": validation,
        "completeness": completeness,
        "gap_queries": gap_queries,  # 需要补充搜索的查询列表
    }


def generate_gap_queries(query: str, analysis: str, missing: list) -> list:
    """
    检测数据缺口，生成补充搜索查询。
    例如：只有到2023年的财务数据 → 生成"2024年财务数据"查询
    """
    missing_str = ", ".join(missing) if missing else "未知"
    
    prompt = f"""用户查询: {query}
现有分析: {analysis[:500]}
已知缺口: {missing_str}

请生成2-3个具体的补充搜索查询，用于填补数据缺口。
要求：
1. 每个查询针对一个具体缺口
2. 包含年份（如2024、2025）以确保获取最新数据
3. 简洁、可搜索

输出每行一个查询，不要序号。"""

    result = _llm_call(prompt, "生成补充查询", max_tokens=200)
    if not result:
        return []

    queries = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if line and len(line) > 5:
            import re as _re
            line = _re.sub(r'^[\d\.\、\)\s]+', '', line).strip()
            if line and line not in queries:
                queries.append(line)

    return queries[:3]


def fill_gaps(query: str, initial_context: str) -> str:
    """
    检测缺口 → 生成补充查询 → 搜索 → 合并。
    返回增强后的搜索上下文。
    """
    from web import search_and_summarize
    from special import smart_search
    from meta_search import meta_search_to_context

    # 第一步：分析
    analysis = analyze_and_score(initial_context, query)
    gap_queries = analysis.get("gap_queries", [])
    completeness = analysis["completeness"]

    if not gap_queries or completeness["score"] >= 0.6:
        return initial_context  # 数据足够，不需要补充

    # 第二步：补充搜索
    extra_contexts = []
    for gq in gap_queries:
        # 先试专业搜索
        result = smart_search(gq)
        if not result or len(result) < 30:
            result = search_and_summarize(gq)
        if not result or len(result) < 30:
            result = meta_search_to_context(gq)
        if result and len(result) > 20:
            extra_contexts.append(f"[补充搜索: {gq}]\n{result}")

    if not extra_contexts:
        return initial_context

    # 第三步：合并
    merged = initial_context + "\n\n--- 补充数据 ---\n\n" + "\n\n".join(extra_contexts)
    return merged
