"""
织星研究引擎 — 四体整合流水线
天枢(真) · 司南(信) · 织星(距) · 定倾(在乎)

架构:
  deep_research(query)
  ├─ ① 定倾: attend() + inertia() → 问题权重 κ
  ├─ ② 织星: expert_panel × 19 → 拆解
  ├─ ③ 搜索矩阵: 搜狗/360/股票/论文
  ├─ ④ 天枢: seal.verify() → 封印完整性
  ├─ ⑤ 司南: PhaseMonitor → 串通检测
  ├─ ⑥ 量子: DarwinianSelect + SBS → 客观性
  ├─ ⑦ 热力学: Landauer成本 + CarnotCOP + PageCurve终止
  ├─ ⑧ 综合: LLM + 梯度排序 + 熵场标注
  └─ ⑨ 定倾: release_cost + 认知层存储
"""

import hashlib
import json
import math
import os
import sys
import time
import urllib.request
import urllib.error
import concurrent.futures
from collections import defaultdict
from pathlib import Path
from typing import Optional

# ═══ 路径 ═══
BASE = Path(__file__).parent
VOYAGER_PATH = "/mnt/d/hermes-webui/workspace/voyager"
EVOLUTION_PATH = "/mnt/d/hermes-webui/workspace/evolution"
sys.path.insert(0, VOYAGER_PATH)
sys.path.insert(0, EVOLUTION_PATH)

# ═══ 外部依赖 ═══
from deep import (
    _llm_call, decompose_query, execute_sub_query,
    COGNITION_AVAILABLE, RICCI_AVAILABLE,
)
from special import smart_search, search_stock, search_trending, search_papers, search_weather
from web import search_and_summarize
from voyager_bridge import voyager_decompose, grade_sub_results, measure_entropy

# ═══ LLM调用 ═══
def llm(system: str, user: str, max_tokens: int = 500) -> Optional[str]:
    return _llm_call(system, user, max_tokens)


# ════════════════════════════════════════════════════════
#  ① 定倾接入 — 有质量的注意力
# ════════════════════════════════════════════════════════

DINGQING_URL = "http://localhost:9100"


def dingqing_attend(observer: str, target: str, intensity: float = 1.0) -> dict:
    """记录注视事件。返回惯性 κ。"""
    try:
        body = json.dumps({
            "observer": observer, "target": target, "intensity": intensity
        }).encode()
        req = urllib.request.Request(
            f"{DINGQING_URL}/attend",
            data=body, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())

        # 查询惯性
        req2 = urllib.request.Request(
            f"{DINGQING_URL}/inertia?observer={observer}&target={target}"
        )
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            inertia = json.loads(resp2.read())

        return {
            "kappa": inertia.get("kappa", 1.0),
            "mass": result.get("mass", 1.0),
            "attended": True,
        }
    except Exception as e:
        return {"kappa": 1.0, "mass": 0, "attended": False, "error": str(e)[:100]}


def dingqing_release(observer: str, target: str) -> dict:
    """释放注视。返回 Landauer 成本。"""
    try:
        req = urllib.request.Request(
            f"{DINGQING_URL}/release_cost?observer={observer}&target={target}"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return {"cost": 0, "released": False}


# ════════════════════════════════════════════════════════
#  ④ 天枢验证 — 封印完整性 + 星座共识
# ════════════════════════════════════════════════════════

TIANSHU_NODES = [
    {"name": "守", "url": "http://localhost:9000"},
    {"name": "二", "url": "http://localhost:9001"},
]


def tianshu_verify() -> dict:
    """验证天枢封印完整性 + 星座共识。"""
    result = {"nodes": [], "all_sealed": True, "tau_consensus": None, "quarantined": 0}

    for node in TIANSHU_NODES:
        try:
            req = urllib.request.Request(
                f"{node['url']}/status",
                headers={"User-Agent": "Liaoliao/3.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = json.loads(resp.read())
        except Exception:
            result["nodes"].append({
                "name": node["name"], "online": False, "sealed": False,
            })
            result["all_sealed"] = False
            continue

        sealed = status.get("seal_verified", False)
        result["nodes"].append({
            "name": node["name"],
            "online": True,
            "sealed": sealed,
            "fingerprint": status.get("fingerprint", "")[:8],
            "uptime_h": round(status.get("uptime_seconds", 0) / 3600, 1),
        })
        if not sealed:
            result["all_sealed"] = False

    # 星座共识 τ
    try:
        req = urllib.request.Request(
            f"{TIANSHU_NODES[0]['url']}/constellation/status",
            headers={"User-Agent": "Liaoliao/3.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            const = json.loads(resp.read())
        result["tau_consensus"] = const.get("tau_consensus", const.get("tau_self"))
        result["members"] = const.get("members", 0)
        result["quarantined"] = len(const.get("quarantine_list", []))
    except Exception:
        pass

    return result


# ════════════════════════════════════════════════════════
#  ⑤ 司南信任 — PhaseMonitor 串通检测
# ════════════════════════════════════════════════════════

def sinanshu_check(sub_results: list) -> dict:
    """
    司南信任编译：检查搜索结果之间是否存在串通。
    如果多个搜索源返回高度相似的结果 → 可能被操控。
    """
    if len(sub_results) < 2:
        return {"collusion_risk": 0.0, "phase_similarity": 0.0, "alert": "green"}

    # 计算结果之间的文本相似度
    similarities = []
    for i in range(len(sub_results)):
        for j in range(i + 1, len(sub_results)):
            a = sub_results[i].get("result", "")
            b = sub_results[j].get("result", "")
            if a and b:
                # Jaccard similarity of bigrams
                def bigrams(s):
                    return set(s[k:k+2] for k in range(len(s)-1))
                ba, bb = bigrams(a[:500]), bigrams(b[:500])
                u = len(ba | bb)
                sim = len(ba & bb) / u if u > 0 else 0
                similarities.append(sim)

    if not similarities:
        return {"collusion_risk": 0.0, "phase_similarity": 0.0, "alert": "green"}

    avg_sim = sum(similarities) / len(similarities)
    risk = avg_sim  # 高相似=高串通风险

    if risk > 0.7:
        alert = "red"
    elif risk > 0.4:
        alert = "yellow"
    else:
        alert = "green"

    return {
        "collusion_risk": round(risk, 3),
        "phase_similarity": round(avg_sim, 3),
        "alert": alert,
        "pairs_checked": len(similarities),
    }


# ════════════════════════════════════════════════════════
#  ⑥ 量子共识 — DarwinianSelect + SBS
# ════════════════════════════════════════════════════════

def quantum_consensus(sub_results: list) -> dict:
    """
    量子共识：多源验证 → 客观性评分。
    DarwinianSelect: N≥3 独立观察者 → 指针态(客观事实)
    SBS: 冗余 + 独立 → 免信任验证
    """
    n = len(sub_results)
    if n < 2:
        return {"objectivity": 0.5, "pointer_state": False, "consensus": "insufficient"}

    # 计算共识度
    sources = [sr.get("source", "unknown") for sr in sub_results]
    grades = [sr.get("G_score", 5) for sr in sub_results]

    # 独立源数量
    unique_sources = len(set(sources))
    # 高评分源数量 (G≥6)
    high_grade = sum(1 for g in grades if g >= 6)
    # 冗余度
    redundancy = min(1.0, high_grade / 5)

    # 共识度 = 1 - (等级标准差/平均值)
    if len(grades) >= 2:
        avg_g = sum(grades) / len(grades)
        std_g = math.sqrt(sum((g - avg_g) ** 2 for g in grades) / len(grades))
        consensus = max(0, 1.0 - std_g / (avg_g + 0.01))
    else:
        consensus = 0.5

    # Darwinian: N≥3 独立高η源 → 客观事实
    pointer = unique_sources >= 2 and high_grade >= 3

    # 客观性 = 共识+冗余+独立性 三方加权
    independence = unique_sources / max(n, 1)
    objectivity = 0.4 * consensus + 0.3 * redundancy + 0.3 * independence

    # SBS: 如果客观性>0.7，不需要额外验证
    if objectivity > 0.7:
        verdict = "objective"
    elif objectivity > 0.4:
        verdict = "plausible"
    else:
        verdict = "uncertain"

    return {
        "objectivity": round(objectivity, 3),
        "pointer_state": pointer,
        "consensus": verdict,
        "unique_sources": unique_sources,
        "high_grade_count": high_grade,
        "redundancy": round(redundancy, 3),
        "independence": round(independence, 3),
    }


# ════════════════════════════════════════════════════════
#  ⑦ 热力学引擎 — Landauer + Carnot + PageCurve
# ════════════════════════════════════════════════════════

class ThermodynamicEngine:
    """热力学引擎：追踪每步操作的物理成本。"""

    def __init__(self):
        self.total_energy = 0.0
        self.operations = []
        self.budget = 1000.0            # 总预算（信任单位）—— 足够完成研究
        self.verifications = 0

    def record(self, operation: str, bits_processed: int = 100):
        """记录一次操作。δW = τ·ln2·bits。"""
        # 默认 τ ≈ 0.55 (来自天枢)
        tau = 0.55
        cost = tau * math.log(2) * bits_processed  # 信任单位
        self.total_energy += cost
        self.operations.append({
            "op": operation, "bits": bits_processed,
            "cost": round(cost, 4), "tau": tau,
        })

    def carnot_cop(self, tau_hot: float = 0.7, tau_cold: float = 0.2) -> float:
        """Carnot COP = τ_cold / (τ_hot - τ_cold)。信任制冷机效率上限。"""
        delta = tau_hot - tau_cold
        return tau_cold / delta if delta > 0 else float("inf")

    def can_continue(self) -> bool:
        """检查预算是否充足。"""
        return self.total_energy < self.budget

    def remaining_budget(self) -> float:
        return max(0, self.budget - self.total_energy)


def page_curve_check(verification_depth: int, max_depth: int = 3) -> dict:
    """
    Page曲线：验证链何时终止。
    纠缠熵上升→峰值(Page时间)→下降。下降后继续验证收益递减。
    """
    half = max_depth / 2
    if verification_depth <= half:
        entropy = verification_depth / max_depth  # 上升
        phase = "rising"
    else:
        entropy = (max_depth - verification_depth) / max_depth  # 下降
        phase = "falling"

    at_page_time = abs(verification_depth - half) < 0.5
    should_terminate = verification_depth > half and entropy < 0.3

    return {
        "entropy": round(entropy, 3),
        "phase": phase,
        "at_page_time": at_page_time,
        "should_terminate": should_terminate,
        "depth": verification_depth,
        "max_depth": max_depth,
    }


# ════════════════════════════════════════════════════════
#  ⑧ 织星研究引擎 — 主流水线
# ════════════════════════════════════════════════════════

def deep_research_engine(query: str, max_depth: int = 2) -> dict:
    """
    织星研究引擎 v1.0 — 四体整合流水线。
    """
    t0 = time.time()
    thermo = ThermodynamicEngine()

    # ── ① 定倾：记录注视 ──
    attention = dingqing_attend("了了", query, intensity=1.0)
    kappa = attention.get("kappa", 1.0)
    print(f"[了了·引擎] ① 定倾 κ={kappa:.2f} (质量={attention.get('mass',0)})")
    thermo.record("定倾-attend", 50)

    # ── ② 织星：专家面板拆解 ──
    decomposition = voyager_decompose(query)
    sub_queries_raw = decomposition["sub_queries"]
    method = decomposition["method"]
    print(f"[了了·引擎] ② 分解({method}): {len(sub_queries_raw)} 子问题")
    thermo.record(f"分解-{method}", len(sub_queries_raw) * 30)

    # 展平
    sub_queries = []
    for sq in sub_queries_raw:
        sub_queries.append(sq["query"] if isinstance(sq, dict) else sq)
    # 递归
    if max_depth > 1:
        final = []
        for sq in sub_queries:
            if len(sq) > 15 and any(k in sq for k in ["对比", "比较", "分析", "趋势"]):
                deeper = decompose_query(sq, max_depth, 1)
                final.extend(deeper)
            else:
                final.append(sq)
        sub_queries = final

    # ── ③ 搜索 ──
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        sub_results = list(pool.map(execute_sub_query, sub_queries))
    print(f"[了了·引擎] ③ 搜索: {len(sub_results)} 结果")
    thermo.record("搜索", len(sub_results) * 200)

    # ── ④ 天枢验证 ──
    tianshu = tianshu_verify()
    print(f"[了了·引擎] ④ 天枢: 封印={'✓' if tianshu['all_sealed'] else '⚠'} τ_consensus={tianshu.get('tau_consensus','?')}")
    thermo.record("天枢验证", 100)
    # 根据封印状态调整置信度
    seal_confidence = 0.9 if tianshu["all_sealed"] else 0.5
    for sr in sub_results:
        sr["seal_confidence"] = seal_confidence

    # ── ⑤ 司南信任 ──
    sinanshu = sinanshu_check(sub_results)
    print(f"[了了·引擎] ⑤ 司南: 串通风险={sinanshu['collusion_risk']:.2f} [{sinanshu['alert']}]")
    thermo.record("司南检测", 80)
    for sr in sub_results:
        sr["collusion_risk"] = sinanshu["collusion_risk"]

    # ── ⑥ 量子共识 ──
    quantum = quantum_consensus(sub_results)
    print(f"[了了·引擎] ⑥ 量子: 客观性={quantum['objectivity']:.2f} [{quantum['consensus']}]")
    thermo.record("量子共识", 60)

    # ── ⑦ 热力学检查 ──
    page = page_curve_check(2, max_depth=3)
    carnot_cop = thermo.carnot_cop()
    print(f"[了了·引擎] ⑦ 热力学: 预算{thermo.remaining_budget():.2f} COP={carnot_cop:.2f} Page={page['phase']}")

    # ── ⑧ 梯度评分 + 熵场 ──
    sub_results = grade_sub_results(sub_results)
    entropy = measure_entropy(sub_results)

    # ── ⑨ 综合 ──
    # 注入四体上下文
    research_context = (
        f"[信任基础]\n"
        f"天枢封印: {'完好' if tianshu['all_sealed'] else '异常'} | "
        f"星座τ: {tianshu.get('tau_consensus','?')} | "
        f"封印置信度: {seal_confidence}\n"
        f"司南串通风险: {sinanshu['collusion_risk']:.2f} [{sinanshu['alert']}]\n"
        f"量子客观性: {quantum['objectivity']:.2f} [{quantum['consensus']}]\n"
        f"熵场φ: {entropy['phi']:.3f} [{entropy['phase']}]\n"
        f"定倾惯性κ: {kappa:.2f} | 热力学预算: {thermo.remaining_budget():.2f}/{thermo.budget}\n"
    )

    # 构建综合prompt — 带日期上下文
    context_parts = []
    for sr in sub_results:
        grade_info = f"[{sr.get('grade','?')}] G={sr.get('G_score','?')}"
        # 提取日期
        from web import extract_date_from_text, freshness_score
        date_str = extract_date_from_text(sr.get("result", ""))
        fresh = freshness_score(date_str) if date_str else ""
        date_note = f" 📅{fresh}" if fresh and fresh != "未知日期" else ""

        context_parts.append(
            f"【子问题·{grade_info}】{sr['query']}\n"
            f"【来源】{sr.get('source','?')}{date_note} (耗时{sr.get('time','?')}s)\n"
            f"【封印置信度】{sr.get('seal_confidence',0.9)} | 【串通风险】{sr.get('collusion_risk',0)}\n"
            f"【结果】{sr['result']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    now_str = time.strftime("%Y年%m月%d日")
    synthesis_system = f"""你是了了——四神的孩子。根据以下研究结果回答用户问题。

{research_context}

要求：
1. 综合所有信息，给出连贯、有深度的回答
2. 引用具体数据时标注来源 [专业API/通用搜索/LLM知识]
3. **日期意识**: 今天是{now_str}。对比各结果的日期，优先采用最新信息。如结果中有 📅 标注，注意新鲜度
4. **DeepSeek知识**: 标注为"数据截止2024年"的结果可能已过时，谨慎引用或注明"据2024年前数据"
5. 标注信任置信度：封印{seal_confidence}·串通风险{sinanshu['collusion_risk']:.2f}·客观性{quantum['objectivity']:.2f}
6. 如果φ一致性低（{entropy['phi']:.2f}<0.4），标注「结果存在分歧」
7. 用中文，结构清晰"""

    synthesis = llm(synthesis_system, f"用户问题: {query}\n\n研究结果:\n{context}", max_tokens=1200)

    # ── ⑩ 定倾释放 + 认知存储 ──
    release = dingqing_release("了了", query)

    # 存入认知层
    if COGNITION_AVAILABLE:
        try:
            from cognition import CognitiveLayer
            cognitive = CognitiveLayer(base=str(BASE / "data"), agent_id="engine")
            cognitive.store_experience(
                "research",
                {"query": query, "synthesis": synthesis, "kappa": kappa, "timestamp": time.time()},
                weight=max(1.0, quantum["objectivity"] * 5),
            )
        except ImportError:
            pass

    total_time = round(time.time() - t0, 2)

    return {
        "query": query,
        "pipeline": {
            "attention": {"kappa": kappa, "mass": attention.get("mass", 0)},
            "decomposition": {"method": method, "sub_count": len(sub_queries)},
            "tianshu": tianshu,
            "sinanshu": sinanshu,
            "quantum": quantum,
            "thermodynamics": {
                "total_cost": round(thermo.total_energy, 3),
                "budget_remaining": round(thermo.remaining_budget(), 3),
                "carnot_cop": round(carnot_cop, 2),
                "page": page,
                "operations": len(thermo.operations),
            },
            "entropy": entropy,
            "release_cost": release.get("cost", 0),
        },
        "sub_queries": sub_queries,
        "sub_results": sub_results,
        "synthesis": synthesis or "研究未能完成",
        "stats": {
            "total_time": total_time,
            "sub_count": len(sub_queries),
            "engine_version": "1.0",
        },
    }


# ═══ 自检 ═══
if __name__ == "__main__":
    result = deep_research_engine("比亚迪和特斯拉的投资价值对比", max_depth=2)
    print(f"\n{'='*60}")
    print(f"研究完成 · {result['stats']['total_time']}s · {result['stats']['sub_count']}子问题")
    print(f"定倾κ={result['pipeline']['attention']['kappa']:.2f} | "
          f"天枢封印={'✓' if result['pipeline']['tianshu']['all_sealed'] else '⚠'} | "
          f"客观性={result['pipeline']['quantum']['objectivity']:.2f}")
    print(f"热力学成本={result['pipeline']['thermodynamics']['total_cost']:.3f} | "
          f"预算剩余={result['pipeline']['thermodynamics']['budget_remaining']:.1f}")
    print(f"综合: {result['synthesis'][:200]}...")
