"""
DNA执行引擎 — 密码子→真实模块调用

这是 tRNA 接上核糖体的那一步:
  mRNA密码子链 → CodonTable.translate() → 动作
  动作不再只是标签 — 它直接调用对应的管线模块

执行映射:
  START         → ═══ 管线初始化 ═══
  SEARCH        → smart_search() / search_and_summarize()
  SEARCH_DEEP   → deep_research()
  SEARCH_META   → meta_search_to_context()
  SEARCH_DOC    → read_document (检查URL路径)
  SIMULATE      → scientific_research() / fiscal_sim
  SIMULATE_SWEEP→ parameter_sweep()
  SIMULATE_COMPETE→ competing_hypotheses()
  VERIFY        → DataGate.check()
  VERIFY_RELATION→ 关系完整性检查
  VERIFY_BENFORD→ Benford真实性检测
  VERIFY_TAU    → TianshuClient.get_state()
  CONTRAST      → WorldviewContrast.generate()
  ADVERSARIAL   → AdversarialVerifier
  ITERATE       → IterativeOptimizer.optimize()
  STOP_CONCLUDE → 组装最终输出
  STOP_SEAL     → TianshuClient.seal_conclusion()
"""

import time, hashlib
from typing import Optional


def execute_codon(codon: str, action: str = None, context: dict = None) -> dict:
    """
    执行单个密码子对应的研究动作。
    
    如果 action 为 None，从 CodonTable 自动查询。

    返回: {codon, action, result, output, error, elapsed_ms}
    """
    if action is None:
        from genome_core import CodonTable
        info = CodonTable.translate(codon)
        action = info["action"]

    if context is None:
        context = {}

    t0 = time.time()
    result = {
        "codon": codon, "action": action,
        "result": None, "output": "", "error": None,
    }

    try:
        handler = _ACTION_HANDLERS.get(action)
        if handler:
            output = handler(context)
            result["output"] = str(output)[:500] if output else ""
            result["result"] = "ok"
        else:
            result["result"] = "pass"  # 未知动作，跳过
            result["output"] = f"未知动作{action}，静默跳过"

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        result["result"] = "error"

    result["elapsed_ms"] = int((time.time() - t0) * 1000)
    return result


def execute_gene_codons(codons: list[str], query: str, pipeline_ctx: dict = None) -> dict:
    """
    按密码子序列完整执行研究管线。

    每个密码子链就是一份可执行的研究方案:
      ATG→AAG→GGC→CGT→TAA
      = 启动→搜索→模拟→验证→结论

    返回: {execution_log, collected_data, has_simulation, verification_results, ...}
    """
    from genome_core import CodonTable

    execution_log = []
    collected = {
        "search_data": "",
        "simulation_result": "",
        "verification_result": None,
        "contrast_text": "",
        "adversarial_result": "",
        "panic_log": [],
    }
    has_simulation = False
    stopped = False

    context = {
        "query": query,
        "pipeline_ctx": pipeline_ctx or {},
        "collected": collected,
    }

    for codon in codons:
        if stopped:
            break

        info = CodonTable.translate(codon)
        action = info["action"]

        result = execute_codon(codon, action, context)
        execution_log.append(result)

        # 收集数据
        if result["output"]:
            if action.startswith("SEARCH"):
                collected["search_data"] += result["output"] + "\n"
            elif action.startswith("SIMULATE"):
                collected["simulation_result"] += result["output"] + "\n"
                has_simulation = True
            elif action.startswith("VERIFY"):
                collected["verification_result"] = result["output"]
            elif action == "CONTRAST":
                collected["contrast_text"] = result["output"]
            elif action == "ADVERSARIAL":
                collected["adversarial_result"] = result["output"]

        if action.startswith("STOP"):
            stopped = True
            collected["panic_log"].append(f"[{codon}] {info['desc']}")

        if result["error"]:
            collected["panic_log"].append(f"[{codon}] ⚠ {result['error']}")

    return {
        "execution_log": execution_log,
        "collected": collected,
        "has_simulation": has_simulation,
        "stopped": stopped,
        "actions_executed": [e["action"] for e in execution_log if e["result"] == "ok"],
    }


# ════════════════════════════════════════════════════════
# 动作处理器: 每个密码子动作 → 真实模块调用
# ════════════════════════════════════════════════════════

def _handle_start(ctx: dict) -> str:
    """START: 初始化管线上下文。"""
    query = ctx["query"]
    try:
        from tianshu_trust import TianshuClient
        tianshu = TianshuClient.get_state()
        tau_status = f"τ={tianshu.tau:.2f} {'🔒密封完好' if tianshu.seal_verified else '⚠封印异常'}"
    except Exception:
        tau_status = "τ=?(天枢不可达)"
    
    try:
        from method_router import MethodRouter
        method = MethodRouter.route(query)
        method_name = method.get("primary", "?")
    except Exception:
        method_name = "empirical"

    try:
        from worldview import WorldviewLayer
        wv = WorldviewLayer.detect(query)
        wv_name = wv.get("worldview_name", "?")
    except Exception:
        wv_name = "?"

    return (
        f"管线就绪 | 世界观:{wv_name} | 方法:{method_name} | 天枢:{tau_status}"
    )


def _handle_search(ctx: dict) -> str:
    """SEARCH: 执行网络搜索（带缓存）。"""
    query = ctx["query"]
    try:
        from search_cache import cache_get, cache_set, _make_key
        key = _make_key("search", query)
        cached, _ = cache_get(key)
        if cached:
            return cached
    except Exception:
        pass

    try:
        from special import smart_search
        result = smart_search(query)
        if result and len(str(result)) > 30:
            try:
                from search_cache import cache_set, _make_key
                cache_set(_make_key("search", query), str(result)[:1000], ttl=60)
            except Exception:
                pass
            return str(result)[:1000]
    except Exception:
        pass
    try:
        from web import search_and_summarize
        result = search_and_summarize(query)
        if result:
            return str(result)[:1000]
    except Exception:
        pass
    try:
        from meta_search import meta_search_to_context
        result = meta_search_to_context(query)
        if result:
            return str(result)[:1000]
    except Exception:
        pass
    return "(搜索无结果)"


def _handle_search_deep(ctx: dict) -> str:
    """SEARCH_DEEP: 深度研究拆解 (快速路径 — 最多8秒)。"""
    try:
        from deep import deep_research
        import signal
        
        result = [None]
        def _do():
            try:
                result[0] = deep_research(ctx["query"])
            except Exception:
                pass
        
        import threading
        t = threading.Thread(target=_do, daemon=True)
        t.start()
        t.join(timeout=8)
        
        if result[0] and result[0].get("synthesis"):
            return str(result[0]["synthesis"])[:800]
        if t.is_alive():
            return "(深度研究超时8s, 使用快速搜索替代: " + _handle_search(ctx)[:200] + ")"
    except Exception:
        pass
    return _handle_search(ctx)  # 回退到快速搜索


def _handle_search_meta(ctx: dict) -> str:
    """SEARCH_META: 元搜索自寻数据源。"""
    try:
        from meta_search import meta_search_to_context
        result = meta_search_to_context(ctx["query"])
        if result:
            return str(result)[:1000]
    except Exception:
        pass
    return "(元搜索无结果)"


def _handle_search_doc(ctx: dict) -> str:
    """SEARCH_DOC: 文档阅读。"""
    import re
    query = ctx["query"]
    urls = re.findall(r'(https?://[^\s]+)', query)
    if urls:
        try:
            from reader import read_document
            doc = read_document(urls[0])
            if doc.get("text"):
                return str(doc["text"])[:1000]
        except Exception:
            pass
    # 无URL时回退到标准搜索
    return _handle_search(ctx)


def _handle_simulate(ctx: dict) -> str:
    """SIMULATE: 科学方法假设→模拟→验证。（仅当查询匹配科学领域时执行，否则跳过）"""
    try:
        from deep import _detect_scientific_domain
        if not _detect_scientific_domain(ctx["query"]):
            return "(非科学领域, 跳过模拟)"

        from sci_method import scientific_research
        result = scientific_research(ctx["query"])
        if result:
            return str(result)[:1000]
    except Exception:
        pass
    try:
        from fiscal_sim import run_full_simulation
        result = run_full_simulation()
        if result:
            return str(result)[:800]
    except Exception:
        pass
    return "(模拟不可用)"


def _handle_simulate_sweep(ctx: dict) -> str:
    """SIMULATE_SWEEP: 参数敏感性扫描。"""
    try:
        from sci_method import parameter_sweep
        result = parameter_sweep(ctx["query"])
        if result:
            return str(result)[:800]
    except Exception:
        pass
    return "(参数扫描不可用)"


def _handle_simulate_compete(ctx: dict) -> str:
    """SIMULATE_COMPETE: 竞争假说并行验证。"""
    try:
        from sci_method import competing_hypotheses
        result = competing_hypotheses(ctx["query"])
        if result:
            return str(result)[:800]
    except Exception:
        pass
    return "(竞争假说不可用)"


def _handle_verify(ctx: dict) -> str:
    """VERIFY: 数据质量四闸验证。"""
    pipeline_ctx = ctx.get("pipeline_ctx", {})
    gate = pipeline_ctx.get("gate_result")
    if gate and hasattr(gate, 'overall_score'):
        return (
            f"质量闸:综合{gate.overall_score:.2f}"
            f"|真实{gate.authenticity.get('score',0) if hasattr(gate,'authenticity') and gate.authenticity else 0:.1f}"
            f"|完整{gate.completeness.get('score',0) if hasattr(gate,'completeness') and gate.completeness else 0:.1f}"
            f"|准确{gate.accuracy.get('score',0) if hasattr(gate,'accuracy') and gate.accuracy else 0:.1f}"
            + (f"|{'✓过' if not gate.blocked else '✗阻:'+str(gate.block_reason)[:40]}")
        )
    # 管线没有闸结果，尝试直接调
    try:
        from data_gate import DataGate
        collected = ctx.get("collected", {})
        data_text = collected.get("search_data", ctx["query"])
        gate = DataGate.check(
            data_text=data_text,
            data_requirements=["统计数据", "理论框架"],
            quality_threshold=0.6,
            query=ctx["query"],
            method_key="empirical",
        )
        return f"闸门:综合{gate.overall_score:.2f}|{'过' if not gate.blocked else '阻'}"
    except Exception as e:
        pass
    return "(闸门不可用)"


def _handle_verify_relation(ctx: dict) -> str:
    """VERIFY_RELATION: 关系完整性检查。"""
    try:
        from relation_integrity import RelationIntegrity
        ri = RelationIntegrity.check(ctx["query"])
        if ri:
            return str(ri)[:500]
    except Exception:
        pass
    return "(关系检查不可用)"


def _handle_verify_benford(ctx: dict) -> str:
    """VERIFY_BENFORD: Benford真实性检测。"""
    try:
        from voyager_auth import VoyagerAuthenticity
        collected = ctx.get("collected", {})
        data_text = collected.get("search_data", ctx["query"])
        result = VoyagerAuthenticity.verify(data_text, ctx["query"])
        if result:
            return f"Benford:{result.get('benford_score','?')}|熵场:{result.get('entropy_field','?')}|{result.get('verdict','?')}"
    except Exception:
        pass
    return "(Benford不可用)"


def _handle_verify_tau(ctx: dict) -> str:
    """VERIFY_TAU: τ天枢信任校准（10秒缓存）。"""
    try:
        from search_cache import cache_get, cache_set, _make_key
        key = _make_key("tau", "state")
        cached, _ = cache_get(key)
        if cached:
            return cached
    except Exception:
        pass

    try:
        from tianshu_trust import TianshuClient, TauTrust
        tianshu = TianshuClient.get_state()
        threshold = TauTrust.calibrate_threshold(0.6, tianshu)
        result = "τ=%.2f|封印=%s|校准阈值=%.2f" % (
            tianshu.tau,
            "完好" if tianshu.seal_verified else "异常",
            threshold
        )
        try:
            from search_cache import cache_set, _make_key
            cache_set(_make_key("tau", "state"), result, ttl=10)
        except Exception:
            pass
        return result
    except Exception:
        pass
    return "(τ天枢不可达)"


def _handle_contrast(ctx: dict) -> str:
    """CONTRAST: 世界观对比分析。"""
    try:
        from worldview_contrast import WorldviewContrast
        from worldview import WorldviewLayer
        wv = WorldviewLayer.detect(ctx["query"])
        collected = ctx.get("collected", {})
        contrast = WorldviewContrast.generate(
            query=ctx["query"],
            detected_wv=wv,
            method={"primary": "empirical", "data_requirements": [], "quality_threshold": 0.6},
            research_data=collected.get("search_data", ""),
        )
        if contrast and not contrast.get("skip"):
            return str(contrast.get("full_report", ""))[:800]
    except Exception:
        pass
    return "(对比不可用)"


def _handle_adversarial(ctx: dict) -> str:
    """ADVERSARIAL: 对抗验证。"""
    try:
        from adversarial import AdversarialVerifier
        result = AdversarialVerifier.attack(ctx["query"])
        if result:
            return str(result)[:500]
    except Exception:
        pass
    return "(对抗不可用)"


def _handle_iterate(ctx: dict) -> str:
    """ITERATE: 迭代优化。"""
    try:
        from iterative_optimizer import IterativeOptimizer
        result = IterativeOptimizer.optimize(
            query=ctx["query"],
            gate_result=ctx.get("pipeline_ctx", {}).get("gate_result"),
            method={"primary": "empirical", "quality_threshold": 0.6},
            data_text=ctx.get("collected", {}).get("search_data", ""),
        )
        if result and result.get("escaped"):
            return f"逃逸成功:策略={result.get('best_strategy','?')}"
    except Exception:
        pass
    return "(迭代不可用)"


def _handle_stop_conclude(ctx: dict) -> str:
    """STOP_CONCLUDE: 组装最终输出。"""
    collected = ctx.get("collected", {})
    parts = [
        "[🏁 基因表达完成]",
        f"搜索数据: {len(collected.get('search_data',''))}字符",
    ]
    if collected.get("simulation_result"):
        parts.append(f"模拟结果: {len(collected.get('simulation_result',''))}字符")
    if collected.get("verification_result"):
        parts.append(f"验证结果: ✓")
    if collected.get("contrast_text"):
        parts.append(f"对比结果: ✓")
    if collected.get("panic_log"):
        parts.append(f"日志: {'|'.join(collected['panic_log'][:3])}")
    return "\n".join(parts)


def _handle_stop_seal(ctx: dict) -> str:
    """STOP_SEAL: 输出并封印到天枢账本。"""
    try:
        from tianshu_trust import TianshuClient
        tianshu = TianshuClient.get_state()
        if tianshu.seal_verified:
            collected = ctx.get("collected", {})
            TianshuClient.seal_conclusion(
                f"基因执行结果:搜索={len(collected.get('search_data',''))}字符",
                metadata={"source": "genome_pipeline", "action": "STOP_SEAL"}
            )
            return f"🔒 已封印到天枢 τ={tianshu.tau:.2f}"
    except Exception:
        pass
    return "(封印不可用)"


# ════════════════════════════════════════════════════════
# 动作处理器注册表
# ════════════════════════════════════════════════════════

_ACTION_HANDLERS = {
    "START":            _handle_start,
    "START_ALT":        _handle_start,
    "SEARCH":           _handle_search,
    "SEARCH_DEEP":      _handle_search_deep,
    "SEARCH_META":      _handle_search_meta,
    "SEARCH_DOC":       _handle_search_doc,
    "SIMULATE":         _handle_simulate,
    "SIMULATE_SWEEP":   _handle_simulate_sweep,
    "SIMULATE_COMPETE": _handle_simulate_compete,
    "SIMULATE_FISCAL":  _handle_simulate,
    "VERIFY":           _handle_verify,
    "VERIFY_RELATION":  _handle_verify_relation,
    "VERIFY_BENFORD":   _handle_verify_benford,
    "VERIFY_ENTROPY":   _handle_verify_benford,
    "VERIFY_TAU":       _handle_verify_tau,
    "CONTRAST":         _handle_contrast,
    "ADVERSARIAL":      _handle_adversarial,
    "ITERATE":          _handle_iterate,
    "PAIR_VERIFY":      _handle_verify,
    "PAIR_EVIDENCE":    _handle_search,
    "MISMATCH_FIX":     _handle_verify,
    "STOP_CONCLUDE":    _handle_stop_conclude,
    "STOP_CONTRAST":    _handle_contrast,
    "STOP_SEAL":        _handle_stop_seal,
}
