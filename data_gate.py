"""
数据质量闸 — 三重验证：真实性 · 完整性 · 准确性

在研究开始前，所有数据必须通过三道闸门。
任一闸门失败 → 阻断深化研究 → 返回缺陷报告。

架构:
  DataGate.check(data, method_requirements) -> GateResult
    ├─ Gate 1: 真实性 (Authenticity)
    │   ├─ 来源可信度评分
    │   ├─ 天枢验证（如有）
    │   └─ 阈值: 0.6
    ├─ Gate 2: 完整性 (Completeness)
    │   ├─ 对比方法所需字段 vs 实际数据
    │   ├─ 缺口检测 → 自动补搜
    │   └─ 阈值: 0.5
    └─ Gate 3: 准确性 (Accuracy)
        ├─ 多源交叉验证
        ├─ 矛盾检测
        ├─ 时效性检查
        └─ 阈值: 0.6
"""

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent
DATA_DIR = BASE / "data" / "data_gate"
DATA_DIR.mkdir(parents=True, exist_ok=True)

from voyager_llm import safe_llm_call as _llm_call
from relation_integrity import RelationVerifier, SimulationIntegrity
from voyager_auth import VoyagerAuthenticity
from search_terms import build_targeted_search_queries


# ════════════════════════════════════════════════════════
# 数据类型
# ════════════════════════════════════════════════════════

@dataclass
class GateResult:
    """数据质量闸门检查结果。"""
    passed: bool = False                # 是否通过所有闸门
    overall_score: float = 0.0          # 综合质量分 (0-1)
    
    # 各闸门详情
    authenticity: dict = field(default_factory=dict)  # {score, issues, sources}
    completeness: dict = field(default_factory=dict)  # {score, missing, filled}
    accuracy: dict = field(default_factory=dict)      # {score, contradictions, stale}
    relation_integrity: dict = field(default_factory=dict)  # {score, violations, passed, failed}
    
    # 阻断信息
    blocked: bool = False
    block_reason: str = ""
    block_gate: str = ""
    
    # 修复信息
    auto_fixed: bool = False
    fix_log: list = field(default_factory=list)


# ════════════════════════════════════════════════════════
# 数据质量闸门
# ════════════════════════════════════════════════════════

class DataGate:
    """数据质量三重验证闸门。"""

    # 可信来源域名权重
    TRUSTED_SOURCES = {
        # 政府/官方
        "gov.cn": 0.95, "stats.gov.cn": 1.0, "pbc.gov.cn": 0.95,
        "mof.gov.cn": 0.95, "ndrc.gov.cn": 0.95,
        # 国际组织
        "imf.org": 0.95, "worldbank.org": 0.95, "bis.org": 0.95,
        "oecd.org": 0.90, "un.org": 0.90,
        # 学术
        "arxiv.org": 0.85, "scholar.google": 0.80,
        "ssrn.com": 0.85, "nber.org": 0.90,
        # 财经
        "bloomberg.com": 0.80, "reuters.com": 0.80,
        "ft.com": 0.80, "wsj.com": 0.75,
        # 中文财经
        "eastmoney.com": 0.65, "sina.com.cn": 0.55,
        "hexun.com": 0.60, "cninfo.com.cn": 0.85,
        # 低信任
        "zhihu.com": 0.40, "weibo.com": 0.30,
        "tieba.baidu.com": 0.25,
    }

    @classmethod
    def check(
        cls,
        data_text: str,
        data_requirements: list[str],
        quality_threshold: float = 0.6,
        query: str = "",
        worldview_key: str = "",
        method_key: str = "",
    ) -> GateResult:
        """
        数据通过三道闸门。

        参数:
          data_text: 搜索/文档获取的原始数据文本
          data_requirements: 方法路由要求的数据类型列表
          quality_threshold: 方法要求的最低质量分
          query: 原始问题（用于LLM验证）

        返回:
          GateResult — 包含通过状态和详细检查报告
        """
        result = GateResult()
        fix_log = []

        # ─── 数据预处理 ───
        if not data_text or len(data_text.strip()) < 20:
            result.blocked = True
            result.block_reason = "无有效数据输入"
            result.block_gate = "authenticity"
            result.overall_score = 0.0
            return result

        # ─── 闸门1: 真实性（织星φ分析） ───
        auth = cls._check_authenticity_voyager(data_text, query)
        result.authenticity = auth
        result.overall_score = auth["score"]

        if auth["score"] < 0.3:
            result.blocked = True
            result.block_reason = f"数据源可信度过低 ({auth['score']:.1f})"
            result.block_gate = "authenticity"
            return result

        # ─── 闸门2: 完整性 ───
        comp = cls._check_completeness(data_text, data_requirements, query)
        result.completeness = comp

        # 自动补搜缺口
        if comp["missing"] and comp["score"] < 0.5:
            filled = cls._auto_fill_gaps(
                comp["missing"], query, worldview_key, method_key
            )
            if filled:
                data_text = f"{data_text}\n\n[自动补全]\n{filled}"
                fix_log.append(f"自动补全 {len(comp['missing'])} 个缺口")
                result.auto_fixed = True
                # 重新检查完整性
                comp = cls._check_completeness(data_text, data_requirements, query)
                result.completeness = comp

        result.fix_log = fix_log

        # 重新计算综合分
        auth_w = 0.30
        comp_w = 0.20
        acc_w = 0.30
        rel_w = 0.20

        # ─── 闸门3: 准确性 ───
        acc = cls._check_accuracy(data_text, query)
        result.accuracy = acc

        # ─── 闸门4: 关系完整性 ───
        rel = RelationVerifier.verify(
            data_text,
            worldview_key="",
            method_key="",
        )
        result.relation_integrity = {
            "score": rel["overall_score"],
            "violations": rel["violations"],
            "passed": rel["passed_count"],
            "failed": rel["failed_count"],
            "suggestions": rel["suggestions"],
        }

        # 关系完整性失败 → 降级
        if rel["overall_score"] < 0.4:
            result.blocked = True
            result.block_reason = (
                f"数据关系完整性过低 ({rel['overall_score']:.2f}) — "
                f"{rel['failed_count']}个关系约束被违反"
            )
            result.block_gate = "关系完整性"

        # 最终综合分
        result.overall_score = (
            auth_w * auth["score"]
            + comp_w * comp["score"]
            + acc_w * acc["score"]
            + rel_w * rel["overall_score"]
        )

        # ─── 判定 ───
        if result.overall_score >= quality_threshold:
            result.passed = True
        else:
            result.blocked = True
            result.block_reason = (
                f"数据质量不足 (综合{result.overall_score:.2f} < 阈值{quality_threshold})"
            )
            # 找出最短板
            scores = {
                "真实性": auth["score"],
                "完整性": comp["score"],
                "准确性": acc["score"],
            }
            weakest = min(scores.keys(), key=lambda k: scores[k])
            result.block_gate = weakest

        return result

    # ─── 闸门1: 真实性（织星φ分析） ───

    @classmethod
    def _check_authenticity_voyager(cls, data_text: str, query: str = "") -> dict:
        """织星φ分析 + URL信任辅证。"""
        # 主检测: 织星三合一
        voyager_result = VoyagerAuthenticity.verify(data_text, query)

        # 辅证: URL来源评分
        url_auth = cls._check_authenticity(data_text)

        # 融合评分: 织星为主(0.7), URL为辅(0.3)
        voyager_score = voyager_result["authenticity_score"]
        url_score = url_auth.get("score", 0.5)
        combined_score = 0.7 * voyager_score + 0.3 * url_score

        issues = url_auth.get("issues", [])
        if not voyager_result["passed"]:
            issues.append(f"织星真实性: {voyager_result['verdict']}")

        return {
            "score": round(combined_score, 2),
            "voyager_score": voyager_score,
            "url_score": url_score,
            "issues": issues,
            "sources_found": url_auth.get("sources_found", 0),
            "trusted_sources": url_auth.get("trusted_sources", 0),
            "benford": voyager_result.get("benford", {}),
            "entropy_field": voyager_result.get("entropy", {}),
            "voyager_verdict": voyager_result.get("verdict", ""),
        }

    @classmethod
    def _check_authenticity(cls, data_text: str) -> dict:
        """检查数据来源可信度。"""
        issues = []

        # 提取URL
        urls = re.findall(r'https?://[^\s\)\]>"]+', data_text)

        if not urls:
            # 没有URL — 可能是模型内在知识或匿名数据
            return {
                "score": 0.5,
                "issues": ["无明确数据源URL，来源不可追溯"],
                "sources_found": 0,
                "trusted_sources": 0,
                "detail": "数据缺乏可验证来源",
            }

        # 计算来源分数
        source_scores = []
        trusted = 0
        for url in urls:
            score = cls._score_url(url)
            source_scores.append(score)
            if score >= 0.7:
                trusted += 1

        avg_score = sum(source_scores) / len(source_scores) if source_scores else 0.5

        if trusted == 0:
            issues.append(f"所有{len(urls)}个来源可信度均低于0.7")
        if len(urls) < 2:
            issues.append("仅单源数据，缺乏交叉验证基础")

        return {
            "score": round(avg_score, 2),
            "issues": issues,
            "sources_found": len(urls),
            "trusted_sources": trusted,
            "source_scores": dict(zip(urls[:5], [round(s, 2) for s in source_scores[:5]])),
        }

    @classmethod
    def _score_url(cls, url: str) -> float:
        """根据域名估算来源可信度。"""
        for domain, score in cls.TRUSTED_SOURCES.items():
            if domain in url:
                return score
        return 0.45  # 未知来源默认中等偏低

    # ─── 闸门2: 完整性 ───

    @classmethod
    def _check_completeness(
        cls, data_text: str, required: list[str], query: str
    ) -> dict:
        """检查是否覆盖了方法所需的所有数据库类型。"""
        text_lower = data_text.lower()
        found = []
        missing = []

        for req in required:
            # 用关键词映射检查覆盖度
            kw_map = {
                "统计数据": ["数字", "数据", "统计", "同比", "环比", "%", "亿元", "万亿"],
                "官方报告": ["官方", "报告", "年报", "公报", "白皮书", "统计"],
                "学术论文": ["论文", "研究", "学术", "期刊", "doi", "arxiv"],
                "时效性数据": ["2025", "2026", "最新", "今日", "本周", "今年"],
                "参数空间": ["参数", "变量", "因子", "系数", "权重"],
                "初始条件": ["初始", "基准", "基线", "默认", "假设"],
                "历史校准数据": ["历史", "趋势", "历年", "过去", "回溯"],
                "定义": ["定义", "是指", "指的是", "概念", "含义"],
                "公理": ["公理", "定理", "假设", "前提", "推论"],
                "已有理论框架": ["框架", "模型", "体系", "理论", "范式"],
                "对照组数据": ["对照", "对比", "实验组", "控制组", "基线"],
                "竞争性解释": ["争议", "质疑", "另一种", "反对", "不同"],
                "差异指标": ["差异", "差距", "区别", "delta", "变化"],
                "原始账本": ["账本", "报表", "财务", "利润", "资产", "负债"],
                "审计记录": ["审计", "审查", "核查", "核实"],
                "时序数据": ["时间", "季度", "年度", "趋势", "变化"],
                "多源文献": ["文献", "资料", "参考", "来源", "引"],
                "历史脉络": ["历史", "演变", "发展", "阶段", "历程"],
                "不同视角": ["角度", "观点", "认为", "主张", "立场"],
            }

            keywords = kw_map.get(req, [req])
            if any(k in text_lower for k in keywords):
                found.append(req)
            else:
                missing.append(req)

        score = len(found) / max(len(required), 1)
        return {
            "score": round(min(score, 1.0), 2),
            "found": found,
            "missing": missing,
            "required_total": len(required),
            "coverage_pct": round(score * 100, 1),
        }

    @classmethod
    def _auto_fill_gaps(
        cls, missing: list[str], query: str,
        worldview_key: str = "", method_key: str = "",
    ) -> Optional[str]:
        """
        尝试自动填补数据缺口 — 使用专业搜索词提高命中率。

        不再"缺什么搜什么"，而是:
          1. 将通用需求翻译为专业检索词
          2. 附加优先站点限定
          3. 逐条独立搜索（不合并，避免互相污染）
        """
        if not query:
            return None

        # 使用专业搜索词生成多个精准查询
        targeted_queries = build_targeted_search_queries(
            missing, worldview_key, method_key, query
        )

        if not targeted_queries:
            return None

        # 逐条搜索，收集结果
        all_results = []
        from web import search_and_summarize

        for tq in targeted_queries[:5]:  # 最多5条查询
            try:
                result = search_and_summarize(tq)
                if result and len(result) > 20:
                    all_results.append(f"[搜索: {tq[:60]}]\n{result[:500]}")
            except Exception:
                pass

        # 常规搜索也回退
        if not all_results:
            try:
                result = search_and_summarize(f"{' '.join(missing)} {query}")
                if result and len(result) > 30:
                    all_results.append(result)
            except Exception:
                pass

        # 元搜索回退
        if not all_results:
            try:
                from meta_search import meta_search_to_context
                result = meta_search_to_context(f"{' '.join(missing)} {query[:100]}")
                if result and len(result) > 30:
                    all_results.append(result)
            except Exception:
                pass

        return "\n\n---\n\n".join(all_results) if all_results else None

    # ─── 闸门3: 准确性 ───

    @classmethod
    def _check_accuracy(cls, data_text: str, query: str = "") -> dict:
        """多源交叉验证 + 矛盾检测 + 时效性检查。"""

        # ① 提取数字并检查一致性
        numbers = re.findall(r'(\d+(?:\.\d+)?)\s*(万亿|亿|万|%|元|美元)', data_text)
        contradictions = []

        # 检查重复出现的相同指标是否有矛盾值
        # 简化版：找相同上下文的数字分组
        value_groups = {}
        for val, unit in numbers:
            # 找这个数字附近的上下文词
            pos = data_text.find(val)
            context = data_text[max(0, pos - 20):pos + 30]
            key = f"{unit}_{context[:15]}"
            if key in value_groups:
                prev_val = value_groups[key]
                try:
                    if abs(float(val) - float(prev_val)) / max(float(prev_val), 0.01) > 0.1:
                        contradictions.append({
                            "context": context[:30],
                            "values": [prev_val, val],
                            "unit": unit,
                        })
                except ValueError:
                    pass
            else:
                value_groups[key] = val

        # ② 时效性检查
        current_year = 2026
        year_mentions = re.findall(r'(20\d{2})年', data_text)
        years = [int(y) for y in year_mentions if 2000 <= int(y) <= current_year + 1]
        stale_issues = []

        if years:
            max_year = max(years)
            age = current_year - max_year
            if age >= 3:
                stale_issues.append(f"最新数据年份为{max_year}年（{age}年前），可能过时")
            elif age >= 1:
                stale_issues.append(f"数据为{max_year}年（{age}年前），时效性一般")

        if not years and not any(k in data_text for k in ["2025", "2026", "最新", "今日"]):
            stale_issues.append("无明确年份标注，数据时效性不可判断")

        # ③ LLM辅助矛盾检测 (仅深度数据>500字)
        llm_contradictions = []
        if data_text and query and len(data_text) > 500:
            try:
                system = """你是数据质量审查员。检查以下数据是否有内部矛盾。
输出格式（如有矛盾，每行一条；如无矛盾，输出"无"）：
矛盾描述（简洁）"""

                result = _llm_call(
                    system,
                    f"问题: {query}\n\n数据:\n{data_text[:2000]}",
                    max_tokens=150,
                )
                if result and "无" not in result[:5]:
                    for line in result.strip().split("\n"):
                        if len(line.strip()) > 5:
                            llm_contradictions.append(line.strip())
            except Exception:
                pass

        all_contradictions = contradictions + [
            {"llm_detected": c} for c in llm_contradictions
        ]

        # 计算准确性分
        base_score = 0.8
        penalty = 0.1 * len(all_contradictions)
        penalty += 0.15 * len(stale_issues)
        accuracy = max(0.0, base_score - penalty)

        return {
            "score": round(accuracy, 2),
            "contradictions": all_contradictions,
            "contradiction_count": len(all_contradictions),
            "stale_issues": stale_issues,
            "years_found": years,
            "freshest_year": max(years) if years else None,
        }


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def gate_data(
    data_text: str,
    data_requirements: list[str],
    quality_threshold: float = 0.6,
    query: str = "",
) -> GateResult:
    """数据通过质量闸门。"""
    return DataGate.check(data_text, data_requirements, quality_threshold, query)


# ═══ 自检 ═══
if __name__ == "__main__":
    # 模拟一份搜索结果
    test_data = """
    根据国家统计局2025年数据，中国GDP增长率为5.2%。
    财政部报告显示2024年赤字率为3.0%。
    东方财富网报道，2024年财政支出同比增长6.1%。
    新浪财经称，2024年GDP增长5.0%。
    """

    result = DataGate.check(
        test_data,
        data_requirements=["统计数据", "官方报告", "时效性数据", "学术论文"],
        quality_threshold=0.6,
        query="中国财政政策效果分析",
    )

    print(f"通过: {result.passed}")
    print(f"综合分: {result.overall_score}")
    print(f"真实性: {result.authenticity['score']} (来源{result.authenticity['sources_found']}个, 可信{result.authenticity['trusted_sources']}个)")
    print(f"完整性: {result.completeness['score']} (找到{len(result.completeness['found'])}个, 缺失{len(result.completeness['missing'])}个)")
    print(f"准确性: {result.accuracy['score']} (矛盾{result.accuracy['contradiction_count']}条)")
    if result.blocked:
        print(f"阻断: {result.block_reason}")
        print(f"故障闸门: {result.block_gate}")
    if result.auto_fixed:
        print(f"自动修复: {result.fix_log}")
