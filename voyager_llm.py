"""
织星LLM安全包装层 — 所有LLM调用的统一φ控制

每个LLM调用点都是潜在的幻觉入口。
注意力没有重量——上下文长了，前面的数字从窗口滑出去，LLM开始生成幻影。

织星三层控制:
  织星(φ): 长上下文分块 → 独立验证 → φ-drift检测
  天枢(τ): 输入数字=锚 → 输出数字回溯 → 不在锚内=幻觉
  司南: 确定性规则作基线 → 偏离基线=校准警告

用法:
  from voyager_llm import safe_llm_call
  result = safe_llm_call(system_prompt, user_message, max_tokens=200)
  # result 是经过织星验证的文本
  # 如果检测到幻觉，result 中会包含 [⚠ 织星警告: ...] 标记
"""

import re
import json
from typing import Optional

# 原始LLM调用
from deep import _llm_call


# ════════════════════════════════════════════════════════
# 织星安全LLM调用
# ════════════════════════════════════════════════════════

def safe_llm_call(
    system: str,
    user_message: str,
    max_tokens: int = 300,
    verify_numbers: bool = True,
    max_chunk_size: int = 1200,
) -> str:
    """
    织星包装的LLM调用。

    自动检测并应用:
      - 分块验证（长上下文 > max_chunk_size 时自动分块）
      - 数值锚定（输出数字必须能回溯到输入）
      - 标记警告（幻觉检测到时不静默，显式标注）

    参数:
      system: 系统提示
      user_message: 用户消息
      max_tokens: 最大输出token
      verify_numbers: 是否启用数值锚定
      max_chunk_size: 分块阈值（字符数）

    返回:
      验证后的LLM输出文本（可能包含织星警告标记）
    """
    # ─── 天枢: 提取输入中的数字作为锚 ───
    input_numbers = set()
    if verify_numbers:
        # 从user_message中提取
        for m in re.finditer(r'(\d+(?:\.\d+)?)', user_message):
            input_numbers.add(m.group(1))
        # 从system中提取
        for m in re.finditer(r'(\d+(?:\.\d+)?)', system):
            input_numbers.add(m.group(1))

    # ─── 织星: 是否需要分块？ ───
    combined = f"{system}\n\n{user_message}"
    if len(combined) <= max_chunk_size:
        # 短上下文 → 直接调用
        result = _llm_call(system, user_message, max_tokens)
    else:
        # 长上下文 → 分块
        result = _chunked_llm_call(system, user_message, max_tokens, max_chunk_size)

    if not result:
        return ""

    # ─── 天枢: 数值锚定检查 ───
    if verify_numbers and input_numbers and result:
        # 提取LLM输出中的所有数字
        output_numbers = set(re.findall(r'(\d+(?:\.\d+)?)', result))
        new_numbers = output_numbers - input_numbers

        if new_numbers:
            # 幻觉数字：LLM引入了输入中不存在的数字
            # 对于小数字（1-10的整数）可能是LLM自己的编号/推理，宽容处理
            significant_new = [
                n for n in new_numbers
                if not (n.isdigit() and 1 <= int(n) <= 10 and len(n) <= 2)
            ]
            if significant_new:
                result = (
                    f"{result}\n\n"
                    f"[⚠ 织星天枢警告: LLM引入了输入数据中不存在的数字 "
                    f"{significant_new[:5]}，这些数字无锚定来源，不可直接采信]"
                )

    return result


def _chunked_llm_call(
    system: str,
    user_message: str,
    max_tokens: int,
    max_chunk_size: int = 1200,
) -> str:
    """
    织星分块: 将长输入切成小块，分别调用LLM，检测φ-drift后合并。
    
    如果φ-drift（块间结论矛盾），返回合并结果并标注。
    """
    # 按段落分块
    paragraphs = re.split(r'\n\n+', user_message)
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > max_chunk_size and current:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)

    if len(chunks) <= 1:
        # 无需分块
        return _llm_call(system, user_message, max_tokens)

    # 只取前3块（控制成本）
    chunks = chunks[:3]

    # 分别调用
    chunk_results = []
    for i, chunk in enumerate(chunks):
        result = _llm_call(system, chunk, max_tokens=max_tokens // len(chunks))
        if result:
            chunk_results.append(result)

    if not chunk_results:
        return _llm_call(system, user_message[:max_chunk_size], max_tokens)

    # ─── φ-drift检测: 比较块间关键断言 ───
    if len(chunk_results) >= 2:
        drift = _detect_phi_drift(chunk_results[0], chunk_results[1])
    else:
        drift = ""

    # 合并
    merged = "\n\n".join(chunk_results)
    if drift:
        merged += f"\n\n[⚠ 织星φ-drift: 分块验证检测到块间不一致 — {drift}]"

    return merged


def _detect_phi_drift(result_a: str, result_b: str) -> str:
    """检测两个分块结果的关键断言冲突。"""
    if not result_a or not result_b:
        return ""

    # 简单启发式: 检查是否有否定词翻转
    # "符合"/"通过" vs "不符合"/"不通过"
    positive_keywords = ["符合", "通过", "成立", "支持", "正常", "真实"]
    negative_keywords = ["不符合", "不通过", "不成立", "不支持", "异常", "不真实", "虚假"]

    a_positive = any(k in result_a for k in positive_keywords)
    a_negative = any(k in result_a for k in negative_keywords)
    b_positive = any(k in result_b for k in positive_keywords)
    b_negative = any(k in result_b for k in negative_keywords)

    if a_positive and b_negative:
        return "块A判定为肯定，块B判定为否定"
    if a_negative and b_positive:
        return "块A判定为否定，块B判定为肯定"

    return ""


def safe_llm_call_json(
    system: str,
    user_message: str,
    max_tokens: int = 300,
) -> Optional[dict]:
    """
    安全LLM调用 + JSON解析。

    先做织星安全调用，再尝试解析JSON。
    如果解析失败，返回None。
    """
    result = safe_llm_call(system, user_message, max_tokens)
    if not result:
        return None

    result = result.strip()
    # 去掉织星警告标记
    if "[⚠ 织星" in result:
        result = result.split("[⚠ 织星")[0].strip()

    if result.startswith("```"):
        result = result.split("\n", 1)[1]
        if result.endswith("```"):
            result = result.rsplit("\n```", 1)[0]

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return None


# ═══ 自检 ═══
if __name__ == "__main__":
    # 测试基本调用
    result = safe_llm_call(
        "你是数据分析师。只使用给定的数据回答。",
        "2024年GDP为126万亿，消费48万亿，投资42万亿。问：GDP构成是否合理？",
        max_tokens=100,
    )
    print("=== 安全调用结果 ===")
    print(result[:300])
