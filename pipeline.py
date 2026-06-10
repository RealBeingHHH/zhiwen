# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Copyright (c) 2026 知纹 (Zhiwen) Project

"""
管线编排器 — chat流程的完整编排

从server.py提取, 包含:
  - run_pipeline(): 完整的20层管线执行
  - 返回: pipeline_context (所有层的结果)

server.py 现在只需:
  from pipeline import run_pipeline
  context = run_pipeline(req.message)
  reply = llm_backend.generate(context)
"""

import time, hashlib, re as _re
from typing import Optional

from worldview import WorldviewLayer
from method_router import MethodRouter
from config import TIANSHU_URL
from tianshu_trust import TianshuClient, TauTrust
from niannian_weight import NiannianEta, rank_facts
from storage_manager import StorageManager
from matrix_store import matrix_search
from cross_session import share_knowledge_across_sessions
from deep_rounds import DeepRounds
from route_fast import RouteLevel
from feedback_loop import FeedbackLoop
from data_gate import DataGate, GateResult
from deep import deep_research, _detect_scientific_domain
from web import search_and_summarize
from special import smart_search
from meta_search import meta_search_to_context
from analyze import analyze_and_score, fill_gaps
from reader import read_document
from sci_method import scientific_research
from worldview_contrast import WorldviewContrast
from assurance_panel import AssurancePanel
from causal_chain import CausalTracer
from iterative_optimizer import IterativeOptimizer
from uncertainty import UncertaintyPropagator


# ════════════════════════════════════════════════════════
# 全局错误收集
# ════════════════════════════════════════════════════════

_pipeline_errors = []

def pipeline_error(layer: str, error: Exception, context: str = "") -> None:
    msg = f"[{layer}] {type(error).__name__}: {str(error)[:100]}"
    if context:
        msg += f" | {context[:80]}"
    _pipeline_errors.append(msg)
    print(f"⚠ Pipeline error: {msg}")


# ════════════════════════════════════════════════════════
# 核心管线
# ════════════════════════════════════════════════════════

def run_pipeline(query: str, skip_layers: set = None) -> dict:
    """
    执行完整研究管线，返回所有上下文。

    返回:
      {
        message: str,       # 组合后的最终消息(给LLM)
        wv, method, gate_result, panel_text, trace_text,
        contrast_text, uncertainty_bounds, ...
      }
    """
    global _pipeline_errors
    _pipeline_errors = []

    if skip_layers is None:
        skip_layers = set()

    ctx = {"query": query, "skip_layers": skip_layers}

    # ═══ 知识图谱检索 ═══
    try:
        kg_facts = matrix_search(query, top_k=5)
        kg_facts = rank_facts(kg_facts)
        for f in kg_facts:
            NiannianEta.gaze(f.get("node_id", ""), weight=1, context="retrieval")

        kg_context = ""
        if kg_facts:
            kg_context = "[知识图谱 · 已验证事实]\n"
            for f in kg_facts:
                kg_context += (
                    f"  · {f.get('fact', '')[:100]} "
                    f"(置信度{f.get('effective_confidence', 0):.2f}, "
                    f"{f.get('age_days', 0):.0f}天前)\n"
                )
            kg_context += "如与当前问题相关，优先采信已验证事实。\n\n"

        cross_facts = share_knowledge_across_sessions(query)
        if cross_facts:
            cross_context = "[跨对话共享 · 未重验 · 辅助参考]\n"
            for cf in cross_facts[:3]:
                if isinstance(cf, dict):
                    tag = cf.get("shared_tag", "[共享]")
                    cross_context += (
                        f"  {tag} {cf.get('fact', '')[:100]}"
                        f"(来源:{cf.get('source_session', '?')[:6]}, 相似度{cf.get('similarity',0):.2f})\n"
                    )
                else:
                    cross_context += f"  {cf}\n"
            cross_context += "以上为辅助参考，不可替代本对话的独立验证。\n\n"
            kg_context += cross_context

        ctx["kg_context"] = kg_context
    except Exception as e:
        pipeline_error("知识图谱检索", e)
        ctx["kg_context"] = ""

    # ═══ 世界观 + 方法论 ═══
    if "worldview" not in skip_layers:
        try:
            wv = WorldviewLayer.detect(query)
            ctx["wv"] = wv

            overrides = FeedbackLoop.get_overrides(query)
            learned_method = StorageManager.retrieve_method_suggestion(query)
            method = MethodRouter.route(query)

            if overrides.get("preferred_method"):
                method["primary"] = overrides["preferred_method"]
            elif learned_method and learned_method != method.get("primary"):
                method["primary"] = learned_method

            ctx["method"] = method
        except Exception as e:
            pipeline_error("世界观/方法论", e)

    # ═══ 数据收集 ═══
    if "data_gate" not in skip_layers:
        try:
            method = ctx.get("method", {"primary": "empirical", "data_requirements": ["统计数据"], "quality_threshold": 0.6})
            search_context = ""

            if method["primary"] in ("theoretical", "synthesis"):
                deep_result = deep_research(query)
                if deep_result and deep_result.get("synthesis"):
                    search_context = deep_result["synthesis"]
            else:
                smart_result = smart_search(query)
                search_context = smart_result if (smart_result and len(smart_result) > 30) else search_and_summarize(query)
                if not search_context or len(search_context) < 50:
                    search_context = meta_search_to_context(query) or ""
                if search_context:
                    search_context = fill_gaps(query, search_context) or search_context

            ctx["search_context"] = search_context
            ctx["data_text"] = search_context or ""
        except Exception as e:
            pipeline_error("数据收集", e)
            ctx["search_context"] = ""
            ctx["data_text"] = ""

    # ═══ 数据质量闸 + τ校准 ═══
    if "data_gate" not in skip_layers:
        try:
            tianshu = TianshuClient.get_state()
            method = ctx.get("method", {"quality_threshold": 0.6, "data_requirements": []})
            tau_threshold = TauTrust.calibrate_threshold(method.get("quality_threshold", 0.6), tianshu)

            gate_result = DataGate.check(
                data_text=ctx.get("data_text", ""),
                data_requirements=method.get("data_requirements", []),
                quality_threshold=tau_threshold,
                query=query,
                worldview_key=ctx.get("wv", {}).get("worldview_key", ""),
                method_key=method.get("primary", ""),
            )
            ctx["gate_result"] = gate_result
            ctx["tianshu"] = tianshu
            ctx["tau_threshold"] = tau_threshold

            # ═══ 迭代优化: 闸门阻断→自动换路逃逸 ═══
            if gate_result and gate_result.blocked and "iterative" not in skip_layers:
                try:
                    from iterative_optimizer import IterativeOptimizer
                    escape = IterativeOptimizer.optimize(
                        query=query,
                        gate_result=gate_result,
                        method=method,
                        wv=ctx.get("wv", {}),
                        data_text=ctx.get("data_text", ""),
                    )
                    ctx["escape_result"] = escape
                    if escape.get("escaped"):
                        # 逃逸成功 → 用新数据重新过闸
                        new_data = escape.get("new_data_text", "")
                        if new_data:
                            gate_result = DataGate.check(
                                data_text=new_data,
                                data_requirements=method.get("data_requirements", []),
                                quality_threshold=tau_threshold,
                                query=query,
                                worldview_key=ctx.get("wv", {}).get("worldview_key", ""),
                                method_key=method.get("primary", ""),
                            )
                            ctx["gate_result"] = gate_result
                            ctx["data_text"] = new_data
                            ctx["search_context"] = new_data
                except Exception as e:
                    pipeline_error("迭代优化", e)

        except Exception as e:
            pipeline_error("数据质量闸", e)

    # ═══ 不确定性 + 增强层 ═══
    if "uncertainty" not in skip_layers:
        try:
            gate = ctx.get("gate_result")
            if gate:
                uncertainty_bounds = UncertaintyPropagator.quantify(
                    gate_result=gate, nominal_value=1.0,
                    has_simulation=bool(_detect_scientific_domain(query)),
                )
                ctx["uncertainty"] = uncertainty_bounds
        except Exception as e:
            pipeline_error("不确定性", e)

    # ═══ 世界观对比 ═══
    contrast_text = ""
    if "contrast" not in skip_layers:
        try:
            contrast = WorldviewContrast.generate(
                query=query,
                detected_wv=ctx.get("wv", {}),
                method=ctx.get("method", {}),
                research_data=ctx.get("data_text", ""),
            )
            if not contrast.get("skip"):
                contrast_text = contrast.get("full_report", "")
            ctx["contrast"] = contrast
        except Exception as e:
            pipeline_error("世界观对比", e)

    # ═══ 保证面板 + 追溯链 ═══
    if "panel" not in skip_layers:
        try:
            gate = ctx.get("gate_result")
            wv = ctx.get("wv", {})
            method_ = ctx.get("method", {"primary": "unknown", "data_requirements": [], "quality_threshold": 0.6})
            contrast = ctx.get("contrast")

            if gate:
                panel_text = AssurancePanel.from_chat_context_full(
                    wv=wv, method=method_, gate_result=gate, contrast=contrast,
                )
                trace_text = CausalTracer.build_trace_map(
                    wv=wv, method=method_, gate_result=gate,
                    data_text=ctx.get("data_text", ""), contrast=contrast,
                )
                ctx["panel_text"] = panel_text
                ctx["trace_text"] = trace_text
        except Exception as e:
            pipeline_error("保证面板", e)

    # ═══ 组装最终消息 ═══
    ctx["message"] = _build_message(query, ctx, contrast_text)

    return ctx


def _build_message(query: str, ctx: dict, contrast_text: str) -> str:
    """组装发送给LLM的最终消息。"""
    method = ctx.get("method", {"primary": "unknown", "quality_threshold": 0.6})
    gate = ctx.get("gate_result")
    tianshu = ctx.get("tianshu")
    wv = ctx.get("wv", {})
    tau_threshold = ctx.get("tau_threshold", 0.6)
    uncertainty = ctx.get("uncertainty")

    parts = [query]

    # KG上下文
    if ctx.get("kg_context"):
        parts.append(ctx["kg_context"])

    # τ行
    if tianshu:
        parts.append(
            f"τ天枢: {'🔒封印完好' if tianshu.seal_verified else '⚠封印异常'} "
            f"τ={tianshu.tau:.2f} | 阈值{tau_threshold}"
        )

    # 面板
    if ctx.get("panel_text"):
        parts.append(ctx["panel_text"])

    # 追溯
    if ctx.get("trace_text"):
        parts.append(ctx["trace_text"])

    # 世界观+方法
    if wv:
        parts.append(f"[🌌 世界观: {wv.get('worldview_name', '')}]")

    if method:
        parts.append(f"[🧭 方法: {method.get('primary', '')}]")

    # 数据
    if ctx.get("search_context"):
        parts.append(f"[数据收集结果]\n{ctx['search_context']}")

    # 指令
    gate_score = gate.overall_score if gate else 0
    method_threshold = method.get('quality_threshold', 0.6)
    blocked = gate.blocked if gate else False

    instructions = [
        "【强制】每个结论标注追溯链 [追溯: 公理→%s→闸%s] 链强度 [链:强/中/弱]" % (
            method.get('primary', '方法'),
            '阻' if gate_score < method_threshold else '过'
        ),
        "【强制】回答末尾对抗自检: 生成2个反例攻击自己的结论 → [对抗: 攻击描述→存活/致命]",
        "开篇标注: 世界观、方法、数据完整度、置信度。",
        "在选定框架内推理。数据不足诚实说明。不确定的数据标注「待验证」。",
    ]

    # 闸门阻断 → 逃逸报告注入
    escape = ctx.get("escape_result")
    if escape:
        if escape.get("needed"):
            instructions.insert(0, "【迭代逃逸】原始数据闸门阻断 → 自动尝试换方法/换数据源/降精度")
            if escape.get("escaped"):
                instructions.insert(1, "逃逸成功 (策略:%s) → 使用替代数据源" % escape.get("best_strategy", "?"))
            else:
                instructions.insert(1, "逃逸失败 (%d次尝试均失败) → 以下结论基于不完整数据" % escape.get("attempts", 0))

    if blocked:
        instructions.append("⚠ 数据质量低于阈值，以下结论需标注[数据不足]")

    parts.append("\n".join(instructions))

    return "\n\n".join(parts)


def pipeline_errors() -> list:
    return _pipeline_errors
