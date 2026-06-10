"""
关系完整性验证 — 数据三性的深层检测

数据不仅有来源和覆盖——数据之间有内在的数学关系。
会计等式、部门平衡、守恒律、边界条件——这些关系是数据真实性的钢筋。
关系断裂 = 数据不可信。

架构:
  RelationSchema: 一组数学关系 (等式/不等式/边界)
  RelationVerifier: 从文本中提取数字，验证关系是否成立
  SimulationIntegrity: 模拟输入/输出必须满足方法论预设关系

核心原则:
  前提错 → 结论不可能对
  数据错 → 结果不可能对
"""

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

BASE = Path(__file__).parent

from voyager_llm import safe_llm_call as _llm_call


# ════════════════════════════════════════════════════════
# 关系Schema定义
# ════════════════════════════════════════════════════════

@dataclass
class Relation:
    """一条数据关系约束。"""
    name: str                    # 关系名
    formula: str                 # 公式描述
    category: str                # 真实性/完整性/准确性
    check_fn: Optional[Callable] = None  # 可执行检查函数
    severity: str = "error"      # error/warning/info
    worldview_tags: list = field(default_factory=list)  # 适用世界观
    method_tags: list = field(default_factory=list)      # 适用方法论

@dataclass
class RelationSchema:
    """一组数据关系约束集。"""
    name: str
    relations: list[Relation]
    worldview: str = ""
    methodology: str = ""

# ════════════════════════════════════════════════════════
# 预定义关系库
# ════════════════════════════════════════════════════════

# ── 会计基本关系 ──
ACCOUNTING_RELATIONS = [
    Relation(
        name="会计恒等式",
        formula="资产 = 负债 + 所有者权益",
        category="真实性",
        worldview_tags=["forensic", "empirical"],
        method_tags=["forensic", "empirical"],
        severity="error",
    ),
    Relation(
        name="借贷平衡",
        formula="借方总额 = 贷方总额",
        category="真实性",
        worldview_tags=["forensic"],
        method_tags=["forensic"],
        severity="error",
    ),
    Relation(
        name="留存收益等式",
        formula="Δ留存收益 = 净利润 - 分红",
        category="准确性",
        worldview_tags=["forensic", "empirical"],
        method_tags=["forensic", "empirical"],
    ),
    Relation(
        name="利润表钩稽",
        formula="营业收入 - 营业成本 - 费用 = 营业利润",
        category="准确性",
        worldview_tags=["forensic"],
        method_tags=["forensic"],
    ),
]

# ── 宏观经济关系 ──
MACRO_RELATIONS = [
    Relation(
        name="GDP恒等式",
        formula="GDP = C + I + G + (X - M)",
        category="完整性",
        worldview_tags=["neoclassical", "mmt", "empirical"],
        method_tags=["empirical", "comparative"],
        severity="warning",
    ),
    Relation(
        name="MMT部门平衡",
        formula="(S - I) = (G - T) + (X - M)",
        category="真实性",
        worldview_tags=["mmt"],
        method_tags=["empirical", "theoretical"],
        severity="error",
    ),
    Relation(
        name="货币数量方程",
        formula="M × V = P × Y",
        category="准确性",
        worldview_tags=["neoclassical"],
        method_tags=["empirical", "theoretical"],
    ),
    Relation(
        name="政府预算约束",
        formula="G - T = ΔB + ΔM (政府支出-税收 = 新增债务+新增货币)",
        category="真实性",
        worldview_tags=["mmt", "neoclassical", "four_gods"],
        method_tags=["empirical", "simulation"],
    ),
    Relation(
        name="通货膨胀率定义",
        formula="通胀率 = (当期CPI - 基期CPI) / 基期CPI × 100%",
        category="准确性",
        worldview_tags=["all"],
        method_tags=["empirical", "simulation"],
    ),
]

# ── 四神体系关系 ──
FOUR_GODS_RELATIONS = [
    Relation(
        name="τ有界性",
        formula="0 ≤ τ ≤ 1 (信任温度必须在[0,1]区间内)",
        category="真实性",
        worldview_tags=["four_gods"],
        method_tags=["simulation", "theoretical"],
        severity="error",
    ),
    Relation(
        name="φ非负性",
        formula="φ ≥ 0 (系统间隔不能为负)",
        category="真实性",
        worldview_tags=["four_gods"],
        method_tags=["simulation", "theoretical"],
        severity="error",
    ),
    Relation(
        name="η定义一致性",
        formula="η ≈ ∂τ / ∂φ (观测灵敏度的定义)",
        category="准确性",
        worldview_tags=["four_gods"],
        method_tags=["simulation", "theoretical"],
    ),
    Relation(
        name="φ+τ守恒",
        formula="Σφ_ij + Στ_i ≈ 常数 (间隔与信任的守恒律)",
        category="准确性",
        worldview_tags=["four_gods"],
        method_tags=["simulation"],
    ),
]

# ── 通用数值关系 ──
UNIVERSAL_RELATIONS = [
    Relation(
        name="百分比归一",
        formula="同组百分比之和应接近100%",
        category="完整性",
        worldview_tags=["all"],
        method_tags=["all"],
    ),
    Relation(
        name="增长率方向一致性",
        formula="同比增长率与绝对值变化方向应一致",
        category="准确性",
        worldview_tags=["all"],
        method_tags=["all"],
    ),
    Relation(
        name="时间序列单调性",
        formula="累计值不应递减（如GDP、总资产）",
        category="准确性",
        worldview_tags=["all"],
        method_tags=["all"],
        severity="warning",
    ),
    Relation(
        name="比率边界",
        formula="比率应在其定义的数学范围内（如失业率∈[0,1]，利润率∈[-1,∞)）",
        category="真实性",
        worldview_tags=["all"],
        method_tags=["all"],
        severity="error",
    ),
]


# ════════════════════════════════════════════════════════
# 关系验证引擎
# ════════════════════════════════════════════════════════

class RelationVerifier:
    """从数据文本中提取数字，验证预设关系是否成立。"""

    # 数值提取正则（更宽松匹配）
    NUMBER_PATTERN = re.compile(
        r'([\w\u4e00-\u9fff]{1,8})\s*(?:[:：=＝]|为|是|达到|约为|约)\s*'
        r'(\d+(?:\.\d+)?)\s*'
        r'(?:万亿|亿|万|%|元|美元|点|倍)?'
    )
    
    # 宽松匹配: "GDP 126万亿" 形式
    NUMBER_LOOSE = re.compile(
        r'([\w\u4e00-\u9fff]{1,8})\s+(\d+(?:\.\d+)?)\s*(?:万亿|亿|万|%|元|美元)?'
        r'(?![\u4e00-\u9fff])'  # 数字后面不是中文（避免"第3季度"匹配）
    )

    # 中文财务紧凑格式: "资产200亿" (无空格无分隔符)
    NUMBER_COMPACT = re.compile(
        r'(资产|负债|权益|收入|利润|成本|费用|支出|盈余|亏损|现金流|净资产|总资产|总负债|'
        r'所有者权益|股东权益|营收|毛利|净利|GDP|CPI|PPI|M2|赤字|盈余)'
        r'[:：]?\s*[-]?(\d+(?:\.\d+)?)\s*(万亿|亿|万|千|百|%|％|元|美元|点|倍)?'
    )

    @classmethod
    def extract_key_values(cls, data_text: str) -> dict:
        """从文本中提取关键数值对 (指标名→值)。使用多重匹配策略。"""
        values = {}
        
        # 策略1: "GDP为126万亿"
        for m in cls.NUMBER_PATTERN.finditer(data_text):
            key = m.group(1).strip()
            try:
                val = float(m.group(2))
                values[key] = val
            except ValueError:
                continue
        
        # 策略2: "GDP 126万亿" (宽松)
        for m in cls.NUMBER_LOOSE.finditer(data_text):
            key = m.group(1).strip()
            if key not in values:  # 不覆盖策略1的结果
                try:
                    val = float(m.group(2))
                    values[key] = val
                except ValueError:
                    continue
        
        # 策略3: 直接数字扫描（百分比、比率等）
        pct_pat = re.compile(r'([\w\u4e00-\u9fff]{1,6})\s*(\d+(?:\.\d+)?)\s*%')
        for m in pct_pat.finditer(data_text):
            key = m.group(1).strip() + "%"
            if key not in values:
                try:
                    values[key] = float(m.group(2))
                except ValueError:
                    continue

        # 策略4: 中文财务紧凑格式 "资产200亿" (无分隔符·无LLM依赖)
        for m in cls.NUMBER_COMPACT.finditer(data_text):
            key = m.group(1).strip()
            if key not in values:
                try:
                    val = float(m.group(2))
                    unit = m.group(3) or ""
                    # 单位换算
                    if unit == "万亿":
                        val *= 10000
                    elif unit == "亿":
                        pass  # 保持原值
                    elif unit == "万":
                        val /= 10000
                    values[key] = val
                except ValueError:
                    continue

        return values

    @classmethod
    def verify(
        cls,
        data_text: str,
        worldview_key: str = "",
        method_key: str = "",
    ) -> dict:
        """
        验证数据是否满足关系约束。
        """
        # 选择适用的关系集
        relations = cls._select_relations(worldview_key, method_key)
        values = cls.extract_key_values(data_text)

        violations = []
        passed = 0
        failed = 0
        suggestions = []

        for rel in relations:
            result = cls._check_relation(rel, data_text, values)
            if result is True:
                passed += 1
            elif result is False:
                failed += 1
                violations.append({
                    "relation": rel.name,
                    "formula": rel.formula,
                    "severity": rel.severity,
                    "category": rel.category,
                    "detail": f"数据中检测到不符合 {rel.name} ({rel.formula})",
                })
                if rel.severity == "error":
                    suggestions.append(
                        f"{rel.name} 不成立({rel.category}缺陷) — "
                        f"数据可能存在伪造或录入错误"
                    )

        # LLM辅助深度关系验证
        if data_text and len(data_text) > 100:
            llm_violations = cls._llm_verify_relations(
                data_text, worldview_key, method_key
            )
            for v in llm_violations:
                violations.append(v)
                failed += 1
                if v.get("severity") == "error":
                    suggestions.append(v.get("detail", "")[:100])

        # 综合评分
        total = passed + failed
        if total == 0:
            score = 0.5
        else:
            base = passed / total
            error_penalty = sum(
                0.2 for v in violations if v.get("severity") == "error"
            )
            score = max(0.0, base - error_penalty)

        return {
            "passed_count": passed,
            "failed_count": failed,
            "total_checked": total,
            "violations": violations,
            "overall_score": round(score, 2),
            "suggestions": suggestions[:5],
            "values_found": len(values),
        }

    @classmethod
    def _llm_verify_relations(
        cls, data_text: str, worldview_key: str, method_key: str
    ) -> list[dict]:
        """
        LLM辅助验证复杂关系 — 四神控制版。

        织星(φ): 分块验证 + 块间φ-drift检测 → 不一致=幻觉信号
        司南: 规则基线校准 → LLM偏离规则结果=校准冲突 → 信规则
        天枢(τ): 数值锚定 → LLM输出的数字必须出现在输入数据中
        """
        # 选择需要LLM验证的关系（无法程序化检查的）
        llm_relations = []
        for rel in MACRO_RELATIONS + FOUR_GODS_RELATIONS + ACCOUNTING_RELATIONS:
            tags = rel.worldview_tags + rel.method_tags
            if "all" in tags or worldview_key in tags or method_key in tags:
                if rel.check_fn is None:
                    llm_relations.append(rel)

        if not llm_relations or len(data_text) < 200:
            return []

        # ═══ 天枢: 提取输入数据中所有数字作为锚 ═══
        input_numbers = set()
        for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:万亿|亿|万|%|元|美元)?', data_text):
            input_numbers.add(m.group(1))
        # 也加入提取的键值对
        key_vals = cls.extract_key_values(data_text)
        for v in key_vals.values():
            input_numbers.add(str(v))

        # ═══ 织星: 分块验证 ═══
        chunks = cls._chunk_text(data_text, max_chars=500)
        rel_desc = "\n".join([f"- {r.name}: {r.formula}" for r in llm_relations[:5]])

        chunk_results = []
        for i, chunk in enumerate(chunks):
            result = cls._verify_single_chunk(chunk, rel_desc, i)
            if result:
                chunk_results.append(result)

        # ═══ 织星 φ-drift: 块间一致性检测 ═══
        merged_violations = []
        drift_flags = []

        if len(chunk_results) >= 2:
            # 比较第1块和第2块的结果
            r1_relations = {v["relation"] for v in chunk_results[0]}
            r2_relations = {v["relation"] for v in chunk_results[1]}
            only_in_1 = r1_relations - r2_relations
            only_in_2 = r2_relations - r1_relations
            if only_in_1 or only_in_2:
                drift_flags.append({
                    "type": "φ-drift",
                    "detail": f"块间不一致: 块1检测到{only_in_1}但块2未检测到; 块2检测到{only_in_2}但块1未检测到",
                    "severity": "warning",
                })

        # 合并所有块的违规（去重）
        seen_relations = set()
        for cr in chunk_results:
            for v in cr:
                if v["relation"] not in seen_relations:
                    seen_relations.add(v["relation"])
                    merged_violations.append(v)

        # ═══ 天枢: 数值锚定检查 ═══
        anchored_violations = []
        hallucination_count = 0
        for v in merged_violations:
            detail = v.get("detail", "")
            # 提取LLM输出中的所有数字
            llm_numbers = set(re.findall(r'(\d+(?:\.\d+)?)', detail))
            # 检查是否都出现在输入数据中
            new_numbers = llm_numbers - input_numbers
            if new_numbers:
                hallucination_count += 1
                # 标记但不丢弃 — 告知下游这是LLM生成的数字，不可信
                v["hallucination_risk"] = True
                v["hallucinated_numbers"] = list(new_numbers)
                v["detail"] += f" [⚠ 天枢警告: LLM引入了输入数据中不存在的数字 {new_numbers}]"
            else:
                v["hallucination_risk"] = False
            anchored_violations.append(v)

        # ═══ 司南: 规则基线校准 (事后) ═══
        # 对LLM指出的每一条违规，尝试用规则验证
        calibrated_violations = []
        for v in anchored_violations:
            rel_name = v.get("relation", "")
            # 找对应的关系定义
            rel_obj = None
            for r in MACRO_RELATIONS + FOUR_GODS_RELATIONS + ACCOUNTING_RELATIONS:
                if r.name == rel_name:
                    rel_obj = r
                    break

            if rel_obj and rel_obj.check_fn is not None:
                # 这个关系可以程序化检查 — 司南校准
                rule_result = cls._check_relation(rel_obj, data_text, key_vals)
                if rule_result is True:
                    # 规则说通过，LLM说违规 → 司南冲突
                    v["sinanshu_conflict"] = True
                    v["severity"] = "info"  # 降级
                    v["detail"] += (
                        f" [🧭 司南校准: 确定性规则检查显示此关系成立, "
                        f"LLM判断可能为幻觉, 已降级为info]"
                    )
                elif rule_result is False:
                    # 规则也说违规 → 确认
                    v["sinanshu_confirmed"] = True
                # rule_result is None → 规则无法判断，LLM结果保持不变
            calibrated_violations.append(v)

        # 汇总
        final_violations = [
            {
                "relation": v["relation"],
                "severity": v.get("severity", "error"),
                "category": v.get("category", "真实性"),
                "detail": v.get("detail", ""),
                "llm_detected": True,
                "hallucination_risk": v.get("hallucination_risk", False),
                "sinanshu_conflict": v.get("sinanshu_conflict", False),
                "sinanshu_confirmed": v.get("sinanshu_confirmed", False),
            }
            for v in calibrated_violations
        ]

        # 织星φ-drift标记作为额外的info级违规
        for df in drift_flags:
            final_violations.append({
                "relation": "织星φ-drift检测",
                "severity": "info",
                "category": "准确性",
                "detail": df["detail"],
                "llm_detected": True,
                "voyager_drift": True,
            })

        return final_violations

    @classmethod
    def _chunk_text(cls, text: str, max_chars: int = 500) -> list[str]:
        """织星分块: 将长文本按句子边界切成短块。"""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        sentences = re.split(r'[。\n；;]', text)

        current = ""
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(current) + len(sent) > max_chars and current:
                chunks.append(current)
                current = sent
            else:
                current = f"{current}。{sent}" if current else sent

        if current:
            chunks.append(current)

        return chunks[:5]  # 最多5块

    @classmethod
    def _verify_single_chunk(
        cls, chunk: str, rel_desc: str, chunk_idx: int
    ) -> Optional[list[dict]]:
        """验证单个数据块的关系。短上下文减少幻觉。"""
        system = f"""你是数据关系审计员。只检查以下数据片段是否违反关系约束。

需检查的关系:
{rel_desc}

只输出JSON数组（只输出违反的关系）:
[{{"relation": "关系名", "violated": true, "detail": "具体违规描述"}}]

如果没有违规，输出空数组 []。
重要: 只使用上面给出的数据片段，不要引入你"知道"的外部信息。"""

        try:
            result = _llm_call(system, chunk[:600], max_tokens=250)
            if not result or "[" not in result:
                return []
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
                if result.endswith("```"):
                    result = result.rsplit("\n```", 1)[0]
            data = json.loads(result)
            return [
                {
                    "relation": v.get("relation", "未知"),
                    "category": "真实性",
                    "detail": f"[块{chunk_idx}] {v.get('detail', '')}",
                }
                for v in data
                if v.get("violated") or v.get("relation")
            ]
        except Exception:
            return None

    @classmethod
    def _select_relations(cls, worldview_key: str, method_key: str) -> list[Relation]:
        """根据世界观和方法论选择适用的关系约束。"""
        selected = []

        # 通用关系始终适用
        selected.extend(UNIVERSAL_RELATIONS)

        # 会计关系（对 forensic 和包含财务数据的场景）
        if worldview_key in ("forensic",) or method_key in ("forensic", "empirical"):
            selected.extend(ACCOUNTING_RELATIONS)

        # 宏观关系
        if worldview_key in ("neoclassical", "mmt") or method_key in ("empirical", "comparative", "simulation"):
            selected.extend(MACRO_RELATIONS)

        # 四神关系
        if worldview_key == "four_gods" or method_key in ("simulation", "synthesis"):
            selected.extend(FOUR_GODS_RELATIONS)

        return selected

    @classmethod
    def _check_relation(cls, rel: Relation, text: str, values: dict) -> Optional[bool]:
        """检查单条关系。返回 True/False/None。"""
        name = rel.name

        # ── 百分比归一 ──
        if name == "百分比归一":
            return cls._check_pct_sum(text)

        # ── 增长率方向一致性 ──
        if name == "增长率方向一致性":
            return cls._check_growth_direction(text)

        # ── 比率边界 ──
        if name == "比率边界":
            return cls._check_ratio_bounds(text)

        # ── 会计恒等式 ──
        if name == "会计恒等式":
            return cls._check_accounting_identity(values)

        # ── GDP恒等式 ──
        if name == "GDP恒等式":
            return cls._check_gdp_identity(values)

        # ── MMT部门平衡 ──
        if name == "MMT部门平衡":
            return cls._check_sectoral_balance(values)

        # ── 政府预算约束 ──
        if name == "政府预算约束":
            return cls._check_budget_constraint(values)

        # ── τ有界性 ──
        if name == "τ有界性":
            return cls._check_tau_bounds(text)

        # ── φ非负性 ──
        if name == "φ非负性":
            return cls._check_phi_nonnegative(text)

        # ── 无法程序化检查的 → 返回None（不扣分）
        return None

    # ─── 具体检查方法 ───

    @classmethod
    def _check_pct_sum(cls, text: str) -> Optional[bool]:
        """检查同一组百分比是否接近100%。"""
        # 找连续的百分比
        pcts = re.findall(r'(?:占比|比例|份额|构成)[^。\n]*?(\d+(?:\.\d+)?)\s*%', text)
        if len(pcts) < 2:
            return None

        nums = [float(p) for p in pcts[:6]]  # 最多取6个
        total = sum(nums)
        # 100% ± 5% 容差（允许四舍五入）
        return abs(total - 100) <= 5

    @classmethod
    def _check_growth_direction(cls, text: str) -> Optional[bool]:
        """增长率方向与绝对值方向应一致。"""
        # 简化版：找"增长X%"与"增加值"是否同向
        growth_matches = re.findall(
            r'(?:增长|增加|上升|提高)\s*(\d+(?:\.\d+)?)\s*%', text
        )
        decline_matches = re.findall(
            r'(?:下降|减少|降低)\s*(\d+(?:\.\d+)?)\s*%', text
        )
        # 如果有增长又提到减少 → 可能矛盾
        # 这个检查比较弱，大多数时候返回None
        if growth_matches and decline_matches:
            return None  # 可能不同指标，不武断判错
        return None

    @classmethod
    def _check_ratio_bounds(cls, text: str) -> Optional[bool]:
        """检查比率是否在数学可行范围内。"""
        # 失业率
        ur_match = re.search(r'失业率[^0-9]*(\d+(?:\.\d+)?)\s*%', text)
        if ur_match:
            ur = float(ur_match.group(1))
            if ur < 0 or ur > 100:
                return False

        # 通胀率（可以为负，但不应该离谱）
        inf_match = re.search(r'通胀[率指数][^0-9]*(-?\d+(?:\.\d+)?)\s*%', text)
        if inf_match:
            inf = float(inf_match.group(1))
            if inf > 1000 or inf < -100:
                return False

        # 利润率
        pm_match = re.search(r'利润率[^0-9]*(\d+(?:\.\d+)?)\s*%', text)
        if pm_match:
            pm = float(pm_match.group(1))
            if pm > 100 or pm < -200:
                return False

        return None  # 无法判断

    @classmethod
    def _check_accounting_identity(cls, values: dict) -> Optional[bool]:
        """资产 = 负债 + 权益。"""
        asset = values.get("资产") or values.get("总资产") or values.get("资产总计")
        liability = values.get("负债") or values.get("总负债") or values.get("负债合计")
        equity = values.get("权益") or values.get("所有者权益") or values.get("净资产")

        if asset and liability and equity:
            expected = liability + equity
            if expected > 0:
                diff = abs(asset - expected) / expected
                return diff < 0.05  # 5%容差
        return None

    @classmethod
    def _check_gdp_identity(cls, values: dict) -> Optional[bool]:
        """GDP = C + I + G + NX。"""
        gdp = values.get("GDP") or values.get("国内生产总值")
        cons = values.get("消费") or values.get("居民消费")
        inv = values.get("投资") or values.get("固定资产投资")
        gov = values.get("政府支出") or values.get("政府消费")
        nx = values.get("净出口") or values.get("贸易顺差")

        if gdp and (cons or inv):
            total = (cons or 0) + (inv or 0) + (gov or 0) + (nx or 0)
            if total > 0 and gdp > 0:
                diff = abs(gdp - total) / gdp
                return diff < 0.15  # 15%容差（部分数据可能用名义值）
        return None

    @classmethod
    def _check_sectoral_balance(cls, values: dict) -> Optional[bool]:
        """(S-I) = (G-T) + (X-M)。"""
        private_balance = values.get("私人部门盈余") or values.get("S-I")
        gov_deficit = values.get("政府赤字") or values.get("G-T") or values.get("财政赤字")
        trade_surplus = values.get("贸易顺差") or values.get("X-M") or values.get("经常账户")

        if private_balance is not None and gov_deficit is not None:
            expected = gov_deficit + (trade_surplus or 0)
            if abs(expected) > 0.01:
                diff = abs(private_balance - expected) / max(abs(expected), 1)
                return diff < 0.2
        return None

    @classmethod
    def _check_budget_constraint(cls, values: dict) -> Optional[bool]:
        """G - T = ΔB + ΔM。"""
        deficit = values.get("赤字") or values.get("财政赤字") or values.get("G-T")
        debt_change = values.get("新增债务") or values.get("ΔB") or values.get("国债发行")
        money_change = values.get("新增货币") or values.get("ΔM")

        if deficit is not None and (debt_change is not None or money_change is not None):
            expected = (debt_change or 0) + (money_change or 0)
            if abs(deficit) > 0.01:
                diff = abs(deficit - expected) / abs(deficit)
                return diff < 0.25
        return None

    @classmethod
    def _check_tau_bounds(cls, text: str) -> Optional[bool]:
        """τ ∈ [0, 1]。"""
        tau_match = re.search(r'[ττ]\s*[=＝]\s*(\d+(?:\.\d+)?)', text)
        if tau_match:
            tau = float(tau_match.group(1))
            return 0 <= tau <= 1
        return None

    @classmethod
    def _check_phi_nonnegative(cls, text: str) -> Optional[bool]:
        """φ ≥ 0。"""
        phi_match = re.search(r'[φφ]\s*[=＝]\s*(\d+(?:\.\d+)?)', text)
        if phi_match:
            phi = float(phi_match.group(1))
            return phi >= 0
        return None


# ════════════════════════════════════════════════════════
# 模拟验证完整性
# ════════════════════════════════════════════════════════

class SimulationIntegrity:
    """模拟输入/输出必须满足方法论预设关系。"""

    @classmethod
    def verify(
        cls,
        sim_params: dict,
        sim_output: dict,
        method_key: str = "simulation",
        worldview_key: str = "",
    ) -> dict:
        """
        验证模拟数据的三性。

        参数:
          sim_params: 模拟输入参数 (如 {deficit_ratio: 0.15, ...})
          sim_output: 模拟输出 (如 {gdp: 245, inflation: 0.003, ...})
          method_key: 方法论标识
          worldview_key: 世界观标识

        返回:
          {passed: bool, violations: [...], suggestions: [...]}
        """
        violations = []
        suggestions = []

        # ① 参数范围检查
        param_bounds = {
            "deficit_ratio": (0, 1, "赤字率"),
            "spending_infra": (0, 1, "基建支出占比"),
            "spending_welfare": (0, 1, "福利支出占比"),
            "tax_rate": (0, 1, "税率"),
            "kappa": (0, 1, "定倾κ"),
            "phi": (0, float("inf"), "φ"),
            "tau": (0, 1, "τ"),
        }
        for param, val in sim_params.items():
            if param in param_bounds:
                lo, hi, label = param_bounds[param]
                if val < lo or val > hi:
                    violations.append({
                        "param": param,
                        "value": val,
                        "expected": f"[{lo}, {hi}]",
                        "severity": "error",
                        "detail": f"{label}={val} 超出合理范围 [{lo}, {hi}]",
                    })
                    suggestions.append(
                        f"模拟参数 {label}={val} 超出 [{lo}, {hi}] — "
                        f"模拟结果不可信"
                    )

        # ② 输出关系检查
        # GDP恒等式（宏观经济模拟）
        if all(k in sim_output for k in ["gdp", "inflation", "unemployment"]):
            # 通胀率应在合理范围
            if "inflation" in sim_output:
                inf = sim_output["inflation"]
                if abs(inf) > 1.0:  # 超过100%通胀
                    violations.append({
                        "output": "inflation",
                        "value": inf,
                        "severity": "warning",
                        "detail": f"模拟输出通胀率={inf} 异常高，检查参数设置",
                    })

            # 失业率
            if "unemployment" in sim_output:
                ue = sim_output["unemployment"]
                if ue < 0 or ue > 1:
                    violations.append({
                        "output": "unemployment",
                        "value": ue,
                        "severity": "error",
                        "detail": f"失业率={ue} 超出[0,1]范围",
                    })

        # ③ 四神关系检查
        if "phi" in sim_params and "tau" in sim_params:
            tau = sim_params.get("tau", 0)
            phi = sim_params.get("phi", 0)
            if tau + phi > 2.0:
                violations.append({
                    "relation": "φ+τ守恒",
                    "severity": "warning",
                    "detail": f"τ={tau}+φ={phi} = {tau+phi}，可能超出守恒约束",
                })

        # ④ 方法论特定检查
        if method_key == "mmt" or "mmt" in str(sim_params.get("method", "")):
            # MMT: 赤字率应该与通胀和失业有关联
            deficit = sim_params.get("deficit_ratio", 0)
            inflation = sim_output.get("inflation", 0)
            gdp = sim_output.get("gdp", 0)

            if deficit > 0.3 and inflation < 0.01 and gdp < 100:
                violations.append({
                    "relation": "MMT高赤字低通胀",
                    "severity": "warning",
                    "detail": (
                        f"赤字率={deficit}极高但通胀={inflation}极低、GDP={gdp}偏低"
                        f"— 这说明模型可能存在资源利用率假设问题"
                    ),
                })
                suggestions.append(
                    "MMT框架下高赤字+低通胀可能对应资源闲置状态"
                    "— 检查资源利用率参数是否被隐式压低"
                )

        # ⑤ 汇总
        errors = [v for v in violations if v.get("severity") == "error"]
        warnings = [v for v in violations if v.get("severity") == "warning"]
        passed = len(errors) == 0

        return {
            "passed": passed,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "violations": violations,
            "suggestions": suggestions,
            "summary": (
                f"模拟完整性: {'✅ 通过' if passed else '❌ 不通过'} "
                f"({len(errors)}错误, {len(warnings)}警告)"
            ),
        }


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def verify_relations(
    data_text: str,
    worldview_key: str = "",
    method_key: str = "",
) -> dict:
    """验证数据关系完整性。"""
    return RelationVerifier.verify(data_text, worldview_key, method_key)


def verify_simulation(
    sim_params: dict,
    sim_output: dict,
    method_key: str = "",
    worldview_key: str = "",
) -> dict:
    """验证模拟数据的完整性。"""
    return SimulationIntegrity.verify(sim_params, sim_output, method_key, worldview_key)


# ═══ 自检 ═══
if __name__ == "__main__":
    # 测试1: 正常数据
    good_data = """
    2024年GDP为126万亿，消费支出48万亿，投资42万亿，
    政府支出30万亿，净出口3万亿。
    失业率5.2%，通胀率0.3%。
    """

    bad_data = """
    2024年GDP为100万亿，消费支出90万亿，投资50万亿。
    资产总额200亿，负债150亿，所有者权益30亿。
    失业率-5%，通胀率2000%。
    """

    tau_data = "天枢τ = 1.5，织星φ = -0.3"

    print("=== 正常数据 ===")
    result = RelationVerifier.verify(good_data, worldview_key="neoclassical")
    print(f"  检查: {result['passed_count']}通过/{result['failed_count']}失败")
    for v in result["violations"]:
        print(f"  ⚠ {v['relation']}: {v['detail'][:80]}")

    print("\n=== 伪造数据 ===")
    result = RelationVerifier.verify(bad_data, worldview_key="forensic")
    print(f"  检查: {result['passed_count']}通过/{result['failed_count']}失败")
    print(f"  评分: {result['overall_score']}")
    for v in result["violations"]:
        print(f"  ❌ {v['relation']}: {v['detail'][:80]}")
    for s in result["suggestions"]:
        print(f"  💡 {s[:80]}")

    print("\n=== 四神参数 ===")
    result = RelationVerifier.verify(tau_data, worldview_key="four_gods")
    print(f"  检查: {result['passed_count']}通过/{result['failed_count']}失败")
    for v in result["violations"]:
        print(f"  ❌ {v['relation']}: {v['detail'][:80]}")

    print("\n=== 模拟完整性 ===")
    sim_params = {"deficit_ratio": 0.15, "spending_infra": 0.8, "tau": 0.55, "phi": 0.41}
    sim_output = {"gdp": 245, "inflation": 0.003, "unemployment": 0.02}
    sim_result = SimulationIntegrity.verify(sim_params, sim_output, method_key="simulation", worldview_key="four_gods")
    print(f"  {sim_result['summary']}")
    for v in sim_result["violations"]:
        print(f"  {'❌' if v.get('severity')=='error' else '⚠️'} {v['detail'][:100]}")
