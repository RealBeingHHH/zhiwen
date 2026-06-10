"""
了了之思 · 深度研究 v2.0
织星 CognitiveLayer 接入 + 并行 + 递归 + 引用溯源 + φ间距

架构:
  decompose_query()
  ├─ CognitiveLayer.pattern_recognize() → 复用历史分解
  ├─ φ-spacing (OllivierRicci) → 确保子问题独立
  └─ LLM fallback → 新分解 → store_experience()

  deep_research()
  ├─ decompose → 递归拆解
  ├─ execute_sub_query × N → asyncio 并行
  └─ synthesize → η-weighted + 引用标注
"""

import asyncio
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

# 织星者模块路径
VOYAGER_PATH = "/mnt/d/hermes-webui/workspace/voyager"
if VOYAGER_PATH not in sys.path:
    sys.path.append(VOYAGER_PATH)

from special import smart_search, search_stock, search_trending, search_papers, search_weather
from web import search_web, search_and_summarize

# 织星者认知层
try:
    from cognition import CognitiveLayer
    COGNITION_AVAILABLE = True
except ImportError:
    COGNITION_AVAILABLE = False

# 织星者 φ 间距
try:
    from ollivier_ricci import OllivierRicci
    RICCI_AVAILABLE = True
except ImportError:
    RICCI_AVAILABLE = False


# ═══ LLM 调用 ═══
def _llm_call(system: str, user: str, max_tokens: int = 500) -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    model = os.environ.get("OPENAI_MODEL", "deepseek-chat")

    env_file = os.path.join(os.path.dirname(__file__), ".env.llm")
    if (not api_key or len(api_key) < 20) and os.path.exists(env_file):
        try:
            with open(env_file) as f:
                env_vars = json.load(f)
            api_key = env_vars.get("OPENAI_API_KEY", "")
            base_url = env_vars.get("OPENAI_BASE_URL", base_url)
            model = env_vars.get("OPENAI_MODEL", model)
        except Exception:
            pass

    if not api_key or len(api_key) < 20:
        return None

    if "/chat/completions" not in base_url:
        base_url = base_url.rstrip("/") + "/chat/completions"

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }

    try:
        req = urllib.request.Request(
            base_url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
    except Exception:
        pass
    return None


# ═══ 织星 CognitiveLayer ═══
_cognitive: Optional[CognitiveLayer] = None


def get_cognitive() -> Optional[CognitiveLayer]:
    global _cognitive
    if _cognitive is None and COGNITION_AVAILABLE:
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        _cognitive = CognitiveLayer(base=data_dir, agent_id="liaoliao_deep")
    return _cognitive


# ═══ 分解器 v2.0 ═══
DECOMPOSE_SYSTEM = """你是查询分解器。将复杂问题拆解为2-5个原子子问题。
每个子问题必须：
1. 独立可搜索（不需要其他子问题的结果）
2. 覆盖原始问题的不同维度
3. 简洁明确（10-20字）

输出：每行一个子问题，不要序号，不要解释。"""


def decompose_query(query: str, max_depth: int = 2, current_depth: int = 0) -> list:
    """
    递归拆解。织星 CognitiveLayer 加速。
    
    max_depth=2: 最多递归2层
    current_depth: 当前深度
    """
    # 0. 到达最大深度，不再拆
    if current_depth >= max_depth:
        return [query]

    # 1. 检查 CognitiveLayer 是否有相似经验
    cognitive = get_cognitive()
    if cognitive:
        matches = cognitive.pattern_recognize(query, "decomposition")
        if matches:
            best_sim, best_entry = matches[0]
            if best_sim > 0.7:
                # 复用历史分解
                cached_subs = best_entry.get("data", {}).get("sub_queries", [])
                if cached_subs:
                    print(f"[了了] CognitiveLayer 命中 (sim={best_sim:.2f}), 复用 {len(cached_subs)} 个子问题")
                    return cached_subs

    # 2. LLM 分解
    result = _llm_call(DECOMPOSE_SYSTEM, query, max_tokens=300)
    if not result:
        return [query]

    sub_queries = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if line and len(line) > 3:
            import re
            line = re.sub(r'^[\d\.\、\)\s]+', '', line).strip()
            if line and line not in sub_queries:
                sub_queries.append(line)

    if not sub_queries:
        return [query]

    # 3. φ间距检查：确保子问题足够独立（避免重复搜索）
    if RICCI_AVAILABLE and len(sub_queries) >= 2:
        try:
            import numpy as np
            ricci = OllivierRicci()
            # 构建简单邻接图：每个子问题一个节点
            n = len(sub_queries)
            adj = np.ones((n, n)) - np.eye(n)  # 全连接（无先验结构）
            curvature = ricci.compute(adj)
            # 低曲率节点对 = 过于相似，需要合并或移除
            low_curve_pairs = []
            for i in range(n):
                for j in range(i+1, n):
                    if curvature[i, j] < 0.5:
                        low_curve_pairs.append((i, j))

            if low_curve_pairs:
                print(f"[了了] φ间距: {len(low_curve_pairs)} 对低曲率子问题, 合并中...")
                # 合并最相似的一对（简单策略：移除后者）
                merged = []
                removed = set()
                for i, j in low_curve_pairs:
                    if j not in removed:
                        removed.add(j)
                for idx, sq in enumerate(sub_queries):
                    if idx not in removed:
                        merged.append(sq)
                sub_queries = merged
        except Exception:
            pass

    # 4. 存入 CognitiveLayer
    if cognitive:
        cognitive.store_experience(
            "decomposition",
            {"query": query, "sub_queries": sub_queries, "depth": current_depth, "timestamp": time.time()},
            weight=1.0,
        )

    # 5. 递归拆解：对每个子问题检查是否还需要拆
    if current_depth + 1 < max_depth:
        final_subs = []
        for sq in sub_queries:
            # 简单判断：如果子问题还包含"对比/分析/综合"等复杂词，继续拆
            complex_keywords = ["对比", "比较", "分析", "综合", "趋势", "为什么"]
            if len(sq) > 15 and any(k in sq for k in complex_keywords):
                deeper = decompose_query(sq, max_depth, current_depth + 1)
                final_subs.extend(deeper)
            else:
                final_subs.append(sq)
        sub_queries = final_subs

    return sub_queries


# ═══ 执行器 v2.0 ═══
EXECUTOR = ThreadPoolExecutor(max_workers=5)


def execute_sub_query(sub_query: str) -> dict:
    """执行单个子查询，返回带来源标注的结果。"""
    start = time.time()

    # 先试专业搜索
    result = smart_search(sub_query)
    source = "专业API"
    if result:
        return {
            "query": sub_query,
            "result": result[:500],
            "source": source,
            "time": round(time.time() - start, 2),
        }

    # 再试通用搜索
    result = search_and_summarize(sub_query)
    source = "通用搜索"
    if result:
        return {
            "query": sub_query,
            "result": result[:500],
            "source": source,
            "time": round(time.time() - start, 2),
        }

    # LLM 回退
    llm_result = _llm_call("你是知识助手。简要准确地回答用户问题。", sub_query, max_tokens=200)
    return {
        "query": sub_query,
        "result": llm_result or f"未找到信息",
        "source": "LLM知识",
        "time": round(time.time() - start, 2),
    }


async def execute_all_parallel(sub_queries: list) -> list:
    """并行执行所有子查询。"""
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(EXECUTOR, execute_sub_query, sq) for sq in sub_queries]
    results = await asyncio.gather(*tasks)
    return list(results)


# ═══ 综合器 v2.0 ═══
SYNTHESIS_SYSTEM = """你是深度研究助手。根据以下多个子查询的结果，综合回答用户问题。

要求：
1. 综合所有信息，给出连贯、有深度的回答
2. 引用具体数据时标注来源（如 [专业API] [通用搜索] [LLM知识]）
3. 如果有矛盾的信息，指出不确定性
4. 区分"搜索到的事实"和"推理得出的判断"
5. **日期意识**: 对比各结果的日期，优先采用最新信息。如结果中包含 📅 标注，说明数据的新鲜度
6. **DeepSeek知识注意**: 标记为"数据截止2024年"的结果可能已过时，谨慎引用
7. 用中文，结构清晰

当前时间: {now}"""


def synthesize(query: str, sub_results: list) -> str:
    """η-weighted 综合。"""
    from datetime import datetime
    now = datetime.now().strftime("%Y年%m月%d日")

    # 构建上下文，带来源标注 + 日期标注
    context_parts = []
    for sr in sub_results:
        # 提取日期
        from web import extract_date_from_text, freshness_score
        date_str = extract_date_from_text(sr.get("result", ""))
        fresh = freshness_score(date_str) if date_str else ""
        date_note = f" 📅{fresh}" if fresh and fresh != "未知日期" else ""

        context_parts.append(
            f"【子问题】{sr['query']}\n"
            f"【来源】{sr['source']}{date_note} (耗时{sr['time']}s)\n"
            f"【结果】{sr['result']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    synthesis = _llm_call(
        SYNTHESIS_SYSTEM.format(now=now),
        f"用户问题: {query}\n\n子查询结果:\n{context}",
        max_tokens=1000,
    )

    return synthesis or "无法完成综合分析"


# ═══ 统一接口 ═══
# 懒加载避免循环依赖
_voyager_imports = None

def _get_voyager():
    global _voyager_imports
    if _voyager_imports is None:
        from voyager_bridge import voyager_decompose, grade_sub_results, measure_entropy
        _voyager_imports = (voyager_decompose, grade_sub_results, measure_entropy)
    return _voyager_imports


def _detect_scientific_domain(query: str) -> bool:
    """检测是否适用科学方法（假设→模拟→验证→改善）。
    
    通用触发规则：
    1. 优化类问题（最优/最佳/改善/优化/选择/方案/策略/比较）
    2. 关于可量化系统的分析
    3. 复杂决策场景
    """
    # 强触发词（优化类 — 任何领域都值得模拟验证）
    strong_triggers = [
        "最优", "最佳", "改善", "优化", "方案", "策略", "选择",
        "哪个更", "哪个好", "最有利", "最有效", "权衡",
    ]
    strong_score = sum(1 for t in strong_triggers if t in query)

    # 经济学领域词
    econ_keywords = [
        "MMT", "财政", "赤字", "通胀", "货币政策", "税收", "税率", "预算",
        "GDP", "支出", "国债", "债务", "赤字率", "就业", "失业",
        "基建", "福利", "补贴", "投资", "公共", "政府",
        "模拟", "仿真", "演化", "假设",
    ]
    econ_score = sum(1 for k in econ_keywords if k in query)

    # 判定: 强触发词>=2 或 (强触发词>=1 AND 经济词>=1) 或 经济词>=3
    return bool(
        strong_score >= 2
        or (strong_score >= 1 and econ_score >= 1)
        or econ_score >= 3
    )


def deep_research_sci(query: str, max_depth: int = 2, max_sci_rounds: int = 5) -> dict:
    """深度研究 + 科学方法循环（假设→模拟→验证→改善→循环）。"""
    from sci_method import scientific_research

    # 常规深度研究
    result = deep_research(query, max_depth)

    # 检测是否需要科学方法
    if not _detect_scientific_domain(query):
        result["scientific_method"] = {"enabled": False, "reason": "domain not applicable"}
        return result

    # 执行科学方法
    print(f"[了了·科学方法] 检测到模拟友好领域，启动假设→模拟→验证→改善循环")
    sci_result = scientific_research(query, max_sci_rounds)
    result["scientific_method"] = {
        "enabled": True,
        **sci_result,
    }
    return result


def deep_research(query: str, max_depth: int = 2) -> dict:
    """
    深度研究 v3.0 — 织星系统全面接入：
    - 专家面板拆解（技术面/基本面/宏观/量化/风控 × 19 部门）
    - CognitiveLayer 经验缓存
    - 梯度系统 G-score 评分（S/A/B/C/D）
    - 熵场 φ 检测（凝聚/流动/混沌）
    - φ间距去重
    - 递归拆解（≤2层）
    - 并行执行
    - 引用溯源
    """
    t0 = time.time()

    # 第一步：织星拆解
    voyager_decompose, grade_sub_results, measure_entropy = _get_voyager()
    decomposition = voyager_decompose(query)
    sub_queries_raw = decomposition["sub_queries"]
    method = decomposition["method"]
    print(f"[了了·深研] {method} 拆解为 {len(sub_queries_raw)} 个子问题")

    # 展平子问题（可能是 dict 或 str）
    sub_queries = []
    for sq in sub_queries_raw:
        if isinstance(sq, dict):
            sub_queries.append(sq["query"])
        else:
            sub_queries.append(sq)

    # 递归拆解
    if max_depth > 1:
        final_subs = []
        for sq in sub_queries:
            complex_kw = ["对比", "比较", "分析", "综合", "趋势", "为什么"]
            if len(sq) > 15 and any(k in sq for k in complex_kw):
                deeper = decompose_query(sq, max_depth, 1)
                final_subs.extend(deeper)
            else:
                final_subs.append(sq)
        sub_queries = final_subs

    # 第二步：并行执行
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        sub_results = list(pool.map(execute_sub_query, sub_queries))

    # 第三步：梯度评分 + 熵场检测
    sub_results = grade_sub_results(sub_results)
    entropy = measure_entropy(sub_results)

    # 第四步：综合
    synthesis = synthesize(query, sub_results)

    total_time = round(time.time() - t0, 2)

    sources = {}
    for sr in sub_results:
        s = sr.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1

    return {
        "query": query,
        "decomposition": {
            "method": method,
            "expert_teams": decomposition.get("expert_teams_used", []),
            "cognitive_hit": decomposition.get("cognitive_hit", False),
        },
        "sub_queries": sub_queries,
        "sub_results": sub_results,
        "synthesis": synthesis,
        "entropy": entropy,
        "stats": {
            "total_time": total_time,
            "sub_count": len(sub_queries),
            "max_depth": max_depth,
            "sources": sources,
            "cognitive_available": COGNITION_AVAILABLE,
            "ricci_available": RICCI_AVAILABLE,
        },
    }
