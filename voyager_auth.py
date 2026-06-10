"""
织星真实性验证 — 数据真实性的φ层判断

真实性不是靠"来源是.gov就信"来判断的。
真实的数据有其不可伪造的数学指纹：Benford分布、熵场温度、模式指纹。

分工:
  完整性: 网络爬取补全 → web.py / meta_search.py
  真实性: 织星φ分析 → 本模块 (Voyager pattern + Benford + entropy)
  准确性: 关系验证 → relation_integrity.py

参考文献:
  - Benford, F. (1938). The Law of Anomalous Numbers
  - Nigrini, M. (2012). Benford's Law: Applications for Forensic Accounting
  - 熵场理论: Voyager φ涨落 → 人造数据的"太干净"或"太随机"信号
"""

import math
import re
import sys
import json
from collections import Counter
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent

# 织星者路径
VOYAGER_PATH = "/mnt/d/hermes-webui/workspace/voyager"
if VOYAGER_PATH not in sys.path:
    sys.path.append(VOYAGER_PATH)

# 织星API URL
VOYAGER_API = "http://localhost:8765/api/phi"


def _read_voyager_phi() -> Optional[float]:
    """读取织星的实时全局φ值 (带缓存: 30秒内不重复请求)。"""
    try:
        import urllib.request, json, time
        # 简单缓存
        if not hasattr(_read_voyager_phi, "_cache"):
            _read_voyager_phi._cache = {"phi": None, "ts": 0}
        cache = _read_voyager_phi._cache
        if time.time() - cache["ts"] < 30:
            return cache["phi"]
        
        req = urllib.request.Request(VOYAGER_API, headers={"User-Agent": "VoyagerAuth/1.0"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            phi = data.get("global_phi", 0)
            cache["phi"] = phi
            cache["ts"] = time.time()
            return phi
    except Exception:
        return None  # 织星不可达时不影响评分


from voyager_llm import safe_llm_call as _llm_call


# ════════════════════════════════════════════════════════
# ① Benford定律检测
# ════════════════════════════════════════════════════════

# Benford预期分布: 首位数字1-9的概率
BENFORD_EXPECTED = {
    1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097,
    5: 0.079, 6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046,
}

# 前两位数字的Benford分布（更严格的检测）
BENFORD_2D_EXPECTED = {
    10: 0.0414, 11: 0.0377, 12: 0.0346, 13: 0.0320, 14: 0.0297,
    15: 0.0278, 16: 0.0261, 17: 0.0246, 18: 0.0233, 19: 0.0221,
    20: 0.0210, 25: 0.0170, 30: 0.0143, 35: 0.0123, 40: 0.0108,
    50: 0.0087, 60: 0.0072, 70: 0.0062, 80: 0.0054, 90: 0.0048, 99: 0.0044,
}


def benford_check(data_text: str) -> dict:
    """
    Benford定律检测 — 数字的首位分布是否符合自然规律。

    人造数字（人类编造的）往往偏离Benford分布：
    - 首位1出现太少 → 可能人为"均匀化"
    - 首位5出现太多 → 心理锚定效应
    - 整体偏离过大 → 高度可疑

    返回:
      {passed, chi2, p_value, first_digit_dist, deviation, assessment}
    """
    # 提取所有有意义数字（去掉单位、%、年份等）
    numbers = []
    for m in re.finditer(r'(?<!\d)([1-9]\d*(?:\.\d+)?)(?!\d)', data_text):
        num_str = m.group(1)
        try:
            val = float(num_str)
            # 跳过太小的数字（<10）和年份（如2024）
            if val >= 10 and val <= 999999999:
                # 跳过纯年份（整千的数字如2000, 2024）
                if val.is_integer() and 2000 <= val <= 2100:
                    continue
                numbers.append(val)
        except ValueError:
            continue

    if len(numbers) < 10:
        return {
            "passed": None,
            "reason": f"样本不足（仅{len(numbers)}个数字，需≥10）",
            "sample_size": len(numbers),
        }

    # 提取首位数字
    first_digits = []
    for n in numbers:
        # 科学记数法处理: 去掉小数点后的0
        s = f"{n:.0f}"
        first_digits.append(int(s[0]))

    # 计算实际分布
    digit_counts = Counter(first_digits)
    total = len(first_digits)
    observed = {d: digit_counts.get(d, 0) / total for d in range(1, 10)}

    # 卡方检验
    chi2 = 0
    for d in range(1, 10):
        expected_count = BENFORD_EXPECTED[d] * total
        actual_count = digit_counts.get(d, 0)
        if expected_count > 0:
            chi2 += (actual_count - expected_count) ** 2 / expected_count

    # 自由度=8的卡方检验临界值 (α=0.05 → 15.51, α=0.01 → 20.09)
    # 简化判断
    if chi2 > 20:
        passed = False
        assessment = f"严重偏离Benford分布 (χ²={chi2:.1f})，数据可能经过人为编造或修改"
    elif chi2 > 12:
        passed = False
        assessment = f"中等偏离Benford分布 (χ²={chi2:.1f})，数据值得怀疑"
    elif chi2 > 5:
        passed = True
        assessment = f"轻微偏离Benford分布 (χ²={chi2:.1f})，在正常范围内"
    else:
        passed = True
        assessment = f"符合Benford分布 (χ²={chi2:.1f})"

    # 计算最大偏差
    max_deviation = max(abs(observed.get(d, 0) - BENFORD_EXPECTED[d]) for d in range(1, 10))
    most_deviant = max(range(1, 10), key=lambda d: abs(observed.get(d, 0) - BENFORD_EXPECTED[d]))

    return {
        "passed": passed,
        "chi2": round(chi2, 1),
        "sample_size": total,
        "first_digit_dist": {d: round(observed.get(d, 0), 3) for d in range(1, 10)},
        "benford_expected": BENFORD_EXPECTED,
        "max_deviation": round(max_deviation, 3),
        "most_deviant_digit": most_deviant,
        "assessment": assessment,
    }


# ════════════════════════════════════════════════════════
# ② 熵场检测
# ════════════════════════════════════════════════════════

def entropy_field_check(data_text: str) -> dict:
    """
    熵场检测 — 数据的"信息温度"是否在自然范围内。

    人造数据的两种极端:
    - 熵太低: "太干净" — 所有数字都是0或5结尾，分布完美对称
    - 熵太高: "太随机" — 没有任何模式，每一位都是随机的

    真实数据在两者之间 —— 有模式但不完美。

    返回:
      {entropy, digit_entropy, last_digit_bias, roundness_score, assessment}
    """
    # 提取所有数字
    numbers = []
    for m in re.finditer(r'(\d+(?:\.\d+)?)', data_text):
        try:
            numbers.append(float(m.group(1)))
        except ValueError:
            continue

    if len(numbers) < 10:
        return {"passed": None, "reason": f"样本不足（{len(numbers)}个）", "sample_size": len(numbers)}

    # ① 末位数字分布 → 检测"人为圆整"
    last_digits = []
    for n in numbers:
        s = f"{n:.2f}"  # 保留两位小数
        # 取最后一个非零数字
        stripped = s.rstrip('0').rstrip('.')
        if stripped:
            last_digits.append(int(stripped[-1]))
        else:
            last_digits.append(0)

    digit_counts = Counter(last_digits)
    total_ld = len(last_digits)

    # 0和5的偏好 = 人为圆整信号
    zero_five_ratio = (digit_counts.get(0, 0) + digit_counts.get(5, 0)) / max(total_ld, 1)
    roundness_score = zero_five_ratio

    # ② 香农熵 (末位分布)
    entropy = 0
    for d in range(10):
        p = digit_counts.get(d, 0) / max(total_ld, 1)
        if p > 0:
            entropy -= p * math.log2(p)

    max_entropy = math.log2(10)  # 均匀分布 ≈ 3.32
    normalized_entropy = entropy / max_entropy

    # ③ 评估
    if roundness_score > 0.45:
        assessment = (
            f"末位0/5占比={roundness_score:.1%}，显著偏高"
            f"→ 数据可能经过了人为圆整或编造（真实数据末位0/5占比≈25%-35%）"
        )
        passed = False
    elif roundness_score > 0.35:
        assessment = (
            f"末位0/5占比={roundness_score:.1%}，偏高"
            f"→ 建议进一步检查"
        )
        passed = True
    elif normalized_entropy > 0.95:
        assessment = (
            f"末位熵={normalized_entropy:.2f}，接近理论最大值"
            f"→ 末位分布过于均匀，可能被随机数生成器修改"
        )
        passed = False
    elif normalized_entropy < 0.6:
        assessment = (
            f"末位熵={normalized_entropy:.2f}，过低"
            f"→ 末位缺乏多样性，数据可能被大幅简化"
        )
        passed = False
    else:
        assessment = f"熵场正常（熵={normalized_entropy:.2f}，0/5占比={roundness_score:.1%}）"
        passed = True

    return {
        "passed": passed,
        "entropy": round(normalized_entropy, 3),
        "raw_entropy": round(entropy, 3),
        "roundness_score": round(roundness_score, 3),
        "zero_five_ratio": round(zero_five_ratio, 3),
        "last_digit_dist": {d: digit_counts.get(d, 0) for d in range(10)},
        "sample_size": total_ld,
        "assessment": assessment,
    }


# ════════════════════════════════════════════════════════
# ③ 织星认知层模式识别
# ════════════════════════════════════════════════════════

def voyager_pattern_check(data_text: str, query: str = "") -> dict:
    """
    织星认知层模式检测 — 数据是否匹配已知的真实模式。

    利用 Voyager 的 CognitiveLayer:
    - store_experience → 将已知真数据模式存入
    - pattern_recognize → 检测新数据是否匹配已存模式
    - 偏离过大 → 可能不真实
    """
    try:
        from cognition import CognitiveLayer
        cognitive = CognitiveLayer(base=str(VOYAGER_PATH), agent_id="authenticity_checker")
    except ImportError:
        return {"passed": None, "reason": "Voyager认知层不可用", "cognitive_available": False}

    # 提取数据的特征向量
    features = _extract_features(data_text)

    # 尝试匹配已有模式
    pattern_result = None
    try:
        pattern_result = cognitive.pattern_recognize(features)
    except Exception:
        pass

    # LLM辅助判断数据是否符合预期模式 (仅长文本·有实质查询)
    llm_check = None
    if query and len(data_text) > 60 and _extract_features(data_text).get("count", 0) > 5:
        try:
            llm_check = _llm_pattern_assess(data_text, query)
        except Exception:
            pass

    return {
        "passed": pattern_result is not None or (llm_check and llm_check.get("passed")),
        "cognitive_available": True,
        "pattern_match": bool(pattern_result),
        "pattern_score": pattern_result.get("confidence", 0) if pattern_result and isinstance(pattern_result, dict) else 0,
        "features_extracted": len(features),
        "llm_assessment": llm_check.get("assessment", "") if llm_check else "",
    }


def _extract_features(data_text: str) -> dict:
    """从数据文本中提取统计特征。"""
    numbers = []
    for m in re.finditer(r'(\d+(?:\.\d+)?)', data_text):
        try:
            numbers.append(float(m.group(1)))
        except ValueError:
            continue

    if not numbers:
        return {"count": 0}

    n = len(numbers)
    mean = sum(numbers) / n
    variance = sum((x - mean) ** 2 for x in numbers) / n
    std = math.sqrt(variance)

    # 数量级分布
    orders = Counter()
    for x in numbers:
        if x > 0:
            orders[int(math.log10(x))] += 1

    return {
        "count": n,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "cv": round(std / max(mean, 0.01), 3),  # 变异系数
        "min": min(numbers),
        "max": max(numbers),
        "order_dist": dict(orders),
    }


def _llm_pattern_assess(data_text: str, query: str) -> Optional[dict]:
    """LLM辅助判断数据是否符合问题域的真实模式。"""
    system = """你是数据真实性检测专家。判断以下数据是否在问题域中"看起来真实"。

真实数据的特征:
- 有合理的波动和不完美性
- 数值在领域常识范围内
- 没有过度整齐的模式

人造/篡改数据的特征:
- 数字过于整齐（太多0/5结尾）
- 增长曲线过于平滑
- 数值违背领域常识

输出JSON:
{"passed": true/false, "assessment": "判断理由(1-2句)"}"""

    try:
        result = _llm_call(system, f"问题: {query}\n\n数据:\n{data_text[:1500]}", max_tokens=200)
        if result:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
                if result.endswith("```"):
                    result = result.rsplit("\n```", 1)[0]
            return json.loads(result)
    except Exception:
        pass
    return None


# ════════════════════════════════════════════════════════
# ④ 统一真实性评分
# ════════════════════════════════════════════════════════

class VoyagerAuthenticity:
    """织星真实性判断 — 整合 Benford + 熵场 + 模式识别。"""

    @classmethod
    def verify(cls, data_text: str, query: str = "") -> dict:
        """
        织星真实性三合一检测。

        返回:
          {
            "authenticity_score": float (0-1),
            "passed": bool,
            "benford": {...},
            "entropy": {...},
            "pattern": {...},
            "verdict": str,
          }
        """
        # ① Benford
        benford = benford_check(data_text)

        # ② 熵场
        entropy = entropy_field_check(data_text)

        # ③ 织星模式
        pattern = voyager_pattern_check(data_text, query)

        # 综合评分
        points = []
        weights = []

        # Benford权重: 0.30（样本<30时降权为0.15）
        benford_sample = benford.get("sample_size", 0)
        benford_weight = 0.15 if benford_sample < 30 else 0.30
        if benford.get("passed") is not None:
            points.append(1.0 if benford["passed"] else 0.0)
            weights.append(benford_weight)
        else:
            points.append(0.5)
            weights.append(0.10)

        # 熵场权重: 0.40（末位分布是最强的人造信号）
        if entropy.get("passed") is not None:
            # 熵场不过 → 强惩罚
            points.append(1.0 if entropy["passed"] else 0.15)
            weights.append(0.40)
        else:
            points.append(0.5)
            weights.append(0.10)

        # 模式权重: 0.20
        if pattern.get("passed") is not None:
            points.append(1.0 if pattern["passed"] else 0.0)
            weights.append(0.20)
        else:
            points.append(0.5)
            weights.append(0.10)

        # 加权平均
        total_w = sum(weights)
        score = sum(p * w for p, w in zip(points, weights)) / max(total_w, 0.01)

        # ④ 织星φ修正: 读取实时全局φ值
        phi_adjustment = _read_voyager_phi()
        if phi_adjustment is not None:
            # φ高 → 系统熵高 → 数据可信度降低
            # φ低 → 系统稳定 → 数据可信度微升
            phi_factor = 1.0 - phi_adjustment * 0.3  # φ=1.0 → -30%, φ=0 → 不变
            score *= max(phi_factor, 0.5)

        # 判定
        passed = score >= 0.6

        # 生成综合判断
        signals = []
        if benford.get("passed") is False:
            signals.append(f"Benford偏离(χ²={benford.get('chi2', '?')})")
        if entropy.get("passed") is False:
            signals.append(f"熵场异常(0/5占比={entropy.get('roundness_score', 0):.0%})")
        if pattern.get("passed") is False:
            signals.append("模式不匹配")

        if not signals:
            verdict = "织星真实性检测通过 — 数据数学指纹正常"
        elif len(signals) == 1:
            verdict = f"织星真实性警告: {signals[0]}"
        else:
            verdict = f"织星真实性异常: {'; '.join(signals)} — 数据可能经过人为编造"

        return {
            "authenticity_score": round(score, 2),
            "passed": passed,
            "benford": benford,
            "entropy": entropy,
            "pattern": pattern if pattern.get("cognitive_available") else {"skipped": True},
            "verdict": verdict,
        }


# ════════════════════════════════════════════════════════
# 快捷接口
# ════════════════════════════════════════════════════════

def verify_authenticity(data_text: str, query: str = "") -> dict:
    """织星真实性三合一检测。"""
    return VoyagerAuthenticity.verify(data_text, query)


# ═══ 自检 ═══
if __name__ == "__main__":
    # 测试1: 真实财务数据（应该通过）
    real_data = """
    2024年营业收入分别为: 12.3亿, 8.7亿, 15.2亿, 6.9亿, 11.8亿,
    7.4亿, 13.1亿, 9.6亿, 14.5亿, 5.2亿, 10.1亿, 16.8亿,
    8.3亿, 12.7亿, 7.9亿, 11.2亿, 13.6亿, 9.1亿, 15.7亿, 6.4亿
    """

    # 测试2: 人造数据（编造的整齐数字）
    fake_data = """
    2024年营业收入分别为: 10亿, 20亿, 30亿, 40亿, 50亿,
    60亿, 70亿, 80亿, 90亿, 100亿, 150亿, 200亿,
    250亿, 300亿, 350亿, 400亿, 450亿, 500亿, 550亿, 600亿
    """

    for label, data in [("真实财务数据", real_data), ("人造整齐数据", fake_data)]:
        print(f"\n{'='*50}")
        print(f"  {label}")
        result = VoyagerAuthenticity.verify(data)
        print(f"  真实性评分: {result['authenticity_score']:.2f}")
        print(f"  通过: {result['passed']}")
        print(f"  Benford: χ²={result['benford'].get('chi2','?')} 通过={result['benford'].get('passed')}")
        print(f"  熵场: 0/5占比={result['entropy'].get('roundness_score',0):.0%} 通过={result['entropy'].get('passed')}")
        print(f"  判决: {result['verdict']}")
