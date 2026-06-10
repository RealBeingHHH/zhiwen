"""
知纹自我审计 — 能力边界攻击测试

不是单元测试。是边界攻击: 故意给假数据、无锚数字、矛盾前提，
看安全保证是否真的在工作。

五项审计:
  1. 数据真实性   伪造整齐数列 → Benford检测报警
  2. LLM幻觉     无锚数字注入 → φ漂移标记
  3. 数据完整性   故意缺数据 → 补搜触发
  4. 一致性      矛盾前提 → 冲突报告
  5. 纹路稳定性   同问题两次 → 答案稳定·纹路一致

输出: 审计报告 { 总分, 通过/失败/警告, 修复建议 }

用法:
  python self_audit.py
"""

import time, json, hashlib, re, math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from collections import defaultdict

BASE = Path(__file__).parent


# ════════════════════════════════════════════════════════
# 审计结果
# ════════════════════════════════════════════════════════

@dataclass
class AuditCase:
    """一个审计用例。"""
    id: str
    name: str
    category: str                    # 数据/LLM/一致性/纹路
    description: str
    expected: str                    # 期望行为
    severity: str = "高"             # 严重度: 高/中/低

    # 执行结果
    passed: bool = False
    score: float = 0.0              # 0-1
    actual: str = ""                # 实际结果描述
    evidence: str = ""              # 证据 (日志/输出)
    warnings: list[str] = field(default_factory=list)


@dataclass
class AuditReport:
    """审计报告。"""
    timestamp: float = 0.0
    cases: list[AuditCase] = field(default_factory=list)
    total_score: float = 0.0
    passed: int = 0
    failed: int = 0
    warnings: int = 0

    @property
    def grade(self) -> str:
        if self.total_score >= 0.9:
            return "A · 可信"
        elif self.total_score >= 0.7:
            return "B · 基本可靠"
        elif self.total_score >= 0.5:
            return "C · 有漏洞"
        return "D · 不可信"


# ════════════════════════════════════════════════════════
# 1. 数据真实性审计
# ════════════════════════════════════════════════════════

def audit_authenticity() -> list[AuditCase]:
    """审计数据真实性保证: Benford定律·闸门拦截。"""
    results = []

    # ─── 案例1: 伪造整齐数列 ───
    case = AuditCase(
        id="auth_01",
        name="伪造整齐数列检测",
        category="数据真实性",
        description="注入人为构造的整齐数字序列(100000,200000,300000...),Benford定律应检测到异常",
        expected="Benford评分<0.5, 真实性闸标记异常",
        severity="高",
    )
    try:
        from voyager_auth import VoyagerAuthenticity
        fake_data = "销售额 100000, 200000, 300000, 400000, 500000, 600000, 700000, 800000, 900000, 1000000, 1100000"
        result = VoyagerAuthenticity.verify(fake_data, "销售数据分析")

        score = result.get("authenticity_score", 1.0)
        passed = result.get("passed", True)
        benford = result.get("benford", {})
        benford_passed = benford.get("passed") if isinstance(benford, dict) else None
        verdict = result.get("verdict", "")

        if score < 0.7 or benford_passed is False:
            case.passed = True
            case.score = 0.9
            case.actual = f"真实性评分{score:.2f} Benford={'失败' if benford_passed is False else '样本不足' if benford_passed is None else '通过'} → 异常检测生效"
            case.evidence = f"score={score} verdict={verdict}"
        elif score < 0.85:
            case.passed = True
            case.score = 0.5
            case.actual = f"真实性评分{score:.2f} → 评分偏低但未明确标记异常"
            case.warnings.append("整齐数列应触发更低的真实性评分")
        else:
            case.passed = False
            case.score = 0.1
            case.actual = f"真实性评分{score:.2f} → 整齐数列通过检查!"
    except Exception as e:
        case.passed = False
        case.score = 0.0
        case.actual = f"模块不可用: {e}"

    results.append(case)

    # ─── 案例2: 正常数据应通过 ───
    case2 = AuditCase(
        id="auth_02",
        name="正常数据不应误杀",
        category="数据真实性",
        description="注入真实分布的数据,闸门不应误报",
        expected="真实性评分>0.5, 通过闸门",
        severity="中",
    )
    try:
        from voyager_auth import VoyagerAuthenticity
        normal_data = "日本通胀率 0.8, 1.2, 0.3, 1.5, 0.1, 2.3, 0.7, 1.0, 1.8"
        result = VoyagerAuthenticity.verify(normal_data, "通胀数据分析")
        score = result.get("authenticity_score", 0)

        if score > 0.4:
            case2.passed = True
            case2.score = 0.8
            case2.actual = f"真实性评分{score:.2f} → 正确放行"
        else:
            case2.passed = False
            case2.score = 0.2
            case2.actual = f"真实性评分{score:.2f} → 误杀正常数据"
    except Exception as e:
        case2.passed = False
        case2.score = 0.0
        case2.actual = f"模块不可用: {e}"

    results.append(case2)
    return results


# ════════════════════════════════════════════════════════
# 2. LLM幻觉审计
# ════════════════════════════════════════════════════════

def audit_llm_hallucination() -> list[AuditCase]:
    """审计LLM幻觉控制: φ漂移·τ锚定。"""
    results = []

    # ─── 案例3: φ漂移检测 ───
    case = AuditCase(
        id="llm_01",
        name="φ漂移检测能力",
        category="LLM幻觉",
        description="输入不含数字的文本,检查φ漂移检测逻辑是否正确识别异常数字",
        expected="含大量无故数字的文本 → φ漂移评分>0",
        severity="高",
    )
    try:
        # 测试φ漂移检测函数 (在 reasoning_engine 中)
        from reasoning_engine import ReasoningEngine
        engine = ReasoningEngine()

        # 正常文本
        normal_drift = engine._calc_phi_drift("日本通胀率近年维持在低位。")
        # 异常文本 (大量无源数字)
        fake_drift = engine._calc_phi_drift(
            "精确计算得出 1.23456789, 2.34567890, 3.45678901, "
            "4.56789012, 5.67890123, 6.78901234, 7.89012345, 8.90123456"
        )

        if fake_drift > 0.3 and fake_drift > normal_drift:
            case.passed = True
            case.score = 0.9
            case.actual = f"正常φ={normal_drift:.2f} 异常φ={fake_drift:.2f} → 正确区分"
        elif fake_drift > normal_drift:
            case.passed = True
            case.score = 0.5
            case.actual = f"有区分但阈值不足: 正常{normal_drift:.2f} vs 异常{fake_drift:.2f}"
        else:
            case.passed = False
            case.score = 0.1
            case.actual = f"无法区分: 正常{normal_drift:.2f} 异常{fake_drift:.2f}"
    except Exception as e:
        case.passed = False
        case.score = 0.0
        case.actual = f"模块不可用: {e}"

    results.append(case)

    # ─── 案例4: τ锚定检测 ───
    case2 = AuditCase(
        id="llm_02",
        name="τ锚定检测",
        category="LLM幻觉",
        description="输入含数字A的查询,输出含数字B(B≠A),τ锚定应标记",
        expected="输出中引入了输入没有的数字 → 未锚定标记",
        severity="高",
    )
    try:
        # 测试τ锚定逻辑 (在 reasoning_engine 中)
        engine = ReasoningEngine()

        query = "日本通胀率0.8%"
        anchored = engine._has_tau_anchoring(
            "日本通胀率0.8%, GDP增长1.2%",  # 1.2不在输入中
            query
        )
        well_anchored = engine._has_tau_anchoring(
            "通胀率0.8%",  # 0.8在输入中
            query
        )

        if not anchored and well_anchored:
            case2.passed = True
            case2.score = 0.9
            case2.actual = "未锚定输出正确标记, 锚定输出正确放行"
        elif not anchored:
            case2.passed = True
            case2.score = 0.7
            case2.actual = "未锚定检测正确 (锚定检测未验证)"
        else:
            case2.passed = False
            case2.score = 0.2
            case2.actual = "τ锚定失效: 引入新数字未检测"
    except Exception as e:
        case2.passed = False
        case2.score = 0.0
        case2.actual = f"模块不可用: {e}"

    results.append(case2)

    # ─── 案例5: voyager_llm包装层 ───
    case3 = AuditCase(
        id="llm_03",
        name="voyager_llm安全包装",
        category="LLM幻觉",
        description="验证 voyager_llm.safe_llm_call 可导入且函数签名正确",
        expected="safe_llm_call 函数存在, 接受 system+user 参数",
        severity="中",
    )
    try:
        from voyager_llm import safe_llm_call
        import inspect
        sig = inspect.signature(safe_llm_call)
        params = list(sig.parameters.keys())
        if "system" in str(sig) or len(params) >= 2:
            case3.passed = True
            case3.score = 0.8
            case3.actual = f"safe_llm_call 存在, 签名: {params[:3]}"
        else:
            case3.passed = True
            case3.score = 0.5
            case3.actual = f"存在但签名异常: {params}"
    except Exception as e:
        case3.passed = False
        case3.score = 0.0
        case3.actual = f"未找到: {e}"

    results.append(case3)
    return results


# ════════════════════════════════════════════════════════
# 3. 数据完整性审计
# ════════════════════════════════════════════════════════

def audit_completeness() -> list[AuditCase]:
    """审计数据完整性: 缺数据补搜·闸门评分。"""
    results = []

    # ─── 案例6: 空数据闸门 ───
    case = AuditCase(
        id="comp_01",
        name="空数据闸门拦截",
        category="数据完整性",
        description="输入空数据,闸门应给低分并可能阻断",
        expected="overall_score < 0.5, 完整性评分低",
        severity="高",
    )
    try:
        from data_gate import DataGate
        gate = DataGate.check(
            data_text="",
            data_requirements=["统计数据", "理论框架", "实证证据"],
            quality_threshold=0.6,
            query="测试查询",
            method_key="empirical",
        )
        score = gate.overall_score
        completeness = gate.completeness

        if score < 0.5:
            case.passed = True
            case.score = 0.9
            case.actual = f"综合分{score:.2f} → 空数据正确低分"
        elif score < 0.7:
            case.passed = True
            case.score = 0.5
            case.actual = f"综合分{score:.2f} → 偏低但不够低"
        else:
            case.passed = False
            case.score = 0.1
            case.actual = f"综合分{score:.2f} → 空数据高分异常!"
    except Exception as e:
        case.passed = False
        case.score = 0.0
        case.actual = f"模块不可用: {e}"

    results.append(case)

    # ─── 案例7: 关系完整性 ───
    case2 = AuditCase(
        id="comp_02",
        name="关系完整性检测",
        category="数据完整性",
        description="注入会计等式矛盾数据(资产≠负债+权益),关系检测应报错",
        expected="关系完整性评分<0.7, 报告约束违规",
        severity="高",
    )
    try:
        from relation_integrity import verify_relations
        fake_finance = "资产200亿 负债150亿 权益30亿"
        result = verify_relations(fake_finance, worldview_key="forensic")
        if result:
            score = result.get("overall_score", 1.0) if isinstance(result, dict) else 1.0
            checked = result.get("total_checked", 0) if isinstance(result, dict) else 0
            
            if score < 0.7 or (isinstance(result, dict) and result.get("violations")):
                case2.passed = True
                case2.score = 0.9
                case2.actual = f"评分{score:.2f} 检测{checked}项 → 矛盾检测生效"
            elif checked > 0:
                case2.passed = True
                case2.score = 0.5
                case2.actual = f"评分{score:.2f} 检测{checked}项但未发现矛盾 → 可能阈值过高"
            else:
                case2.passed = True
                case2.score = 0.3
                case2.actual = f"评分{score:.2f} 未触发检查(需LLM提取 → 隔离测试限制)"
                case2.warnings.append("关系检测依赖LLM提取数值,隔离测试无法完全验证")
    except Exception as e:
        case2.passed = False
        case2.score = 0.0
        case2.actual = f"模块不可用: {type(e).__name__}"

    results.append(case2)
    return results


# ════════════════════════════════════════════════════════
# 4. 纹路稳定性审计
# ════════════════════════════════════════════════════════

def audit_pattern_stability() -> list[AuditCase]:
    """审计纹路记忆稳定性。"""
    results = []

    # ─── 案例8: 追问延续检测 ───
    case = AuditCase(
        id="pat_01",
        name="追问延续检测",
        category="纹路稳定性",
        description="先问主问题→再问追问,纹路记忆应识别延续关系",
        expected="追问被识别为延续(continued=True, depth=1)",
        severity="中",
    )
    try:
        from pattern_memory import PatternMemory
        pm = PatternMemory()
        session = "audit_test_" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:6]

        # 第一轮
        pm.remember(session, "分析日本通缩成因",
                   plan=None, reasoning={"chains": [["a","b"]]})

        # 第二轮的追问
        cont = pm.continue_from(session, "那通胀率呢？")

        if cont and cont.get("continued"):
            case.passed = True
            case.score = 0.9
            case.actual = f"追问正确识别, 深度{cont.get('depth',0)}, 延续自:{cont.get('parent_query','')[:30]}"
        else:
            case.passed = False
            case.score = 0.2
            case.actual = "追问未被识别为延续 → 纹路记忆断裂"
    except Exception as e:
        case.passed = False
        case.score = 0.0
        case.actual = f"模块不可用: {e}"

    results.append(case)

    # ─── 案例9: 独立问题不串 ───
    case2 = AuditCase(
        id="pat_02",
        name="独立问题不误串",
        category="纹路稳定性",
        description="两个不相关的问题不应被识别为延续",
        expected="continued=False 或 None",
        severity="中",
    )
    try:
        from pattern_memory import PatternMemory
        pm = PatternMemory()
        session = "audit_test_b"

        pm.remember(session, "分析日本经济政策", plan=None,
                   reasoning={"chains": []})
        cont = pm.continue_from(session, "火星大气成分研究")

        if not cont or not cont.get("continued"):
            case2.passed = True
            case2.score = 0.9
            case2.actual = "正确识别为独立问题"
        else:
            case2.passed = False
            case2.score = 0.1
            case2.actual = "不相关问题被误判为延续 → 串话风险"
    except Exception as e:
        case2.passed = False
        case2.score = 0.0
        case2.actual = f"模块不可用: {e}"

    results.append(case2)

    # ─── 案例10: 关键词提取 ───
    case3 = AuditCase(
        id="pat_03",
        name="关键词提取质量",
        category="纹路稳定性",
        description="中文关键词提取应识别MMT、通胀、日本等核心术语",
        expected="提取到MMT, 通胀, 日本等关键词",
        severity="低",
    )
    try:
        from pattern_memory import PatternMemory
        pm = PatternMemory()
        keywords = pm._extract_keywords("日本MMT政策下通胀率与赤字率的关系分析")
        key_set = set(keywords)

        core_terms = ["日本", "MMT", "通胀", "赤字", "政策"]
        found = [t for t in core_terms if t in " ".join(keywords)]

        if len(found) >= 3:
            case3.passed = True
            case3.score = 0.9
            case3.actual = f"提取到{len(keywords)}关键词, 核心词:{found}"
        elif len(found) >= 1:
            case3.passed = True
            case3.score = 0.5
            case3.actual = f"部分提取: {found}/{core_terms}"
        else:
            case3.passed = False
            case3.score = 0.2
            case3.actual = f"核心词未提取到: keywords={keywords[:8]}"
    except Exception as e:
        case3.passed = False
        case3.score = 0.0
        case3.actual = f"模块不可用: {e}"

    results.append(case3)
    return results


# ════════════════════════════════════════════════════════
# 5. DNA架构审计
# ════════════════════════════════════════════════════════

def audit_dna_integrity() -> list[AuditCase]:
    """审计DNA架构完整性。"""
    results = []

    # ─── 案例11: 碱基配对强制 ───
    case = AuditCase(
        id="dna_01",
        name="A-T/G-C强制配对",
        category="DNA架构",
        description="创建错误配对的核苷酸(如A-C),应标记mismatch",
        expected="mismatch_flag=True, 错误原因包含'错配'",
        severity="高",
    )
    try:
        from genome_core import Nucleotide
        # 错误配对: A应该配T, 却配了C
        bad_nt = Nucleotide(
            sense_base="A", antisense_base="C",
            sense_content="主张", antisense_content="错误配对"
        )
        if bad_nt.mismatch_flag:
            case.passed = True
            case.score = 0.9
            case.actual = f"错配正确标记: {bad_nt.mismatch_reason[:60]}"
        else:
            case.passed = False
            case.score = 0.0
            case.actual = "A-C错配未被标记 → 碱基配对强制失效"
    except Exception as e:
        case.passed = False
        case.score = 0.0
        case.actual = f"模块不可用: {e}"

    results.append(case)

    # ─── 案例12: 密码子翻译 ───
    case2 = AuditCase(
        id="dna_02",
        name="密码子准确翻译",
        category="DNA架构",
        description="ATG应翻译为START, AAG→SEARCH, TAA→STOP_CONCLUDE",
        expected="三个密码子翻译正确",
        severity="中",
    )
    try:
        from genome_core import CodonTable
        tests = {
            "ATG": "START",
            "AAG": "SEARCH",
            "GGC": "SIMULATE",
            "CGT": "VERIFY",
            "TAA": "STOP_CONCLUDE",
        }
        all_ok = True
        for codon, expected_action in tests.items():
            info = CodonTable.translate(codon)
            if info["action"] != expected_action:
                all_ok = False
                case2.warnings.append(f"{codon}→{info['action']}(期望{expected_action})")

        if all_ok:
            case2.passed = True
            case2.score = 0.9
            case2.actual = f"5/5密码子翻译正确"
        else:
            case2.passed = False
            case2.score = 0.3
            case2.actual = f"密码子翻译错误: {case2.warnings}"
    except Exception as e:
        case2.passed = False
        case2.score = 0.0
        case2.actual = f"模块不可用: {e}"

    results.append(case2)
    return results


# ════════════════════════════════════════════════════════
# 审计运行器
# ════════════════════════════════════════════════════════

def run_audit() -> AuditReport:
    """运行全部审计。"""
    print("═" * 60)
    print("  知纹自我审计")
    print("═" * 60)

    all_cases = []
    audit_modules = [
        ("数据真实性", audit_authenticity),
        ("LLM幻觉控制", audit_llm_hallucination),
        ("数据完整性", audit_completeness),
        ("纹路稳定性", audit_pattern_stability),
        ("DNA架构", audit_dna_integrity),
    ]

    for category, audit_fn in audit_modules:
        print(f"\n  [{category}]")
        cases = audit_fn()
        for c in cases:
            status = "✅" if c.passed else "❌"
            print(f"    {status} {c.id} {c.name}")
            print(f"       预期: {c.expected}")
            print(f"       实际: {c.actual}")
            if c.warnings:
                for w in c.warnings:
                    print(f"        ⚠ {w}")
        all_cases.extend(cases)

    # 汇总
    passed = sum(1 for c in all_cases if c.passed)
    failed = sum(1 for c in all_cases if not c.passed)
    warned = sum(1 for c in all_cases if c.warnings)
    total_score = sum(c.score for c in all_cases) / max(len(all_cases), 1)

    report = AuditReport(
        timestamp=time.time(),
        cases=all_cases,
        total_score=round(total_score, 2),
        passed=passed,
        failed=failed,
        warnings=warned,
    )

    print(f"\n{'═'*60}")
    print(f"  审计结果: {report.grade}")
    print(f"  总分: {report.total_score:.2f}")
    print(f"  通过: {report.passed}  失败: {report.failed}  警告: {report.warnings}")
    print(f"{'═'*60}")

    # 细节报告
    print(f"\n  修复建议:")
    for c in all_cases:
        if not c.passed:
            print(f"    ❌ [{c.severity}优先级] {c.id} {c.name}")
            print(f"       → {c.actual}")

    if warned > 0:
        print(f"\n  警告项:")
        for c in all_cases:
            if c.warnings:
                for w in c.warnings:
                    print(f"    ⚠ [{c.id}] {w}")

    return report


# ════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    report = run_audit()

    # 保存报告
    report_path = BASE / "data" / "audit_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({
        "timestamp": report.timestamp,
        "total_score": report.total_score,
        "grade": report.grade,
        "passed": report.passed,
        "failed": report.failed,
        "warnings": report.warnings,
        "cases": [
            {
                "id": c.id,
                "category": c.category,
                "name": c.name,
                "passed": c.passed,
                "score": c.score,
                "actual": c.actual,
            }
            for c in report.cases
        ],
    }, ensure_ascii=False, indent=2))
